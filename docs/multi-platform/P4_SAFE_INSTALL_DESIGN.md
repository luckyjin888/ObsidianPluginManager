# P4 — Safe installation design

Status: design baseline; no installation or enablement code is implemented yet.

## Goals

Provide a predictable, reversible way to place a verified community-plugin release into the current vault on desktop and mobile, without relying on Node.js, Electron, shell commands, undocumented Obsidian internals, or direct copying from another device.

## Platform boundary

- Use Obsidian's public `requestUrl` API for network requests.
- Use `app.vault.configDir` to locate the configured Obsidian configuration directory. Never hard-code `.obsidian`.
- Use the public `app.vault.adapter` interface for hidden configuration-folder files. Do not cast it to `FileSystemAdapter`; mobile uses a different adapter implementation.
- Do not use Obsidian CLI as the mobile install mechanism. CLI availability is desktop-oriented.
- Do not call private plugin-manager internals to load, enable, disable, reload, or uninstall plugins.
- After files are installed, show the user how to enable/reload the plugin from Obsidian Settings → Community plugins. Do not alter `community-plugins.json` or other enablement state.

## Eligibility gates (all required)

1. Plugin ID is a safe lowercase identifier and matches the shared catalogue entry.
2. Catalogue has a canonical HTTPS upstream URL on an explicitly supported host; no arbitrary user-supplied download URL.
3. Exact current runtime platform has status `verified`. `declared_unverified`, `unknown`, and `incompatible` all block installation.
4. Plugin manifest is valid JSON and its `id` exactly matches the catalogue ID.
5. Manifest version is valid and `minAppVersion` is compatible with the running Obsidian version.
6. Release metadata identifies the expected upstream repository and version. Redirects and asset origins must be constrained to an approved host policy.
7. Required assets are present: `manifest.json` and `main.js`; `styles.css` is optional.
8. Enforce per-file and total download size limits before writing.

A catalogue value of `isDesktopOnly: false` is never sufficient for eligibility. High-risk plugins require a separate explicit warning and user acknowledgement; unknown provenance is blocked.

## Integrity and provenance

- Prefer a release asset checksum/digest published by the upstream release and verify it before writing.
- If the upstream does not publish a verifiable digest, label the release as HTTPS-transport-only integrity and require a separate explicit confirmation; do not display it as cryptographically verified.
- Never execute downloaded code in the manager or inspect it by evaluating it.
- Do not silently fall back to a different repository, tag, branch, or mirror.

## Non-destructive installation transaction

Target path: `<app.vault.configDir>/plugins/<plugin-id>/`.

Only manager-owned runtime assets may be changed: `main.js`, `manifest.json`, and optional `styles.css`. Preserve plugin data/settings files such as `data.json`, unknown files, and the user's enabled/disabled state.

1. Show a preflight summary: plugin, source repository, release/version, exact platform evidence, minimum Obsidian version, files and sizes, checksum status, and existing target state.
2. Require a user confirmation immediately before writing.
3. Create a unique staging directory under the configured plugin directory using adapter APIs.
4. Download and validate all assets before touching the live target.
5. Back up each existing manager-owned asset before replacement. Do not overwrite plugin data/settings.
6. Write assets into staging; read back and validate the staged manifest and expected file set.
7. Move existing managed assets to backup and move staged assets into place. Do not claim adapter rename is atomic across every adapter implementation.
8. If any write or move fails, restore the previous managed assets. Report any rollback failure and retain the backup for manual recovery.
9. Leave unrelated files untouched. Never automatically uninstall or enable the plugin.
10. Present manual enable/reload instructions and a clear completion/rollback report.

## Backup retention

- Keep a versioned backup for every update/install that replaces existing runtime assets.
- Never delete backups automatically in the first release.
- Provide a future explicit user-controlled backup cleanup action only after backup/restore behavior is tested on all target adapters.

## Required tests before enabling writes

- Unit tests for ID/path validation, compatibility gates, manifest matching, version checks, asset allowlist, file-size limits, checksum validation, and rollback decision paths.
- Adapter contract tests for directory creation, write/read, rename, and restoration.
- Fault injection at every transaction step.
- Tests confirming `data.json`, unknown files, and plugin enabled state are not touched.
- Real-device smoke tests on Windows, macOS, iPhone, iPad, and Android before platform status can become `verified`.
- No claim of atomicity or full mobile support without evidence.

## Current implementation boundary

This document records the approved safety boundary for P4. The current plugin remains a read-only catalogue viewer. No release downloader, installer, backup writer, or plugin lifecycle action is present yet.

## Official API references reviewed

- [Obsidian `requestUrl` API](https://docs.obsidian.md/Reference/TypeScript%20API/requestUrl)
- [Obsidian Vault API](https://docs.obsidian.md/Plugins/Vault)
- [Obsidian plugin manifest requirements](https://docs.obsidian.md/Reference/Manifest)
- [Obsidian mobile development guidance](https://docs.obsidian.md/Plugins/Getting%20started/Mobile%20development)
- [Obsidian plugin self-critique checklist](https://docs.obsidian.md/oo/plugin)

These references are the basis for using `requestUrl`, `Vault.configDir`, and the generic vault adapter, and for avoiding Node/Electron-only assumptions on mobile.
