# The Telegram Documentaries

A Telegram bot that turns you into the star of a comedy wildlife documentary.
Send it a portrait, answer a short interview, and get back a portrait of yourself
as a human–animal hybrid plus a dramatic British-documentary voiceover.

**Current status: Phase 2 (the Bouncer).** Send the bot a photo: a Gemini 3.1
Flash-Lite vision agent (Google ADK) checks that it contains a real human. No human
gets a cheeky rejection and a fresh start; a human gets through. Text messages get a
nudge to send a photo. See [`SPECS/ROADMAP.md`](SPECS/ROADMAP.md) for what comes next.

## Setup

Prerequisites: Python 3.12+ and [uv](https://docs.astral.sh/uv/)
(`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
uv sync                  # create .venv and install dependencies
cp .env.example .env     # then edit .env with your real values
```

`.env` variables:

| Variable | Status | Where to get it |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | required | Message [@BotFather](https://t.me/BotFather) → `/newbot` |
| `GEMINI_API_KEY` | required | [Google AI Studio](https://aistudio.google.com/apikey) |

`.env` is git-ignored. Never commit real secrets.

## Run the bot

```bash
uv run telegram-documentaries
```

The bot uses long polling, so it works on a laptop with no public URL; it only
answers while this command is running. Stop with **Ctrl+C**. If `.env` is missing
or a value is malformed or still the placeholder, the bot exits with a
`config_invalid` log line naming the problem.

## Development scripts

These are the source of truth for checks; run them before committing.

| Command | What it does |
| --- | --- |
| `scripts/test` | Run the pytest suite (extra args go to pytest, e.g. `-k gateway`) |
| `scripts/lint` | ruff lint + format check (`--fix` to apply fixes) |
| `scripts/typecheck` | mypy in strict mode |
| `scripts/hooks` | Install a pre-commit hook running all three (`--run` to run them now) |
| `scripts/test-live` | Opt-in tests that call the real Gemini API (see below) |

Development is Red/Green TDD: write a failing test first, then the code. The default
test run never calls Gemini or Telegram; external services are faked.

### Live tests

`scripts/test-live` sends real images to Gemini to confirm the Bouncer's judgement.
It needs `GEMINI_API_KEY` in `.env` and two images (JPEG, PNG or WebP) you provide:

```
tests/live/fixtures/person.jpg      a photo with a clearly visible person
tests/live/fixtures/landscape.jpg   a landscape or object, no people
```

That folder is git-ignored so personal photos never reach the repo. Tests skip with a
message if the key or an image is missing. Each run makes two small paid API calls.

## Project layout

```
src/telegram_documentaries/
  __main__.py       entrypoint: load settings, wire dependencies, start long polling
  config.py         typed settings from .env
  gateway.py        Telegram handlers (the only module that imports telegram)
  bouncer.py        ADK vision agent: does the photo contain a human?
  session.py        in-memory, per-chat session state (single state driver)
  media.py          ImageInput contract for images sent to Gemini
  logging_setup.py  key=value logging, logged_stage decorator, token kept out of logs
tests/              pytest suite (tests/live/ = opt-in real-API tests)
scripts/            dev scripts (above)
SPECS/              project constitution: MISSION, TECH, ROADMAP
```

## Bot commands

None yet. `/start` and `/restart` arrive in Phase 7; for now they get the same
reply as any other text. Sending a new photo always starts the check again.
