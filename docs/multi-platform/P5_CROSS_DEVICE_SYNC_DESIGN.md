# P5 — Cross-device policy synchronization design

Status: read-only preview, conservative conflict-copy hints, content fingerprint, and explicit per-plugin resolution preview UI implemented. No synchronization writer is enabled.

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


## Safe-write protocol for a future policy editor

When write support is considered, use the public Obsidian Vault API rather than writing through the adapter or Node filesystem:

1. Read the current file with `vault.cachedRead(file)` and retain the exact baseline string.
2. Perform any user interaction and merge preparation outside the write callback.
3. Re-enter `vault.process(file, current => ...)`. Inside its synchronous callback, compare `current` byte-for-byte/string-for-string with the retained baseline.
4. If they differ, return the current content unchanged and report a stale-preview conflict. Do not apply the candidate.
5. If they match, return the fully validated candidate JSON string. Do not perform asynchronous work inside the `process` callback.
6. After the operation, re-read and validate the resulting file before reporting success.

Obsidian documents that `Vault.process()` guarantees the file does not change between its read and write, and specifically recommends comparing the `process()` callback data with a prior `cachedRead()` result when asynchronous work occurs between reading and writing. This is a **local file operation guarantee**, not a distributed lock: it cannot guarantee that another device's sync provider will not later deliver a competing version. The UI must still warn about that limitation, and no automatic merge or conflict-copy deletion is allowed.

An isolated guarded writer helper now exists in `mobile-plugin/src/shared-policy-write.ts`, including a typed adapter that delegates to the public `Vault.process()` and `Vault.read()` methods. Its process port accepts the public API's asynchronous return value without depending on it. A contract test verifies that the adapter forwards the same `TFile`, callback, and read call. It is not connected to a command, modal, or Save button. It accepts a previously captured baseline (the future caller must obtain it with `Vault.cachedRead()` before user review), validates the proposed JSON, then uses `Vault.process()` to compare exact current content with that baseline. A mismatch returns the current content unchanged and reports `stale`; a match returns the candidate. It then re-reads and verifies exact output. The helper reports invalid candidate, stale baseline, process/read failure, and post-write verification failure distinctly. Fault-injection tests use a fake Vault adapter to exercise these paths. This code is an isolated protocol implementation, not permission to enable writes: there is no user-facing caller, no confirmation UI, no backup/journal/rollback, and no cross-device lock. This adapter test verifies delegation shape only; it is not a real Obsidian runtime or mobile filesystem test. Real-device adapter behavior, sync-provider races, backup/journal/rollback, and failure-recovery design remain required before a Save action is exposed.


## Explicit resolution preview (read-only)

A pure helper now builds an in-memory resolution preview from two valid policies and a per-plugin choice map:

- Every plugin ID present in either copy requires an explicit choice: keep the current entry, keep the candidate entry, or remove the ID.
- If an ID exists in only one source, choosing the other source is invalid.
- When the same ID has different notes, choosing a source also explicitly chooses that source's note.
- Missing choices, invalid choices, invalid revisions, or invalid resulting policy data produce no JSON output.
- The result is a deterministic JSON preview only. It does not write the Vault, change either input object, install plugins, or authorize installation.

The interactive preview UI is implemented in `mobile-plugin/src/shared-policy-view.ts`. For each valid candidate copy, the user must choose current, candidate, or remove for every plugin ID. Source choices are offered only when that source contains the ID. The revision is editable, and the resulting deterministic JSON is displayed in a read-only text area. Missing choices or invalid revisions prevent preview generation. The UI reports that the result is in memory only. There is deliberately no Save button and no Vault write path. This is not a synchronization action or an installation authorization.

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

The read-only preview, pure explicit-resolution helper, interactive in-memory resolution preview UI, isolated guarded-write protocol helper, and thin typed Obsidian Vault adapter are implemented in `mobile-plugin/src/shared-policy.ts`, `mobile-plugin/src/shared-policy-view.ts`, and `mobile-plugin/src/shared-policy-write.ts`. It reads only `PluginManager/shared-policy.json` through the public Vault API, checks the file size before reading, validates a strict bounded JSON shape, displays desired IDs with this device's bundled-catalogue compatibility evidence, reports similarly named sibling files as possible conflict copies, and displays a SHA-256 fingerprint when Web Crypto is available. For valid primary policies it also reads bounded candidate files and displays a read-only set difference of plugin IDs; it never merges or changes either copy. A separate pure helper can construct a proposed merged JSON string from explicit per-ID choices, but this result remains in memory and is not saved. The scan is heuristic and the fingerprint is not a lock; neither can guarantee race-free multi-device editing. It does not create or modify the file, fetch arbitrary sources, infer installed/enabled state, or synchronize plugin folders/binaries. Policy writes remain disabled in the UI pending adapter contract tests, failure-recovery safeguards, explicit confirmation, and an honest limitation warning.
