# Phase 4 — The Converter: validation

Merge when every box is ticked.

## Automated

- [x] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [x] Mocked tests cover `plan.md` §1–4; earlier stages' tests unchanged and green.
- [x] `scripts/test-live` passes, and `tests/live/output/portrait.*` is a recognisable
      hybrid of the person in `person.jpg`.

## Manual (on Telegram, bot running locally)

Items marked *(tests)* were accepted on mocked-test coverage instead of a hand check, at the user's request (2026-10-18). The user also approved the upload-timeout addition.

- [x] Selfie → interview → field notes ending "Developing your hybrid portrait now…".
- [x] A hybrid portrait arrives as a photo, captioned `📸 Exhibit A: Homo sapiens × <animal>`,
      followed by "narration coming soon".
- [x] *(tests)* Text afterwards → "narration coming soon" reply; a new selfie starts over.
- [x] *(tests)* Logs show `stage=converter` with `duration_ms` and `event=portrait_delivered`.

## Contract and policy checks

- [x] `gateway.py` is still the only module importing `telegram`.
- [x] Portrait bytes travel as `PortraitImage` and never appear in logs.
- [x] A Converter failure keeps the interview results and lets any message retry.
- [x] The Dossier is passed to Gemini as quoted data, with an injection warning.
- [x] `tests/live/output/` is git-ignored.

## Spec drift

- [x] Any difference between spec and implementation is listed in the PR and approved;
      `SPECS/` updated accordingly.
