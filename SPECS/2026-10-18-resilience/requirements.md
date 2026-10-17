# Phase 7 — Resilience: requirements

Roadmap phase 7 (`SPECS/ROADMAP.md`). Serves the **reset** and **robustness** success
criteria in `SPECS/MISSION.md`.

## Goal

The bot never strands a user: `/start` and `/restart` wipe the session from any phase,
every phase answers every kind of input sensibly, every external call has a timeout,
and even an unexpected bug gets a friendly reply instead of silence.

## Decisions (confirmed with the user, 2026-10-18)

| Topic | Decision |
| --- | --- |
| Commands | `/start` (welcome) and `/restart` ("clean slate") both wipe everything; the wording differs |
| Command menu | Register `/start` and `/restart` with Telegram at startup (the "/" menu) |
| Unexpected errors | The error handler logs loudly **and** replies with an apology plus a `/restart` hint |
| Converter | Fold in the "exactly one figure" fix (a live portrait showed two hybrids) |

## Scope

### In scope

1. **Commands.** `CommandHandler`s for `start` and `restart` (new messages only),
   registered before the other handlers, so they work in **every** phase, including
   mid-interview. Both call `SessionStore.reset(chat_id)` and reply:
   - `/start` → the existing welcome (`NUDGE_SEND_PHOTO`);
   - `/restart` → "🧹 Clean slate! Everything from your last documentary is gone. Send
     me a photo of yourself to begin a new one."
   Logged as `event=session_reset command=<name> chat_id=… from_phase=…`. Any other
   command keeps today's behaviour for the current phase.
2. **Temporary media.** Nothing is written to disk: photos, portraits and audio live
   only in the in-memory session or in local variables. `reset` drops them. This is
   documented and tested (a reset session holds no photo, dossier or script).
3. **Command menu.** An application `post_init` hook calls `set_my_commands` with both
   commands. A `TelegramError` there is logged as a warning and does not stop the bot
   (non-critical, user-invisible work).
4. **Unexpected errors.** `log_error` keeps its loud log. When the failing update has a
   message, it also replies "Something went wrong on set. 🎬 Send /restart to start
   over." If that reply itself fails, it is logged, never raised.
5. **Timeouts audit.** All external calls are bounded:
   - Gemini stages: Bouncer 30 s, Interviewer 30 s, Converter 90 s, Scripter 30 s,
     Narrator 60 s (already in place).
   - Telegram media: `PHOTO_UPLOAD_TIMEOUT_S` becomes `MEDIA_TRANSFER_TIMEOUT_S` (60 s)
     and now also covers **downloading** the user's photo (`get_file` and
     `download_as_bytearray`), whose 5 s default could time out on large photos.
6. **Wrong-input matrix.** A parametrised test covers every phase × every input kind
   (text, unknown command, sticker or other non-text, photo, image file, non-image
   file) and asserts at least one reply, no exception, and the expected phase
   afterwards. Plus `/start` and `/restart` from every phase.
7. **Converter "exactly one figure".** The instruction requires exactly one human-animal
   hybrid figure: the person is never duplicated, and real animals may appear around
   them.

### Out of scope

- Cancelling a stage that is already running (python-telegram-bot handles updates one at
  a time, so `/restart` takes effect as soon as the current stage finishes).
- Session expiry, persistence, rate limiting.

## Backward compatibility

None kept: `PHOTO_UPLOAD_TIMEOUT_S` is renamed.
