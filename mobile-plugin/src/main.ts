import { Notice, Plugin } from "obsidian";
import { detectRuntimePlatform, isMobileRuntime } from "./platform";
import { PluginCatalogModal } from "./catalog-view";
import { SharedPolicyBackupPreviewModal, SharedPolicyPreviewModal } from "./shared-policy-view";
import { SharedPolicyManagerModal } from "./shared-policy-manager-view";

export default class CrossPlatformPluginManager extends Plugin {
  async onload(): Promise<void> {
    this.addCommand({
      id: "show-device-platform",
      name: "Show current device platform",
      callback: () => {
        const platform = detectRuntimePlatform();
        const deviceClass = isMobileRuntime() ? "mobile" : "desktop";
        new Notice(`Plugin Manager foundation: ${platform} (${deviceClass})`);
      },
    });

    this.addCommand({
      id: "preview-shared-plugin-policy",
      name: "Preview shared plugin policy (read-only)",
      callback: () => new SharedPolicyPreviewModal(this.app).open(),
    });

    this.addCommand({
      id: "manage-shared-plugin-policy",
      name: "Manage shared plugin policy (save / restore)",
      callback: () => new SharedPolicyManagerModal(this.app).open(),
    });

    this.addCommand({
      id: "preview-shared-policy-backups",
      name: "Preview shared policy backups (read-only)",
      callback: () => new SharedPolicyBackupPreviewModal(this.app).open(),
    });

    this.addCommand({
      id: "open-plugin-compatibility-catalogue",
      name: "Open plugin compatibility catalogue",
      callback: () => new PluginCatalogModal(this.app).open(),
    });
  }
}
