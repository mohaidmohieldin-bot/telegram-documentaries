# Phase 7 — Resilience: validation

Merge when every box is ticked.

## Automated

- [x] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [x] Matrix tests: every phase × every input kind, plus `/start` and `/restart` from
      every phase.
- [x] `scripts/test-live` passes; the new portrait shows exactly one hybrid figure.

## Manual (on Telegram, bot running locally)

Items marked *(tests)* were accepted on mocked-test coverage instead of a hand check, at the user's request (2026-10-18). Live: the Menu button appeared, `/restart` after the wrap gave "Clean slate!", and `/start` gave the welcome.

- [x] The "/" menu lists `/start` and `/restart`.
- [x] *(tests)* `/restart` mid-interview → "Clean slate!"; the next text gets the photo nudge.
- [x] `/start` after the wrap → welcome; *(tests)* a selfie starts a fresh interview.

## Contract and policy checks

- [x] Every Gemini and Telegram media call has an explicit timeout.
- [x] No files are written to disk; reset drops all media.
- [x] Unexpected errors are logged loudly and the user gets a friendly reply.
- [x] No bare `except`, no swallowed exceptions, every fallback logged.

## Spec drift

- [x] Any difference between spec and implementation is listed in the PR and approved;
      `SPECS/` updated accordingly.
