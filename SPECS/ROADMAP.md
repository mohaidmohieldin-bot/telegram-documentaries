# ROADMAP — Build plan

Part of the project constitution (with `MISSION.md` and `TECH.md`). Phases are
built in order. Each phase gets its own feature spec in
`SPECS/<YYYY-MM-DD>-<feature-name>/` (written by the `plan` agent). A phase is
marked complete only after it is verified and `scripts/test`, `scripts/lint`
and `scripts/typecheck` pass.

Status key: `[ ]` not started · `[~]` in progress · `[x]` verified complete

---

## Phase 1 — Repository & gateway `[x]`

Project skeleton and a working Telegram connection.

- `uv` project, `pyproject.toml`, `uv.lock`, `.gitignore` (includes `.env`).
- `scripts/test`, `scripts/lint`, `scripts/typecheck`, `scripts/hooks`.
- Settings loaded from `.env` into a typed model; startup fails clearly if a
  variable is missing.
- Long-polling loop that replies to any message with a fixed text.
- README with setup, run and scripts sections.

**Acceptance:** the bot runs locally, replies to a message with the fixed text,
and all scripts pass.
**Serves:** happy path (foundation), secrets non-negotiable.

## Phase 2 — Bouncer `[x]`

- Session store and state machine introduced, starting in `AWAITING_PHOTO`.
- Photo → Gemini 3.1 Flash Lite vision check → typed yes/no result.
- Human present → advance to `INTERVIEWING`. No human → cheeky rejection and
  reset to `AWAITING_PHOTO`.

**Acceptance:** a human portrait advances; a non-human image is rejected and the
session resets; tests cover both with the model mocked.
**Serves:** rejection criterion.

## Phase 3 — Interviewer `[x]`

- Asks 5–7 questions, one at a time, storing each answer in the `chat_id`'s
  dossier.
- Ends with a dossier summary and a suggested animal (structured output).
- Acts as the orchestrator that routes to later stages.

**Acceptance:** questions arrive one per turn, answers accumulate per chat with
no cross-chat leakage, and the final dossier and animal are validated models.
**Serves:** happy path.

## Phase 4 — Converter `[x]`

- Original photo + dossier → Gemini 3.1 Flash Image → hybrid portrait.
- Image sent directly to the chat (no intermediate text hop).

**Acceptance:** the hybrid portrait is delivered to the correct chat; model
failure produces a graceful reply.
**Serves:** happy path.

## Phase 5 — Scripter `[x]`

- Dossier → one paragraph (~60–90 words) of dramatic British-documentary
  narration.

**Acceptance:** output is validated as a single paragraph within the word range;
it is sent to the chat as text.
**Serves:** happy path.

## Phase 6 — Narrator `[ ]`

- Script → Gemini TTS (`gemini-3.8-flash-tts`) → WAV → sent to the chat as a file.
  (Model and format changed from the original plan on 2026-10-18; see the Narrator spec.)
- Temp media cleaned up after delivery; session moves to `DONE`.

**Acceptance:** audio plays in Telegram; the full happy path runs end to end.
**Serves:** happy path.

## Phase 7 — Resilience `[ ]`

- `/start` and `/restart` purge state and temp files from any phase.
- Wrong-payload-at-wrong-stage guards for every phase (friendly nudge, no state
  change).
- Explicit timeouts and graceful fallbacks for Gemini, TTS and Telegram calls.

**Acceptance:** tests cover reset from every phase, every wrong-input
combination, and a simulated timeout at each external call; the user can always
continue or restart.
**Serves:** reset and robustness criteria.
