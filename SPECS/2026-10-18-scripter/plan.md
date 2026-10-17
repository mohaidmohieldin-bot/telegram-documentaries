# Phase 5 — The Scripter: plan

Red/Green TDD for every group (`write-tests` skill); checks only via `scripts/`.

## 1. Contracts and handoff

1. Tests: `NarrationScript` accepts 60 and 90 words, rejects 59 and 91, rejects multiple
   paragraphs, collapses whitespace; `InterviewHandoff` carries the transcript.
2. Implement in `session.py` (`NarrationScript`, handoff transcript) and `scripter.py`
   (`NarrationDraft`). Update existing `InterviewHandoff(...)` call sites.

## 2. Session v4

1. Tests: `store_script` only from `PORTRAIT_DELIVERED`; `SCRIPT_READY` keeps the script;
   `start_interview` allowed from `SCRIPT_READY`; `handoff()` there; `schema_version == 4`.
2. Implement in `session.py`.

## 3. Scripter

1. Tests (fake runner): agent config (model, schema, instruction phrases); the message
   holds the animal, quirks and answers as quoted JSON; a valid draft is returned as
   `NarrationScript`; a short draft triggers exactly one retry whose message names the
   word count, and a good retry succeeds; two misses raise `ScripterError`; model
   failure raises without a retry.
2. Implement `scripter.py` (`build_scripter_agent`, `Scripter`, `create_scripter`).

## 4. Gateway

1. Tests: full flow ends with portrait → script message → coming-soon, phase
   `SCRIPT_READY`, logged; Scripter failure → friendly reply, phase stays
   `PORTRAIT_DELIVERED`, portrait not re-sent; text in `PORTRAIT_DELIVERED` retries the
   script only; text in `SCRIPT_READY` → coming-soon; photo in `SCRIPT_READY` → fresh
   interview.
2. Implement in `gateway.py`; wire `create_scripter()` in `__main__.py`.

## 5. Live test, docs, verification

1. `tests/live/test_scripter_live.py`.
2. README update. `scripts/hooks --run`, `scripts/test-live`, a full run on Telegram.
3. Walk `validation.md`; mark Phase 5 `[x]` once verified.
