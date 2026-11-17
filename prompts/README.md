# Prompts

Every prompt the Engine sends to an LLM. One file per job; the module that
uses it is next to it in the table. 🔒 = thesis-methodology content: don't
change without flagging it to the researcher first (CLAUDE.md).

## The robot in a Live session, in conversation order

| Prompt file | Constants | What it does | Used by |
|---|---|---|---|
| `small_talk_prompt.py` | `SMALL_TALK_SYSTEM_PROMPT`, `BRIDGE_SYSTEM_PROMPT`, `FOLLOW_UP_SYSTEM_PROMPT`, `FALLBACK_LINES` | Opening and closing small talk; the short reaction before each fixed opening-script line; follow-up questions | `small_talk.py` |
| `acknowledgement_prompt.py` | `ACKNOWLEDGEMENT_SYSTEM_PROMPT`, `FALLBACK_LINES` | The 2–3 sentence reply after a non-PBDI main answer (content only, no praise) | `acknowledgement.py` |
| `reaction_line_prompt.py` | `REACTION_LINE_SYSTEM_PROMPT`, `FALLBACK_LINES` | What the robot says while its face shows the emotion (never names it) | `reaction_line.py` |
| `pe_check_prompt.py` | `PE_CHECK_SYSTEM_PROMPT`, `WORD_LISTS`, `HEBREW_NAMES` | Grades the participant's PE answer: emotion (Correct/Partial/Wrong) and reason (Matches/Partly/No/Missing); Hebrew word lists per emotion | `pe_check.py` (word lists also `debrief.py`) |
| `pe_feedback_prompt.py` | `PE_FEEDBACK_SYSTEM_PROMPT` | The robot reveals what it felt and why | `pe_feedback.py` |
| `debrief_prompt.py` | `OPENER_SYSTEM_PROMPT`, `FOLLOW_UP_SYSTEM_PROMPT`, `GOODBYE_SYSTEM_PROMPT`, `EXTRACT_SYSTEM_PROMPT`, `FALLBACK_LINES` | The friend debrief at the end: open questions, goodbye, and extracting the moments the participant told | `debrief.py` |

## Judging and research tools

| Prompt file | Constants | What it does | Used by |
|---|---|---|---|
| `evaluator_prompt.py` 🔒 | `EVALUATOR_SYSTEM_PROMPT_A`, `EVALUATOR_SYSTEM_PROMPT_B` | Content-only answer evaluation (GOOD/NEUTRAL/BAD + VA stance); A/B variants | `evaluator.py`, `ab_test.py` |
| `persona_prompts.py` 🔒 | `PERSONAS` | Synthetic candidate personas (communication styles; bias probe) | `personas.py`, `run_demo.py`, `ab_test.py`, `demo_app.py` |
| `listening_gestures_prompt.py` | `LISTENING_GESTURES_SYSTEM_PROMPT` | Offline generation of small "I'm listening" gestures | `listening_gestures.py` |

## Not in this folder

- **Emotion classifier** — its prompt is `_SYSTEM_PROMPT` inside
  `emotion_classifier.py` (emotion, intensity and the trigger sentence).
- **No-Masking guardrail** 🔒 — `config.NO_MASKING_FLAG_PATTERNS`, a word
  list, not a prompt.
- **Website-builder prompts** (for building the lab website, not the
  robot) — `docs/website-prompts/`.
