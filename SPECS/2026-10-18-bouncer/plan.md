# Phase 2 — The Bouncer: plan

Red/Green TDD throughout: for every task group, write the tests first (following
the `write-tests` skill), confirm they fail for the right reason, then implement.
Run checks only through the dev scripts in `scripts/` (see README):
`scripts/test`, `scripts/lint`, `scripts/typecheck`, `scripts/hooks --run`.

## 1. Dependencies and configuration

1. Add `google-adk` to `pyproject.toml`; register the `live` pytest marker and
   exclude it from the default run; add `scripts/test-live`.
2. Tests: `GEMINI_API_KEY` required, placeholder/empty rejected, hidden in repr;
   `export_gemini_credentials` sets `GOOGLE_API_KEY`.
3. Implement in `config.py`.

## 2. Logging decorator

1. Tests: `logged_stage` logs start and success with `duration_ms`; on error it
   logs `stage_failed` with the error and re-raises the same exception.
2. Implement in `logging_setup.py`.

## 3. Session store

1. Tests: default session is `AWAITING_PHOTO` with `schema_version == 1`;
   `set_phase` persists; `reset` returns to default (also for unknown chats);
   two chats are isolated; sessions are immutable.
2. Implement `session.py`.

## 4. Image contract

1. Tests: valid JPEG/PNG accepted; empty bytes, > 20 MB, and unsupported MIME
   types rejected.
2. Implement `media.py`.

## 5. Bouncer agent

1. Tests (fake ADK runner, no network):
   - agent uses `gemini-3.1-flash-lite` and `output_schema=BouncerVerdict`;
   - the image bytes and MIME type are sent as the user message;
   - human / no-human JSON is parsed into `BouncerVerdict`;
   - invalid JSON, no final response, runner exception and timeout each raise
     `BouncerError`;
   - the throwaway ADK session is deleted on success and on failure.
2. Implement `bouncer.py` (`BouncerVerdict`, `BouncerError`, `Bouncer` protocol,
   `AdkBouncer`, `build_bouncer_agent`, `create_bouncer`).

## 6. Gateway wiring

1. Tests (fake Telegram objects, fake Bouncer):
   - text while `AWAITING_PHOTO` → nudge, Bouncer not called;
   - person photo → confirmation, phase `PHOTO_ACCEPTED`, Bouncer got the
     downloaded bytes;
   - landscape/object photo → cheeky rejection, session reset (also from
     `PHOTO_ACCEPTED`);
   - PNG sent as a document → checked with `image/png`;
   - GIF document → unsupported-type reply, Bouncer not called;
   - photo over 20 MB → too-large reply, no download, Bouncer not called;
   - Telegram download failure → friendly reply, no state change;
   - `BouncerError` → friendly reply, no state change;
   - text while `PHOTO_ACCEPTED` → "you're in" reply;
   - chats are isolated;
   - routing: photo and image-document updates reach the photo handler, text
     reaches the other handler, edited messages are ignored, error handler set.
2. Implement in `gateway.py`; wire `Settings`, `SessionStore` and the Bouncer in
   `__main__.py`.

## 7. Live verification (opt-in)

1. `tests/live/test_bouncer_live.py`: person image → `human_present is True`;
   landscape/object image → `False`. Skips with a clear reason if the key or an
   image is missing. Git-ignore `tests/live/fixtures/`.

## 8. Docs and verification

1. Update README (setup, `GEMINI_API_KEY`, `scripts/test-live`, what the bot does
   now).
2. Run `scripts/hooks --run`; run `scripts/test-live` with real images; check a
   person photo and a landscape photo on Telegram by hand.
3. Walk `validation.md`; mark Phase 2 `[x]` in ROADMAP only once verified.
