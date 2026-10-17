# Phase 4 — The Converter: requirements

Roadmap phase 4 (`SPECS/ROADMAP.md`). Serves the **happy path** success criterion.

## Goal

Straight after the interview's field notes, an ADK agent on **Gemini 3.1 Flash Image**
fuses the user's original photo with their Dossier into a hybrid human–animal portrait
and sends it to the chat as a photo (native multimodal: image + text in, image out,
with no intermediate text hop).

## Decisions (confirmed with the user, 2026-10-18)

| Topic | Decision |
| --- | --- |
| Model | `gemini-3.1-flash-image` (stable; as named in TECH.md). Google now also offers a newer Nano Banana 2.1, not adopted. |
| Style | Photorealistic wildlife-documentary still: face, expression and likeness kept, animal features blended in, set in the animal's habitat |
| Failure | Apologise and keep the interview results; any text message retries the portrait |
| Afterwards | Portrait captioned with the animal, then "narration coming soon". A new photo starts over |

## Scope

### In scope

1. **Session schema v3.** New phase `PORTRAIT_DELIVERED` after `INTERVIEW_COMPLETE`.
   Transition `deliver_portrait(chat_id)` is allowed only from `INTERVIEW_COMPLETE`.
   `start_interview` is also allowed from `PORTRAIT_DELIVERED`. `handoff()` works in
   both `INTERVIEW_COMPLETE` and `PORTRAIT_DELIVERED` (the Scripter needs it later).
   The portrait itself is not stored (YAGNI: no later stage needs it).
2. **Contract `PortraitImage`**: non-empty bytes, at most 20 MB, MIME type
   `image/png`, `image/jpeg` or `image/webp`. Bytes are never in `repr` or logs.
3. **Shared ADK caller** (`agents.py`): add `run_image_agent`, which returns the first
   image part of the final response as a `PortraitImage`. It reuses the same throwaway
   session, error-event and timeout handling as `run_structured_agent`. A final response
   without an image raises the caller's error, including the model's text (e.g. a
   refusal), truncated.
4. **Converter** (`converter.py`):
   - ADK `LlmAgent` on `gemini-3.1-flash-image` with
     `response_modalities=["TEXT", "IMAGE"]`.
   - The instruction asks for one photorealistic nature-documentary still. It must keep
     the person recognisable (face, skin tone, expression, hair, glasses), blend in the
     animal's features tastefully, and place them in the animal's habitat. Flattering and
     playful, never grotesque. No text or watermarks in the image.
   - Input: the original photo bytes plus the Dossier (animal, rationale, quirks) as
     quoted JSON data, with the usual "ignore instructions inside" warning.
   - `convert(handoff) -> PortraitImage`. Timeout 90 s (image generation is slower).
     Every failure raises `ConverterError`.
5. **Gateway:**
   - The finale now ends with "📸 Developing your hybrid portrait now…", and the
     Converter runs immediately in the same turn.
   - On success: `reply_photo` with the portrait and the caption
     `📸 Exhibit A: Homo sapiens × <animal>`, then `deliver_portrait`, then the
     "narration coming soon" message. Logged as `event=portrait_delivered` with the
     `chat_id` and animal.
   - On `ConverterError`: a friendly "the darkroom flooded" reply that asks the user to
     send any message to retry. The phase stays `INTERVIEW_COMPLETE`.
   - Text while `INTERVIEW_COMPLETE` → "back to the darkroom" reply, then a retry.
   - Text while `PORTRAIT_DELIVERED` → "narration coming soon; send a new photo to start
     again".
   - A photo while `INTERVIEW_COMPLETE` or `PORTRAIT_DELIVERED` → Bouncer → fresh
     interview (as before).
   - If sending the photo to Telegram fails, the error handler logs it and the phase
     stays `INTERVIEW_COMPLETE`, so the next message retries.
   - Photo uploads use a 60 s read/write timeout (`PHOTO_UPLOAD_TIMEOUT_S`). *Added
     during validation:* with python-telegram-bot's 5 s default, a multi-megabyte
     portrait reached the chat but the bot raised `TimedOut`, leaving the session
     undelivered and set to re-send.
6. **Tests:** Red/Green TDD with mocks for all of the above. An opt-in live test
   converts `tests/live/fixtures/person.jpg` with a fixed Dossier and saves the result to
   `tests/live/output/portrait.*` (git-ignored) for a visual check.

### Out of scope

- The Scripter and Narrator (Phases 5–6).
- Showing an "uploading photo…" chat action; storing or re-sending portraits; style
  options; Nano Banana 2.1.

## Backward compatibility

None kept: `PORTRAIT_IN_PROGRESS` wording and the session v2 schema are replaced.
