# Phase 4 — The Converter: validation

Merge when every box is ticked.

## Automated

- [ ] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [ ] Mocked tests cover `plan.md` §1–4; earlier stages' tests unchanged and green.
- [ ] `scripts/test-live` passes, and `tests/live/output/portrait.*` is a recognisable
      hybrid of the person in `person.jpg`.

## Manual (on Telegram, bot running locally)

- [ ] Selfie → interview → field notes ending "Developing your hybrid portrait now…".
- [ ] A hybrid portrait arrives as a photo, captioned `📸 Exhibit A: Homo sapiens × <animal>`,
      followed by "narration coming soon".
- [ ] Text afterwards → "narration coming soon" reply; a new selfie starts over.
- [ ] Logs show `stage=converter` with `duration_ms` and `event=portrait_delivered`.

## Contract and policy checks

- [ ] `gateway.py` is still the only module importing `telegram`.
- [ ] Portrait bytes travel as `PortraitImage` and never appear in logs.
- [ ] A Converter failure keeps the interview results and lets any message retry.
- [ ] The Dossier is passed to Gemini as quoted data, with an injection warning.
- [ ] `tests/live/output/` is git-ignored.

## Spec drift

- [ ] Any difference between spec and implementation is listed in the PR and approved;
      `SPECS/` updated accordingly.
