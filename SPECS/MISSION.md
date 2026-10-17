# MISSION — The Telegram Documentaries

This file is part of the project constitution (with `TECH.md` and `ROADMAP.md`).
Every other document and agent defers to it.

## Vision

A Telegram bot that turns a user into the star of a comedy wildlife documentary.
The user sends a portrait, answers a short interview, and receives a portrait of
themselves as a human–animal hybrid plus a dramatic, British-documentary-style
voiceover about their "behaviour in the wild".

## User experience (happy path)

1. The user opens a private chat with the bot and sends `/start`.
2. The user sends a portrait photo.
3. **The Bouncer** checks the photo contains a human. If not, it replies with a
   cheeky rejection and the session resets to "waiting for photo".
4. **The Interviewer** asks 5–7 questions, one at a time, waiting for each answer.
   It builds a behavioural dossier and suggests a matching animal.
5. **The Converter** fuses the original photo and the dossier into a hybrid
   human–animal portrait, sent directly to the chat.
6. **The Scripter** writes one paragraph (~60–90 words) of dramatic
   British-documentary narration from the dossier.
7. **The Narrator** (not an agent) turns the script into speech with Gemini TTS
   and sends it to the chat as audio.

## In scope

- The five-stage pipeline above, in private 1:1 chats.
- `/start` and `/restart`: at any point, purge the user's session state and
  temporary media and return to "waiting for photo", without restarting the
  process.
- Out-of-order input: text when a photo is expected, a photo when an answer is
  expected, or any other unsupported message type. The bot replies with a
  friendly nudge describing what it expects next; it never crashes or stalls.

## Out of scope

- Group chats and channels.
- Persisting sessions across process restarts (no database; memory only).
- Languages other than English.
- Video output (image + audio only).
- Webhooks or any public URL.

## Success criteria

- **Happy path:** one user completes photo → Bouncer → interview → hybrid
  portrait → narration text → audio, end to end, in a single chat.
- **Rejection:** a non-human image is rejected cheekily and the session resets.
- **Reset:** `/restart` (and `/start`) mid-flow leaves no residual state or temp
  files and the next photo starts a fresh session.
- **Robustness:** wrong-payload-at-wrong-stage and external API failures produce
  a graceful reply, and the conversation can continue or be restarted.

## Non-negotiables

- One user's session, dossier or media is never visible to another user.
- Secrets (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`) are never hardcoded or
  committed; they come from `.env` only.
