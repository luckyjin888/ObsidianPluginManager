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
- [ ] **P4 — Safe installation workflow (in progress)**: P4.1 eligibility preflight, P4.2 latest-release metadata inspection, and P4.3 downloaded-byte SHA-256/manifest verification are implemented. Runtime minimum-version comparison now uses the official public `apiVersion` export. P4.4 transaction protocol is documented only; no vault writes are enabled. Final CDN hostname is not exposed by `requestUrl`; the documented trust model instead binds downloaded bytes to GitHub API SHA-256 metadata. Adapter contract tests and fault injection remain required before writes.
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

P1, P2, and P3 are complete at the code/CI-foundation level. P4.1–P4.3 are implemented; P4.3 now checks the running Obsidian API version through the official `apiVersion` export. P4.4 remains design-only. Redirect-host attestation is unavailable through the public API; the documented integrity model relies on canonical GitHub API metadata plus exact downloaded-byte SHA-256 verification. Adapter contract tests, fault injection, and physical-device validation remain outstanding. Physical-device testing on Windows, macOS, iPhone, iPad, and Android remains outstanding. The PR must remain a draft until all implementation phases and acceptance criteria are complete.


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
