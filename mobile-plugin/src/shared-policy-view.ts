import { App, Modal, Notice } from "obsidian";
import { detectRuntimePlatform, type RuntimePlatform } from "./platform";
import { findPolicyConflictCandidates, fingerprintSharedPolicy, parseSharedPluginPolicy, SHARED_POLICY_PATH } from "./shared-policy";
import catalogData from "../../shared/plugin-catalog.json";

type PlatformKey = "windows" | "macos" | "ios" | "ipados" | "android";
type CompatibilityStatus = "verified" | "declared_unverified" | "incompatible" | "unknown";

interface CataloguePlugin {
  id: string;
  name: string;
  platforms: Record<PlatformKey, { status: CompatibilityStatus; evidence: string }>;
}

interface PluginCatalogue {
  plugins: CataloguePlugin[];
}

const catalogue = catalogData as PluginCatalogue;

function localPlatformKey(platform: RuntimePlatform): PlatformKey | null {
  if (platform === "ios") return "ios";
  if (platform === "android") return "android";
  if (platform === "macos") return "macos";
  if (platform === "windows") return "windows";
  return null;
}

function statusText(status: CompatibilityStatus): string {
  switch (status) {
    case "verified": return "Verified on this platform";
    case "declared_unverified": return "Declared but not tested";
    case "incompatible": return "Marked incompatible";
    default: return "Compatibility unknown";
  }
}

/**
 * Read-only preview. It never creates, modifies, or deletes a Vault file.
 * Missing/invalid policy data is reported without attempting a repair.
 */
export class SharedPolicyPreviewModal extends Modal {
  constructor(app: App) {
    super(app);
  }

  async onOpen(): Promise<void> {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Shared plugin policy (read-only)" });
    contentEl.createEl("p", {
      text: `Source: ${SHARED_POLICY_PATH}`,
      cls: "setting-item-description",
    });
    contentEl.createEl("p", {
      text: "This preview reads only the desired plugin list. It does not install plugins, change settings, or write to your Vault.",
      cls: "setting-item-description",
    });

    const adapter = this.app.vault.adapter;
    try {
      const exists = await adapter.exists(SHARED_POLICY_PATH);
      if (!exists) {
        contentEl.createEl("p", {
          text: "No shared policy file exists yet. This command will not create one.",
        });
        return;
      }

      let possibleConflicts: string[] = [];
      let conflictScanAvailable = true;
      try {
        const siblings = await adapter.list("PluginManager");
        possibleConflicts = findPolicyConflictCandidates(siblings.files);
      } catch {
        conflictScanAvailable = false;
      }

      const raw = await adapter.read(SHARED_POLICY_PATH);
      const fingerprint = await fingerprintSharedPolicy(raw);
      const parsed = parseSharedPluginPolicy(raw);
      if (!parsed.ok || !parsed.policy) {
        contentEl.createEl("h3", { text: "Policy cannot be previewed" });
        for (const error of parsed.errors) contentEl.createEl("p", { text: error });
        contentEl.createEl("p", {
          text: "The original file has been left untouched. Fix it manually or restore a valid synced copy.",
        });
        return;
      }

      if (!conflictScanAvailable) {
        contentEl.createEl("p", {
          text: "Could not inspect sibling files for possible sync conflict copies. Check the PluginManager folder manually.",
        });
      } else if (possibleConflicts.length > 0) {
        contentEl.createEl("h3", { text: "Possible sync conflict copies found" });
        contentEl.createEl("p", {
          text: "These similarly named files may be conflict copies or backups. They are not modified or deleted. Compare them manually before making changes.",
        });
        for (const path of possibleConflicts) contentEl.createEl("p", { text: path });
      } else {
        contentEl.createEl("p", {
          text: "No similarly named conflict candidates were found. This filename scan cannot guarantee that the sync provider has no hidden or differently named conflicts.",
          cls: "setting-item-description",
        });
      }

      const policy = parsed.policy;
      const runtime = detectRuntimePlatform();
      const platformKey = localPlatformKey(runtime);
      contentEl.createEl("p", {
        text: `Schema v${policy.schema_version} · Revision ${policy.revision} · ${policy.plugins.length} desired plugins`,
      });
      contentEl.createEl("p", {
        text: `This device: ${runtime}. Compatibility is evaluated locally and is not synchronized.`,
        cls: "setting-item-description",
      });
      contentEl.createEl("p", {
        text: `Current file SHA-256: ${fingerprint}`,
        cls: "setting-item-description",
      });
      contentEl.createEl("p", {
        text: "This fingerprint identifies the exact text read for this preview. It is not a lock and does not prevent another device from changing the file.",
        cls: "setting-item-description",
      });

      if (policy.plugins.length === 0) {
        contentEl.createEl("p", { text: "The shared policy currently has no desired plugins." });
        return;
      }

      const list = contentEl.createDiv({ cls: "shared-policy-preview-list" });
      for (const entry of policy.plugins) {
        const item = list.createDiv({ cls: "plugin-catalog-item" });
        const known = catalogue.plugins.find((plugin) => plugin.id === entry.id);
        item.createEl("h3", { text: known ? known.name : entry.id });
        item.createEl("p", { text: `Plugin ID: ${entry.id}` });
        item.createEl("p", {
          text: known
            ? platformKey
              ? statusText(known.platforms[platformKey].status)
              : "This platform is outside the current five-platform catalogue."
            : "Unknown to this device's bundled catalogue; inert entry, no source lookup performed.",
        });
        if (known && platformKey) {
          item.createEl("p", {
            text: `Evidence: ${known.platforms[platformKey].evidence}`,
            cls: "setting-item-description",
          });
        }
        if (entry.note) item.createEl("p", { text: `Note: ${entry.note}` });
        item.createEl("p", {
          text: "Desired by shared policy. Installed/enabled status is not inferred or synchronized.",
          cls: "setting-item-description",
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown Vault adapter read error.";
      contentEl.createEl("p", { text: `Could not read the shared policy: ${message}` });
      new Notice("Shared policy preview failed. No Vault files were changed.", 8000);
    }
  }

  onClose(): void {
    this.contentEl.empty();
  }
}
