# Phase 5 — The Scripter: validation

Merge when every box is ticked.

## Automated

- [ ] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [ ] Mocked tests cover `plan.md` §1–4; earlier stages' tests green.
- [ ] `scripts/test-live` passes, including a live script that is one paragraph of
      60–90 words.

## Manual (on Telegram, bot running locally)

- [ ] Full run: portrait, then "📜 From the narrator's script:" with a hushed, reverent
      paragraph that names the animal and mentions something from the answers.
- [ ] Then "voiceover … coming soon"; text afterwards gets the same reply.
- [ ] Logs show `stage=scripter` with `duration_ms` and `event=script_ready words=…`.

## Contract and policy checks

- [ ] The script is validated by `NarrationScript` (60–90 words, one paragraph) in code.
- [ ] Exactly one automatic retry on a word-range miss; none on API failure.
- [ ] A Scripter failure never re-sends the portrait; any message retries the script.
- [ ] Answers and Dossier are passed as quoted data, with an injection warning.
- [ ] The narrator is original: no real presenter is named or imitated.

## Spec drift

- [ ] Any difference between spec and implementation is listed in the PR and approved;
      `SPECS/` updated accordingly.
