# Phase 6 — The Narrator: requirements

Roadmap phase 6 (`SPECS/ROADMAP.md`). Completes the **happy path** success criterion:
photo → Bouncer → interview → portrait → script → **voiceover**.

## Goal

After the script is sent, the Narrator (a plain function, not an agent, per TECH.md)
turns it into speech with Gemini TTS in a hushed, reverent delivery, and sends the
audio to the chat. The session then moves to `DONE`.

## Decisions (confirmed with the user, 2026-10-18)

| Topic | Decision |
| --- | --- |
| TTS model | `gemini-3.8-flash-tts` (current, built for narration). **Constitution change:** TECH.md and ROADMAP.md previously named `gemini-3.1-flash-tts-preview`, now a legacy preview |
| Format | WAV (24 kHz mono 16-bit, as returned by Gemini) sent as a **file** (`voiceover.wav`); no ffmpeg/OGG. Telegram's audio message type expects MP3/M4A, so a document is the reliable way to send WAV; it plays when tapped |
| Voice | Prebuilt voice `Enceladus` (described by Google as breathy) with a hushed, reverent style hint. A British accent is not guaranteed |
| Script text | Kept: the text script message, then the voiceover file |

## API (per Google's speech-generation docs, 2026-10-18)

`client.interactions.create(model=…, input=[{"type": "user_input", "content": [{"type":
"text", "text": …, "annotations": [{"type": "speech_metadata", "style": …}]}]}],
response_format={"type": "audio", "mime_type": "audio/wav"},
generation_config={"speech_config": [{"voice": …}]})`. The audio is base64 in
`interaction.output_audio.data`. The call is synchronous, so it runs in a worker thread
(`asyncio.to_thread`) to keep the bot responsive.

## Scope

### In scope

1. **Contract `VoiceoverAudio`** (`media.py`): bytes with a RIFF/WAVE header that the
   stdlib `wave` module can parse, between 1 and 120 seconds long, and at most 20 MB.
   Exposes `duration_s`. Bytes never appear in `repr` or logs.
2. **`TtsRequest`** (model, voice, style, text) is the typed boundary to the TTS adapter.
3. **`GeminiTts`**: the adapter. It builds the Interactions request above, decodes the
   base64 audio, and raises `NarratorError` when no audio comes back.
4. **`Narrator`**: `narrate(script) -> VoiceoverAudio`, with a 60 s timeout. Every failure
   (timeout, API error, missing or invalid audio) raises `NarratorError`. It is decorated
   with `logged_stage("narrator")`.
5. **Session schema v5.** New phase `DONE`. Transition `finish(chat_id)` is allowed only
   from `SCRIPT_READY`. `start_interview` is also allowed from `DONE`, and `handoff()` works
   there. Nothing is written to disk, so the roadmap's "temp media cleanup" needs no code:
   all media lives in memory and is dropped on reset or on a new interview.
6. **Gateway:**
   - After the script message: narrate, then `reply_document(voiceover.wav, caption
     "🎧 Your documentary voiceover")` with the 60 s upload timeouts, then `finish`, then
     "🎬 That's a wrap on your documentary! Send a new photo any time…". Logged as
     `event=voiceover_delivered` with the `chat_id` and seconds.
   - On `NarratorError`: "The narrator's microphone crackled… send any message to try
     again". The phase stays `SCRIPT_READY`, and nothing is re-sent.
   - Text in `SCRIPT_READY` → "Back in the recording booth…", then a retry of the voiceover.
   - Text in `DONE` → the "that's a wrap" reply. A photo in `DONE` → Bouncer → fresh
     interview.
7. **Tests:** Red/Green TDD with mocks, including the adapter against a fake client. An
   opt-in live test synthesizes a fixed script and saves `tests/live/output/voiceover.wav`
   for listening.

### Out of scope

- OGG/Opus voice notes, ffmpeg, British voice-library voices, voice choice per user.
- `/start` and `/restart` (Phase 7).

## Backward compatibility

None kept: session v4 and `VOICEOVER_COMING_SOON` are replaced.
