import { Notice, Plugin } from "obsidian";
import { detectRuntimePlatform, isMobileRuntime } from "./platform";
import { PluginCatalogModal } from "./catalog-view";

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
      id: "open-plugin-compatibility-catalogue",
      name: "Open plugin compatibility catalogue",
      callback: () => new PluginCatalogModal(this.app).open(),
    });
  }
}
