# Phase 7 — Resilience: validation

Merge when every box is ticked.

## Automated

- [ ] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [ ] Matrix tests: every phase × every input kind, plus `/start` and `/restart` from
      every phase.
- [ ] `scripts/test-live` passes; the new portrait shows exactly one hybrid figure.

## Manual (on Telegram, bot running locally)

- [ ] The "/" menu lists `/start` and `/restart`.
- [ ] `/restart` mid-interview → "Clean slate!"; the next text gets the photo nudge.
- [ ] `/start` after the wrap → welcome; a selfie starts a fresh interview.

## Contract and policy checks

- [ ] Every Gemini and Telegram media call has an explicit timeout.
- [ ] No files are written to disk; reset drops all media.
- [ ] Unexpected errors are logged loudly and the user gets a friendly reply.
- [ ] No bare `except`, no swallowed exceptions, every fallback logged.

## Spec drift

- [ ] Any difference between spec and implementation is listed in the PR and approved;
      `SPECS/` updated accordingly.
