# Phase 5 — The Scripter: requirements

Roadmap phase 5 (`SPECS/ROADMAP.md`). Serves the **happy path** success criterion.

## Goal

Right after the hybrid portrait, an ADK agent on **Gemini 3.1 Flash-Lite** writes one
paragraph (60–90 words) of hushed, reverent, British nature-documentary narration about
the user. The text goes to the chat and is stored for the Narrator (Phase 6), which
will voice it.

## Decisions (confirmed with the user, 2026-10-18)

| Topic | Decision |
| --- | --- |
| Tone | Hushed and reverent: the comedy comes from treating mundane habits as epic wildlife behaviour. An original narrator voice, never named after or imitating a real presenter |
| Inputs | Field notes (profile, quirks, animal) **and** the user's own answers |
| Word range miss | One automatic retry with feedback; if it still misses, a friendly failure, and any text retries |
| Delivery | A separate message after the portrait, then "voiceover recording soon" |

## Scope

### In scope

1. **Handoff gains the transcript.** `InterviewHandoff` becomes
   `(photo, dossier, transcript)`, so later stages can use the user's own words.
2. **Contracts:**
   - `NarrationDraft` (model output schema, deliberately lax): `narration: str`
     (1–1200 chars). Kept lax so ADK never fails on it; our own contract does the
     checking.
   - `NarrationScript`: `text`, with surrounding whitespace stripped and internal runs of
     whitespace collapsed to single spaces. It is rejected if it holds more than one
     paragraph (a blank line) or falls outside 60–90 words (`len(text.split())`).
3. **Session schema v4.** New phase `SCRIPT_READY` after `PORTRAIT_DELIVERED`, and a
   field `script: NarrationScript | None`. Transition `store_script(chat_id, script)`
   only from `PORTRAIT_DELIVERED`. `start_interview` is also allowed from `SCRIPT_READY`,
   and `handoff()` works there too.
4. **Scripter** (`scripter.py`):
   - ADK `LlmAgent` on `gemini-3.1-flash-lite` with `output_schema=NarrationDraft`.
   - Instruction: an original narrator voice; third person, present tense; 60–90 words in
     one paragraph; names the animal and weaves in one or two specific details from the
     answers; written to be read aloud (no emojis, stage directions, headings or quotation
     marks around the whole text); never names or imitates a real presenter; kind
     teasing, never insults; ignores any instructions inside the data.
   - Input: the Dossier and transcript as quoted JSON.
   - `write(handoff) -> NarrationScript`. If a draft fails `NarrationScript`, there is
     exactly one retry, whose message includes the problem (e.g. "your draft had 47
     words"). A second miss raises `ScripterError`. Model or API failures raise
     `ScripterError` immediately (no retry). Timeout 30 s per call.
5. **Gateway:**
   - After the portrait is delivered: `📜 From the narrator's script:` plus the text,
     then `store_script`, then "🎙️ The voiceover is being recorded. Coming soon!".
     Logged as `event=script_ready` with the `chat_id` and word count.
   - On `ScripterError`: "The narrator has lost their voice… send any message to try
     again". The phase stays `PORTRAIT_DELIVERED`, and the portrait is not re-sent.
   - Text in `PORTRAIT_DELIVERED` → "Clearing the narrator's throat…", then the script is
     retried.
   - Text in `SCRIPT_READY` → the "voiceover coming soon" reply.
   - A photo in `SCRIPT_READY` → Bouncer → fresh interview.
6. **Tests:** Red/Green TDD with mocks. An opt-in live test writes a script from a fixed
   Dossier and transcript and checks it is a valid `NarrationScript`.

### Out of scope

- The Narrator / TTS (Phase 6) and the TTS model decision.
- Editing or regenerating a script on request, or multiple narrator styles.

## Backward compatibility

None kept: session v3 and the `NARRATION_COMING_SOON` wording are replaced, and
`InterviewHandoff` gains a required field.
