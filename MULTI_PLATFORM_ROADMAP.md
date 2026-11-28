# Multi-platform Plugin Manager Roadmap

## Goal

Extend ObsidianPluginManager to support a shared plugin-management workflow across Windows, macOS, iOS, iPadOS, and Android while preserving the existing Python desktop application.

## Non-regression requirements

- Keep the existing Windows and macOS Python desktop manager and its current workflows.
- Do not replace or remove existing desktop launchers, configuration, or functionality as part of the mobile work.
- Keep all development on this feature branch until reviewed and merged.
- Do not modify `main` directly.
- Do not automatically merge this pull request.

## Proposed architecture

1. **Existing desktop application**: retain the current Python manager for Windows and macOS.
2. **Mobile Obsidian plugin**: add a TypeScript-based Obsidian plugin for iOS, iPadOS, and Android, using supported mobile APIs only.
3. **Shared plugin catalogue and policy**: define plugin metadata, source, version, desktop-only declaration, platform verification status, risk notes, and validation date in a shared format.
4. **Per-device installation decisions**: synchronize desired plugin selections/policies, but evaluate compatibility and install independently on each device.
5. **Settings and enablement safety**: do not blindly overwrite device-specific settings or enabled-plugin state; back up before changes and avoid automatic uninstall.
6. **Evidence-based compatibility**: distinguish upstream manifest claims from verified real-device results. Use separate statuses for verified, declared-but-unverified, incompatible, and unknown.

## Delivery phases

- [x] **P1 — Baseline and regression protection**: inventory existing desktop behavior and tests. Baseline recorded in [P1 Desktop Regression Baseline](docs/multi-platform/P1_DESKTOP_BASELINE.md). Initial PR CI run passed all 9 OS/Python matrix jobs.
- [x] **P2 — Shared catalogue and compatibility model**: versioned schema, nine-entry seed catalogue, compatibility evidence policy, dependency-free validator, seven unit tests, and CI validation step. Latest P2 commit `0790ce0bac7fcde2054b1017d12b912077cc274c` passed all 9 OS/Python matrix jobs.
- [x] **P3 — Mobile plugin foundation**: TypeScript plugin scaffold, platform detection, reproducible bundle/type-check workflow, and a read-only searchable catalogue view. Commit `b43aaf01a250d7c75156ef935f4dae1d935779b4` passed all 10 CI jobs (mobile build + 9 OS/Python matrix jobs). Physical-device smoke testing remains a separate release-validation requirement.
- [ ] **P4 — Safe installation workflow (in progress)**: P4.1 eligibility preflight, P4.2 latest-release metadata inspection, and P4.3 downloaded-byte SHA-256/manifest verification are implemented. Runtime minimum-version comparison now uses the official public `apiVersion` export. P4.4.1 adds an isolated pure install-plan gate that re-hashes the exact in-memory bytes, validates the allowlist, manifest, platform evidence, size limits, and target path; it performs no Vault writes. P4.4 staging, backup, replacement, rollback, adapter contract tests, and fault injection remain outstanding. Final CDN hostname is not exposed by `requestUrl`; the documented trust model instead binds downloaded bytes to GitHub API SHA-256 metadata.
- [ ] **P5 — Cross-device policy sync**: design documented in [P5 Cross-device Sync Design](docs/multi-platform/P5_CROSS_DEVICE_SYNC_DESIGN.md). Read-only preview and P5.4 interactive conflict-resolution preview implemented. P5.5 isolated guarded-write helper and fake-Vault fault-injection tests are now added; the helper is not wired to any UI/command, so policy writes remain disabled. Strict bounded parser, device-local compatibility display, conflict-copy hints, fingerprint, read-only ID comparison, explicit per-plugin current/candidate/remove choices, and deterministic in-memory JSON preview remain the user-facing scope. Fingerprint is not a lock and conflict scanning is heuristic; real adapter contract and recovery tests remain outstanding. The documented future write guard uses `Vault.cachedRead()` plus `Vault.process()` with an exact baseline comparison; this is local stale-write protection, not a cross-device lock.
- [ ] **P6 — CI and device validation**: keep Python CI; expand TypeScript build/type checks and static checks that prevent Node/Electron-only APIs from entering the mobile bundle. Record simulator and physical-device tests separately.
- [ ] **P7 — Documentation and release readiness**: document setup, limitations, compatibility evidence, and upgrade/rollback steps.

## Compatibility policy

- **Verified**: tested successfully on the named platform and recorded with device/OS/app details.
- **Declared, unverified**: upstream manifest does not mark the plugin desktop-only, but no real-device verification has been completed.
- **Incompatible**: known desktop-only dependency or confirmed platform failure.
- **Unknown**: insufficient evidence.

A manifest value such as `isDesktopOnly: false` is not proof of successful operation on every mobile platform.

## Safety and scope boundaries

- Mobile code must not depend on Node.js, Electron, Python, or shell execution.
- Do not rely on undocumented Obsidian internal APIs for critical installation or enablement behavior.
- Do not overwrite user plugin settings without an explicit policy and backup.
- Do not automatically uninstall plugins.
- Do not claim full platform compatibility until validated on actual devices.
- Any feature that cannot be implemented with supported APIs should degrade to a documented manual workflow.

## Acceptance criteria

- Existing Windows and macOS desktop workflows continue to pass regression tests.
- The shared catalogue has schema validation and explicit evidence status per platform.
- The mobile plugin builds and passes type/static checks.
- Mobile installation logic is isolated from desktop-only dependencies.
- Sync does not blindly copy desktop binaries or overwrite device-specific configuration.
- CI results and real-device test evidence are documented before the PR is marked ready for review.

## Current status

P1, P2, and P3 are complete at the code/CI-foundation level. P4.1–P4.3 are implemented; P4.3 now checks the running Obsidian API version through the official `apiVersion` export. P4.4.1 provides a pure install-plan validation gate. P4.4.2 adds an isolated staging helper that writes only to a manager-owned staging directory and verifies exact read-back; it is not connected to UI/commands and never touches the live plugin directory. P4.4.2 CI is pending. Backup, replacement, rollback, public adapter contract tests, and physical-device validation remain outstanding. Redirect-host attestation is unavailable through the public API; the documented integrity model relies on canonical GitHub API metadata plus exact downloaded-byte SHA-256 verification. Adapter contract tests, fault injection, and physical-device validation remain outstanding. Physical-device testing on Windows, macOS, iPhone, iPad, and Android remains outstanding. The PR must remain a draft until all implementation phases and acceptance criteria are complete.


### P5.4 — explicit conflict-resolution preview UI

- Added a pure in-memory builder requiring an explicit per-plugin choice (keep current, keep candidate, or remove).
- Added interactive controls for each plugin ID; current/candidate choices are offered only when that source contains the ID.
- Added an editable revision field and a read-only JSON preview area.
- Missing choices and invalid source selections are rejected; notes follow the explicitly selected source.
- Produces deterministic preview JSON only; no Save action or Vault write is enabled.
- Added tests for incomplete choices, invalid source selections, source/note selection, deterministic output, and input immutability.
- CI Run #289 passed all 10 jobs, including mobile type-check/build/package and Windows/macOS/Ubuntu Python test jobs.


### P5.5 — guarded write protocol foundation (not user-enabled)

- Added isolated `writeSharedPolicyWithBaseline()` using a caller-supplied baseline, strict candidate validation, synchronous `Vault.process()` content comparison, and post-write exact-content verification.
- The helper distinguishes invalid candidate, stale baseline, process/read failure, and post-write verification failure.
- Added fake-Vault fault-injection tests for successful guarded update, concurrent/stale content, invalid candidate, process exception, post-write corruption, read exception, and missing process callback.
- CI now runs all `tests/*.test.mjs` under `npm run test:policy`.
- The helper is not connected to any command or UI. No Save button, confirmation flow, backup journal, rollback, or cross-device lock exists; policy writes remain disabled.


### P5.5.1 — public Obsidian Vault adapter contract

- Added a typed adapter over the public `Vault.process()` and `Vault.read()` methods.
- Updated the adapter port to accept the asynchronous result returned by the public process API without coupling the policy helper to a concrete return type.
- Added a delegation contract test proving the same file and synchronous callback are forwarded and that post-write verification uses Vault.read().
- This is a mocked adapter contract test, not an Obsidian runtime, device filesystem, or multi-device sync test.
- Policy writes remain disabled in the UI; real-device testing and backup/recovery design are still required.


### P5.5.2 — stale-process side-effect caveat

- Documented that returning the unchanged current string from a stale `Vault.process()` callback does not prove the adapter performs no write, timestamp update, sync notification, or file event.
- The helper reports `stale` and does not report success, but this no-op side-effect behavior must be verified against real Obsidian adapters before any Save UX is enabled.


### P5.6.1 — backup/recovery format foundation (not persisted)

- Added a strict versioned backup envelope preserving the exact original policy bytes, target path, timestamp, and SHA-256 digest.
- Added validation for envelope size, schema/fields/path, timestamp, digest format, and content integrity.
- Added deterministic sanitized backup filename generation.
- Added tests for exact-byte round trip, tamper detection, unsupported fields, malformed timestamps, and unsafe filename inputs.
- This is in-memory only: no backup file is created, no durable read-back verification exists, and no restore/rollback path is enabled. Writes remain disabled.


### P5.6.2 — Vault backup persistence helper (not wired to policy writes)

- Added a public Vault adapter using `getAbstractFileByPath()`, `createFolder()`, `create()`, and `read()`.
- Added a helper that creates a versioned backup file under `PluginManager/backups/`, refuses to overwrite a different existing file, and reads the new file back.
- The helper reports `created` only after exact serialized-byte read-back and SHA-256 envelope validation; identical existing backups are reported as already present.
- Added fake-Vault tests for successful creation, idempotent identical backup, path collision, corrupted read-back, folder failure, create failure, and read failure.
- Immediate Vault read-back is not proof of remote sync durability or cross-device availability. No restore/rollback UI exists; the helper is not connected to the policy writer and Save remains disabled.


### P5.6.2 test correction

- The first persistence-test run failed because the fake Vault fixture implemented the helper port rather than the public Obsidian Vault API expected by the adapter.
- Updated the fixture to model `getAbstractFileByPath()`, `createFolder()`, `create()`, and `read()`, including structural file/folder objects.
- Awaiting a fresh CI run for the corrected fixture. Previous persistence test failures are not counted as passing.


### P5.6.3 — read-only backup inventory and comparison

- Added a Vault backup-directory scanner with size-before-read checks, envelope SHA-256 validation, and embedded policy validation.
- Invalid, unreadable, oversized, and invalid-policy backups are reported as diagnostics; nothing is deleted or repaired.
- Added the Obsidian command **Preview shared policy backups (read-only)**.
- Valid entries show backup path, size, timestamp, digest, policy revision, desired-plugin count, and set-difference counts against the current valid policy.
- No restore, overwrite, or delete action is exposed. Remote sync durability and device-loss recovery are not proven.
- CI for this latest work is pending.


### P4.4.1 — isolated install-plan validation gate (no Vault writes)

- Added `mobile-plugin/src/install-transaction.ts` as a pure preflight module that accepts the exact in-memory asset bytes intended for installation.
- Recomputes SHA-256 for each allowlisted asset and checks the published digest, per-file/aggregate size limits, required `manifest.json` and `main.js`, manifest ID/version/minimum API version, and explicit `isDesktopOnly: false`.
- Requires verified evidence for the exact runtime platform; iOS runtime requires both iOS and iPadOS evidence.
- Validates plugin ID and relative `configDir` path before deriving the target directory.
- Added `mobile-plugin/tests/install-transaction.test.mjs` for successful planning, digest mismatch, platform evidence, minimum API version, unsafe path/ID, unknown assets, and duplicate asset names.
- This stage only returns a plan. It does not create directories, stage files, back up installations, replace files, roll back, or enable plugins.
- Latest P4.4.1 CI result has not yet been reported; do not count this stage as CI-passing until the workflow completes.


### P4.4.2 — isolated verified staging helper (not wired to installation UI)

- Added `mobile-plugin/src/install-staging.ts`: requires an explicit confirmation flag, validates the plan target and transaction ID, refuses an existing transaction directory, and writes only allowlisted plan bytes beneath `<configDir>/plugins/.plugin-manager-staging/<plugin-id>/<transaction-id>/`.
- Re-hashes plan bytes immediately before writing and reads every staged file back to verify exact byte length and SHA-256.
- On a staging failure, attempts to remove only files and directories created by that staging attempt; reports any paths that could not be cleaned.
- Added fake-adapter contract/fault-injection tests for success, missing confirmation, collision, unsafe paths/IDs, write failure cleanup, and corrupted read-back.
- The live plugin directory is never changed by this helper. It does not create a backup, replace files, roll back an installation, enable a plugin, or provide real Obsidian/mobile adapter verification.
- CI for this P4.4.2 batch is pending; do not count it as passed until the workflow completes.
