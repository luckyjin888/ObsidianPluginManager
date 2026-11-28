# Audio Recording and Speech-to-Text Research

**Research date:** 2026-11-28  
**Target:** ObsidianPluginManager / Company-Hub  
**Scope:** Open-source recording inside Obsidian, high-quality Chinese transcription, and a viable Windows/macOS/iOS/iPadOS/Android workflow.

## Executive summary

Do not build a recorder or ASR model from scratch yet. Reuse a maintained Obsidian recorder where possible and keep the transcription engine replaceable.

**First candidate to validate: Advanced Audio Recorder**  
It has the broadest recording workflow in this review: microphone capture, pause/resume, recovery, waveform playback, bookmarks/chapters, format conversion, and transcription integrations. Its upstream README says it supports desktop and mobile, but explicitly marks multi-track recording, automatic splitting, local whisper.cpp transcription, and input-device selection as desktop-only. Mobile transcription therefore needs a remote compatible endpoint/provider; this must be tested on actual iOS and Android devices.

**Chinese ASR candidate: SenseVoiceSmall served by FunASR**  
SenseVoiceSmall explicitly supports Mandarin, Cantonese, English, Japanese, and Korean. FunASR provides VAD and optional speaker diarization pipelines. A self-hosted service would let mobile devices upload recordings for transcription while keeping the model and compute off the phone. This is a promising candidate, not a verified accuracy winner for our own audio.

**Offline/mobile alternative: Voice Scribe**  
Voice Scribe is MIT-licensed and advertises on-device transcription on desktop and mobile. Its README says non-Russian mobile speech uses Whisper `base`, while larger Whisper models are desktop/GPU constrained. This is attractive for privacy/offline capture, but the mobile model-size limit means it should not be assumed to deliver the best Chinese accuracy.

## Candidate Obsidian plugins

| Project | License / maintainer | Recording | Transcription | Mobile evidence / caveats | Assessment |
|---|---|---|---|---|---|
| [Advanced Audio Recorder](https://github.com/akhmialeuski/advanced-audio-recorder) | MIT; akhmialeuski | Yes; pause/resume, recovery, waveform, bookmarks, chapters, formats | Whisper-compatible API, Deepgram, Gemini, local whisper.cpp | Upstream says desktop and mobile. Multi-track, auto-split, local whisper.cpp and input-device selection are desktop-only. Verify mobile recording and remote transcription on iOS/Android. | **Best first recorder candidate** |
| [Voice Scribe](https://github.com/mrrepac/voice-scribe) | MIT; mrrepac | Yes; voice-note recording and existing-audio transcription | On-device Whisper; no API key or cloud required | Upstream says mobile works offline, but uses Whisper `base` on phones for non-Russian languages due WebView memory constraints. Larger `large-v3-turbo` is desktop/GPU-only. | Best offline/privacy alternative; Chinese quality needs benchmark |
| [Whisper for Obsidian](https://github.com/nikdanilov60k/whisper-obsidian-plugin) | MIT; nikdanilov60k | Yes; record or upload audio | Whisper-compatible API (OpenAI, Groq, Azure, compatible endpoints) | Community listing says desktop and mobile. It is API-backed, so cost, network, data residency and provider behavior depend on the configured endpoint. | Simple dictation/transcription alternative |
| [AI Notes](https://github.com/derogab/obsidian-ai-notes) | GPL-3.0; derogab | Yes | whisper.cpp or OpenAI-compatible endpoint | Community listing currently says desktop only. | Do not select for the five-platform target without upstream mobile support |
| [LexVoice](https://github.com/Lynn-x/LexVoice) | **Proprietary license** in upstream README badge; Lynn-x | Yes; meeting recording, live outline, imports | User-configured transcription and AI services | Community listing says desktop/mobile workflows; verify exact platform feature parity. Not an open-source candidate under the current published license indicator. | Feature reference only; exclude from open-source shortlist unless license changes |

### Important license note

A repository being publicly visible on GitHub does not make it open source. LexVoice's README currently labels its license as Proprietary; do not treat it as an open-source dependency or redistribute its code without a clear permissive license. Re-check each upstream LICENSE file and release artifact before adding any plugin to a distributable catalogue.

## Candidate ASR engines

| Engine | What it offers | Fit for this project | Caveats |
|---|---|---|---|
| [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) / SenseVoiceSmall | Mandarin, Cantonese, English, Japanese and Korean ASR; language identification and audio-event/emotion tags | Strong Chinese-first candidate; can be served remotely for mobile clients | Upstream benchmark claims are not our own test. Check model-weight terms separately from source-code license and verify deployment/runtime support |
| [FunASR](https://github.com/modelscope/FunASR) | ASR toolkit and pipelines including VAD, punctuation and optional speaker diarization | Useful server-side orchestration for long recordings and meeting transcription | More operational complexity; diarization requires additional models and should be tested independently |
| [Whisper](https://github.com/openai/whisper) / whisper.cpp | Broad multilingual recognition; whisper.cpp offers local inference | Strong baseline and fallback; local desktop mode and server mode are possible | Large models need substantial memory/compute; mobile offline model size is constrained |

Do not compare headline WER/CER numbers across unrelated datasets as if they were directly comparable. Accuracy depends on language, accents, noise, microphone, domain vocabulary, segmentation and model size.

## Recommended architecture

1. **Capture layer:** integrate or recommend Advanced Audio Recorder first; preserve the original audio file in the user's vault.
2. **Transcription provider interface:** keep provider configuration independent from the recorder. Support a user-configured OpenAI-compatible endpoint and a documented local/server endpoint.
3. **Chinese-first server option:** evaluate SenseVoiceSmall through FunASR with VAD and punctuation. Optionally evaluate Whisper large-v3 / large-v3-turbo as a baseline.
4. **Mobile path:** iPhone, iPad and Android record locally, then send audio only after explicit user action to the configured transcription endpoint. Do not claim reliable iOS background transcription.
5. **Output:** create a Markdown transcript beside or linked from the recording, with source audio link, date, language, model/provider, timestamps when available, and optional speaker labels. Keep raw transcript separate from AI-cleaned summaries.
6. **Privacy:** show where audio is sent, never ship a shared API key, store user credentials using platform-appropriate secure storage where available, and support local-only mode when a compatible local runtime exists.
7. **Failure safety:** never delete the original recording when transcription fails; support retry and resumable chunk processing for long audio.

## Validation plan before implementation

Use the same consented test set for every candidate:

- Mandarin: quiet single-speaker dictation, conversational speech, technical/financial vocabulary, proper nouns and numbers.
- Cantonese: at least one natural conversation sample.
- Mixed Chinese/English: code-switching and English product names.
- Noisy environment: realistic phone recording with background noise.
- Long form: 30–60 minute meeting split into chunks, checking omissions and duplicated boundary text.
- Multiple speakers: evaluate speaker separation separately from word accuracy.

Record ground-truth transcripts and compare Chinese Character Error Rate (CER), proper-noun/number accuracy, omission rate, diarization quality, real-time factor, peak memory, upload time, and cost per audio hour. Do not publish a blanket “best accuracy” claim without this test.

## Proposed acceptance criteria

- Recording starts/stops reliably on Windows, macOS, iPhone, iPad and Android; pause/resume and interruption recovery are documented per platform.
- Original audio is saved in the vault before transcription begins.
- A failed/offline transcription never loses the recording and can be retried.
- At least two ASR backends can be configured without changing the recording workflow.
- Mandarin, Cantonese and mixed-language benchmark results are documented using the same test set.
- Provider/API keys are not committed, synced in shared policy, or logged.
- User is clearly told whether audio remains local or is uploaded to a third-party/self-hosted endpoint.
- Plugin license and mobile support are verified from upstream sources before being marked installable in the manager catalogue.

## Sources checked

- Advanced Audio Recorder README and mobile support: https://github.com/akhmialeuski/advanced-audio-recorder
- Voice Scribe README: https://github.com/mrrepac/voice-scribe
- Whisper Obsidian plugin: https://github.com/nikdanilov60k/whisper-obsidian-plugin
- AI Notes: https://github.com/derogab/obsidian-ai-notes
- LexVoice: https://github.com/Lynn-x/LexVoice
- SenseVoice: https://github.com/FunAudioLLM/SenseVoice
- FunASR: https://github.com/modelscope/FunASR
- Whisper: https://github.com/openai/whisper

---

**Status:** Research/design only. This PR does not bundle third-party plugin code, download model weights, add API credentials, or claim physical-device validation. Implementation should follow after the user approves the chosen recorder/provider architecture.
