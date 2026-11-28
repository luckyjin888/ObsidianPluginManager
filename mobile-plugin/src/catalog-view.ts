import { Modal, App, Notice, apiVersion } from "obsidian";
import { assessInstallEligibility } from "./installation-policy";
import { detectRuntimePlatform } from "./platform";
import { inspectLatestRelease, type ReleaseInspection } from "./release-inspector";
import { verifyLatestReleaseAssets } from "./release-verifier";
import { buildInstallPlan } from "./install-transaction";
import { createObsidianInstallStagingAdapter, stageInstallPlan } from "./install-staging";
import { commitStagedInstall, createObsidianInstallCommitAdapter } from "./install-commit";
import catalogData from "../../shared/plugin-catalog.json";

type CompatibilityStatus = "verified" | "declared_unverified" | "incompatible" | "unknown";
type PlatformKey = "windows" | "macos" | "ios" | "ipados" | "android";

interface CatalogPlugin {
  id: string;
  name: string;
  upstream_url: string | null;
  manifest_is_desktop_only: boolean;
  risk_level: string;
  risk_notes: string[];
  platforms: Record<PlatformKey, { status: CompatibilityStatus; evidence: string }>;
}

interface PluginCatalog {
  catalog_version: number;
  generated_at: string;
  plugins: CatalogPlugin[];
}

const catalog = catalogData as PluginCatalog;

const platformLabels: Record<PlatformKey, string> = {
  windows: "Windows",
  macos: "macOS",
  ios: "iOS",
  ipados: "iPadOS",
  android: "Android",
};

function statusLabel(status: CompatibilityStatus): string {
  switch (status) {
    case "verified": return "Verified";
    case "declared_unverified": return "Declared, not tested";
    case "incompatible": return "Incompatible";
    default: return "Unknown";
  }
}

export class PluginCatalogModal extends Modal {
  constructor(app: App) {
    super(app);
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Plugin compatibility catalogue" });
    contentEl.createEl("p", {
      text: `Catalogue v${catalog.catalog_version} · Updated ${catalog.generated_at}`,
      cls: "setting-item-description",
    });
    contentEl.createEl("p", {
      text: "Compatibility is evidence-based. A plugin manifest that is not desktop-only does not prove that it works on a mobile device.",
      cls: "setting-item-description",
    });

    const search = contentEl.createEl("input", {
      type: "search",
      placeholder: "Search plugins",
      attr: { "aria-label": "Search plugins" },
    });
    const list = contentEl.createDiv({ cls: "plugin-catalog-list" });

    const render = (query: string): void => {
      list.empty();
      const normalized = query.trim().toLowerCase();
      const matches = catalog.plugins.filter((plugin) =>
        `${plugin.name} ${plugin.id}`.toLowerCase().includes(normalized),
      );

      if (matches.length === 0) {
        list.createEl("p", { text: "No matching plugins." });
        return;
      }

      for (const plugin of matches) {
        const item = list.createDiv({ cls: "plugin-catalog-item" });
        item.createEl("h3", { text: plugin.name });
        item.createEl("p", {
          text: `Risk: ${plugin.risk_level} · Desktop-only: ${plugin.manifest_is_desktop_only ? "Yes" : "No (not proof of mobile support)"}`,
        });

        const statuses = item.createDiv({ cls: "plugin-catalog-platforms" });
        for (const platform of Object.keys(platformLabels) as PlatformKey[]) {
          const status = plugin.platforms[platform];
          statuses.createEl("p", {
            text: `${platformLabels[platform]}: ${statusLabel(status.status)}`,
            cls: "plugin-catalog-status",
          });
        }

        if (plugin.risk_notes.length > 0) {
          item.createEl("p", { text: `Notes: ${plugin.risk_notes.join(" ")}` });
        }
        const preflight = item.createEl("button", { text: "Check install eligibility" });
        preflight.addEventListener("click", () => {
          const decision = assessInstallEligibility(plugin, detectRuntimePlatform());
          if (decision.eligible) {
            new Notice("Preflight passed. This is not an installation; release integrity and manifest checks are still required.");
          } else {
            new Notice(`Installation blocked: ${decision.reasons.join(" ")}`, 10000);
          }
        });

        const releaseButton = item.createEl("button", { text: "Inspect latest release" });
        const releaseDetails = item.createDiv({ cls: "plugin-catalog-release" });
        let latestReleaseReport: ReleaseInspection | null = null;
        let latestVerifiedAssets: Awaited<ReturnType<typeof verifyLatestReleaseAssets>> | null = null;
        releaseButton.addEventListener("click", async () => {
          if (!plugin.upstream_url) {
            new Notice("Release inspection blocked: no upstream repository URL.");
            return;
          }
          releaseButton.disabled = true;
          releaseButton.setText("Inspecting release…");
          releaseDetails.empty();
          latestVerifiedAssets = null;
          try {
            const report = await inspectLatestRelease(plugin.upstream_url);
            latestReleaseReport = report;
            releaseDetails.createEl("p", {
              text: `Latest stable release: ${report.tag} · ${report.repository}`,
            });
            for (const asset of report.assets) {
              const digestText = asset.digestVerified ? "SHA-256 digest published" : "SHA-256 digest missing/invalid";
              releaseDetails.createEl("p", {
                text: `${asset.name} · ${asset.size.toLocaleString()} bytes · ${digestText}`,
              });
            }
            if (report.installable) {
              new Notice("Release metadata and SHA-256 digest presence checks passed. Downloaded bytes and manifest are not yet verified; installation remains disabled.");
            } else {
              new Notice(`Release inspected but blocked: ${report.reasons.join(" ")}`, 10000);
            }
          } catch (error) {
            const message = error instanceof Error ? error.message : "Unknown release inspection error.";
            releaseDetails.createEl("p", { text: message });
            new Notice(`Release inspection failed: ${message}`, 10000);
          } finally {
            releaseButton.disabled = false;
            releaseButton.setText("Inspect latest release");
          }
        });

        const verifyButton = item.createEl("button", { text: "Verify downloaded release files" });
        verifyButton.addEventListener("click", async () => {
          if (!latestReleaseReport) {
            new Notice("Inspect the latest release metadata first.");
            return;
          }
          verifyButton.disabled = true;
          verifyButton.setText("Verifying assets…");
          try {
            const report = await verifyLatestReleaseAssets(
              latestReleaseReport,
              plugin.id,
              apiVersion,
            );
            latestVerifiedAssets = report.verified ? report : null;
            installButton.disabled = !report.verified;
            releaseDetails.createEl("p", {
              text: report.verified
                ? `Verified manifest ${report.manifest?.id} v${report.manifest?.version}; no vault files were changed.`
                : `Asset verification blocked: ${report.reasons.join(" ")}`,
            });
            new Notice(report.verified
              ? "Release bytes and manifest verified. Installation is still not enabled."
              : "Release verification failed; installation remains blocked.", 10000);
          } catch (error) {
            const message = error instanceof Error ? error.message : "Unknown asset verification error.";
            releaseDetails.createEl("p", { text: message });
            new Notice(`Asset verification failed: ${message}`, 10000);
          } finally {
            verifyButton.disabled = false;
            verifyButton.setText("Verify downloaded release files");
          }
        });

        const installButton = item.createEl("button", { text: "Install verified release" });
        installButton.disabled = true;
        installButton.addEventListener("click", async () => {
          if (!latestReleaseReport || !latestVerifiedAssets?.verified || !latestVerifiedAssets.verifiedAssets.length) {
            new Notice("Inspect and verify release files before installing.");
            return;
          }
          const runtime = detectRuntimePlatform();
          if (runtime !== "windows" && runtime !== "macos" && runtime !== "ios" && runtime !== "android") {
            new Notice("This runtime platform is not supported by the installation workflow.", 8000);
            return;
          }
          const result = await buildInstallPlan({
            pluginId: plugin.id,
            releaseVersion: latestReleaseReport.version ?? "",
            obsidianApiVersion: apiVersion,
            runtimePlatform: runtime,
            platformEvidence: plugin.platforms,
            configDir: this.app.vault.configDir,
            assets: latestVerifiedAssets.verifiedAssets,
          });
          if (result.status !== "ready") {
            new Notice("Installation blocked: " + result.reasons.join(" "), 10000);
            return;
          }
          const transactionId = globalThis.crypto.randomUUID().replace(/-/g, "");
          const confirmed = window.confirm(
            "Install " + plugin.name + " v" + result.plan.releaseVersion + " on " + runtime + "? Existing manifest/main/styles files will be backed up and verified before replacement. Plugin settings/data and enabled state will not be changed. Manual enable/reload may be required.",
          );
          if (!confirmed) return;
          installButton.disabled = true;
          installButton.setText("Staging verified files…");
          try {
            const staged = await stageInstallPlan({
              adapter: createObsidianInstallStagingAdapter(this.app.vault),
              plan: result.plan,
              transactionId,
              confirmed: true,
            });
            if (staged.status !== "staged") {
              new Notice(staged.status === "blocked" ? "Installation blocked: " + staged.reason : "Staging failed: " + staged.reason + ". Leftovers: " + staged.leftoverPaths.join(", "), 10000);
              return;
            }
            installButton.setText("Installing with backup…");
            const committed = await commitStagedInstall(
              createObsidianInstallCommitAdapter(this.app.vault),
              result.plan, staged.files, staged.stagingDirectory, transactionId, true, new Date().toISOString(),
            );
            if (committed.status === "installed") {
              new Notice("Installed " + plugin.name + " v" + result.plan.releaseVersion + ". Backup retained at " + committed.backupDirectory + ". Plugin enablement was not changed.", 10000);
              releaseDetails.createEl("p", { text: "Installed " + result.plan.releaseVersion + "; backup retained at " + committed.backupDirectory + ". Enable/reload manually if needed." });
            } else if (committed.status === "blocked") {
              new Notice("Installation blocked: " + committed.reason, 10000);
            } else {
              new Notice("Installation failed: " + committed.reason + ". Rollback: " + committed.rollback + ". Backup: " + committed.backupDirectory + ". " + committed.rollbackFailures.join(", "), 12000);
            }
          } catch (error) {
            new Notice("Installation failed: " + (error instanceof Error ? error.message : "unknown error"), 10000);
          } finally {
            installButton.disabled = false;
            installButton.setText("Install verified release");
          }
        });
        if (plugin.upstream_url) {
          const link = item.createEl("a", {
            text: "Upstream project",
            href: plugin.upstream_url,
          });
          link.setAttr("target", "_blank");
          link.setAttr("rel", "noopener noreferrer");
        }
      }
    };

    search.addEventListener("input", () => render(search.value));
    render("");
  }

  onClose(): void {
    this.contentEl.empty();
  }
}
