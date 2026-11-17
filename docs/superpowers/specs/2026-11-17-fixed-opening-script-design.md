# Fixed opening script, a more talkative interviewer, and question skipping — design

Date: 2026-11-17. Status: approved by the researcher 2026-11-17.
Repos: `conversation_engine` (Engine) and `furhat-insight-lab` (website, Supabase).

## Intent

Today the Live interview opens with 2–3 small-talk turns whose lines the LLM
writes freely (`small_talk.py`), so every participant hears a different
opening. The researcher wants:

1. **A fixed opening script** that every participant hears, word for word,
   while the robot still reacts to what was said and can branch into a short
   side conversation before returning to the script.
2. **An interviewer who talks more**: after an answer, 2–3 sentences that
   respond to what the participant said, instead of one short line.
3. **Skipping questions from the website**, both before the session (choose
   which planned questions won't be asked) and during it (jump ahead).

## Researcher decisions (2026-11-16/17)

- **Script (Full interview), in order:**
  1. "שלום, נעים מאוד. מה שלומך? איך הייתה הדרך לכאן?"
  2. "אז נתחיל. קודם כול, תודה שהגעת. אני אשמח שנכיר קצת. תוכל/י לספר לי בכמה מילים על עצמך?"
  3. "ומה גרם לך להתעניין דווקא בתפקיד הזה ובחברה שלנו?"
  4. "ספר/י לי על נקודת חוזקה שלך, משהו שאתה/את טוב/ה בו במיוחד בעבודה."
  5. "ומה לגבי נקודה שאתה/את עדיין עובד/ת עליה? משהו שהיית רוצה לשפר?"
- **The question is fixed; the reaction before it is generated.** The
  researcher's drafts opened lines 2 and 3 with "מעולה." / "מעניין."; those
  fixed openers are replaced by a generated 1–2 sentence reaction to the
  previous answer (so "the drive was awful" doesn't get "מעולה"). The question
  part is said word for word.
- **Gender:** slash forms ("תוכל/י") are rendered in the participant's
  gender by `hebrew_gender.render()`, never read with a slash (decision of
  2026-11-13).
- **Strength/weakness are part of the opening**, so they are not evaluated
  and get no PBDI emotion reaction.
- **Where the script lives: approach A** — rows in the website's `questions`
  table (see Approaches).
- **Longer interviewer replies:** the acknowledgement after a non-PBDI Main
  answer becomes 2–3 sentences that pick up a specific detail of the answer;
  small-talk follow-ups may also be 2–3 sentences. No evaluation, no comment
  on delivery, no new question inside an acknowledgement (No-Masking). PBDI
  reaction lines (`reaction_line.py`) stay as they are.
- **Skipping: both** — per-question checkboxes before the session starts,
  and "skip to here" during the session. PBDI questions can't be removed
  before the session.

## Goals

- Every participant hears the same five opening questions, in the same order.
- The robot's speech around those questions responds to the participant.
- The researcher can edit the script's wording on the website, without code.
- The researcher can remove planned questions before a session and jump
  ahead during one; every skipped turn stays in the data with a reason.

## Non-goals

- No change to Main question selection (random Easy/Hard with the PBDI
  guarantee), the PE flow, PBDI reactions, or the Closing turns.
- No change to Simulation/Mock modes beyond what the shared plan code gives
  them for free.
- No reordering of turns during a session.

## Anti-goals (would be a failure even if it works)

- The bridge or acknowledgement **evaluates** the answer ("great answer",
  "very convincing") or comments on delivery style — a No-Masking breach.
- A side conversation that never returns to the script, or a script line
  that is reworded by the LLM.
- Skipped questions that vanish from the data with no trace or reason.
- A slash form read aloud.

## Constraints

- No-Masking (CLAUDE.md): every generated line passes `guardrail.check_rationale`;
  on a flag, fall back (see below).
- The website owns Turn creation on Supabase; the Engine reads turns and
  writes back. `ENGINE_INTEGRATION.md` / `migration/ENGINE_API.md` are the
  contract and must be updated with any new column or status meaning.
- Latency: the participant waits for every generated line; one extra LLM
  call per opening turn is acceptable, two is not.
- `conversation_flow.advance()` handlers must stay safe to run twice
  (Retry re-runs the current status).

## Approaches considered (where the script lives)

- **A. Rows in the `questions` table with phase "Opening" — chosen.** The
  site picks them by script order, the same way it picks Main questions. The
  researcher edits wording in Admin; each turn stores the question id, which
  helps the analysis.
- B. A constant in `interviewPlan.js`. Fastest, but every wording change
  needs a developer and a deploy.
- C. A constant in the Engine (`prompts/opening_script.py`). Next to the
  other prompts, but the website wouldn't know the question until the robot
  asks it, and the researcher can't edit it.

## Design

### Website: data

Migration `supabase/migrations/2026111700000_questions_phase.sql`:

- `questions.phase text not null default 'Main' check (phase in ('Main', 'Opening'))`
- `questions.script_order integer` (null for Main; 1..n for Opening)
- Seed the five script rows above (`phase='Opening'`, `script_order` 1–5,
  `category` '', `difficulty` 1, `level` '').
- `src/api/entities.js`: add `phase`, `script_order` to the questions columns.

### Website: plan (`src/lib/interviewPlan.js`)

- Main pools filter `phase !== 'Opening'` (Opening rows must never be drawn
  as Main questions).
- Opening turns come from active Opening questions sorted by
  `script_order`, the first `counts.opening` of them: `question` = the row's
  id, `question_text` = its text (still with slash forms),
  `generated_by_engine: false`, `phase: 'Opening'`.
- **Builder's call (adjustable in `COUNTS`):** Full = 5 opening turns
  (all of the script), Short = 3 (lines 1–3). If fewer active Opening rows
  exist than needed, NewSession reports it like missing Easy/Hard questions.
- Admin's question editor shows and edits `phase` and `script_order`.

### Website: skipping before the session (`NewSession.jsx`)

- After the plan is built and before the session is created, a review step
  lists every planned turn (Opening and Main; Closing too), each with a
  checkbox, checked by default. "Reshuffle" rebuilds the Main picks.
- Unchecked turns are **still created**, with `status: 'skipped'`,
  `skipped: true`, `skip_reason: 'planned_skip'`, so the plan and the
  researcher's choice stay in the data. The Engine already treats
  `skipped` as finished.
- **Researcher decision (2026-11-17): PBDI questions can't be removed.**
  Their row shows a locked, checked box (tooltip: PBDI questions are part
  of every session), so the session always keeps its PBDI count.

### Website: skipping during the session (`LiveSession.jsx`)

- In the turn list, every turn after the current one gets a "skip to here"
  action. It marks the current turn and every turn between it and the chosen
  one as skipped: `skip_reason: 'researcher_jump'` for the in-between turns;
  the current turn goes through the existing `skipTurn` logic (same checks as
  the "Skip this turn" button, `canSkipTurn`). If the current turn can't be
  skipped right now, the action is disabled, with the same tooltip.
- **Researcher decision (2026-11-17):** a jump may pass over PBDI turns
  (e.g. when time runs out); only the pre-session review locks them.
- `SKIP_REASON_LABELS` gets `planned_skip` and `researcher_jump` (he/en).

### Engine: opening turns (`conversation_flow.py`, `small_talk.py`)

- An Opening turn **with a `question_text`** (not generated) is a scripted
  turn. In `_speak`:
  - position 1 (the greeting): say the rendered question as is.
  - later positions: one LLM call, new `small_talk.bridge(history, ...)`,
    returns a 1–2 sentence reaction to the participant's last answer
    (from `dialogue_history`). The robot says `bridge + " " + rendered question`.
    On LLM failure or a guardrail flag: no bridge, just the question.
  - `small_talk_log` starts with the robot line as actually said (bridge +
    question), so later prompts see what the participant heard.
- The answer handling stays as today: `_small_talk_reply` → `follow_up`
  may ask a side question (the "side conversation") or say NONE and move on;
  the next scripted turn's bridge reacts to the last thing said, so the
  conversation returns to the script naturally.
- Opening turns with no `question_text` (old sessions, or a plan built
  before the migration) keep today's generated small talk — backward
  compatible.
- The bridge prompt (`prompts/small_talk_prompt.py`, new `BRIDGE_SYSTEM_PROMPT`):
  react to the content of the last answer in 1–2 short sentences, in the
  speakers' genders, no evaluation or praise of the answer's quality, no
  comment on how it was said, **no question** (the script supplies it), no
  name overuse (existing `NAME_RULE`).
- `_question_to_say` already renders slash forms for non-generated turns —
  scripted turns get that for free.

### Engine: longer replies (`prompts/acknowledgement_prompt.py`, `prompts/small_talk_prompt.py`)

- Acknowledgement: 2–3 sentences, pick up one specific detail of the
  answer, may add a short linking thought; no evaluation, no delivery
  comments, no question. Fallback line unchanged.
- Follow-up: allow up to 2–3 sentences (a short reaction, then the
  question).
- Builder: check `llm_line` cleaning/token limits don't cut multi-sentence
  lines to one sentence; check the guardrail still sees the whole line.

### Contract and docs

- Update the website's `ENGINE_INTEGRATION.md` / `migration/ENGINE_API.md`:
  Opening turns may now carry `question_text` (scripted) and new skip reasons.
- Engine `CLAUDE.md` / `SESSION_LOG.md`: note scripted openings.

## Testing

- Engine (pytest, `tests/fakes.py`): scripted Opening turn at position 1
  says the rendered question; at position 2 says bridge + question; bridge
  failure → question only; guardrail flag → question only; follow-up still
  works; unscripted Opening turns behave as before; skipped turns (both new
  reasons) are passed over by `current_turn`.
- Website: `buildTurnPlan` unit tests (Opening rows never in Main pools,
  script order, Full=5 / Short=3, missing-Opening error); manual check of
  the review step and "skip to here".
- One live run on the virtual robot.

## Left to the builder

- Exact UI layout of the review step and the "skip to here" control.
- Wording of the bridge/acknowledgement prompts within the rules above
  (prompts are not methodology-locked, but the researcher reviews them).
- Migration file name/timestamp.
