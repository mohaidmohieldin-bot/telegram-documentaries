# Phase 2 — The Bouncer: validation

Merge when every box is ticked.

## Automated

- [x] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [x] Mocked tests cover every case listed in `plan.md` §1–6.
- [x] `scripts/test-live` passes with `GEMINI_API_KEY` set and both fixture images
      present: person → human, landscape/object → no human.

## Manual (on Telegram, bot running locally)

Items marked *(tests)* were accepted on mocked-test coverage instead of a hand check, at the user's request (2026-10-18).

- [x] Text before any photo → nudge to send a photo. *(tests)*
- [x] Landscape or object photo → cheeky rejection.
- [x] …and a following text gets the "send a photo" nudge again (state was reset). *(tests)*
- [x] Photo of a person → confirmation.
- [x] …and a following text gets the "you're in" reply. *(tests)*
- [x] Photo of a person sent as a file (uncompressed) → confirmation. *(tests)*
- [x] *(tests)* Logs show `stage=bouncer` start/done with `duration_ms` and the verdict, and
      never the bot token, API key or image bytes.

## Contract and policy checks

- [x] `gateway.py` is still the only module importing `telegram`.
- [x] No raw dicts cross module boundaries: `ImageInput`, `BouncerVerdict`,
      `Session`, `Settings` at every edge.
- [x] No bare `except`, no swallowed exceptions, every fallback logged.
- [x] Missing `GEMINI_API_KEY` aborts startup with `config_invalid`.
- [x] `tests/live/fixtures/` is git-ignored and contains no committed images.

## Spec drift

- [x] Any difference between this spec and the implementation is listed in the PR
      and approved by the user; `SPECS/` updated accordingly.
