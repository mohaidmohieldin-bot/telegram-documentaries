# Phase 4 — The Converter: plan

Red/Green TDD for every group (`write-tests` skill); checks only via `scripts/`.

## 1. Image contract and image caller

1. Tests: `PortraitImage` bounds and MIME types; `run_image_agent` returns the first
   inline image of the final response, skips text parts, raises the given error (with
   the model's text) when no image is present, and shares the existing error-event,
   timeout and session-cleanup behaviour.
2. Implement `PortraitImage` in `media.py` and `run_image_agent` in `agents.py`, with
   the common final-response loop factored out. Existing agent, Bouncer and Interviewer
   tests stay green unchanged.

## 2. Session v3

1. Tests: `deliver_portrait` from `INTERVIEW_COMPLETE` only; `start_interview` allowed
   from `PORTRAIT_DELIVERED`; `handoff()` works in both completed phases;
   `schema_version == 3`.
2. Implement in `session.py`.

## 3. Converter

1. Tests (fake runner): agent model `gemini-3.1-flash-image` with
   `response_modalities` TEXT+IMAGE; the message holds the photo bytes and MIME type plus
   the Dossier as quoted JSON; the instruction requires likeness, habitat and no text;
   an image is returned as `PortraitImage`; a text-only answer or failure raises
   `ConverterError`.
2. Implement `converter.py` (`build_converter_agent`, `Converter`, `create_converter`).

## 4. Gateway

1. Tests: final answer → finale, captioned portrait, "narration coming soon", phase
   `PORTRAIT_DELIVERED`, logged; Converter failure → friendly retry reply, phase stays
   `INTERVIEW_COMPLETE`; text in `INTERVIEW_COMPLETE` retries and delivers; text in
   `PORTRAIT_DELIVERED` → coming-soon reply; photo after delivery → fresh interview;
   Telegram send failure leaves state retryable.
2. Implement in `gateway.py`; wire `create_converter()` in `__main__.py`.

## 5. Live test, docs, verification

1. `tests/live/test_converter_live.py`; git-ignore `tests/live/output/`.
2. README update. `scripts/hooks --run`, `scripts/test-live`, full run on Telegram.
3. Walk `validation.md`; mark Phase 4 `[x]` once verified.
