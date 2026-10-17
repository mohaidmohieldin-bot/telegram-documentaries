# Phase 5 — The Scripter: validation

Merge when every box is ticked.

## Automated

- [x] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [x] Mocked tests cover `plan.md` §1–4; earlier stages' tests green.
- [x] `scripts/test-live` passes, including a live script that is one paragraph of
      60–90 words.

## Manual (on Telegram, bot running locally)

Items marked *(tests)* were accepted on mocked-test coverage instead of a hand check, at the user's request (2026-10-18).

- [x] Full run: portrait, then "📜 From the narrator's script:" with a hushed, reverent
      paragraph that names the animal and mentions something from the answers.
- [x] Then "voiceover … coming soon"; *(tests)* text afterwards gets the same reply.
- [x] *(tests)* Logs show `stage=scripter` with `duration_ms` and `event=script_ready words=…`.

## Contract and policy checks

- [x] The script is validated by `NarrationScript` (60–90 words, one paragraph) in code.
- [x] Exactly one automatic retry on a word-range miss; none on API failure.
- [x] A Scripter failure never re-sends the portrait; any message retries the script.
- [x] Answers and Dossier are passed as quoted data, with an injection warning.
- [x] The narrator is original: no real presenter is named or imitated.

## Spec drift

- [x] Any difference between spec and implementation is listed in the PR and approved;
      `SPECS/` updated accordingly.
