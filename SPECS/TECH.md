# TECH — Technical contract

Part of the project constitution (with `MISSION.md` and `ROADMAP.md`). Agents
enforce these policies; changes require updating this file first.

## Stack

| Concern | Choice |
| --- | --- |
| Language | Python 3.12+ |
| Dependencies / env | `uv` with `pyproject.toml` and a committed `uv.lock` |
| Telegram transport | `python-telegram-bot` (async), **long polling** only |
| Agent framework | Google Agent Development Kit (ADK) |
| Bouncer, Interviewer, Scripter | Gemini 3.1 Flash Lite |
| Converter | Gemini 3.1 Flash Image (native multimodal: photo + dossier → image) |
| Narrator | Gemini TTS `gemini-3.8-flash-tts` (Interactions API) → WAV, sent as a file |
| Validation | Pydantic v2 |
| Tests / lint / types | pytest, ruff, mypy (strict) |

## Architecture

- **Hub-and-spoke in ADK.** The Interviewer is the orchestrator and routes to the
  other stages. Each stage is a discrete agent/module with a single job:
  - Bouncer — vision classification only (human present or not). No TTS, no video.
  - Interviewer — sequential Q&A (5–7 questions), dossier, suggested animal.
  - Converter — returns the hybrid image straight to Telegram, with no
    intermediate text hop.
  - Scripter — one paragraph, ~60–90 words.
  - Narrator — plain function, not an agent: script → TTS → WAV voiceover file.
- **Explicit state machine.** Each session has one phase (e.g.
  `AWAITING_PHOTO`, `INTERVIEWING`, `CONVERTING`, `SCRIPTING`, `NARRATING`,
  `DONE`). Every incoming update is dispatched by phase; each phase declares the
  input types it accepts. Anything else gets a friendly nudge and no state change.
- **Telegram adapter at the edge.** Only the gateway module talks to
  `python-telegram-bot`; pipeline modules receive and return typed models.

## Contracts at boundaries

- Parse Telegram updates, Gemini responses and TTS output into Pydantic models
  at the edge. Never pass raw dicts or unvalidated payloads across module
  boundaries.
- Treat all external input as untrusted and arbitrary: user text, images, and
  model output (including malformed or empty model responses).
- Prefer structured model output (response schemas) over regex parsing.

## Session state

- In-memory store keyed by `chat_id`, behind a single shared state driver. No
  module mutates session state directly.
- The session schema is a versioned Pydantic model (`schema_version` field).
- `/start` and `/restart` purge the session and its temporary media files, in any
  phase, without restarting the process.
- Temporary media lives in a per-`chat_id` temp directory, removed on reset and on
  pipeline completion.
- Sessions never share data; concurrent chats are isolated.

## Logging and error policy

- Structured logging (JSON-friendly key/values, always including `chat_id` and
  phase where known). Prefer decorators/context managers over logging calls
  mixed into business logic.
- **Non-critical, user-invisible work:** fail loudly and log.
- **A validated user's conversation path:** catch errors at the stage boundary,
  log them loudly with context, and reply with a graceful fallback so the user
  can continue or `/restart`. Never raise into the user's flow.
- External calls (Gemini, TTS, Telegram) have explicit timeouts; a timeout is
  handled as above.
- Forbidden: bare `except:`, `except ...: pass`, swallowed exceptions, and
  un-logged fallbacks.

## Testing

- **Red/Green TDD.** Write a failing test first, then the code that makes it
  pass.
- Unit tests mock Gemini, TTS and Telegram at the adapter boundary; no network in
  the default test run.
- Dev scripts in `scripts/` are the ground truth and are documented in the README:
  - `scripts/test` — run the test suite.
  - `scripts/lint` — ruff check and format check.
  - `scripts/typecheck` — mypy.
  - `scripts/hooks` — install git hooks that run the above before commit.
- A phase is complete only when `scripts/test`, `scripts/lint` and
  `scripts/typecheck` all pass.

## Repo hygiene

- `.env` is in `.gitignore`; `.env.example` lists every required variable with
  placeholder values only.
- Environment is reproducible from `uv sync` plus `.env`.
- No hypothetical features or "just in case" configuration (YAGNI).

## README policy

The README must document, and be kept in sync with the code:

- What the bot does, in two or three sentences.
- Setup: prerequisites, `uv sync`, creating `.env` from `.env.example`.
- How to run the bot locally (long polling).
- The `scripts/` commands and what each does.
- The pipeline stages and the commands users can send (`/start`, `/restart`).
