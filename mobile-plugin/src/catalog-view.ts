import { Modal, App } from "obsidian";
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
