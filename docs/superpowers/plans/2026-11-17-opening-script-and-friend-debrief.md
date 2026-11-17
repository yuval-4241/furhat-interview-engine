# Fixed opening script (Engine side) + friend debrief and two-grade PE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Engine runs the website's scripted opening (generated bridge + fixed question), talks a little more after answers, records why each reaction happened, grades PE answers on emotion and reason, and ends the session with a debrief conversation with a "friend" character.

**Architecture:** All robot behaviour stays in `conversation_flow.py` handlers that call small, testable line modules (`small_talk.py`, new `debrief.py`) and graders (`pe_check.py`). The website owns the turn plan and the DB schema; the Engine only reads turns and writes new columns. Website first (schema), Engine second.

**Tech Stack:** Python 3.10+, pytest (`tests/fakes.py`), LLM via `llm_client`/`llm_line`; website React + Supabase (SQL migration, `node --test`).

**Spec:** `docs/superpowers/specs/2026-11-17-fixed-opening-script-design.md` (website part already built: website commit `0fc6391`) and `docs/superpowers/specs/2026-11-17-friend-debrief-pe-design.md`.

## Global Constraints

- No-Masking: every generated line passes `guardrail.check_rationale`; no line grades the answer or comments on delivery. Methodology-locked content (`NO_MASKING_FLAG_PATTERNS`, `PERSONAS`, `EVALUATOR_SYSTEM_PROMPT_A/_B`) is not touched.
- Handlers stay safe to run twice (Retry re-runs the current status).
- Scripted Opening turns: `phase == "Opening"`, `generated_by_engine` false, non-empty `question_text` (slash forms; render with `hebrew_gender.render`). The question is said **word for word**; only a bridge may precede it.
- Bridge: 1–2 sentences reacting to the last thing the participant said, **no question**, no praise; on LLM failure or guardrail flag: no bridge.
- Acknowledgement and small-talk follow-ups: 2–3 sentences. PBDI reaction lines (`reaction_line.py`) unchanged.
- Reason grade values: exactly `Matches`, `Partly`, `No`, `Missing`; emotion grade (`pe_result`) keeps its meaning.
- Debrief: friend asks at most **2** follow-ups (`config.DEBRIEF_MAX_FOLLOW_UPS = 2`); the friend never names or hints an emotion; once the friend's persona is set the robot never switches back.
- Friend face/voice: one setting for everyone, `config.FRIEND_FACE` / `config.FRIEND_VOICE` (env `FRIEND_FACE` / `FRIEND_VOICE`, default `""` = don't switch, log it).
- New DB columns on `turns` (website migration, applied **before** the Engine change runs live): `emotion_trigger text`, `pe_reason_result text` (null or one of the 4 values), `pe_reason_explanation text`, `debrief_moments jsonb` (null or array); `phase` also allows `'Debrief'`.
- Per-turn PE question wording is a proposal: `"שמת לב איך הגבתי? מה לדעתך עבר עליי?"` — one constant on each side (Engine `conversation_flow.PE_QUESTION`, website `sessionUtils.PE_QUESTION`), changed in one commit with a `TODO(researcher): approve wording` comment.

## Review Focus

1. **Older sessions** — Opening turns with empty `question_text` keep today's generated small talk; Main turns are unaffected by the Opening routing. (Task 2 test.)
2. **Retry mid-scripted-turn** — a crash after the bridge was spoken must not generate a different bridge on re-run; the line in `small_talk_log` is reused. (Task 2 test.)
3. **Silence in the debrief** — no answer to the friend's opener: the turn is skipped (`no_answer`), extraction never runs, nothing crashes. (Task 5 test.)
4. **Friend persona not configured** — `FRIEND_FACE`/`FRIEND_VOICE` empty: the debrief still runs in the current face, a log line says so. (Task 5 test.)
5. **No trigger recorded** (old turns, classifier fallback) — reason grade stays empty, emotion grade unchanged, PE step doesn't fail. (Task 4 test.)

---

### Task 1: Website — schema, Debrief turn, PE question, reason grade on screen

Repo: `~/Documents/Workspace/University/lab-website/furhat-insight-lab` (was `base44/`, renamed 2026-11-17).

**Files:**
- Create: `supabase/migrations/20261118000000_debrief_pe.sql`
- Modify: `src/api/entities.js` (turns columns), `src/lib/interviewPlan.js` (Debrief turn after Closing; `PHASE_LABELS.Debrief`), `src/lib/interviewPlan.test.mjs`, `src/lib/sessionUtils.js` (`PE_QUESTION`), `src/components/session/TranscriptTurn.jsx` (reason grade + debrief moments), `src/components/session/ChatTranscript.jsx` (`GROUP_ORDER` += `'Debrief'`), `package.json` (`test:db` lists the new migration), `ENGINE_INTEGRATION.md`, `migration/ENGINE_API.md`

**Interfaces:**
- Produces: turns columns above; Debrief turn `{phase: 'Debrief', question: '', question_text: '', expects_answer: true, generated_by_engine: true, status: 'awaiting_answer'}` as the **last** turn of every plan (Full and Short); `debrief_moments` items `{turn_order: int|null, emotion_named: str, reason_given: str, quote: str, emotion_result: str, reason_result: str}`.

- [ ] **Step 1: Failing plan test** — in `interviewPlan.test.mjs`: `test('every plan ends with one Debrief turn', …)` asserting for Full and Short: last turn `phase === 'Debrief'`, exactly one Debrief turn, `generated_by_engine === true`, its `order` is the max.
- [ ] **Step 2:** `npm run test:plan` → FAIL.
- [ ] **Step 3:** Add the Debrief turn in `buildTurnPlan` after the Closing loop (`COUNTS.*.debrief = 1`); `PHASE_LABELS.Debrief = {he: 'שיחה עם חבר', en: 'Friend debrief'}`; `GROUP_ORDER` gets `'Debrief'`.
- [ ] **Step 4:** Migration: the 4 columns, `turns_pe_reason_result_check` (`null or in ('Matches','Partly','No','Missing')`), `turns_debrief_moments_is_array`, replace the `phase` check to allow `'Debrief'`, `notify pgrst, 'reload schema'`; comment header like `20261114000000_turns_small_talk_log.sql`. Add to `entities.js` turns columns and to `test:db`.
- [ ] **Step 5:** `PE_QUESTION.he` = the proposal above (+ English `"Did you notice how I reacted? What do you think was going on with me?"`), with the TODO comment. `TranscriptTurn`: under the PE grade, the reason grade + explanation when present; on a Debrief turn, the `small_talk_log` and a list of `debrief_moments` (turn order, emotion, reason, both grades).
- [ ] **Step 6:** `npm run test:plan && npm run test:db` → PASS; `npm run build` → no errors.
- [ ] **Step 7:** Docs: ENGINE_API.md section "Friend debrief and reason grade (2026-11-18)" (columns, value sets, Debrief turn, `debrief_moments` shape); ENGINE_INTEGRATION.md table rows for the new columns (writer: Engine).
- [ ] **Step 8:** Commit `"Friend debrief turn, reason grade and emotion trigger columns"`. **Manual (researcher):** apply the migration on Supabase and deploy before Task 3 runs live.

### Task 2: Engine — scripted Opening turns (bridge + fixed question)

**Files:**
- Modify: `conversation_flow.py` (`_speak`, `_process`, `_small_talk_reply`), `small_talk.py`, `prompts/small_talk_prompt.py`
- Test: `tests/test_conversation_flow.py`, `tests/test_small_talk.py`

**Interfaces:**
- Produces: `conversation_flow._is_scripted_opening(turn: dict) -> bool`; `small_talk.bridge(history: list, language="he", participant_gender=None, robot_gender=None, participant_name=None) -> str | None` (None on failure/flag/empty); `prompts.small_talk_prompt.BRIDGE_SYSTEM_PROMPT`.

- [ ] **Step 1: Failing tests** (`test_conversation_flow.py`, using `fake`, `opening_turns`-style helpers):
  - `test_scripted_opening_first_turn_says_question_only` — position 1: robot says `hebrew_gender.render(question_text, gender)` exactly; `small_talk.bridge` not called.
  - `test_scripted_opening_later_turn_says_bridge_then_question` — bridge stubbed `"פקקים זה מתיש."`; robot line == `"פקקים זה מתיש. " + rendered question`; `small_talk_log[0] == {"speaker": "robot", "text": that line}`.
  - `test_scripted_opening_bridge_failure_says_question_only` — bridge returns None → line == rendered question.
  - `test_scripted_opening_rerun_reuses_spoken_line` — turn already has `small_talk_log` with a robot line, status `robot_speaking`, no answer → that same text is said again; bridge not called.
  - `test_scripted_opening_answer_goes_to_small_talk_not_ack` — after the answer: `acknowledgement.acknowledge` not called; `small_talk.follow_up` called; last scripted opening turn may also get a follow-up.
  - `test_unscripted_opening_unchanged` — `generated_by_engine` true, empty `question_text`: `small_talk.generate_line` used as before.
  - `test_small_talk.py::test_bridge_returns_none_when_guardrail_flags` and `::test_bridge_rejects_a_question` (line ending with `?` → None).
- [ ] **Step 2:** `pytest tests/test_conversation_flow.py tests/test_small_talk.py -q` → the new tests FAIL.
- [ ] **Step 3:** Implement: `_is_scripted_opening` = phase Opening and not `generated_by_engine` and `question_text`. In `_speak`, for a scripted opening with no answer and no pending follow-up: reuse `small_talk_log[0]` if present, else build line = `bridge + " " + rendered question` (no bridge at position 1 or when `bridge` returns None), save `small_talk_log=[robot line]` **before** saying it. `_process`: scripted openings go to `_small_talk_reply`. `_small_talk_reply`: the "ready to start?" exclusion applies to unscripted openings only. `small_talk.bridge`: `llm_line.request_line(BRIDGE_SYSTEM_PROMPT.format(...), format_history(history))`, None if empty, flagged, or contains `?`. Prompt: react to the content of the participant's last answer in 1–2 short sentences, speakers' genders (`gender_rule`), `NAME_RULE`, no praise/evaluation, no comment on how it was said, **no question**.
- [ ] **Step 4:** `pytest tests/ -q` → all pass.
- [ ] **Step 5:** Commit `"Scripted opening: generated bridge + fixed question, answers go to small talk"`.

### Task 3: Engine — longer acknowledgement and follow-ups; reaction trigger

**Files:**
- Modify: `prompts/acknowledgement_prompt.py`, `prompts/small_talk_prompt.py` (`FOLLOW_UP_SYSTEM_PROMPT`), `emotion_classifier.py`, `engine_worker.py` (`build_proposal`)
- Test: `tests/test_acknowledgement.py`, `tests/test_small_talk.py`, `tests/test_emotion_classifier.py`, `tests/test_engine_worker.py`

**Interfaces:**
- Produces: `classify_emotion(...) -> {"emotion": str, "intensity": int, "trigger": str}` (`""` on fallback or guardrail flag); `build_proposal(...)` adds `"emotion_trigger"`.

- [ ] **Step 1: Failing tests:**
  - `test_acknowledgement_prompt_asks_for_two_to_three_sentences` — `"2-3 sentences"` (or `"two or three"`) in the prompt and `"ONE short sentence"` not in it; `test_multi_sentence_ack_is_kept_whole` (LLM returns 3 sentences → returned line equal).
  - `test_follow_up_prompt_allows_two_to_three_sentences`.
  - `test_classifier_returns_trigger` (LLM JSON with `"trigger": "led a project alone"` → in result); `test_classifier_fallback_has_empty_trigger`; `test_classifier_trigger_flagged_by_guardrail_is_dropped`.
  - `test_build_proposal_includes_emotion_trigger`.
- [ ] **Step 2:** run them → FAIL.
- [ ] **Step 3:** Prompts: acknowledgement = 2–3 sentences, one specific content detail, an optional short linking thought, existing strict rules kept (no question). Follow-up = a short reaction then the question, up to 3 sentences. Classifier prompt: add `"trigger": "<one short sentence: what in the CONTENT of the answer led to this emotion>"` to the JSON shape; `_FALLBACK` gets `"trigger": ""`; `max_tokens` 80 → 160. `build_proposal` (non-Mock) sets `emotion_trigger`; Mock sets `""`.
- [ ] **Step 4:** `pytest tests/ -q` → pass.
- [ ] **Step 5:** Commit `"Longer acknowledgement/follow-ups; record what triggered each reaction"`.

### Task 4: Engine — two-grade PE and the friend-toned question

**Files:**
- Modify: `pe_check.py`, `prompts/pe_check_prompt.py`, `conversation_flow.py` (`PE_QUESTION`, `_grade_pe`)
- Test: `tests/test_pe_check.py`, `tests/test_conversation_flow.py`

**Interfaces:**
- Consumes: `turn["emotion_trigger"]` (Task 3).
- Produces: `grade_pe_answer(target_emotion: str, pe_answer_text: str, trigger: str = "") -> {"result", "explanation", "reason_result", "reason_explanation"}`; `pe_check.REASON_RESULTS = ("Matches", "Partly", "No", "Missing")`.

- [ ] **Step 1: Failing tests:**
  - `test_reason_grade_parsed` (LLM JSON with `"reason_result": "Matches"` → returned); `test_unknown_reason_value_fails_closed` (→ `reason_result == ""`, emotion grade still returned).
  - `test_no_trigger_means_no_reason_grade` — `trigger=""` → `reason_result == ""`, and the LLM user message does not ask for a reason grade.
  - `test_prompt_grades_reason_on_content_only` — prompt contains `"Matches"`, `"Missing"` and a sentence that wording/length never matter.
  - `test_check_pe_answer_shape_unchanged` (interaction_app's shape).
  - `test_conversation_flow.py::test_pe_grade_saves_reason_fields` — `pe_reason_result` / `pe_reason_explanation` saved; `test_pe_question_is_friend_toned` — `PE_QUESTION` is the proposal string.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** User message adds `Recorded cause of the reaction: <trigger>` when non-empty; prompt adds the reason scale (Matches = points to the same content; Partly = related but vaguer; No = a different cause; Missing = no reason given) and the JSON keys `reason_result`, `reason_explanation`; parse with fail-closed per field. `_grade_pe` passes `turn.get("emotion_trigger", "")` and saves both new fields. `PE_QUESTION` = proposal + `TODO(researcher)` comment.
- [ ] **Step 4:** `pytest tests/ -q` → pass.
- [ ] **Step 5:** Commit `"PE: separate reason grade against the recorded trigger; friend-toned question"`.

### Task 5: Engine — the friend debrief

**Files:**
- Create: `debrief.py`, `prompts/debrief_prompt.py`, `tests/test_debrief.py`
- Modify: `config.py` (`FRIEND_FACE`, `FRIEND_VOICE`, `DEBRIEF_MAX_FOLLOW_UPS = 2`), `conversation_flow.py` (Debrief routing), `tests/test_conversation_flow.py`

**Interfaces:**
- Consumes: Debrief turn shape (Task 1); `pe_check` grading rules (Task 4); `turns[*].target_emotion`, `emotion_trigger`, `question_text`, `participant_answer`.
- Produces: `debrief.opener(language="he", participant_gender=None, friend_gender=None) -> str`; `debrief.follow_up(history: list, language, participant_gender, friend_gender) -> str | None`; `debrief.goodbye(language, participant_gender, friend_gender) -> str`; `debrief.extract_moments(story: list, turns: list) -> list[dict]` (shape from Task 1); `debrief.mentions_emotion(line: str) -> bool`.

- [ ] **Step 1: Failing tests** (`test_debrief.py`, LLM mocked):
  - `test_friend_line_naming_an_emotion_falls_back` — a line containing `"מופתע"` or `"surprised"` → fixed fallback (uses `pe_check_prompt.WORD_LISTS` + `HEBREW_NAMES` + English names).
  - `test_follow_up_none_on_NONE_or_flag`.
  - `test_extract_moments_maps_to_turn_and_grades` — mocked JSON with `turn_order: 7` → item has all six keys; unknown `turn_order` → `null`.
  - `test_extract_moments_empty_story_returns_empty_list` (no LLM call).
  - `test_friend_prompts_contain_no_emotion_words` — none of the 11 Hebrew names / English names appear in the opener/follow-up system prompts.
- [ ] **Step 2: Failing flow tests** (`test_conversation_flow.py`):
  - `test_debrief_switches_to_friend_then_asks` — `config.FRIEND_FACE="Friend"`: `furhat_client.set_persona("Friend", <voice>, lang)` called once before the opener is said.
  - `test_debrief_without_friend_config_still_runs` — empty config: no `set_persona` call, opener said, log mentions it (Review Focus 4).
  - `test_debrief_follow_ups_capped_at_two` then goodbye said, `debrief_moments` saved, status `done`.
  - `test_debrief_silence_skips_without_extraction` (Review Focus 3).
- [ ] **Step 3:** run → FAIL.
- [ ] **Step 4:** Implement. Flow: in `_speak`, `phase == "Debrief"` with empty `question_text` → set persona (if configured; once — skip if `small_talk_log` exists), generate `debrief.opener`, save as `question_text` + `small_talk_log`. `_process` routes Debrief to a `_debrief_reply` like `_small_talk_reply` with `debrief.follow_up` and the cap; when no follow-up: say `debrief.goodbye`, run `debrief.extract_moments(small_talk_log, turns)` (one retry, then `engine_error`), save `debrief_moments`, `done`. Friend gender: `config.VOICE_GENDERS.get(config.FRIEND_VOICE)`. Prompts: friend persona (a friend meeting the candidate right after their interview), open questions only, follow-ups only about what the participant already said, never name/suggest feelings, never summarise; extraction prompt returns JSON list with the six keys, grading emotion and reason with the Task 4 rules.
- [ ] **Step 5:** `pytest tests/ -q` → pass.
- [ ] **Step 6:** Commit `"Friend debrief: persona switch, open questions, moment extraction and grading"`.

### Task 6: Docs and a live run

**Files:** `CLAUDE.md` (module list: `debrief.py`; PE two grades), `SESSION_LOG.md`, `.env.example` if present (`FRIEND_FACE`, `FRIEND_VOICE`).

- [ ] **Step 1:** Update the docs above (one paragraph each, in the files' own style).
- [ ] **Step 2:** `pytest tests/ -q` → all pass; record the count in SESSION_LOG.
- [ ] **Step 3:** Live run on the virtual robot (after the website migration is applied): a Short session — check the bridge + question in the opening, a longer acknowledgement, one PBDI turn with reason grade, the debrief with the friend face. Record what happened in SESSION_LOG.
- [ ] **Step 4:** Commit `"Docs: scripted opening, two-grade PE, friend debrief"`.
