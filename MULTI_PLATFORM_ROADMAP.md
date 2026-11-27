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
- [ ] **P4 — Safe installation workflow (in progress)**: safety design documented in [P4 Safe Install Design](docs/multi-platform/P4_SAFE_INSTALL_DESIGN.md); P4.1 read-only eligibility preflight implemented. Release verification, manifest/version checks, staging, backup, rollback, and device validation remain pending. No files are downloaded or written.
- [ ] **P5 — Cross-device policy sync**: synchronize desired plugin policy while preserving device-specific settings and enabled state.
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

P1, P2, and P3 are complete at the code/CI-foundation level. Commit `b43aaf01a250d7c75156ef935f4dae1d935779b4` passed all 10 CI jobs: mobile TypeScript build plus all nine OS/Python matrix jobs. P4 safety design is documented; implementation has not started. Physical-device testing on Windows, macOS, iPhone, iPad, and Android remains outstanding, and no real-device compatibility is claimed yet.

The PR must remain a draft until all implementation phases and acceptance criteria are complete.
