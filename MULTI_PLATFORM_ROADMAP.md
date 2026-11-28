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

- [x] **P1 — Baseline and regression protection**: inventory existing desktop behavior and tests. Baseline recorded in [P1 Desktop Regression Baseline](docs/multi-platform/P1_DESKTOP_BASELINE.md). Existing desktop regression matrix remains in CI.
- [x] **P2 — Shared catalogue and compatibility model**: versioned schema, five-platform evidence model, validator, tests, and CI validation.
- [x] **P3 — Mobile plugin foundation**: TypeScript plugin scaffold, platform detection, reproducible bundle/type-check workflow, and a read-only searchable catalogue view. Physical-device smoke testing remains a separate release-validation requirement.
- [ ] **P4 — Safe installation workflow (in progress)**: P4.1 eligibility preflight, P4.2 latest-release metadata inspection, P4.3 downloaded-byte SHA-256/manifest verification, P4.4.1 install-plan validation, and P4.4.2 isolated verified staging are implemented. Run #342 passed all 10 jobs for commit `146a472`. Staging is not connected to a live installation transaction. Backup-before-replacement, safe replacement, rollback, recovery journal, public Obsidian Vault adapter contract tests, and device fault testing remain outstanding. No live plugin replacement or enablement is exposed.
- [ ] **P5 — Cross-device policy sync (in progress)**: strict bounded parser, device-local compatibility display, conflict-copy hints, fingerprint, read-only comparison, explicit per-plugin resolution preview, guarded writer, backup envelope/persistence/inventory, restore preview, and confirmed restore helper exist. A new management modal now exposes explicit Save and Restore actions: Save validates the policy, creates and verifies a backup before changing an existing file, uses Vault.process baseline comparison, and checks exact read-back; Restore offers only validated backups, previews the selected recovery, backs up current bytes, and requires explicit confirmation. These operations affect only the desired-plugin policy, not plugin binaries/settings. Vault.process is local stale-write protection, not a distributed lock; sync-provider durability and real-device behavior remain unverified.
- [ ] **P6 — CI and device validation (in progress)**: Python regression tests remain on Windows/macOS/Ubuntu. Mobile type-check, helper tests, bundle build, and ZIP packaging are now configured for Ubuntu, macOS, and Windows CI runners. A source scanner rejects Node.js/Electron-only APIs from mobile runtime source. The expanded CI matrix is pending. Simulator and physical-device tests are separate release-validation requirements.
- [ ] **P7 — Documentation and release readiness (in progress)**: architecture and safety boundaries are documented. User-facing install/update/recovery instructions, release notes, compatibility evidence, and final review remain outstanding.

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
- The mobile plugin builds and passes type/static checks on supported CI operating systems.
- Mobile installation logic is isolated from desktop-only dependencies.
- Sync does not blindly copy desktop binaries or overwrite device-specific configuration.
- CI results and real-device test evidence are documented before the PR is marked ready for review.

## Current status

P1, P2, and P3 are complete at the code/CI-foundation level. P4.1–P4.3 are implemented; P4.4.1 provides a pure install-plan validation gate and P4.4.2 provides an isolated staging helper with exact read-back verification. Run #342 passed all 10 jobs on the previous P4.4.2 head. P4.4 now includes a backup-first live-file commit helper with exact read-back verification, conditional rollback, a public DataAdapter adapter for configDir paths, and a catalogue install action wired behind verified platform evidence and explicit confirmation. The latest commit's CI has not yet validated this integration; real Obsidian/device filesystem behavior remains unverified. P5 now has an explicit Save/Restore management UI wired to backup-first guarded policy writes and confirmed recovery; automated CI and real-device/sync-provider validation are still required. P6 now has an expanded three-OS mobile CI matrix and a source API guard; that expanded matrix has not yet run. No real-device testing has been completed on Windows, macOS, iPhone, iPad, or Android. The PR remains a draft and must not be merged until implementation and acceptance criteria are satisfied.

## P4.4.2 — isolated verified staging helper

- Requires explicit confirmation, validates the target path and transaction ID, refuses an existing staging transaction, and writes only allowlisted verified bytes beneath a manager-owned staging directory.
- Re-hashes bytes before writing and verifies exact read-back length and SHA-256.
- On failure, attempts cleanup of only paths created by the current staging attempt and reports leftovers.
- Does not modify the live plugin directory, back up or replace an installed plugin, roll back, or enable a plugin.
- Fake-adapter fault-injection tests are included; this is not a real Obsidian/mobile adapter test.

## P6 — cross-platform build and runtime API guard

- Mobile build, type-check, helper tests, and package generation now run on Ubuntu, macOS, and Windows CI runners.
- A source scanner rejects Node.js builtin imports, Electron imports, CommonJS require, selected Node process globals, Buffer APIs, and Node path globals in `mobile-plugin/src/**/*.ts`.
- The expanded matrix must pass before this milestone is considered complete. CI is not physical-device validation.


## P5.7 — explicit Save and Restore management UI

- Added a dedicated management modal and command for editing, validating, saving, and restoring the shared desired-plugin policy.
- Saving an existing policy validates the candidate, re-reads the reviewed baseline, persists and verifies an immutable backup, applies a guarded Vault.process update, and verifies exact post-write content.
- Creating a previously absent policy uses a create-only path and exact read-back verification; if a file appears concurrently, the create is refused.
- Restore lists only backups whose envelope digest and embedded policy validate, requires an existing policy file, previews the selected backup against the current bytes, requires explicit confirmation, persists a fresh backup of current content, and delegates to the guarded restore/conditional rollback helper.
- The UI does not synchronize plugin binaries, settings, enabled state, credentials, or device-local compatibility results. It does not install plugins.
- Mocked adapter tests cover the underlying helpers; the new UI wiring requires CI and real Obsidian runtime verification. This is not a distributed lock or proof of remote sync durability.

## P6.1 — Windows test-runner portability fix

- Changed mobile helper test invocation from shell-expanded `tests/*.test.mjs` to Node's built-in test discovery (`node --test`) so PowerShell/Windows does not pass an unexpanded wildcard path.
- Run #343 exposed this Windows-only test-discovery failure; the Ubuntu and macOS mobile jobs and the Python matrix passed. A fresh CI run is required to verify the fix.


## P4.4.3–P4.4.5 — backup-first install commit and rollback

- Added a public Obsidian DataAdapter adapter so paths under the configured plugin directory can be accessed without assuming that hidden config files are exposed as normal Vault TFiles.
- Added a guarded commit helper that validates the plan/staging transaction, re-verifies staged bytes, snapshots all existing allowlisted target files, writes and verifies an immutable backup manifest and backup bytes, and only then replaces the live allowlisted assets.
- Each live target write is read back and checked against the approved SHA-256. A failed commit attempts rollback only for files this transaction attempted to change; pre-existing unknown files, plugin data/settings, and enablement are not touched.
- Backup directories are retained after failures for diagnosis; an occupied transaction path is never overwritten.
- Added the catalogue install action: inspect release, verify downloaded bytes, build a platform-evidence-gated plan, ask for explicit confirmation, stage bytes, commit with backup/rollback, and report backup path. It does not automatically enable the plugin.
- Added fake-adapter tests for successful replacement, preserved user data/unknown files, explicit confirmation, backup collisions, staged-byte tampering, and mid-commit rollback.
- CI must pass before this implementation is considered validated. Fake-adapter tests do not establish real-device filesystem behavior.
