# Phase 3 — The Interviewer: requirements

Roadmap phase 3 (`SPECS/ROADMAP.md`). Serves the **happy path** success criterion
in `SPECS/MISSION.md`.

## Goal

Once the Bouncer accepts a photo, an ADK interviewer driven by Gemini 3.1 Flash-Lite
asks 5–7 investigative, playful, slightly eccentric questions, **exactly one per
turn**, waiting for each answer. After the final answer it synthesizes a concise
behavioural profile (quirks and habits) with a clear suggested animal, shows it to the
user, and stores it with the photo as the handoff for the next stage (the Converter).
The interview resumes correctly across Telegram messages because all state lives in
the per-`chat_id` session.

## Decisions (confirmed with the user, 2026-10-18)

| Topic | Decision |
| --- | --- |
| Question generation | Adaptive: Gemini writes each next question from the answers so far and says when it has enough; code enforces 5 ≤ questions ≤ 7 |
| Finale | Show the profile, quirks and animal, then "your portrait is being developed" |
| Photo mid-interview | Nudge to answer the current question; interview continues |
| Handoff | Session keeps the accepted photo, the profile and the animal for the Converter |

## Scope

### In scope

1. **Session schema v2** (no backward compatibility: in-memory only).
   - Phases: `AWAITING_PHOTO` → `INTERVIEWING` → `INTERVIEW_COMPLETE`.
     `PHOTO_ACCEPTED` is removed.
   - Fields: `photo: ImageInput | None`, `transcript: tuple[QA, ...]`,
     `pending_question: str | None`, `dossier: Dossier | None`.
   - `SessionStore` stays the single driver, with explicit transitions:
     `start_interview(photo, first_question)`, `record_answer(answer, next_question)`,
     `complete_interview(answer, dossier)`, `reset`. A transition from the wrong phase
     raises `InvalidTransition` (fail loud: it is a programming error).
   - `Session.handoff()` returns an `InterviewHandoff(photo, dossier)` for the next stage,
     and raises `InvalidTransition` if the interview is not complete.
2. **Contracts:**
   - `QA`: `question` 1–300 chars, `answer` 1–1000 chars (whitespace stripped).
   - `NextQuestion` (model output): `question` 1–300 chars, `enough_information: bool`.
   - `Dossier` (model output): `profile` 1–800 chars, `quirks` 2–5 items of 1–150 chars,
     `suggested_animal` 1–40 chars, `animal_rationale` 1–300 chars.
3. **Interviewer** (`interviewer.py`), the orchestrator named in TECH.md:
   - Two ADK `LlmAgent`s on `gemini-3.1-flash-lite`, both with structured output:
     a *question writer* (`NextQuestion`) and a *profiler* (`Dossier`).
   - `first_question()` and `next_step(transcript)`, where `next_step` returns either a
     `NextQuestion` or a `Dossier`.
   - Bounds are decided by code, not the model: below 5 answers → always ask; at 7
     answers → always profile; at 5–6 → profile if the model says
     `enough_information`, else ask.
   - User answers are untrusted: they are passed to the model as quoted data, and both
     instructions say to ignore any instructions inside them.
   - Timeout 30 s per call; every failure raises `InterviewerError`.
4. **Shared ADK caller** (`agents.py`): the throwaway-session, error-event, timeout and
   structured-output logic from the Bouncer moves into one helper used by both stages
   (removes duplication; Bouncer behaviour and tests unchanged).
5. **Gateway:**
   - Human photo while `AWAITING_PHOTO` or `INTERVIEW_COMPLETE` → acceptance message,
     then the first question (`🎙️ Question 1: …`).
   - Text while `INTERVIEWING` → the answer. The next question is sent as
     `🎙️ Question N: …`, or the finale when the interview is done.
   - While `INTERVIEWING`: a photo, any other non-text message, a command (`/…`), an
     empty answer, or an answer over 1000 characters → a friendly nudge that repeats the
     current question. No state change.
   - Text while `INTERVIEW_COMPLETE` → "portrait is being developed; send a new photo
     to start again".
   - Interviewer failure → friendly "send your answer again" reply; the answer is
     **not** recorded, so the same turn simply resumes. If the failure happens on the
     first question, the session stays `AWAITING_PHOTO` and the user is asked to resend
     the photo.
   - The finale logs `event=interview_handoff_ready` with `chat_id` and the animal.
6. **Logging:** `logged_stage` on both interviewer calls; each turn logs `chat_id`,
   question number and outcome. Answers and profiles are not logged in full.
7. **Tests:** Red/Green TDD. Mocked tests for everything above; opt-in live test runs a
   full interview with scripted answers against real Gemini.

### Out of scope

- The Converter itself (Phase 4) and anything after it.
- `/start` and `/restart` (Phase 7). Mid-interview commands get the nudge.
- Editing a previous answer, skipping questions, interview timeouts.
- Concurrency control per chat: python-telegram-bot processes updates sequentially by
  default (`concurrent_updates=False`), so turns in one chat cannot interleave.

## Backward compatibility

None kept: `PHOTO_ACCEPTED`, `ALREADY_ACCEPTED` and the old "interview begins soon"
wording are replaced.
