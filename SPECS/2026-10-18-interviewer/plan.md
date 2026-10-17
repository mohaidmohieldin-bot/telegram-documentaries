# Phase 3 — The Interviewer: plan

Red/Green TDD: tests first for every group (`write-tests` skill), confirm they fail for
the right reason, then implement. Checks only through `scripts/` (see README).

## 1. Shared ADK caller

1. Tests (fake runner): structured JSON is parsed into the given schema; error events,
   missing final response, empty content, runner exceptions, timeouts and invalid JSON
   each raise the caller-supplied error type with a useful message; the throwaway ADK
   session is deleted every time.
2. Implement `agents.py` (`AgentCallError`, `run_structured_agent`).
3. Refactor `bouncer.py` onto it (`BouncerError` subclasses `AgentCallError`); all
   existing Bouncer tests must stay green unchanged.

## 2. Contracts and session v2

1. Tests: `QA`, `NextQuestion`, `Dossier` bounds; session defaults; each transition from
   the right phase; `InvalidTransition` from the wrong one; `reset` clears photo,
   transcript and dossier; `handoff()` only when complete; chats are isolated.
2. Implement in `session.py` (QA, Dossier, InterviewHandoff, Session v2, store
   transitions) and `interviewer.py` (NextQuestion).

## 3. Interviewer orchestrator

1. Tests (fake runners):
   - agents use `gemini-3.1-flash-lite` with `NextQuestion` / `Dossier` schemas;
   - first question comes from the question writer;
   - fewer than 5 answers → asks even if the model says `enough_information`;
   - 5–6 answers + `enough_information` → profiler is called and the `Dossier` returned;
   - 5–6 answers without it → asks;
   - 7 answers → profiler, without calling the question writer;
   - the transcript is sent as quoted data, and the instruction warns against
     instructions inside answers;
   - failures raise `InterviewerError`.
2. Implement `interviewer.py` (`Interviewer`, `build_*_agent`, `create_interviewer`).

## 4. Gateway wiring

1. Tests (fake Telegram, fake Bouncer, fake Interviewer):
   - human photo → acceptance + `Question 1`, phase `INTERVIEWING`, photo stored;
   - first-question failure → friendly reply, still `AWAITING_PHOTO`;
   - answer → recorded, `Question N+1` sent;
   - final answer → finale with profile, quirks and animal, phase `INTERVIEW_COMPLETE`,
     `handoff()` holds photo and dossier, handoff logged;
   - full 5-question run across separate messages resumes correctly;
   - mid-interview photo, sticker, command, empty and over-long answer → nudge
     repeating the current question, no state change, Interviewer not called;
   - Interviewer failure mid-interview → friendly reply, answer not recorded, a retry
     of the same answer works;
   - text after completion → "being developed" reply; new photo after completion
     restarts;
   - no-human photo still resets; chats are isolated.
2. Implement in `gateway.py`; wire `create_interviewer()` in `__main__.py`.

## 5. Live verification (opt-in)

1. `tests/live/test_interviewer_live.py`: real Gemini, scripted answers; finishes within
   5–7 questions with a valid `Dossier` and a non-empty animal.

## 6. Docs and verification

1. README: what the bot does now, layout.
2. `scripts/hooks --run`, `scripts/test-live`, a manual interview on Telegram.
3. Walk `validation.md`; mark Phase 3 `[x]` only once verified.
