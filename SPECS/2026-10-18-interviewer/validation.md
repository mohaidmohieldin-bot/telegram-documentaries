# Phase 3 — The Interviewer: validation

Merge when every box is ticked.

## Automated

- [x] `scripts/hooks --run` passes (ruff, mypy strict, pytest).
- [x] Mocked tests cover every case in `plan.md` §1–4; Bouncer tests unchanged and green.
- [x] `scripts/test-live` passes: Bouncer live tests plus a full scripted interview that
      ends within 5–7 questions with a valid `Dossier`.

## Manual (on Telegram, bot running locally)

Items marked *(tests)* were accepted on mocked-test coverage instead of a hand check, at the user's request (2026-10-18).

- [x] Selfie → acceptance, then `🎙️ Question 1`.
- [x] Each answer gets exactly one new question; 5–7 questions in total.
- [x] A photo sent mid-interview → nudge repeating the current question.
- [x] After the last answer → profile, quirks and animal, then "portrait is being
      developed".
- [x] Text afterwards → "being developed" reply; a new selfie starts a fresh interview.
- [x] *(tests)* Logs show `stage=interviewer_question` / `stage=interviewer_profile` with
      durations, and `event=interview_handoff_ready` with the animal.

## Contract and policy checks

- [x] `gateway.py` is still the only module importing `telegram`.
- [x] Session state only changes through `SessionStore` transitions; wrong-phase
      transitions raise `InvalidTransition`.
- [x] Question bounds (5–7) are enforced in code, not trusted to the model.
- [x] User answers are passed to Gemini as quoted data, with an injection warning.
- [x] No bare `except`, no swallowed exceptions, every fallback logged.

## Spec drift

- [x] Any difference between this spec and the implementation is listed in the PR and
      approved by the user; `SPECS/` updated accordingly.
