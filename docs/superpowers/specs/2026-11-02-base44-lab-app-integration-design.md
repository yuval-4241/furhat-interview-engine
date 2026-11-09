# Base44 Lab App Integration — Design

**Date:** 2026-11-02
**Status:** Client layer built and verified read-only against the live app.
Polling worker not built yet.

## Goal

Run the experiments through a researcher-facing website ("Furhat Interview
Lab", built on Base44) instead of the local Streamlit demo. The website is the
UI the researcher uses during a session; the Engine (this repo) does all the
work behind it.

## Core decisions

1. **The website is frontend + DB only.** It never computes, decides, or
   generates anything. It only displays entity data, saves what the researcher
   types, and changes `status` when the researcher clicks a button. All logic
   lives in the Engine: picking questions, LLM evaluation, emotion choice,
   guardrails, PE grading, building and sending robot commands.
2. **Communication is by polling, through `status` fields only.** The app
   never calls the Engine. No webhooks. The Engine polls the Base44 REST API
   every 1–2 s and writes results back. Chosen over webhooks because the
   Engine runs on a lab machine that isn't reachable from the internet, and a
   1–2 s delay doesn't matter for this study.
3. **Python REST client, not `@base44/sdk`.** The SDK is an npm (JavaScript)
   package and can't be imported from Python. `base44_client.py` calls the
   REST API directly with `requests`, which the project already depends on.
   Same pattern as `llm_client.py`: one file owns the external service.
4. **Claiming a turn uses compare-and-set.** `base44_client.claim()` calls
   `PATCH .../update-many` with the query `{id, status: from_status}` and
   treats `updated == 1` as "this Engine got it". This avoids a race where
   two Engine instances process the same turn.
5. **Errors raise.** Unlike `robot_bridge.py` (which never raises),
   `base44_client` raises `Base44Error`. The worker must know a write failed,
   or a turn can be left stuck.
6. **Secrets live in `.env` only.** `BASE44_APP_ID` and `BASE44_API_TOKEN`
   are read with `os.environ.get(..., "")` in `config.py` and never hardcoded.
   This repo doesn't load `.env` automatically (see the SESSION_LOG.md
   python-dotenv note), so each new terminal needs
   `set -a; source .env; set +a`.

## REST API (as used)

Base URL: `https://app.base44.com/api/apps/{BASE44_APP_ID}/entities/{Entity}`
Auth header: `Authorization: Bearer <personal access token>`

| Function | Call |
|---|---|
| `list_records(entity, query, sort, limit)` | `GET .../v2/list?q=<json>&sort=&limit=` |
| `get_record(entity, id)` | `GET .../{id}` |
| `create_record(entity, fields)` | `POST ...` |
| `update_record(entity, id, fields)` | `PUT .../{id}` |
| `claim(entity, id, from_status, fields)` | `PATCH .../update-many` with `{"query": {...}, "data": {"$set": {...}}}` |

**Verified against the live app (2026-11-02):** auth, base URL, and
`v2/list`. It returns a bare JSON list, and the `EngineHeartbeat` record with
`key = "engine-main"` exists.
**Not yet verified live:** `PUT` update path, `POST` create, and whether
`update-many` accepts `id` as a filter field. If it doesn't, `claim()` always
returns False.

## Entities (as delivered by Base44)

| Entity | Fields the Engine reads | Fields the Engine writes |
|---|---|---|
| `Session` | `status` (`Draft`/`Running`/`Paused`/`Completed`/`Aborted`), `session_type` (`Baseline`, `Training1`–`Training5`, `Post`, `Followup`), `language` (`he`/`en`), `persona`, `llm_model`, `expression_level` (`Clear`/`Subtle`/`Ambiguous`/`None`), `mode` (`Live`/`Simulation`/`Mock`) | — (no `engine_error` field on Session) |
| `Turn` | `session`, `order`, `status`, `participant_answer`, `participant_pe_answer` | `question_text`, `order` (on creation), `proposed_reply`, `target_emotion`, `intensity`, `valence`, `arousal`, `evaluation_category`, `evaluator_confidence`, `engine_rationale`, `guardrail_flag`, `guardrail_reason`, `pe_answer_feeling`, `pe_answer_why`, `pe_result`, `pe_explanation`, `proposed_feedback`, `claimed_by`, `claimed_at`, `engine_responded_at`, `engine_error` |
| `Persona` | `furhat_face`, `furhat_voice`, `language` | — |
| `LLMModel` | `engine_key` | — |
| `RobotCommand` | `type`, `status` (to pick up researcher-created `stop`) | everything else: `sequence`, `type`, `text`, `emotion`, `intensity`, `language`, `voice`, `status`, `error_message`, `sent_at`, `completed_at` |
| `EngineHeartbeat` | — | `last_seen`, `engine_version`, `robot_connected`, `active_model` (at least every 30 s; app shows "Engine unavailable" after 60 s) |

The Engine never writes `final_reply`, `final_feedback`,
`participant_answer`, `participant_pe_answer`, `edited_by_researcher`, or
`Session.status`.

Duplicate fields Base44 added: `answer_quality` next to
`evaluation_category`, `voice` next to `furhat_voice`, and `model_id` next to
`engine_key`. The Engine uses only `evaluation_category`, `furhat_voice`, and
`engine_key`.

Enum casing differs from the Engine's internals: the app uses `Low`/`Medium`/
`High`, while `schemas.py` uses `low`/`medium`/`high`. The worker maps between
them at the boundary.

## Turn status machine

| status | set by | Engine action |
|---|---|---|
| `awaiting_answer` | Engine (on creation) / app | — |
| `awaiting_engine` | app (researcher clicks "Send to Engine") | `claim()` → `engine_processing` |
| `engine_processing` | Engine | run evaluator + emotion classifier + guardrail; write the proposal fields; → `awaiting_approval` (on failure: `engine_error`, → `awaiting_engine`) |
| `awaiting_approval` | Engine | — |
| `robot_reacting` | app (researcher clicks "Approve") | create the `RobotCommand` from `final_reply` + `target_emotion` and send it to Furhat (Live mode only); → `awaiting_pe` |
| `awaiting_pe` | Engine | — |
| `awaiting_pe_check` | app (researcher submits the PE answer) | `pe_check` against `target_emotion`; write `pe_result`, `pe_explanation`; → `awaiting_feedback` |
| `awaiting_feedback` | Engine | — |
| `done` | app | — |

`pe_answer_feeling` / `pe_answer_why` are the Engine's answer key (written
during `engine_processing`). The app shows them only once the turn reaches
`awaiting_feedback`, so they can't bias the participant.

## Session modes

- `Live`: LLM + robot commands.
- `Simulation`: LLM, no robot commands.
- `Mock`: fixed placeholder output, no LLM, no robot (for UI testing).

## Decisions log

- **Live sessions are autonomous (2026-11-08):** see the autonomous-conversation
  spec. The typed-answer flow remains for Simulation/Mock.
- **Robot app closed during a `Live` session (2026-11-02):** a `pending`
  RobotCommand waits up to 60 s for the Furhat bridge (`health_check()`). If
  it's still unreachable, the command is set to `error` with
  `error_message`, the website shows it, and the turn continues to
  `awaiting_pe` without the robot reaction. The worker keeps
  `EngineHeartbeat.robot_connected` up to date so the researcher sees the
  robot status before approving. The user noted that the robot app will
  always be open during a session, so this is only a safety net.
- **Emotion list (2026-11-02):** add `EXCITED`, `BORED`, `SLEEPY`, and
  `CALM` to the website's `Turn.target_emotion` enum, so the website records
  exactly what the robot's face showed. Pending on the Base44 side. Until
  then, writing one of those four fails and the turn stays in
  `engine_processing`.
- **Priority (2026-11-02):** first prove the real end-to-end flow, where the
  robot shows an emotion that fits the answer. Everything in "Open
  questions" is deferred until after that.

## MVP worker (`engine_worker.py`, built 2026-11-02)

- `Session` `Running` with no turns → create 6 turns. `Training1`–`5` map
  to question-bank sessions 1–5; everything else uses session 1 for now.
- `awaiting_engine` → `claim()` → evaluator + guardrail +
  `emotion_classifier` + `ResponseBank` (Hebrew only) → `awaiting_approval`.
  On failure: `engine_error` is set and the turn stays in
  `engine_processing`.
- `robot_reacting` → one `say_with_gesture` RobotCommand per turn (`Live`
  only) → `furhat_client.react(emotion, intensity, text, language)` →
  `awaiting_pe`. The persona's `furhat_voice` isn't passed yet, because the
  bridge takes only language and gender.
- `awaiting_pe_check` → `pe_check` → `Correct`/`Wrong` (no `Partial` yet) →
  `awaiting_feedback`. `proposed_feedback` is left empty.
- `pe_answer_why` currently holds the evaluator's rationale (placeholder).
- `stop` commands are marked `error` because the bridge has no `/stop` yet.
- **Fix (2026-11-04):** the website creates `say` RobotCommands too (it
  reads each question aloud), which the first MVP ignored. The worker now
  runs every `pending` RobotCommand of a `Running` + `Live` session in
  `sequence` order (`say` → `furhat_client.say`, everything else →
  `react`). Commands of sessions that aren't `Running` are never replayed.
  `react_turn` only creates the turn's command, and it advances the turn
  once that command is `done` or `error`.
- First live run (2026-11-03): Base44 timed out on every call while two
  worker processes were running at once (one left over from the day
  before). Run only one worker at a time.

## Autonomous robot conversation (brainstorming in progress, 2026-11-04)

The user decided the robot should run the conversation itself instead of the
researcher typing answers. Decisions so far (the full design gets its own spec
once all sections are approved):

- **Listening:** the robot listens through Furhat's built-in ASR via a new
  `/listen` endpoint on the Kotlin bridge, called by the worker ("approach 1").
  End of answer = 3 s silence (`endSil`). Max answer length 2 min
  (`maxSpeech`). If nothing is said for 10 s, the robot repeats the question
  once, then marks the turn skipped. Feasibility check first: Hebrew ASR
  accuracy, and a possible ~20 s per-utterance cap (SahraInterview reports
  one for Microsoft STT). If the cap exists, use Furhat's "listening
  extended" pattern, chaining listens until 3 s of silence.
- **Researcher approval:** still required before every emotional reaction and
  before every PE feedback line (option B). Not required for small talk or
  for non-PBDI acknowledgements.
- **Session structure:** opening small talk, then Main questions (Easy before
  Hard), then closing small talk. `Full` or `Short` length is chosen on the
  website. Opening and closing lines are generated by an LLM every session
  from the dialogue so far (new prompt in `prompts/`), so each conversation
  is different.
- **PBDI questions** (`category = "Behavioral (PBDI)"`): evaluation, emotion,
  approval, reaction, PE question, PE grading, feedback revealing the true
  emotion and why, approval, then the robot says it.
- **Other Main questions:** an LLM-generated, content-only acknowledgement (No
  Masking applies). No emotion and no approval. It goes through the guardrail,
  with a fixed neutral fallback ("תודה, נמשיך") if flagged.
- **PE question:** fixed text, open free-report: "מה לדעתך הרגשתי, ולמה?".
  The literature supports free labeling as comparable to forced choice
  (Rosenberg & Ekman 1995), and the "why" part helps with lexically
  ambiguous emotions like contempt. Forced choice was rejected as long and
  awkward when spoken, with a risk of consensus on the wrong label (Russell
  1993).
- **PE grading:** an LLM judge (`pe_check.py`) accepts synonyms and
  descriptions of the right emotion concept (e.g. "כמה מאושר" for
  HAPPINESS). To do: add Hebrew examples to its prompt.
- **PE grading of near-synonyms (option B, 2026-11-04):** grounded in
  Shaver et al. (1987)'s emotion-prototype hierarchy, where joy subdivides
  into cheerfulness, contentment, pride, zest, optimism, and relief.
  - **Correct:** the core word for the target emotion, a clear synonym
    (e.g. שמח / מאושר / נהנה / מרוצה for HAPPINESS), or a description of the
    emotion through what happened ("חייכת כי סיפרתי שהצלחתי").
  - **Partial:** a word that falls in the target's family but sits closer to
    a different emotion the robot can display (e.g. "מתלהב" ≈ EXCITED or
    "רגוע" ≈ CALM when the target was HAPPINESS).
  - **Wrong:** a different emotion family.
  The judge prompt needs a per-emotion Hebrew word list built on that
  hierarchy. No Hebrew emotion-lexicon study was found, so the Hebrew word
  lists are the researcher's own translation and need her review.
- **The "why" part doesn't affect `pe_result` (option A, 2026-11-04):**
  the score reflects the emotion only. The participant's reason is stored,
  and the judge comments on it in `pe_explanation`, so reasons can be
  analysed separately without confounding the score.

## Future ideas

- **PE confidence rating:** after the PE answer, ask "כמה את/ה בטוח/ה, מ-1
  עד 5?". This gives a metacognition measure (confidence–accuracy
  calibration; Brewer et al. 2022), so training gains in confidence can be
  tracked alongside accuracy.

## Open questions

Methodology questions (the user's call):
- What counts as `pe_result = Partial`? `pe_check.py` returns only match /
  no-match.
- How do the Engine's 11 emotions map onto the app's 8? (`EXCITED`, `BORED`,
  `SLEEPY`, and `CALM` aren't in the app list, and the Engine has no
  `NEUTRAL`.)
- What should `expression_level` (`Clear`/`Subtle`/`Ambiguous`/`None`)
  change: intensity only, or the emotion choice too?
- What exactly is `proposed_feedback`? It must stay content-only under the
  No-Masking constraint.
- Which question sets do `session_type` `Baseline`, `Post`, and `Followup`
  use? (Planned: `Training1`–`5` map to question-bank sessions 1–5.)

## Where and how the worker runs (decided 2026-11-02)

- On the researcher's own laptop, **started by hand only on experiment
  days** (`python engine_worker.py`, stopped with Ctrl+C). There is no
  auto-start and no background service. When it's off, the website shows
  "Engine unavailable".
- It must stay light. The LLM runs remotely, so the worker mostly sleeps
  between small HTTPS polls. Adaptive interval: about 2 s while any Session
  is `Running`, about 10 s when idle. The heartbeat is still written at
  least every 30 s.

Practical questions:
- An English response bank is needed for `language = en`.
- `reset` / `stop` robot commands need new endpoints in the
  `furhat-emotion-study` Kotlin bridge (it has only `/react`, `/say`, and
  `/health`).
