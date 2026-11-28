# Multi-platform install, policy and recovery guide

## Scope

The mobile Obsidian plugin is a front end for the shared plugin catalogue and per-device plugin operations. The existing Python desktop manager remains in place for Windows/macOS.

The shared policy file is `PluginManager/shared-policy.json`. It stores only a desired plugin list, notes and a revision. It does not synchronize plugin binaries, settings/data.json, enabled state, credentials, or device-local compatibility results.

## Compatibility gate

The catalogue records separate evidence for Windows, macOS, iOS, iPadOS and Android:

- `verified`: tested on the named platform with device, Obsidian version and date evidence.
- `declared_unverified`: upstream manifest does not declare desktop-only, but no successful device test is recorded.
- `incompatible`: known dependency or confirmed platform failure.
- `unknown`: insufficient evidence.

Only `verified` platform evidence is eligible for the automated installation path. A manifest field `isDesktopOnly: false` is not sufficient. Until a platform has real device evidence, the install action intentionally blocks on that platform.

## Installing or updating a catalogue plugin

1. Open the Plugin compatibility catalogue command.
2. Find a plugin and inspect its latest stable GitHub Release.
3. Verify downloaded release assets. The plugin checks the allowlisted files, GitHub asset size and SHA-256 metadata, and manifest ID/version/minimum Obsidian API version.
4. Choose Install verified release. The manager builds a per-device install plan and checks the catalogue's verified evidence for the current runtime.
5. Review and confirm the installation prompt.
6. The manager stages the exact verified bytes beneath the configured plugin directory's manager-owned staging path and verifies each file after writing.
7. Before replacing any existing allowlisted file, the manager writes a separate backup under `PluginManager/install-backups/<plugin-id>/<transaction-id>/` and verifies the backup bytes and manifest.
8. The manager writes only `manifest.json`, `main.js` and optional `styles.css`, then reads each target back and checks its SHA-256.
9. If a write or verification fails, the manager attempts a conditional rollback of only the target files this transaction attempted to change. The backup is retained. Inspect the reported backup path and rollback result before retrying.
10. Reload Obsidian if required. The manager does not automatically enable the installed plugin; enable it manually in Obsidian's Community plugins settings if appropriate.

The installer does not delete unknown plugin files, overwrite `data.json`, change plugin settings, or change enabled state. If the new release omits `styles.css`, an existing styles file is preserved rather than silently deleted.

## Shared policy Save

1. Run **Manage shared plugin policy (save / restore)**.
2. Review/edit the JSON. Use **Validate JSON** before saving.
3. Save requires confirmation.
4. When a policy already exists, the manager re-reads the reviewed baseline, writes a checksummed backup under `PluginManager/backups/`, reads that backup back, then applies the candidate only if `Vault.process()` still sees the exact reviewed content.
5. The manager verifies the exact resulting policy text after the write. If the baseline changed, the save is aborted and the newer content is preserved.

Creating a new policy is create-only: if another file appears at the same path before creation, the manager refuses to overwrite it.

## Shared policy Restore

1. Run **Manage shared plugin policy (save / restore)**.
2. Select a backup from the list. Only backups with a valid envelope digest and valid embedded policy are offered.
3. Review the backup revision and digest, then confirm restore.
4. Before restoring, the manager writes and verifies a fresh backup of the current policy.
5. The restore transaction performs a final local baseline check, writes the selected original bytes, and verifies the result. If verification fails, it attempts rollback only while the file still contains the restore candidate.

Restore currently requires an existing primary policy file. It does not create a missing policy file. Do not treat the local `Vault.process()` baseline comparison as a cross-device lock.

## Recovery and troubleshooting

- **Install blocked by compatibility:** do not override the evidence gate. Test the plugin on the exact platform and record device/OS/Obsidian version before marking it verified.
- **Release digest or manifest failure:** do not install. Re-inspect the upstream release; never bypass the verification.
- **Staging failure:** inspect the reported leftover staging paths. The manager attempts to remove only files/directories created during that staging attempt.
- **Install rollback failed:** do not retry blindly. Preserve the reported backup directory and inspect the target plugin files. Restore only after confirming the current state.
- **Policy save stale:** reload the current policy and compare changes; do not overwrite a newer synced copy.
- **Backup invalid/oversized:** it is reported as a diagnostic and is not offered for restore. Do not manually rename it to bypass validation.
- **Sync conflict copies:** compare them manually. Filename scanning is heuristic and cannot prove that every sync provider conflict was found.

## Device validation checklist

Record each platform separately; do not infer iPadOS success from iPhone or Android success.

| Platform | Device/model | OS version | Obsidian version | Install | Update | Rollback | Policy sync | Result/evidence |
|---|---|---|---|---|---|---|---|---|
| Windows | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Not tested |
| macOS | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Not tested |
| iPhone / iOS | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Not tested |
| iPad / iPadOS | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Not tested |
| Android | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Not tested |

Also test two-device offline edits, simultaneous policy edits, sync-provider conflict copies, interrupted file writes, insufficient storage, app termination during install, and restart/reload after a successful update.

## Guarantees and non-guarantees

- GitHub SHA-256 verification proves the downloaded bytes match the digest returned by GitHub's release metadata. It does not protect against a compromised upstream account or GitHub metadata.
- Backup read-back verifies the local Vault/DataAdapter result. It does not prove cloud sync durability or availability on another device.
- The commit helper uses per-file writes and conditional rollback. It is not a filesystem-wide atomic directory swap.
- Fake-adapter tests and desktop CI are not substitutes for real Obsidian runtime tests on physical devices.
- The feature must remain Draft until CI, real-device, multi-device sync and documentation gates are complete.
