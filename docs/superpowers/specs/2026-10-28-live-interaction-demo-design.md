# Live Interaction Demo — Design

**Date:** 2026-10-28
**Status:** Draft, pending user review.
**Spans two repos:** `conversation_engine` (Python, "the brain") and
`furhat-emotion-study` (Kotlin, "the puppet" — a separate Furhat Skill
project at `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study`).

## Context

Everything built so far (`graph.py`, `evaluator.py`, `guardrail.py`,
`emotion_classifier.py`, `EmotionsLibrary.kt`'s continuous-intensity
support, the `RemoteControl.kt` bridge) has been exercised either with
synthetic personas (no human in the loop) or in one manual, hand-run demo
(2026-10-01, confirmed working end to end against a real Virtual Furhat).

This spec is the first version meant to be **the base** for real sessions:
a human speaks to the robot, in Hebrew, through a convenient operator
interface — not a one-off script. Scope: the full turn loop (question →
spoken answer → evaluation → robot reaction → perspective-taking (PE)
question → spoken PE answer → feedback), a Streamlit control surface, and
the plumbing (STT, logging, API keys, one-command launch) around it.

**Not every question carries the full cycle (clarified 2026-10-28).** Only
"central/significant" questions get a robot emotional reaction followed by
a PE question about it. Which questions qualify is decided by
`question_bank_seed.json`'s existing `category` field:
`behavioral_pbdi` and `self_reflection` trigger the full cycle (question →
answer → evaluation → **reaction → PE question → spoken PE answer →
feedback**); `warm_up`, `motivation_fit`, and `closing` get question →
answer → evaluation → plain acknowledgement, no reaction, no PE. This is a
lookup against data already in the question bank — no new field needed,
and no change to `question_bank.py` itself.

**No-Masking still applies in full.** Nothing added here scores or trains
delivery style. The new PE-matching step (below) grades *content*
correctness of an emotion guess against a ground truth the system itself
picked — not how the participant said it.

## Architecture decision (approved 2026-10-28)

Two options were weighed for how Python reaches the robot:

- **Furhat's official Remote/Realtime API** — confirmed (via Furhat's own
  docs) to support raw `ARKitParams` and custom gesture definitions from
  outside a skill. Capable, but using it would mean reimplementing
  `EmotionsLibrary.kt`'s AU-blend tables (including the continuous-
  intensity interpolation added 2026-09-30) in Python — a second copy of
  tuned data that can drift from the first.
- **The existing custom `RemoteControl.kt` bridge** (chosen) — already
  live-demoed working end to end on 2026-10-01. Keeps AU values as a
  single source of truth in Kotlin. Python stays the orchestrator
  ("brain": picks questions, runs STT/evaluation/classification, decides
  what to say); the Furhat skill stays a thin executor ("puppet": say
  this, show that) — already its role today, just extended with two more
  endpoints (below).

## Components

### 1. Furhat skill side (`furhat-emotion-study`)

**`RemoteControl.kt` — two new endpoints, alongside the existing one:**

```
POST /react   {emotion, intensity, text?}   (existing, unchanged)
POST /say     {text}                         (NEW — speech with no gesture change)
GET  /health                                 (NEW — used by the Settings page's
                                               "test connection" button; must NOT
                                               move the robot's face)
```

**New Flow state** replaces the current `Idle -> Test_AU` wiring
(`idle.kt`'s `onUserEnter` currently sends every user straight into the
old AU-preview test state). New state (name TBD at implementation time,
e.g. `LiveSession`) does the minimum: attend the user, hold a neutral/
ready face, and otherwise sit idle — all real interaction logic lives in
Python and arrives via the two endpoints above. This matches the
"puppet" framing: the skill does not need its own conversation logic for
this flow.

**Cleanup, same pass:** remove `PRIDE, TENSION, RAGE` from
`EmotionType` — confirmed still unreachable (`getEmotion()` has no branch
for them, calling with one throws). Dead code, no behavior to preserve.

### 2. Python side (`conversation_engine`) — new modules

| Module | Responsibility |
|---|---|
| `stt.py` | Wraps Google Cloud Speech-to-Text (`he-IL`). Takes audio bytes from `st.audio_input`, returns transcript text. Raises a typed error on failure (caller decides fallback), never silently returns empty. |
| `pe_check.py` | One LLM call: does the participant's free-text PE answer correctly identify the ground-truth emotion the system already picked? Returns `{match: bool, explanation: str}`. Same fail-closed shape as `emotion_classifier.py` — malformed LLM output is a typed failure, not a silent guess. Mirrors content-only framing: judges whether the *emotion concept* was named/described correctly, never how it was said. |
| `furhat_client.py` | Thin HTTP wrapper replacing today's narrower `robot_bridge.py`: `say(text)`, `react(emotion, intensity, text=None)`, `health_check() -> bool`. `robot_bridge.send_reaction()` becomes a call-through for compatibility with existing tests/call sites, or is retired in favor of direct calls — implementation-time decision, not a design one. |
| `interaction_log.py` | Appends one JSONL record per turn to `data/sessions/<session_id>.jsonl` (schema below), plus a shared `data/technical_log.jsonl` for errors/timings. |
| `interaction_app.py` | The Streamlit control surface (below) — new file, does not replace `demo_app.py` (which stays as the synthetic-persona pipeline demo). |

**Emotion dynamics across turns:** per the clarification this session,
"dynamic emotion" means `emotion_classifier.classify_emotion()` is called
fresh every turn from that turn's question+answer (as it already works
today) — not a new momentum/smoothing mechanism carrying state between
turns. **Flag to confirm:** if the intent was for the robot's emotion to
build on prior turns rather than reset each time, that's a different,
larger mechanism (would need deciding what "carries over" and how much) —
say so before implementation starts if this reading is wrong.

### 3. Streamlit control surface (`interaction_app.py`)

Three views, one app (`st.sidebar` navigation or tabs):

**Live session (main view):**
- Big primary-style start control (session code — no names, per privacy —
  + session number + model/provider picker, then one click starts).
- Model picker: provider (OpenAI / lab-server / mock) + model name + base
  URL, backed by `llm_client.py` — no new provider logic, just exposing
  the existing switch as UI instead of an env var.
- Chat-style transcript, growing live: robot turns and participant turns
  rendered like a messaging UI (`st.chat_message`), not a log dump.
- Current question's category shown with a small badge indicating
  whether it's PE-eligible (`behavioral_pbdi`/`self_reflection`) so the
  operator knows a reaction + perspective-taking question is coming, vs.
  a plain warm-up/motivation/closing turn.
- Current robot emotion (label + intensity) and a running Valence/Arousal
  line chart across turns (`st.line_chart` over the session's logged VA
  pairs — no new charting dependency) — only populated on PE-eligible
  turns, since those are the only ones with a robot reaction to plot.
- Transport controls: repeat question, skip, pause, stop. Pause/stop
  must be checked between turns (not mid-LLM-call) — simplest correct
  behavior, avoids half-finished API calls.
- Push-to-talk via `st.audio_input` (confirmed available in the
  installed Streamlit 1.61) for both the interview answer and the PE
  answer; a text box fallback to type/correct the transcript before
  submitting, per the stated STT-failure fallback.

**History:**
- List of `data/sessions/*.jsonl`, newest first, session code + date +
  turn count as the row label (no participant names anywhere, per the
  privacy requirement already baked into "session code, not names").
  Opening one replays its transcript read-only (same chat rendering) and
  offers a CSV export of that session's log.

**Settings:**
- One row per service (OpenAI, lab server, Google STT, Furhat bridge):
  configured-or-not (reads whether the relevant env var / credentials
  path is set — never displays the actual value), plus a "Test
  connection" button. For Furhat, that button calls the new `GET
  /health` — deliberately not `/react`, so checking settings never makes
  the robot flinch.

### 4. Logging schema

Per-turn record in `data/sessions/<session_id>.jsonl`:

```json
{
  "timestamp": "...", "turn": 3, "question_category": "behavioral_pbdi",
  "stage": "interview" | "pe" | "feedback",
  "triggers_pe": true,
  "question": "...", "transcript": "...", "stt_corrected": false,
  "evaluation": {"category": "...", "confidence": 0.0, "rationale": "..."},
  "valence": "...", "arousal": "...",
  "robot_emotion": "...", "robot_intensity": 2,
  "guardrail": {"passed": true, "matched_patterns": []},
  "pe_answer": "...", "pe_match": true, "pe_explanation": "...",
  "model": {"provider": "...", "model": "..."}
}
```

`triggers_pe` is derived straight from `question_category` (`true` for
`behavioral_pbdi`/`self_reflection`, `false` otherwise) and logged
explicitly rather than left implicit, so later analysis never has to
re-derive it from a category string. On a `triggers_pe: false` turn,
`stage` is always `"interview"` — there is no `"pe"`/`"feedback"` record
for that turn, and the robot gets a plain acknowledgement (still spoken
via `furhat_client.say()`, no `react()` call). Fields not relevant to a
given `stage` are simply absent (e.g. `pe_*` only appears on `stage:
"pe"` records) — same "log everything regardless of outcome" convention
`graph.py`'s `finalize()` already follows.

`data/technical_log.jsonl` (separate, shared across sessions): one record
per error/slow-call, with `component` (`stt`/`llm`/`robot`), `elapsed_ms`,
and the error if any. Kept separate so the research log stays clean for
analysis while failures are still fully traceable.

### 5. API keys & launch

- `.env.example` documents every key (`OPENAI_API_KEY`, `LLM_PROVIDER`,
  `LAB_LLM_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS`) — `.env` itself and
  any service-account JSON stay gitignored (already true for `.env`;
  confirm the credentials path pattern is covered too).
- One launcher script (`run.sh`), extending the pattern already proven on
  2026-10-01 (`הפעלת הדגמת הרובוט.command`): build the skill, print the
  manual Furhat-GUI steps and wait for Enter, then launch
  `interaction_app.py`. The Furhat GUI step cannot be scripted (no CLI/
  API for that dashboard) — `run.sh` automates everything that can be
  automated and makes the one manual step unmissable, not silent.
- Hebrew README: install, configure keys, run — one command, matching
  requirement #6.

## Error handling

- STT failure -> typed error surfaced in the UI, falls back to the text
  box (already in requirements) — the turn is never silently skipped.
- Robot unreachable (`furhat_client` calls time out) -> turn continues in
  the UI/log (same "never let a dead robot break the pipeline" rule
  `robot_bridge.py` already follows), with a visible warning in the live
  view so the operator knows the robot didn't react.
- LLM call failure (evaluator/classifier/pe_check) -> turn marked failed
  in the log with the error in `technical_log.jsonl`, operator sees a
  clear retry option rather than a silent skip.

## Testing

- `stt.py`, `pe_check.py`, `furhat_client.py`: unit tests mocking only
  the actual network boundary (Google client / `llm_client.call_llm` /
  `requests`), same pattern used throughout this repo
  (`test_evaluator_retry_hint.py`, `test_ab_test.py`).
- `interaction_log.py`: pure function tests (given records, correct
  JSONL written, correct fields present/absent per stage).
- Kotlin: `RemoteControl.kt`'s two new endpoints get the same manual
  smoke-test treatment as the existing one (`RemoteControlSmokeTest.kt`
  pattern) — a live HTTP call against a running skill, human-verified,
  since there's no simulator to automate against.
- `interaction_app.py` itself: not unit-testable in the usual sense
  (Streamlit UI) — verified by actually running it against a live Virtual
  Furhat, same as the 2026-10-01 demo, before calling this done.

## Open item to confirm before implementation

"Dynamic emotion across the conversation" is implemented here as
per-turn re-classification on PE-eligible turns only (no cross-turn
memory). Flagged above — confirm or correct before build starts.

## Resolved during review (2026-10-28)

Not every question gets a robot reaction + PE question — only
`behavioral_pbdi`/`self_reflection` questions do, decided from the
existing `category` field (see Context). `warm_up`/`motivation_fit`/
`closing` questions get evaluated and acknowledged, no reaction, no PE.
