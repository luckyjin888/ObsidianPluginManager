# Mobile Obsidian plugin foundation

This directory contains the TypeScript Obsidian plugin foundation for the cross-platform manager.

## Current scope

- Loads through the Obsidian plugin lifecycle.
- Detects iOS, Android, macOS, Windows, Linux, and fallback platforms using Obsidian's `Platform` API.
- Adds a command that reports the detected platform.
- Declares `isDesktopOnly: false`; this is a packaging declaration, **not** proof of real-device compatibility.

## Build

Requires Node.js 20+ and npm.

```sh
cd mobile-plugin
npm install
npm run build
npx tsc --noEmit
```

The build emits `main.js` in this directory. The generated bundle is intentionally not committed; release packaging will be handled in a later phase.

## Explicit non-goals at P3

No plugin installation, filesystem traversal, vault adapter casting, enable/disable changes, settings overwrite, remote policy synchronization, or automatic uninstall is implemented. These require separate safety design and platform validation.

Mobile code must not import Node.js or Electron APIs. The build script itself uses Node.js as a development-time tool; it is not bundled into the Obsidian runtime.

## Catalogue view

The plugin now includes an **Open plugin compatibility catalogue** command. It reads the versioned JSON catalogue bundled from `../shared/plugin-catalog.json`, supports name/ID filtering, and displays the recorded status for Windows, macOS, iOS, iPadOS, and Android.

The view is read-only. It does not install, enable, disable, update, or remove plugins. Compatibility labels reflect the catalogue evidence and do not infer support from the upstream desktop-only flag.
