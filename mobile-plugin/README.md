# Cross-platform Manager plugin foundation

This directory contains the TypeScript Obsidian plugin foundation for the cross-platform manager. Its community-plugin ID is `cross-platform-manager`, following the current Obsidian manifest naming rules.

## Current scope

- Loads through the Obsidian plugin lifecycle.
- Detects iOS, Android, macOS, Windows, Linux, and fallback platforms using Obsidian's `Platform` API.
- Adds a command that reports the detected platform.
- Declares `isDesktopOnly: false`; this is a packaging declaration, **not** proof of real-device compatibility.

## Build and package

Requires Node.js 20+, npm, and Python 3.

```sh
cd mobile-plugin
npm install
npm run build
npx tsc --noEmit
npm run package
```

The build emits `main.js`. Packaging creates a flat ZIP in `mobile-plugin/dist/` containing `main.js`, `manifest.json`, and `styles.css` when present. The ZIP is checked to ensure the runtime files are at its root, not nested inside another directory.

The CI workflow uploads this ZIP as a 14-day GitHub Actions artifact. This is a test artifact, not a GitHub Release and not an official Obsidian community listing.

## Installing a test build on a phone or tablet

1. Open the successful GitHub Actions run for this PR and download the `cross-platform-manager-0.1.0` artifact.
2. Extract the ZIP so the plugin package itself is available as a ZIP containing `manifest.json` and `main.js` at its root.
3. In Obsidian, install a trusted ZIP installer that supports mobile, then select the ZIP from the device's Files app.
4. Enable **Cross-platform Manager** under Settings → Community plugins.
5. Run **Open plugin compatibility catalogue** from the command palette.

If the ZIP installer cannot access the downloaded file on iOS, use a trusted desktop-based test installation route instead. Do not manually move files into hidden iOS vault folders unless you understand the storage layout.

## Explicit limitations

This first test package does **not** install, update, enable, disable, or remove other plugins. It does not synchronize plugin settings or policies between devices. Catalogue compatibility values are evidence-based and may remain unknown until the relevant platform is tested.

No mobile compatibility is claimed solely because `isDesktopOnly` is false. Physical testing is still required on iPhone and iPad; Windows and macOS desktop regression coverage remains part of the existing test matrix.

## Explicit non-goals at P3

No plugin installation, filesystem traversal, vault adapter casting, enable/disable changes, settings overwrite, remote policy synchronization, or automatic uninstall is implemented. These require separate safety design and platform validation.

Mobile code must not import Node.js or Electron APIs. The build script itself uses Node.js as a development-time tool; it is not bundled into the Obsidian runtime.

## Catalogue view

The plugin includes an **Open plugin compatibility catalogue** command. It reads the versioned JSON catalogue bundled from `../shared/plugin-catalog.json`, supports name/ID filtering, and displays the recorded status for Windows, macOS, iOS, iPadOS, and Android.

The view is read-only. It does not install, enable, disable, update, or remove plugins. Compatibility labels reflect the catalogue evidence and do not infer support from the upstream desktop-only flag.

## P4.1 eligibility preflight

The catalogue includes a **Check install eligibility** action. This is a read-only policy gate: it blocks unknown, declared-but-untested, and incompatible platform entries, rejects non-canonical upstream URLs, and requires both iOS and iPadOS catalogue evidence because Obsidian exposes a shared iOS runtime flag for iPhone/iPad.

A passed preflight is **not** permission to install. Release provenance/digest validation, downloaded manifest validation, version checks, staging, backups, rollback, and user confirmation must all be implemented before any file writes are enabled. The current action never downloads or writes files.
