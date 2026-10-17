# Phase 6 — The Narrator: validation

Merge when every box is ticked.

## Automated

- [x] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [x] Mocked tests cover `plan.md` §2–5; earlier stages' tests green.
- [x] `scripts/test-live` passes, and `tests/live/output/voiceover.wav` plays as a hushed,
      reverent narration of the test script.

## Manual (on Telegram, bot running locally)

Items marked *(tests)* were accepted on mocked-test coverage instead of a hand check, at the user's request (2026-10-18).

- [x] Full run: portrait → script text → `voiceover.wav` file that plays when tapped →
      "That's a wrap on your documentary!".
- [x] *(tests)* Text afterwards → the wrap reply; a new selfie starts over.
- [x] *(tests)* Logs show `stage=narrator` with `duration_ms` and `event=voiceover_delivered`.

## Contract and policy checks

- [x] `gateway.py` is still the only module importing `telegram`.
- [x] The Narrator is a plain function or class, not an ADK agent (TECH.md).
- [x] Audio travels as `VoiceoverAudio` (validated WAV) and never appears in logs.
- [x] A Narrator failure keeps the portrait and script, and lets any message retry.
- [x] TECH.md and ROADMAP.md reflect `gemini-3.8-flash-tts` and the WAV file.

## Spec drift

- [x] Any difference between spec and implementation is listed in the PR and approved;
      `SPECS/` updated accordingly.
