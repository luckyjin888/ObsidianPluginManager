# P4 — Safe installation design

Status: design baseline plus P4.1 eligibility preflight and P4.2 latest-release metadata inspection. No installation or enablement code is implemented yet.

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


## P4.2 implementation boundary — release metadata only

The mobile plugin now inspects the latest stable release through Obsidian's public `requestUrl` API and GitHub's `/releases/latest` endpoint. This step is metadata-only:

- Accept canonical HTTPS `github.com/{owner}/{repo}` upstream URLs only.
- Require a published, non-draft, non-prerelease release with a semantic-version tag.
- Require `manifest.json` and `main.js`; allow only optional `styles.css` in addition.
- Enforce 256 KiB manifest, 20 MiB main bundle, 2 MiB stylesheet, and 25 MiB aggregate limits.
- Constrain every asset URL to that repository's GitHub Releases download path.
- Inspect GitHub's `sha256:<64 hex>` digest metadata. Missing or malformed digests block install eligibility.
- Treat 404, 403, 429, and other non-success HTTP statuses as explicit failures; never fall back to a branch archive or mirror.

**Important:** a published digest is not yet a verified digest. The current code does not download assets, hash their bytes, compare the downloaded manifest to the catalogue ID/release version, or write anything to the vault. P4.3 and P4.4 remain mandatory before any write path can be enabled.


## P4.3 implementation boundary — downloaded-byte verification only

The plugin now has a separate verification action that downloads each allowlisted asset into memory via Obsidian's public `requestUrl` API, checks the byte length against the release metadata, calculates SHA-256 using Web Crypto, and compares it with the GitHub-published digest. It parses only the digest-verified `manifest.json` and checks exact plugin ID, release version, minimum Obsidian version, and an explicit `isDesktopOnly: false` declaration.

No downloaded bytes are written to the vault, executed, or persisted. A successful P4.3 verification is not install permission. One API limitation remains: Obsidian's `RequestUrlResponse` exposes status, headers, and body but not the final URL after redirects. The requested source URL is restricted to the expected GitHub repository release path, but the final CDN hostname cannot be independently asserted by this code. This must be addressed or explicitly accepted in the final threat model before enabling writes.

## P4.4 transaction protocol — implementation gate and design

P4.4 will be implemented as a separate transaction module and will remain disabled until every precondition below is satisfied.

### Preconditions (all mandatory)

1. The runtime platform is known and the selected catalogue entry is exactly `verified` for that platform (iOS-family devices require both iOS and iPadOS evidence).
2. The release metadata is from the canonical upstream repository and the stable release has the exact allowlisted assets.
3. Every downloaded asset's bytes match its published SHA-256 digest and expected byte length.
4. The manifest plugin ID and version match the selected catalogue entry and release tag.
5. A trustworthy runtime Obsidian version is available and satisfies `minAppVersion`. Until a supported source exists, this condition is false and the transaction must not begin.
6. The user explicitly confirms the exact plugin ID, version, target path, and replacement of any existing installation.
7. The user has been told that activation remains a separate manual action in Obsidian's Community Plugins settings.

### Transaction sequence

1. Resolve the plugin directory using `app.vault.configDir` and the generic `app.vault.adapter`; never assume the configuration directory is named `.obsidian` and never cast to a desktop filesystem adapter.
2. Check adapter capabilities and path existence. Refuse if the target path is ambiguous, a file instead of a directory, or the adapter cannot safely read/write binary files and enumerate required paths.
3. Create a uniquely named staging directory beneath the plugin manager's own staging area using adapter APIs. Write only the three allowlisted verified files.
4. Read every staged file back and re-check byte length and SHA-256 before touching the installed plugin directory.
5. If a target installation exists, create a backup in a separate backup area and verify the copied files. Never overwrite or delete the only known-good copy.
6. Re-check the user confirmation and target state immediately before replacement to reduce time-of-check/time-of-use risk.
7. Copy staged files into the target directory. Since the public adapter contract does not promise an atomic multi-file directory swap on every mobile backend, treat each step as fallible and journal completed operations.
8. On any failure, restore the backup (or remove only files created by this transaction if no prior installation existed), verify the restored bytes, and preserve the backup if recovery is uncertain.
9. Keep backups until the user explicitly removes them. Never delete `data.json`, unknown files, or user settings as part of an update.
10. Do not enable, disable, or reload the plugin programmatically. Show the manual next step only after successful file placement.

### Failure and recovery rules

- A failed stage write must leave the current installation untouched.
- A failed backup must abort before replacement.
- A failed replacement must attempt rollback and report whether rollback itself was verified.
- If rollback cannot be verified, preserve all remaining staged/backup material and clearly instruct the user not to retry until inspected.
- Never claim atomicity. Never silently retry destructive operations.
- Adapter-specific contract tests and injected failures are required for mkdir, exists, readBinary, writeBinary, list, remove, and rename/copy behavior actually used by the implementation.

### Current state

This section is a design only. No transaction writer, backup, rollback, or vault mutation is enabled. The unresolved runtime-version and redirect-target limitations above remain hard blockers, so P4.4 implementation must not bypass them.


## P4.3 runtime version check — resolved

The mobile plugin imports the officially exported `apiVersion` from `obsidian` and compares it against the verified manifest's `minAppVersion`. The official API definition documents `apiVersion` as the app's API version, following the desktop release cycle. The implementation deliberately does not use an undocumented `App.version` property or third-party internal typings. See the [official Obsidian API type definition](https://github.com/obsidianmd/obsidian-api).
