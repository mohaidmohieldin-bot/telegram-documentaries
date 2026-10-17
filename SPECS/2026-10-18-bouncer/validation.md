# Phase 2 — The Bouncer: validation

Merge when every box is ticked.

## Automated

- [ ] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [ ] Mocked tests cover every case listed in `plan.md` §1–6.
- [ ] `scripts/test-live` passes with `GEMINI_API_KEY` set and both fixture images
      present: person → human, landscape/object → no human.

## Manual (on Telegram, bot running locally)

- [ ] Text before any photo → nudge to send a photo.
- [ ] Landscape or object photo → cheeky rejection; a following text gets the
      "send a photo" nudge again (state was reset).
- [ ] Photo of a person → confirmation; a following text gets the "you're in" reply.
- [ ] Photo of a person sent as a file (uncompressed) → confirmation.
- [ ] Logs show `stage=bouncer` start/done with `duration_ms` and the verdict, and
      never the bot token, API key or image bytes.

## Contract and policy checks

- [ ] `gateway.py` is still the only module importing `telegram`.
- [ ] No raw dicts cross module boundaries: `ImageInput`, `BouncerVerdict`,
      `Session`, `Settings` at every edge.
- [ ] No bare `except`, no swallowed exceptions, every fallback logged.
- [ ] Missing `GEMINI_API_KEY` aborts startup with `config_invalid`.
- [ ] `tests/live/fixtures/` is git-ignored and contains no committed images.

## Spec drift

- [ ] Any difference between this spec and the implementation is listed in the PR
      and approved by the user; `SPECS/` updated accordingly.
