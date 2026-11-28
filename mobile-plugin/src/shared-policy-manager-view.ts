import { App, Modal, Notice, TFile, TFolder } from "obsidian";
import {
  createObsidianVaultBackupAdapter,
  createObsidianVaultPolicyAdapter,
  persistSharedPolicyBackup,
  prepareSharedPolicyRestorePreview,
  restoreSharedPolicyWithBackup,
  scanSharedPolicyBackups,
  writeSharedPolicyWithBaseline,
  type SharedPolicyBackupEnvelope,
} from "./shared-policy-write";
import { parseSharedPluginPolicy, SHARED_POLICY_PATH } from "./shared-policy";

function nowIso(): string {
  return new Date().toISOString();
}

/**
 * Explicit shared-policy save/recovery UI.
 *
 * Save validates the candidate, backs up the exact current bytes first, then
 * uses Vault.process baseline comparison and exact read-back verification.
 * Restore requires a valid selected backup, a fresh baseline preview, a new
 * backup of the current bytes, and explicit confirmation.
 *
 * This operates only on PluginManager/shared-policy.json. It never installs,
 * enables, disables, or changes any plugin binary/settings.
 */
export class SharedPolicyManagerModal extends Modal {
  constructor(app: App) {
    super(app);
  }

  async onOpen(): Promise<void> {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.createEl("h2", { text: "Manage shared plugin policy" });
    contentEl.createEl("p", {
      text: "This manages only the desired plugin list. It does not install plugins or synchronize plugin binaries, settings, enabled state, or credentials.",
      cls: "setting-item-description",
    });

    const editor = contentEl.createEl("textarea");
    editor.rows = 16;
    editor.style.width = "100%";
    editor.setAttribute("aria-label", "Shared plugin policy JSON");
    editor.value = JSON.stringify({
      schema_version: 1,
      revision: "initial",
      plugins: [],
    }, null, 2) + "\n";

    let loadedBaseline: string | null = null;
    try {
      const existing = this.app.vault.getAbstractFileByPath(SHARED_POLICY_PATH);
      if (existing instanceof TFile) {
        if (existing.stat.size > 64 * 1024) {
          contentEl.createEl("p", { text: "Existing policy exceeds 64 KiB. It was not loaded or modified." });
          return;
        }
        loadedBaseline = await this.app.vault.cachedRead(existing);
        editor.value = loadedBaseline;
      } else {
        contentEl.createEl("p", {
          text: "No policy exists yet. Saving will create the policy file after validation; no existing file will be overwritten.",
        });
      }
    } catch (error) {
      contentEl.createEl("p", {
        text: `Could not load current policy: ${error instanceof Error ? error.message : "unknown read error"}`,
      });
      return;
    }

    const validation = contentEl.createEl("p", { cls: "setting-item-description" });
    const validateButton = contentEl.createEl("button", { text: "Validate JSON" });
    validateButton.addEventListener("click", () => {
      const parsed = parseSharedPluginPolicy(editor.value);
      validation.setText(parsed.ok
        ? `Valid policy · revision ${parsed.policy!.revision} · ${parsed.policy!.plugins.length} desired plugins`
        : `Invalid policy: ${parsed.errors.join(" ")}`);
    });

    const saveButton = contentEl.createEl("button", { text: "Save shared policy" });
    saveButton.addEventListener("click", async () => {
      const candidate = editor.value;
      const parsed = parseSharedPluginPolicy(candidate);
      if (!parsed.ok) {
        new Notice(`Policy not saved: ${parsed.errors.join(" ")}`, 8000);
        return;
      }
      if (!window.confirm("Save this shared plugin policy? Existing content will be backed up before it is changed.")) return;

      try {
        const currentFile = this.app.vault.getAbstractFileByPath(SHARED_POLICY_PATH);
        if (loadedBaseline === null) {
          if (currentFile) {
            new Notice("A policy file appeared since this editor opened. Reload and review it before saving.", 8000);
            return;
          }
          const folder = this.app.vault.getAbstractFileByPath("PluginManager");
          if (!folder) await this.app.vault.createFolder("PluginManager");
          else if (!(folder instanceof TFolder)) {
            new Notice("PluginManager exists but is not a folder. No changes made.", 8000);
            return;
          }
          try {
            await this.app.vault.create(SHARED_POLICY_PATH, candidate);
            const created = this.app.vault.getAbstractFileByPath(SHARED_POLICY_PATH);
            if (!(created instanceof TFile) || await this.app.vault.read(created) !== candidate) {
              new Notice("Policy create could not be verified. Inspect the file before retrying.", 8000);
              return;
            }
            loadedBaseline = candidate;
            new Notice("Shared policy created and verified.");
          } catch (error) {
            new Notice(`Policy was not created (possibly created concurrently): ${error instanceof Error ? error.message : "unknown error"}`, 8000);
          }
          return;
        }

        if (!(currentFile instanceof TFile)) {
          new Notice("The reviewed policy file is missing or changed type. Reload before saving.", 8000);
          return;
        }
        const fresh = await this.app.vault.cachedRead(currentFile);
        if (fresh !== loadedBaseline) {
          new Notice("Policy changed since review. Reload and resolve the newer version; nothing was overwritten.", 8000);
          return;
        }

        const backupAdapter = createObsidianVaultBackupAdapter(this.app.vault);
        const backup = await persistSharedPolicyBackup(backupAdapter, fresh, nowIso());
        if (backup.status !== "created" && backup.status !== "already-exists") {
          new Notice(`Save blocked: backup was not safely persisted. ${backup.status === "failed" || backup.status === "verification-failed" ? backup.message : ""}`, 8000);
          return;
        }

        const writer = createObsidianVaultPolicyAdapter(this.app.vault);
        const result = await writeSharedPolicyWithBaseline(writer, currentFile, fresh, candidate);
        if (result.status === "written") {
          loadedBaseline = candidate;
          new Notice(`Shared policy saved. Recovery backup: ${backup.path}`, 8000);
        } else if (result.status === "stale") {
          new Notice("Save aborted because another change arrived. Reload and compare before retrying.", 8000);
        } else {
          new Notice(`Policy was not reported as saved: ${result.status}`, 8000);
        }
      } catch (error) {
        new Notice(`Save failed: ${error instanceof Error ? error.message : "unknown error"}`, 8000);
      }
    });

    contentEl.createEl("hr");
    contentEl.createEl("h3", { text: "Restore from a verified backup" });
    const backupSelect = contentEl.createEl("select");
    backupSelect.style.width = "100%";
    backupSelect.createEl("option", { text: "Choose a valid backup…", attr: { value: "" } });
    const restoreDetails = contentEl.createEl("p", { cls: "setting-item-description" });
    const restoreButton = contentEl.createEl("button", { text: "Preview and restore selected backup" });
    restoreButton.disabled = true;

    const validBackups: Array<{ path: string; backup: SharedPolicyBackupEnvelope }> = [];
    try {
      const items = await scanSharedPolicyBackups(createObsidianVaultBackupAdapter(this.app.vault));
      for (const item of items) {
        if (item.status !== "valid") continue;
        validBackups.push({ path: item.path, backup: item.backup });
        backupSelect.createEl("option", {
          text: `${item.backup.created_at} · ${item.backup.original_sha256.slice(0, 12)} · ${item.path}`,
          attr: { value: item.path },
        });
      }
      if (validBackups.length === 0) restoreDetails.setText("No valid backups are available. Invalid backups are not offered for restore.");
    } catch {
      restoreDetails.setText("Backup inventory could not be read.");
    }

    backupSelect.addEventListener("change", () => {
      restoreButton.disabled = !validBackups.some((entry) => entry.path === backupSelect.value);
      const selected = validBackups.find((entry) => entry.path === backupSelect.value);
      restoreDetails.setText(selected
        ? `Selected backup revision will be validated. Original SHA-256: ${selected.backup.original_sha256}`
        : "Choose a valid backup.");
    });

    restoreButton.addEventListener("click", async () => {
      const selected = validBackups.find((entry) => entry.path === backupSelect.value);
      if (!selected) return;
      const file = this.app.vault.getAbstractFileByPath(SHARED_POLICY_PATH);
      if (!(file instanceof TFile)) {
        new Notice("Restore currently requires an existing shared policy file. No file was created.", 8000);
        return;
      }
      try {
        const reviewed = await this.app.vault.cachedRead(file);
        const currentNow = await this.app.vault.cachedRead(file);
        const preview = await prepareSharedPolicyRestorePreview(selected.backup, reviewed, currentNow);
        if (preview.status !== "ready") {
          new Notice(`Restore blocked: ${preview.status}. Reload and inspect the current policy.`, 8000);
          return;
        }
        if (!window.confirm(
          `Restore policy revision ${preview.restored_policy_revision} with ${preview.restored_plugin_count} desired plugins? The current policy will first be backed up. This does not install or enable plugins.`,
        )) return;

        const currentFile = this.app.vault.getAbstractFileByPath(SHARED_POLICY_PATH);
        if (!(currentFile instanceof TFile)) {
          new Notice("Policy file disappeared before restore. No changes made.", 8000);
          return;
        }
        const currentFresh = await this.app.vault.cachedRead(currentFile);
        const policyAdapter = createObsidianVaultPolicyAdapter(this.app.vault);
        const backupAdapter = createObsidianVaultBackupAdapter(this.app.vault);
        const result = await restoreSharedPolicyWithBackup(
          policyAdapter,
          backupAdapter,
          currentFile,
          selected.backup,
          reviewed,
          currentFresh,
          nowIso(),
          true,
        );
        if (result.status === "restored") {
          editor.value = preview.restore_content;
          loadedBaseline = preview.restore_content;
          new Notice(`Policy restored. Previous current policy backed up at ${result.backup_path}`, 8000);
        } else {
          new Notice(`Restore did not complete: ${result.status}`, 8000);
        }
      } catch (error) {
        new Notice(`Restore failed: ${error instanceof Error ? error.message : "unknown error"}`, 8000);
      }
    });
  }

  onClose(): void {
    this.contentEl.empty();
  }
}
