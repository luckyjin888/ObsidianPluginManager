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

- **P1 — Baseline and regression protection**: inventory existing desktop behavior and tests; add regression coverage before changing shared behavior.
- **P2 — Shared catalogue and compatibility model**: define a versioned schema and validate plugin metadata.
- **P3 — Mobile plugin foundation**: add the TypeScript plugin scaffold and platform detection using supported Obsidian APIs.
- **P4 — Safe installation workflow**: validate source/version/platform, back up affected files, and provide rollback behavior.
- **P5 — Cross-device policy sync**: synchronize desired plugin policy while preserving device-specific settings and enabled state.
- **P6 — CI and device validation**: keep Python CI; add TypeScript build/type checks and static checks that prevent Node/Electron-only APIs from entering the mobile bundle. Record simulator and physical-device tests separately.
- **P7 — Documentation and release readiness**: document setup, limitations, compatibility evidence, and upgrade/rollback steps.

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

This draft records the agreed direction and staged plan only. Implementation has not yet been completed. The pull request must remain a draft until the acceptance criteria are met.
