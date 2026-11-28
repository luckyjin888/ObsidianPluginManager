# Advanced Audio Recorder — catalogue integration

**Decision date:** 2026-11-28  
**Upstream:** https://github.com/akhmialeuski/advanced-audio-recorder  
**Obsidian plugin ID:** `advanced-audio-recorder`  
**License:** MIT  
**Upstream release checked:** 2.6.1, published 2026-11-25  
**Minimum Obsidian version:** 1.14.4

## Why this plugin was selected

The Obsidian community listing showed approximately 2,000 downloads. The upstream project is active, has a permissive MIT license, publishes standard Obsidian release assets (`main.js`, `manifest.json`, `styles.css`) with SHA-256 digests, and explicitly documents desktop plus mobile support for iOS and Android.

It reuses an existing plugin rather than reimplementing audio capture or speech recognition.

## Existing capabilities

- Record inside Obsidian; pause, resume and recover interrupted recordings.
- Save audio into the vault and embed it in the active note.
- Transcribe existing or newly recorded audio through supported providers.
- Optional speaker labels and clickable timestamps, depending on provider.
- Optional LLM post-processing to clean up or summarize transcripts.
- Supports cloud providers and local Whisper on supported desktop setups.

## Important limitations

- The current upstream manifest requires Obsidian 1.14.4 or newer.
- Multi-track capture, local whisper.cpp transcription and input-device selection are desktop-only.
- Mobile devices can record and use supported remote transcription providers; do not assume every desktop feature is present on phones.
- Cloud transcription sends audio to the configured provider. LLM post-processing sends transcript text to the configured LLM provider.
- The plugin's own release notes and platform capability checks are authoritative for each feature; a non-desktop-only manifest is not proof of full platform parity.

## Manager integration

- Added to the desktop Python manager's curated community-plugin list. The existing installer still performs its official community-registry, repository, license and archive checks, then uses Obsidian CLI only after the user's batch confirmation.
- Added to `shared/plugin-catalog.json` so the mobile catalogue can display and inspect it.
- All five platform states are recorded as `declared_unverified`, not `verified`. The mobile manager's existing safety policy therefore continues to block installation until real device evidence is recorded.
- No upstream source code is copied, bundled, patched or forked. The manager installs the upstream release through its existing installation path.
- No API key is added or synchronized.

## First-use notes

After installation, open the plugin settings and configure the desired transcription provider and optional LLM provider. API usage may incur charges. The API key belongs to the user's own provider account and must not be committed to the repository or shared vault.

The plugin adds its own microphone ribbon button. Consider disabling or hiding Obsidian's built-in Audio recorder button to avoid confusion between two recorder buttons.

## Sources

- Community listing: https://community.obsidian.md/plugins/advanced-audio-recorder
- Upstream repository: https://github.com/akhmialeuski/advanced-audio-recorder
- Upstream manifest: https://raw.githubusercontent.com/akhmialeuski/advanced-audio-recorder/master/manifest.json
- Latest release: https://github.com/akhmialeuski/advanced-audio-recorder/releases/tag/2.6.1
- Getting started: https://github.com/akhmialeuski/advanced-audio-recorder/blob/master/docs/getting-started.md
