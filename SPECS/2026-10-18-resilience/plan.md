# Phase 7 — Resilience: plan

Red/Green TDD for every group (`write-tests` skill); checks only via `scripts/`.

## 1. Commands and reset

1. Tests: `/start` and `/restart` from every phase → phase `AWAITING_PHOTO`, the
   session emptied, the right reply, and a logged reset; routing sends both commands to
   their handlers (not to `on_other`), and edited command messages are ignored.
2. Implement `on_start` and `on_restart` in `gateway.py` and register them first.

## 2. Command menu and crash reply

1. Tests: the `post_init` hook registers both commands; a `TelegramError` there is
   logged, not raised; `log_error` replies with the apology when there is a message,
   stays silent without one, and survives a failing reply.
2. Implement in `gateway.py`.

## 3. Media timeouts

1. Tests: photo download passes `MEDIA_TRANSFER_TIMEOUT_S` to `get_file` and
   `download_as_bytearray`; uploads use the same constant.
2. Rename the constant and apply it.

## 4. Wrong-input matrix (category sweep)

1. A parametrised test: phases × input kinds (text, unknown command, non-text, photo,
   image file, non-image file) → at least one reply, no exception, expected phase.
2. Fix anything the sweep finds (expected: nothing, since earlier phases added guards).

## 5. Converter one-figure fix

1. Test: the instruction says "exactly one".
2. Update `CONVERTER_INSTRUCTION`.

## 6. Docs and verification

1. README: commands section; ROADMAP Phase 7.
2. `scripts/hooks --run`, `scripts/test-live` (look at the portrait), and on Telegram:
   `/restart` mid-interview, `/start` after the wrap, the command menu.
3. Walk `validation.md`; mark Phase 7 `[x]` once verified.
