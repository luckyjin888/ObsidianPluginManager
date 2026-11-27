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


## P4.2 latest-release inspection (metadata only)

The catalogue now offers **Inspect latest release** for an upstream GitHub repository. It uses Obsidian's public `requestUrl` API to inspect the repository's latest published stable GitHub Release. It accepts semantic-version tags, requires `manifest.json` and `main.js`, permits only those files plus optional `styles.css`, validates GitHub release-asset URLs, and enforces per-file/total size limits (256 KiB / 20 MiB / 2 MiB; 25 MiB total).

The inspector reports whether GitHub publishes a syntactically valid SHA-256 asset digest. If a digest is missing or invalid, the release is marked **not installable**. Even when digest metadata is present, the downloaded bytes have not yet been fetched or hashed, the manifest has not yet been parsed, and no installation is possible. HTTP 404, 403, and 429 responses fail closed; there is no branch/source-archive fallback. No files are downloaded or written to the vault.


## P4.3 downloaded-byte verification (no vault writes)

The catalogue adds **Verify downloaded release files** after release metadata inspection. It downloads only the allowlisted release assets into memory, checks the downloaded byte length against GitHub metadata, computes SHA-256 with Web Crypto, compares the result with GitHub's published digest, parses the digest-verified manifest, and checks plugin ID, release version, `minAppVersion` against the running Obsidian version, and an explicit `isDesktopOnly: false` declaration.

This step does not execute downloaded code, retain files, create plugin folders, or write to the vault. A successful verification is not an installation. Redirect handling is delegated to Obsidian's `requestUrl`; its response API does not expose the final redirected URL, so this stage cannot independently attest the final CDN hostname. The source asset URL is still restricted to the expected GitHub repository release path. Staging, backups, rollback, and explicit confirmation remain disabled.

**Runtime version:** The verifier uses the officially exported Obsidian `apiVersion` value to compare the running app's API version against manifest `minAppVersion`. This is the public API version and follows the desktop app release cycle; it is not an undocumented `App.version` property.


## Shared plugin policy preview (read-only)

The command **Preview shared plugin policy (read-only)** looks for `PluginManager/shared-policy.json` in the current Vault. If present, it validates a strict schema (maximum 64 KiB and 200 entries) and displays desired plugin IDs with compatibility evidence from this device's bundled catalogue. Unknown IDs remain inert. The preview does not create or edit the file, install plugins, inspect installed/enabled state, fetch URLs from policy content, or copy plugin binaries/settings between devices. A missing policy file is reported without creating one.


The preview also scans sibling filenames for possible conflict copies and displays a SHA-256 fingerprint of the exact policy text when Web Crypto is available. These are advisory diagnostics only: sync providers use different naming conventions, and a fingerprint does not lock the file or prevent concurrent edits. Review possible copies manually; the plugin never deletes or reconciles them automatically.


When a possible conflict copy is found, the preview can read a bounded candidate JSON file and show plugin IDs present only in that candidate versus only in the current policy. This is a comparison aid, not an automatic merge: both files remain untouched, and the user must reconcile them manually. Files larger than the policy size limit are skipped before reading.
