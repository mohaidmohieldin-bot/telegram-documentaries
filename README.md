# The Telegram Documentaries

A Telegram bot that turns you into the star of a comedy wildlife documentary.
Send it a portrait, answer a short interview, and get back a portrait of yourself
as a human–animal hybrid plus a dramatic British-documentary voiceover.

**Current status: Phase 1 (gateway).** The bot replies `hey mate!` to every new
message. See [`SPECS/ROADMAP.md`](SPECS/ROADMAP.md) for what comes next.

## Setup

Prerequisites: Python 3.12+ and [uv](https://docs.astral.sh/uv/)
(`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
uv sync                  # create .venv and install dependencies
cp .env.example .env     # then edit .env with your real values
```

`.env` variables:

| Variable | Needed from | Where to get it |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Phase 1 | Message [@BotFather](https://t.me/BotFather) → `/newbot` |
| `GEMINI_API_KEY` | Phase 2 | [Google AI Studio](https://aistudio.google.com/apikey) |

`.env` is git-ignored. Never commit real secrets.

## Run the bot

```bash
uv run telegram-documentaries
```

The bot uses long polling, so it works on a laptop with no public URL. Open your
bot in Telegram, send any message, and it replies `hey mate!`. Stop with
**Ctrl+C**. If `.env` is missing or the token is malformed, the bot exits with a
`config_invalid` log line naming the problem.

## Development scripts

These are the source of truth for checks; run them before committing.

| Command | What it does |
| --- | --- |
| `scripts/test` | Run the pytest suite (extra args go to pytest, e.g. `-k gateway`) |
| `scripts/lint` | ruff lint + format check (`--fix` to apply fixes) |
| `scripts/typecheck` | mypy in strict mode |
| `scripts/hooks` | Install a pre-commit hook running all three (`--run` to run them now) |

Development is Red/Green TDD: write a failing test first, then the code.

## Project layout

```
src/telegram_documentaries/
  __main__.py       entrypoint: load settings, start long polling
  config.py         typed settings from .env
  gateway.py        Telegram handlers (the only module that imports telegram)
  logging_setup.py  structured key=value logging; keeps the token out of logs
tests/              pytest suite
scripts/            dev scripts (above)
SPECS/              project constitution: MISSION, TECH, ROADMAP
```

## Bot commands

None yet. `/start` and `/restart` arrive in Phase 7; for now they get the same
`hey mate!` reply as any other message.
