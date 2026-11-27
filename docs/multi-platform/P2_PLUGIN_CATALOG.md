# P2 — Shared Plugin Catalogue and Compatibility Model

## Deliverables

- `shared/plugin-catalog.schema.json`: versioned JSON Schema contract.
- `shared/plugin-catalog.json`: initial catalogue for nine plugins discussed for this project.
- `tools/validate_plugin_catalog.py`: dependency-free validator for catalogue structure and safety invariants.
- `tests/test_plugin_catalog.py`: tests for unique IDs, five-platform coverage, status rules, and required device evidence.

## Platform model

Each plugin has a separate status for:

- Windows
- macOS
- iOS
- iPadOS
- Android

Allowed statuses:

| Status | Meaning |
|---|---|
| `verified` | Successfully tested on the named platform, with date, device, and Obsidian version recorded |
| `declared_unverified` | Upstream metadata suggests it is not desktop-only, but platform behavior has not been tested |
| `incompatible` | A known dependency or test result shows the plugin cannot work on that platform |
| `unknown` | Evidence is insufficient |

## Important evidence rule

The initial catalogue carries forward the previous manifest review for the nine candidate plugins. A value of `manifest_is_desktop_only: false` is stored as upstream metadata only. It does **not** promote any platform to `verified` or `declared_unverified`.

All five platform statuses are currently `unknown` because no device-specific test record has yet been attached to these catalogue entries. This is deliberately conservative.

## Initial catalogue coverage

| Plugin | ID | Notes |
|---|---|---|
| Obsidian Git | `obsidian-git` | Git operations and mobile execution constraints need review |
| QuickAdd | `quickadd` | User macros/scripts need per-script review |
| Tasks | `obsidian-tasks-plugin` | No platform-specific verification recorded |
| Excalidraw | `obsidian-excalidraw-plugin` | Touch and export behavior need validation |
| Linter | `obsidian-linter` | Validate Vault adapter/file behavior |
| Advanced Tables | `table-editor-obsidian` | Touch editing and keyboard behavior need validation |
| Templater | `templater-obsidian` | High risk: user scripts may call Node APIs |
| Codeblock Customizer | `codeblock-customizer` | Upstream URL and license still need confirmation |
| PDF++ | `pdf-plus` | High risk: previously noted internal API dependencies need review |

Unknown upstream URLs and licenses are left as `null`; they must be verified from authoritative upstream metadata before being populated.

## Validation

Run locally:

```bash
python tools/validate_plugin_catalog.py
python -m unittest tests.test_plugin_catalog -v
```

The existing GitHub Actions OS/Python matrix now runs the catalogue validator and the full Python unit-test suite. This ensures desktop CI checks the shared data contract without adding a third-party Python dependency.

## P2 limitations

- The validator enforces the catalogue's core structural and safety invariants; the JSON Schema remains the formal interchange contract.
- The initial nine entries are a seed list, not a complete Obsidian community plugin catalogue.
- No plugin is declared mobile-compatible based solely on manifest metadata.
- No installer, auto-enable, settings sync, or device sync behavior is implemented in P2.
