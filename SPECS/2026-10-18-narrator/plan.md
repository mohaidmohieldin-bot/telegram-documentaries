# Phase 6 — The Narrator: plan

Red/Green TDD for every group (`write-tests` skill); checks only via `scripts/`.

## 1. Constitution

1. Update TECH.md (Narrator row and architecture line) and ROADMAP.md Phase 6 for
   `gemini-3.8-flash-tts` and WAV-as-file. Done with this spec, user-approved.

## 2. Audio contract

1. Tests: a real WAV built with `wave` is accepted with the right `duration_s`; non-RIFF
   bytes, empty bytes, a zero-length WAV and a WAV over 120 s are rejected; `repr` hides
   the bytes.
2. Implement `VoiceoverAudio` in `media.py`.

## 3. Narrator and TTS adapter

1. Tests:
   - `GeminiTts` with a fake client: the request carries model, text, style annotation,
     WAV response format and voice; base64 audio is decoded; missing audio raises
     `NarratorError`.
   - `Narrator` with a fake synthesizer: the request uses `gemini-3.8-flash-tts`,
     `Enceladus`, a style containing "hushed" and "reverent", and the script text; valid
     audio is returned; invalid audio, exceptions and timeouts raise `NarratorError`.
2. Implement `narrator.py` (`TtsRequest`, `GeminiTts`, `Narrator`, `NarratorError`,
   `create_narrator`).

## 4. Session v5

1. Tests: `finish` only from `SCRIPT_READY`; `start_interview` from `DONE`; `handoff()` in
   `DONE`; `schema_version == 5`.
2. Implement in `session.py`.

## 5. Gateway

1. Tests: a full run ends with script → voiceover file (caption, filename, timeouts) →
   "that's a wrap", phase `DONE`, logged; Narrator failure → friendly reply, phase stays
   `SCRIPT_READY`; text in `SCRIPT_READY` retries only the voiceover; text in `DONE` →
   wrap reply; a photo in `DONE` → fresh interview.
2. Implement in `gateway.py`; wire `create_narrator()` in `__main__.py`.

## 6. Live test, docs, verification

1. `tests/live/test_narrator_live.py` saves `tests/live/output/voiceover.wav`.
2. README update. `scripts/hooks --run`, `scripts/test-live` (listen to the WAV), and a
   full run on Telegram.
3. Walk `validation.md`; mark Phase 6 `[x]` once verified.
