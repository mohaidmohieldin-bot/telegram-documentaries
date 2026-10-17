# Phase 6 — The Narrator: validation

Merge when every box is ticked.

## Automated

- [ ] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [ ] Mocked tests cover `plan.md` §2–5; earlier stages' tests green.
- [ ] `scripts/test-live` passes, and `tests/live/output/voiceover.wav` plays as a hushed,
      reverent narration of the test script.

## Manual (on Telegram, bot running locally)

- [ ] Full run: portrait → script text → `voiceover.wav` file that plays when tapped →
      "That's a wrap on your documentary!".
- [ ] Text afterwards → the wrap reply; a new selfie starts over.
- [ ] Logs show `stage=narrator` with `duration_ms` and `event=voiceover_delivered`.

## Contract and policy checks

- [ ] `gateway.py` is still the only module importing `telegram`.
- [ ] The Narrator is a plain function or class, not an ADK agent (TECH.md).
- [ ] Audio travels as `VoiceoverAudio` (validated WAV) and never appears in logs.
- [ ] A Narrator failure keeps the portrait and script, and lets any message retry.
- [ ] TECH.md and ROADMAP.md reflect `gemini-3.8-flash-tts` and the WAV file.

## Spec drift

- [ ] Any difference between spec and implementation is listed in the PR and approved;
      `SPECS/` updated accordingly.
