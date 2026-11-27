# P5 — Cross-device policy synchronization design

Status: read-only preview foundation implemented. No synchronization writer is enabled.

## Goal

Let a user keep one shared *desired plugin policy* in a vault that is synchronized by the user's existing vault-sync mechanism, while each device independently evaluates compatibility and installation state.

This is policy synchronization, not binary/plugin-folder synchronization.

## What is shared

A future version may store a versioned JSON document at a normal vault path:

`PluginManager/shared-policy.json`

The document contains only user intent, for example:

- schema version;
- a list of plugin IDs the user wants available;
- optional user-authored notes or priority;
- policy document revision metadata.

It must not contain downloaded code, release assets, API tokens, credentials, local filesystem paths, or device-specific plugin settings.

## What is never copied between devices

- `.obsidian/plugins/**` runtime files;
- `main.js`, `manifest.json`, or `styles.css` binaries;
- `data.json` or plugin-specific settings;
- enabled/disabled state;
- platform verification evidence or local install results;
- backup/staging directories.

Each device reads the shared desired list, checks its own platform and local Obsidian version, then independently decides whether a plugin is eligible. A plugin desired on iPhone may be blocked on iPhone while remaining eligible on macOS. One device's success never upgrades another device's compatibility status.

## Data validation

Before accepting a shared policy:

1. Validate the schema version and required fields.
2. Require unique plugin IDs matching the safe identifier syntax.
3. Reject unknown fields that could be interpreted as executable instructions or paths.
4. Bound file size and list length.
5. Treat unknown plugin IDs as inert entries; never fetch arbitrary URLs from the policy file.
6. Resolve all source URLs from the locally bundled trusted catalogue, not from the shared policy.
7. Never interpret a shared policy entry as authorization to install or enable a plugin.

## Conflict and corruption handling

Obsidian vault sync providers may deliver edits asynchronously and may create conflict copies. The adapter API does not provide a cross-device compare-and-swap transaction.

Therefore the first implementation must not silently overwrite a policy file based only on a timestamp or local clock:

- Parse and validate before displaying or applying.
- If JSON is invalid, preserve the original file and show a read-only error.
- If a conflict copy or concurrent edit is detected, pause writes and ask the user to reconcile.
- Before a write, re-read the current file and compare its content hash with the version originally loaded.
- If it changed, abort the write and offer a merge/reload flow; do not use silent last-write-wins.
- Keep a user-visible prior revision or a recoverable copy before any policy mutation.
- Never delete conflict copies automatically.

Because the vault adapter has no atomic cross-device compare-and-swap guarantee, these checks reduce accidental overwrites but cannot eliminate all races. The UI must state this limitation.

## User experience

- Read-only preview is the first milestone.
- The UI must distinguish “desired by shared policy” from “installed on this device”.
- Per-device result labels: eligible, blocked, already present, missing, or unknown.
- A blocked device must never change the shared desired list automatically.
- Explicit user action is required to add/remove a desired plugin.
- The policy file may be synced by Obsidian Sync, iCloud, Git, or another user-selected vault sync mechanism; this plugin does not create accounts or transmit policy to a manager-owned server.

## Required tests before write support

- schema validation and size limits;
- duplicate and unsafe IDs;
- unknown fields and unknown catalogue IDs;
- invalid JSON preservation;
- concurrent-edit detection and abort;
- conflict-copy detection;
- round-trip tests on the generic vault adapter;
- tests proving no plugin binaries, settings, enabled state, tokens, or local paths are copied;
- manual multi-device tests with Mac, Windows, iPhone, iPad, and Android, including offline edits and sync conflicts.

## Implementation boundary

The first read-only preview foundation is implemented in `mobile-plugin/src/shared-policy.ts` and `mobile-plugin/src/shared-policy-view.ts`. It reads only `PluginManager/shared-policy.json`, validates a strict bounded JSON shape, and displays desired IDs with this device's bundled-catalogue compatibility evidence. It does not create or modify the file, fetch arbitrary sources, infer installed/enabled state, or synchronize plugin folders/binaries. Policy writes remain disabled until conflict handling and adapter tests are implemented.
