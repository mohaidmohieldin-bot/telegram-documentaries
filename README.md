# The Telegram Documentaries

A Telegram bot that turns you into the star of a comedy wildlife documentary.
Send it a portrait, answer a short interview, and get back a portrait of yourself
as a human–animal hybrid plus a dramatic British-documentary voiceover.

**Current status: all seven roadmap phases are built.** Send the bot a selfie. A Gemini
3.1 Flash-Lite vision agent (Google ADK) checks there's a real human in it, the
Interviewer asks 5–7 playful questions one at a time and writes field notes with your
spirit animal, the Converter (Gemini 3.1 Flash Image) sends a photorealistic hybrid
portrait, the Scripter writes a hushed 60–90 word narration, and the Narrator (Gemini
3.8 Flash TTS) voices it as `voiceover.wav`. `/start` or `/restart` wipes everything at
any point. See [`SPECS/ROADMAP.md`](SPECS/ROADMAP.md).

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

That folder is git-ignored so personal photos never reach the repo. The Converter's and
Narrator's live tests save `portrait.*` and `voiceover.wav` to `tests/live/output/` (also
git-ignored) so you can look and listen. Tests skip with a
message if the key or an image is missing. A run makes about a dozen small paid text calls (Bouncer checks, a scripted
interview and a narration), one image generation and one speech generation, which cost more than the text calls.

## Project layout

```
src/telegram_documentaries/
  __main__.py       entrypoint: load settings, wire dependencies, start long polling
  config.py         typed settings from .env
  gateway.py        Telegram handlers (the only module that imports telegram)
  agents.py         shared ADK caller: throwaway sessions, timeouts, structured output
  bouncer.py        ADK vision agent: does the photo contain a human?
  interviewer.py    orchestrator: question-writer + profiler agents, 5–7 questions
  converter.py      ADK image agent: photo + field notes → hybrid portrait
  scripter.py       ADK agent: field notes + answers → 60–90 word narration
  narrator.py       Gemini TTS (not an agent): narration → WAV voiceover
  session.py        in-memory, per-chat session state (single state driver)
  media.py          ImageInput contract for images sent to Gemini
  logging_setup.py  key=value logging, logged_stage decorator, token kept out of logs
tests/              pytest suite (tests/live/ = opt-in real-API tests)
scripts/            dev scripts (above)
SPECS/              project constitution: MISSION, TECH, ROADMAP
```

## Bot commands

| Command | What it does |
| --- | --- |
| `/start` | Wipes your session and welcomes you; send a selfie to begin |
| `/restart` | Wipes everything (photo, answers, portrait, script) from any point |

Both appear in Telegram's "/" menu. Any other message is answered according to where you
are in the documentary: mid-interview, photos and other commands get a reminder of the
current question, and if a stage fails (portrait, script or voiceover), any message
retries just that stage. Nothing is written to disk; sessions live in memory and are
lost when the bot restarts.
