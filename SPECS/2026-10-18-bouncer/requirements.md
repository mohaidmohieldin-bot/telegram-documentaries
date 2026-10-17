# Phase 2 — The Bouncer: requirements

Roadmap phase 2 (`SPECS/ROADMAP.md`). Serves the **rejection** success criterion
in `SPECS/MISSION.md`.

## Goal

When a user sends a photo, a Google ADK vision agent backed by Gemini 3.1
Flash-Lite decides whether a discernible human face or body is present.

- **No human:** reset the user's session and reply with a cheeky rejection
  explaining the photo must contain a human.
- **Human:** move the session to `PHOTO_ACCEPTED` and reply with a short
  confirmation. (The Interviewer takes over from here in Phase 3.)

## Decisions (confirmed with the user, 2026-10-18)

| Topic | Decision |
| --- | --- |
| Base | PR #1 merged; work on `feature/2026-10-18-bouncer` from `main` |
| Human found | Short confirmation reply; session phase becomes `PHOTO_ACCEPTED` |
| Text instead of photo | Friendly nudge to send a photo; no model call |
| Verification | Mocked unit tests always run; opt-in live test calls real Gemini with a person image and a landscape/object image |

## Scope

### In scope

1. **Session store** (first version of the shared state driver from TECH.md).
   In memory, keyed by integer `chat_id`, versioned Pydantic schema
   (`schema_version: 1`), phases `AWAITING_PHOTO` (default) and `PHOTO_ACCEPTED`.
   Operations: get (creating the default), set phase, reset.
2. **Image contract** `ImageInput`: non-empty bytes, at most 20 MB, MIME type one
   of `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif`
   (the image types Gemini accepts).
3. **Bouncer agent** (ADK `LlmAgent`):
   - model `gemini-3.1-flash-lite`;
   - instruction: decide whether a real, discernible human face or body is
     present (drawings, statues, toys and pets count as no human);
   - `output_schema = BouncerVerdict` with `human_present: bool` and a short
     `reason: str` (≤ 300 chars, logged, never shown to the user).
   - Run through an ADK `Runner` with an `InMemorySessionService`. Each check uses
     a fresh, throwaway ADK session that is deleted afterwards (the Bouncer is
     stateless; our own session store is the source of truth).
   - Timeout 30 s. Any failure (timeout, API error, missing or invalid model
     output) raises a single `BouncerError`.
4. **Gateway routing** (`gateway.py` stays the only module importing `telegram`):
   - Photos and image documents (an image sent "as a file") go to the photo
     handler: download the largest photo size as bytes, validate as `ImageInput`,
     call the Bouncer, then reject/accept as above.
   - Any other new message is answered by phase: `AWAITING_PHOTO` → nudge to send
     a photo; `PHOTO_ACCEPTED` → "you're in, interview coming soon; send another
     photo to start over".
   - A new photo always re-runs the Bouncer, whatever the phase.
5. **Graceful degradation** on the user path (TECH.md error policy), each logged
   loudly and answered with a friendly reply, with no state change:
   - Bouncer failure (`BouncerError`);
   - photo larger than 20 MB (checked before downloading);
   - unsupported image type (e.g. GIF sent as a file);
   - Telegram download failure.
6. **Configuration:** `GEMINI_API_KEY` becomes required (missing, empty or the
   `.env.example` placeholder fails startup with `config_invalid`). At startup it
   is exported to the process as `GOOGLE_API_KEY`, which is where the ADK/google-genai
   client reads it.
7. **Logging:** a reusable `logged_stage` decorator logs each pipeline stage's
   start, duration, outcome and errors, so stage code holds no logging calls.
   The Bouncer's verdict (`human_present`, `reason`) is logged per check, with
   `chat_id`. Image bytes are never logged.
8. **Tests:** Red/Green TDD. Mocked tests for all of the above. Opt-in live test
   (`scripts/test-live`, pytest marker `live`) that sends a person image and a
   landscape/object image to real Gemini; skipped when `GEMINI_API_KEY` or the
   images are missing. The images live in `tests/live/fixtures/`, which is
   git-ignored (a selfie must never land in the public repo).

### Out of scope

- The Interviewer and anything after `PHOTO_ACCEPTED` (Phase 3+).
- `/start` and `/restart` commands (Phase 7). For now they get the phase nudge.
- Storing the photo for the Converter (added in the phase that needs it).
- Retries, rate limiting, multiple-face handling.

## Contracts

| Boundary | Contract | On violation |
| --- | --- | --- |
| Telegram photo → bytes | `ImageInput` | friendly reply, logged, no state change |
| Gemini → verdict | `BouncerVerdict` (JSON, validated) | `BouncerError` → friendly reply |
| Session state | `Session` (frozen, `schema_version: Literal[1]`, `chat_id: int`, `phase: Phase`) | programming error, fails loudly |
| Settings | `Settings` with `telegram_bot_token`, `gemini_api_key` | startup aborted with `config_invalid` |

## Backward compatibility

None kept. The Phase 1 "hey mate!" reply is removed; every message is now
answered according to the session phase.
