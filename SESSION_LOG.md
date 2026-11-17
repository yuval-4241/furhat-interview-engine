# Session Log

Running audit of decisions and progress made while working on the Conversation
Engine, session by session. Complements `CLAUDE.md` (which holds the standing
plan/rules) — this file records what actually happened and why.

---

## 2026-07-20 — Day 1

**Git setup**
- Discovered the local git repo was rooted at the home directory (`~/.git`)
  instead of the project folder — only `README.md` was ever tracked, so no
  data was lost. Removed `~/.git`, re-initialized git inside
  `conversation_engine/`, merged with the existing GitHub history, and pushed.
  Repo is now correctly scoped to the project folder only.
- Remote: `github.com/yuval-4241/thesis-conversation-engine`, branch `main`.

**Environment**
- Created `venv/` (Python 3.14.6, Homebrew) and installed
  `requirements.txt` (openai, langgraph, streamlit + deps).

**LLM provider — deviation from plan**
- Lab GPU server (`100.110.96.82`) was busy, so Day 1 step 1 (verify lab
  connection) was skipped for today rather than blocking on it.
- Added an `LLM_PROVIDER` switch (`config.py` / `llm_client.py`) so
  `call_llm()` can target either the lab server (`"lab"`, default) or OpenAI
  directly (`"openai"`). No other module changed — matches the abstraction
  `llm_client.py` was already designed for.
- Today's session runs with `LLM_PROVIDER=openai`, `OPENAI_API_KEY` set in
  `.env` (gitignored, never committed). Model for fast/default/Hebrew all set
  to `gpt-4o-mini` while on this provider.
- Smoke test: `llm_client.call_llm()` round-tripped successfully against
  OpenAI (`pong` test).
- **Next-session action:** when the lab server is free again, switch back by
  unsetting `LLM_PROVIDER` (or setting it to `"lab"`) and doing the real Day 1
  step 1 lab verification per `CLAUDE.md` before relying on lab-hosted models
  (`llama3.1-8b`, `gpt-oss-20b`, `dictalm3-12b`) again — those model names
  don't exist on OpenAI's API.

**Status:** Day 1 steps 1 (lab check) substituted with an OpenAI path; step 2
(deps) done. Steps 3–5 (module smoke tests, `graph.py`, full manual pass) not
started yet.

---

## 2026-07-21 — continued

**Docs**
- Added `PROJECT_PLAN.md` (user-authored — full week 1/2 plan, working
  rules: short/bullets, explain job-skill relevance, end-of-session paper
  summaries). Flagged to user that its "Current status" checklist (mock
  mode, all 5 modules tested) doesn't match reality yet — left as-is
  pending user decision on whether to update it or fold its rules into
  `CLAUDE.md`. Not resolved yet.

**Uncommitted changes (as of this entry):**
- `config.py`, `llm_client.py` — the `LLM_PROVIDER` OpenAI-switch edits from
  2026-07-20, not yet committed.
- `PROJECT_PLAN.md`, `SESSION_LOG.md` — new, untracked.
- Nothing pushed to GitHub since the initial merge commit (`fb7843f`).

**RESUME FROM HERE (next session/restart):**
1. Decide whether to commit the pending changes above (user was asked,
   hadn't answered before restart).
2. Run Day 1 step 3 — smoke-test each module standalone, in order:
   `personas.generate_synthetic_answer` → `evaluator.evaluate` →
   `guardrail.check_rationale` → `response_bank.get`. None of these have
   been run yet this project.
3. Still using `LLM_PROVIDER=openai` (`.env`) since lab server
   (`100.110.96.82`) hasn't been re-checked. Switch back to lab when it's
   free, per the 2026-07-20 note above.
4. After smoke tests pass: build `graph.py`, then one full manual pass,
   per `CLAUDE.md` steps 4–5.

---

## 2026-08-03 — Day 1 continued

**Git**
- Committed and pushed the pending changes from the previous entry:
  `config.py`, `llm_client.py` (`LLM_PROVIDER` switch), `PROJECT_PLAN.md`,
  `SESSION_LOG.md`. Commit `fb5a345`, "Add OpenAI provider switch, project
  plan", pushed to `origin/main` (`fb7843f..fb5a345`).

**Day 1 step 3 — module smoke tests (all passed)**
- Ran standalone, in order, with `LLM_PROVIDER=openai` (from `.env`):
  `personas.generate_synthetic_answer` → `evaluator.evaluate` →
  `guardrail.check_rationale` → `response_bank.get`.
- `generate_synthetic_answer("concise_confident", ...)` returned a
  well-formed `SyntheticAnswer`.
- `evaluate(...)` returned valid JSON parsed into an `Evaluation`
  (`category="GOOD"`, `valence="high"`, `arousal="medium"`,
  `confidence=0.9`) — no fence-stripping issues.
- `check_rationale(ev.rationale)` returned `passed=True, matched_patterns=[]`
  — no masking-coded language in this rationale.
- `ResponseBank().get("high", "medium")` returned a Hebrew response string
  from the seed data.
- No modifications made to any of the four modules during this test pass.
- **Still not run:** the real lab-server check (Day 1 step 1) — session
  continues on `LLM_PROVIDER=openai` per the 2026-07-20 note.

**Prompt organization decision**
- User asked whether prompts should move to a dedicated `prompts/` folder,
  or whether the upcoming LangGraph wiring changes that calculus.
  Recommendation given: LangGraph only orchestrates existing functions as
  graph nodes — it has no bearing on where prompt strings live, and a
  `prompts/` folder would be over-engineering for two prompt strings.
- However, flagged that `EVALUATOR_SYSTEM_PROMPT` (in `evaluator.py`) isn't
  just an implementation detail — it encodes the No-Masking methodology
  (content-presence-only scoring, valence/arousal decoupled from quality),
  the same category of thing `PERSONAS` and `NO_MASKING_FLAG_PATTERNS`
  already are in `config.py`.
- User approved. Moved `EVALUATOR_SYSTEM_PROMPT` from `evaluator.py` into
  `config.py`, directly above the `PERSONAS` block, with a comment marking
  it as a methodology decision (do not edit without flagging, consistent
  with the existing `NO_MASKING_FLAG_PATTERNS`/`PERSONAS` convention).
  `evaluator.py` now imports `config` and references
  `config.EVALUATOR_SYSTEM_PROMPT`. `PERSONA_SYSTEM_TEMPLATE` in
  `personas.py` was left in place — it's a formatting wrapper, not itself
  a methodology decision.
- Re-ran the full step-3 smoke test after the move to confirm nothing broke
  — all four modules passed again.
- **This change (`config.py`, `evaluator.py`) is uncommitted as of this
  entry.**

**RESUME FROM HERE (next session/restart):**
1. Decide whether to commit the `EVALUATOR_SYSTEM_PROMPT` move
   (`config.py`, `evaluator.py`) — currently uncommitted.
2. Build `graph.py` per `CLAUDE.md` step 4 (persona_answer → evaluate →
   guardrail_check → routing to review_queue or response_bank → finalize),
   logging every stage to `data/run_log.jsonl`.
3. Run one full manual pass through the graph (`CLAUDE.md` step 5) with a
   real question from `question_bank.py` and one persona.
4. Lab server (`100.110.96.82`) still not re-verified — switch back from
   `LLM_PROVIDER=openai` when it's free, per the 2026-07-20 note.

---

## 2026-09-30 — ab_test.py --session flag + a real config-loading bug found

**Code**
- Added `--session` to `ab_test.py` (default 1, unchanged from before) so it
  can draw questions from any of the 5 sessions, not just session 1. Output
  files are now named per session (`ab_test_results_session5.csv/json` etc.)
  so a re-run at a different difficulty doesn't overwrite the session-1
  results already in `data/`.
- Added `tests/test_ab_test.py` — this script had zero test coverage before.
  TDD (written test-first, watched it fail for the right reason first): two
  tests on `_build_answer_pool`'s session-selection logic, mocking only
  `personas.llm_client.call_llm` (the actual network boundary), same pattern
  `test_evaluator_retry_hint.py` already uses elsewhere in this repo.
- 71/71 tests pass.
- **Committed** (`ab_test.py`, `tests/test_ab_test.py`) — this `SESSION_LOG.md`
  entry was not, since the file already had unrelated uncommitted edits from
  before this session.

**Bug found: `.env` is never actually loaded — `LLM_PROVIDER` silently
defaults to `"lab"`**
- Hit while trying to run `ab_test.py --session 5`: every LLM call failed
  with a consistent ~16s `ConnectTimeout`.
- Investigated via the systematic-debugging process — two false leads first
  (suspected IPv6 routing, then numpy import order breaking httpx) before
  isolating the real cause: nothing in this codebase calls `load_dotenv()`
  or reads `.env` at all. `config.py`'s
  `LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "lab")` only ever sees
  real shell-exported env vars — so despite `.env` saying
  `LLM_PROVIDER=openai`, `config.LLM_PROVIDER` was actually `"lab"` the
  whole time (confirmed directly: a plain `python3 -c "import config;
  print(config.LLM_PROVIDER)"` printed `lab`, with `LLM_PROVIDER` absent
  from `os.environ`) — so `llm_client.get_client()` was trying to reach the
  lab GPU server (`100.110.96.82`, unreachable from this network right now)
  instead of OpenAI.
- Not new today — a pre-existing gap between `.env` (which looks like it
  should work) and `CLAUDE.md`'s actual documented setup (`export
  LLM_PROVIDER=openai` in the shell). Any past run that skipped the manual
  `export` was silently hitting the lab server instead of OpenAI, regardless
  of what `.env` said.
- **Not fixed** — user's call, flagged for later: for now, keep exporting
  `LLM_PROVIDER=openai` manually before running anything (`LLM_PROVIDER=openai
  python ab_test.py ...`), matching `CLAUDE.md`'s documented setup. Whether
  to add real `.env` loading (`python-dotenv`) to `config.py` is a
  project-wide config-loading decision, not a one-script fix — deliberately
  left undecided.

**ab_test.py real result (session 5, hardest, n=36 — all 6 personas × 6
questions, so every persona is actually represented, unlike the n=20
default which never reaches the last 2 personas)**
- `chi2=0.4762, p=0.7881, dof=2` — no significant difference between prompt
  variants A/B, but this time a *real* result: the original session-1 run
  in `data/ab_test_results.csv` was degenerate (every answer scored GOOD
  regardless of variant, `dof=0` — chi-square measuring nothing, not
  evidence of "no difference").
- Only the `vague_low_effort` persona (answer_ids 30-35) produced any
  NEUTRAL/BAD — all other 5 personas scored GOOD on every question, even at
  session-5 difficulty. Suggests the evaluator is far more sensitive to
  persona/answer-style than to question difficulty.
- Caveat: BAD/NEUTRAL cell counts are <5, so the chi-square p-value isn't
  fully reliable at this sample size — would need more `vague_low_effort`
  (or another weak-style persona) samples to trust this number.
- Saved to `data/ab_test_results_session5.csv`/`.json`, alongside (not
  overwriting) the original session-1 files. Not committed (data output,
  not code).

**RESUME FROM HERE (next session/restart):**
1. `.env`/`python-dotenv` decision above is still open — revisit deliberately,
   don't just silently add it.
2. If continuing PROJECT_PLAN.md Week 2 day 8 (bias check): the
   `vague_low_effort` result above is a good starting signal — consider
   more trials weighted toward weak-style personas to get past the
   small-sample-size caveat before drawing conclusions.
3. Lab server still not re-verified (same as every prior entry) — still on
   manual `LLM_PROVIDER=openai` exports.

---

## 2026-11-02 — Base44 experiment website integration (client layer)

**Context**
- The researcher-facing website "Furhat Interview Lab" was built on Base44.
  Its integration protocol (Hebrew) says the app is UI + DB only and talks
  to the Engine only through entity `status` fields: no HTTP calls from the
  app and no webhooks. The Engine polls.

**Decisions**
- **Website = frontend only** (user's decision). All logic moves to the
  Engine: creating a session's 6 Turns, LLM evaluation, emotion choice,
  guardrails, building and sending RobotCommands, PE grading, and the
  semantics of Mock/Simulation/Live. The app only displays data, saves what
  the researcher types, and changes status on button clicks.
- Rewrote the Base44 builder prompt around that. It added `engine_processing`
  (turn claim) and `awaiting_pe_check` (Engine grades the participant's PE
  answer, matching `pe_check.py`) statuses, plus `evaluation_category`,
  `evaluator_confidence`, `claimed_by`/`claimed_at`, `engine_error`,
  `participant_pe_answer`, `pe_explanation`, `Persona.furhat_face`/
  `furhat_voice`, `LLMModel.engine_key`, `RobotCommand.sequence`, and a
  single `EngineHeartbeat` (`key = "engine-main"`).
- **Did not install `@base44/sdk`.** It's an npm package that Python can't
  import. Wrote a REST client with `requests` instead (user agreed).

**Built**
- `base44_client.py`: `list_records`, `get_record`, `create_record`,
  `update_record`, and `claim()` (compare-and-set via `update-many`). Raises
  `Base44Error`.
- `config.py`: `BASE44_BASE_URL`, `BASE44_APP_ID`, `BASE44_API_TOKEN`,
  `BASE44_TIMEOUT`.
- `tests/test_base44_client.py`: 6 tests, mocking `requests.request`.
  Full suite: 111/111 pass.
- Design doc:
  `docs/superpowers/specs/2026-11-02-base44-lab-app-integration-design.md`.

**Security incident (fixed in code, token rotation pending)**
- The real Base44 token and App ID had been hardcoded as `os.environ.get`
  defaults in `config.py`, and the `BASE44_BASE_URL` had been changed to the
  website domain (`furhat-insight-lab.base44.app`), which is not the API
  host. Moved both values into `.env` (gitignored), reset the defaults to
  `""`, and restored the URL to `https://app.base44.com/api/apps`. The token
  value appeared in the Claude session transcript, so **it should be
  regenerated on Base44's API page and replaced in `.env`.** It was never
  committed.

**Verified live (read-only)**
- `list_records('EngineHeartbeat')` returned
  `[{'key': 'engine-main', 'last_seen': None, ...}]`. That confirms auth, the
  base URL, and that `v2/list` returns a bare list.
- Not yet verified live: `PUT` update, `POST` create, and `update-many`
  filtering on `id` (which `claim()` depends on).

**Later the same day: MVP worker**
- Decisions: the worker runs on the user's laptop, started by hand only on
  experiment days (light: about 2 s polls while a session is Running, about
  10 s when idle). If the robot is closed during a Live session, the command
  waits 60 s, then errors and the flow continues (the robot will normally
  always be open). The 4 extra emotions get added to the website's enum
  (pending on the Base44 side). Priority is to see the real flow work first
  and defer the rest.
- Live-verified writes: `update_record` (PUT) works, and `update-many`
  filtering on `id` works, so `claim()` is verified (wrong status → False).
- Built `engine_worker.py` and `tests/test_engine_worker.py` (9 tests with
  an in-memory fake Base44). Suite: 120/120. One live pass: heartbeat sent,
  robot not connected, no Running sessions.

**RESUME FROM HERE (next session/restart):**
1. Regenerate the Base44 token and update `.env`.
2. Ask Base44 to add EXCITED/BORED/SLEEPY/CALM to `Turn.target_emotion`.
3. Real end-to-end run: open the Furhat skill, run
   `python engine_worker.py`, create a Live session on the website, and walk
   one turn through every status.
4. Open methodology questions are listed in the design doc (`Partial` PE,
   11→8 emotion mapping, `expression_level`, `proposed_feedback`,
   Baseline/Post/Followup question sets). These need the user's decision
   before the worker's evaluation step.

---

## 2026-11-07 — Robot foundations (interview-skill, personas, model registry)

**Built** (plan `docs/superpowers/plans/2026-11-04-robot-foundations.md`)
- `furhat_client.listen()` and `set_persona(character, voice, language)`;
  both never raise. New config: `LISTEN_TIMEOUT_MS=10000`,
  `LISTEN_END_SIL_MS=3000`, `LISTEN_MAX_SPEECH_MS=120000`.
- Model registry: `config.LLM_PROVIDERS` / `LLM_MODELS` in the
  "ADD NEW LLM MODELS HERE" block, `model_registry.py` (`sync_to_base44`,
  `model_for_session`), and `llm_client.model_override()`.
- `engine_worker.py` syncs models at startup, applies the Persona's face and
  voice once per Live session, and runs turns under the session's model.
- `furhat-emotion-study` (branch `interview-skill`): new `emotion-library`
  and `interview-skill` modules; bridge on `localhost:8765` with `/say`,
  `/react`, `/listen`, `/persona`, `/health`. `EmotionSkill` no longer hosts
  the bridge. Fixes: Init goes straight to `LiveSession` (no `isVirtual`
  NPE), the persona voice is no longer overridden per utterance, timed-out
  `/persona` and `/listen` events are cancelled and skipped.
- Test suite: 141 passed.
- Open issue: `EmotionSkill-all.skill` is about 36 MB, over the launcher's
  30 MB limit (pre-existing). `InterviewSkill-all.skill` is about 29.5 MiB.
- Decisions 14 and 15 added to the autonomous-conversation spec.

**RESUME FROM HERE (next session/restart):**
1. Run the Task 3 feasibility gate on the robot (plan
   `docs/superpowers/plans/2026-11-04-robot-foundations.md`, Task 3). Also
   confirm the InterviewSkill loads in the launcher at 29.5 MiB and that
   `/listen` with speech and `/persona` work (static-only exclude
   verification).
2. Record the results in the spec.
3. Then write Plan 2.

---

## 2026-11-08 — Plan 2: autonomous robot conversation built

- Live sessions now run through `conversation_flow.py` (small talk,
  questions, listening, reactions, PE, feedback) via
  `engine_worker.run_live_session`; Simulation/Mock keep the typed-answer
  flow. Each proposal records `engine_model`. Heartbeat is on its own thread.
- Test suite: 235 passed, 5 skipped (smoke tests need `RUN_LLM_SMOKE=1`).

**Open items:**
- P3: the researcher must approve the masculine Hebrew guardrail forms
  ("נשמע לחוץ", "נראה לחוץ", "נשמע בטוח", "ארוך מדי", "קצר מדי").
- P11: the PE word lists and fallback lines await researcher review.

**RESUME FROM HERE:** Task 11, the live check. Stop the skill, rebuild the
`.skill` (`interview-skill/rebuild.sh`), load it, then run
`python engine_worker.py` against a Live session with the robot.

---

## 2026-11-09 → 2026-11-13 — Physical robot, new website, OpenRouter

**Done**
- First runs on the physical Furhat (172.19.94.255): the skill on the Mac
  connects to the robot's broker; the speaker works. Blocker: the persona
  voices (AvriNeural/HilaNeural) don't exist on the robot ("Cannot find the
  specified voice").
- ElevenLabs path: `LiveSession.kt` sends `ELEVENLABS_API_KEY` (from `.env`)
  to the robot with `ActionConfigElevenlabs` at startup. Edited, not yet
  rebuilt or committed.
- Personas: Daniel = face Jamie + AvriNeural, Noa = face roni-women (custom
  face) + HilaNeural.
- New website (Claude-built, Supabase): `supabase_client.py` (same functions
  as `base44_client.py`, PostgREST via `requests`, token refresh, 401 retry,
  compare-and-set `claim`), `lab_db.py` picks the backend by `LAB_BACKEND`.
  On Supabase the Engine skips the LLMModel sync and Turn creation (the site
  owns both). Verified read-only against the live site.
- OpenRouter + models split by task: `LLM_JUDGMENT_MODEL=openai/gpt-5`,
  `LLM_LINES_MODEL=openai/gpt-oss-20b`. `call_llm(role=...)`; reasoning
  models get a thinking budget; GPT-5 gets no temperature. Real calls:
  evaluator 5.8 s, emotion 3.2 s, PE check 3.1 s, a line 0.9 s.
- `engine` shell alias runs the worker (documented in CLAUDE.md).
- Test suite: 269 passed, 5 skipped.

**Approved, not started (robot fix bundle)**
1. `/say` and `/react` block until speech ends (the robot transcribed itself).
2. No slash forms in generated lines; render them by gender.
3. Fallback voice when the persona voice is missing.
4. Return to neutral after each reaction.
5. Listening nods at pauses (`backchannel`, `Persona.listening_behavior`).

**RESUME FROM HERE:** rebuild the skill with the ElevenLabs change (stop the
skill first), pick an ElevenLabs Hebrew voice and set it on the personas,
then start the robot fix bundle. Run `ab_test.py` on GPT-5 before
collecting data.

## 2026-11-14 — Reactions, free small talk, listening behaviour, literature

**Built (Engine)**
- Emotion reactions: intensity 2-3 only (1 is raised to 2), and the
  classifier is told which emotions this session already showed, to vary.
- Reaction sentence: `reaction_line.py` writes it from the classified emotion
  and the answer's content, in both speakers' gender; never names the emotion
  (PE) or grades the answer. Replaced the placeholder response-bank lines
  ("התשובה הזו קצת חסרה לי מידע חשוב" on every negative emotion).
- Free small talk: after each small-talk answer the robot may ask up to 3
  follow-ups (`SMALL_TALK_MAX_FOLLOW_UPS`); the conversation is saved in
  `turns.small_talk_log` (jsonb, added on the website). Prompt aims to lower
  stress and build confidence.
- `LLM_LINES_MODEL=openai/gpt-5` (gpt-oss-20b broke Hebrew gender and words).
- Listening gestures: generated offline by GPT-5 within allowed "listening
  muscles", validated, de-duplicated, reviewed on the robot
  (`gesture_review_app.py`). First review: 17 kept, 10 dropped, 13 left.
- `/listen` takes `backchannel` (off for the PE answer); `/react` waits until
  the reaction is over.

**Built (interview-skill)**
- Reaction: emotion held 2 s silently, sentence, then a complete
  `NeutralReset` (4 missing params added). Verified on the robot.
- Gaze aversion at sentence starts while speaking; listening gestures from
  the approved JSON bank, at short pauses (`onInterimResponse`, 0.7 s) plus
  one during long speech (12-15 s) - pause trigger compiled, not yet tested
  on the robot.

**Literature** (`docs/literature/literature_review.xlsx`): Expressive Furhat
(HRI 2026), Xpress (arXiv 2025), Holistic LLM behaviour (HRI 2026), Fujii &
Minato (Sci. Rep. 2026).

**Open questions for the advisor (Mon 16.11)**: emotion in the voice
(pitch/rate/volume, Azure voices only); slight smile and brow furrow while
listening (No-Masking / PE risk).

- Test suite: 309 passed, 5 skipped.

**RESUME FROM HERE:** rebuild the skill (pause-triggered listening gestures)
and test them live; finish reviewing the 13 listening gestures (Tue 17.11);
Py-Feat check of the 33 expressions (Tue 17.11). Run `ab_test.py` on GPT-5
before collecting data.

## 2026-11-16 — Hebrew voice: ElevenLabs

**Decided**
- Female voice (Noa): ElevenLabs "Danit - Natural Israeli Hebrew"
  (`s0T0DT6EAPeX57MQpn3I`). Male voice
  (Daniel): ElevenLabs "Erez - Natural Israeli Hebrew"
  (`AZzja2JCoYeMe9vDQBll`). Both added to the account of the `.env` key (new key, Starter plan) via the
  API, 2026-11-16.
- Option 1 (now): use the ElevenLabs voice through Furhat as is. Checked in
  furhat-commons 2.9.3: `ElevenlabsConfig` carries only the API key (no
  stability / similarity / speed / style), and `ElevenlabsVoice` ignores
  `prosody` (pitch/rate/volume) and `emphasis` - it returns the text
  unchanged. So no voice parameters reach the robot on this path.
- Option 2 (later, if rate/emotion in the voice is needed): the Engine calls
  the ElevenLabs API itself (speed, stability, style per line, maybe per
  emotion), and the robot plays the audio. Costs: added latency per line;
  lip sync with external audio not yet checked. Effort: medium-high.
- Note: `.env` has `LLM_LINES_MODEL=openai/gpt-5` (CLAUDE.md says
  `gpt-oss-20b`) - decide which one.

**RESUME FROM HERE:** find the names the robot lists them under once the ElevenLabs key
is sent, set them as Noa's / Daniel's `furhat_voice`, add them to
`config.VOICE_GENDERS` (female / male), test on the robot.

**Voice switch: Google Chirp 3 HD (decided 2026-11-16, later the same day)**
- ElevenLabs on the virtual robot: the key now reaches the robot (the skill
  falls back to reading `ELEVENLABS_API_KEY` from `conversation_engine/.env`,
  uncommitted in furhat-emotion-study), but `furhat.setVoice(language, name)`
  with "Danit - Natural Israeli Hebrew" returns ok and keeps the old voice.
- Compared 11 Hebrew samples (Google Chirp 3 HD / WaveNet, ElevenLabs v3 / v4
  / v4 Turbo, OpenAI gpt-4o-mini-tts) on one hard sentence. Chosen:
  `he-IL-Chirp3-HD-Charon` (male, Daniel) and `he-IL-Chirp3-HD-Aoede`
  (female, Noa). About 1.5 s per sentence. Key: `GOOGLE_TEXT_TO_SPEECH_API_KEY`.
- Furhat has no Google TTS voice, so this is option 2: generate the audio
  ourselves and have the robot play it. Gemini-TTS (prompt-steerable) needs
  Vertex AI permissions (403 with the current key) - later option.
- Built (interview-skill, uncommitted, compiles, skill tests pass, not yet
  heard on the robot): `tts/GoogleTts.kt` synthesizes each sentence in
  parallel (LINEAR16 16 kHz WAV), caches it in `~/.interview-skill/tts-cache`
  by (voice, text), and serves it on a separate port 8766 (`/audio/`) that
  the robot plays as `Audio(url, text, speech = true)`. A persona voice that
  looks like a Google name (`he-IL-Chirp3-HD-Aoede`) switches to it; in a
  reaction, synthesis runs during the 2 s hold. Google error / > 8 s -> the
  robot's own voice. `tts/EngineEnv.kt`: keys from the environment, else
  from `conversation_engine/.env` (the launcher starts the skill without it).
  Physical robot: set `TTS_AUDIO_HOST` (the Mac's address) in `.env`.
- Engine: `config.VOICE_GENDERS` += Charon (male), Aoede (female). 310
  passed, 5 skipped.

**RESUME FROM HERE:** start the virtual robot, load the skill, hear Aoede via
`/persona` + `/say`; then switch the site's personas (Noa -> Aoede, Daniel ->
Charon); check lip sync; then the physical robot (`TTS_AUDIO_HOST`).

## 2026-11-17 — Expression validation (Py-Feat + MediaPipe), Fear/Disgust retune

All in `furhat-emotion-study/expression_validation/` (README = full method,
decisions and results; commits 3d61a19 .. cbb4b37 in that repo).

**Done**
- Recorded the 12 missing clips (Excited, Bored, Sleepy, Calm x L1-L3): all
  33 expressions now have clips. Recording fixes in EmotionSkill
  (`RECORD_ONLY_MISSING`, `AUTO_RECORD`, OBS never moves a file it didn't
  record).
- Check 1, Py-Feat (researcher decision: hold-window average, baseline
  subtracted): recognition of the 6 basic emotions 56% -> **67%** after the
  retune; **every L3 recognised**. Surprise and Happiness 3/3.
- Check 2, fidelity (MediaPipe's 52 ARKit blendshapes vs. the commanded
  values parsed from `EmotionsLibrary.kt`, Spearman): eye blink, brow raise,
  eye widen, jaw open, smile, frown track; **nose wrinkle, cheek squint,
  dimples, lip press are never visible on this face**.
- Retuned Disgust (mouth-led, since the nose wrinkle doesn't render) and Fear
  (ARKit brow-down + JAW_OPEN). Disgust L3: anger -> disgust (0.69).

**Limitation (thesis): Fear vs. Surprise on the Furhat face.** AU04 barely
rises (brow-down and inner-brow-raise cancel) and AU20 only fires with an
open jaw, so Fear L2 reads as surprise (0.30 vs. 0.46) and Fear L3 only
narrowly as fear (0.44 vs. 0.37). Three Fear L2 retunes tried; the third was
worse and was reverted.

**Decision (researcher, option C):** document the limitation, and in PE
grading a SURPRISE word for a FEAR target is **Partial** (one direction only;
`prompts/pe_check_prompt.py`, test in `tests/test_pe_check.py`).
Not done (option B, declined): forcing Fear to intensity 3.

- Build note: VS Code's Red Hat Java extension imported the Furhat Gradle
  project with Java 25, upgraded the wrapper to 9.7.1 and overwrote
  `emotion-library.jar` with an empty jar. Disabled for that folder in
  `furhat-emotion-study/.vscode/settings.json`; wrapper restored to 8.9.
- Test suite: 311 passed, 5 skipped.

**RESUME FROM HERE:** the researcher looks at the new Fear/Disgust on the
robot (the human eye is the final judge, not Py-Feat) and reviews
`expression_validation/config.py` EXPECTED_AUS; approve the opening-script
design doc (`docs/superpowers/specs/2026-11-17-fixed-opening-script-design.md`);
the API keys / Google TTS voice from 2026-11-16 (deferred to "tomorrow").

## 2026-11-17 (afternoon) — Vocal features review, scripted opening (Engine), two-grade PE, friend debrief

**Literature / voice**
- `docs/literature/vocal_emotion_features.md`: 16 papers, 4-7 acoustic features
  per robot emotion. PDFs that were free are in `תואר שני/מאמרים/זיהוי רגשות בקול`
  (4 of 16) with a list file of all of them.
- Chirp 3 HD control (measured): rate and loudness work; pitch only via SSML,
  imprecise; no pitch range / voice quality. Researcher: pitch within +/-1
  semitone, tempo carries the emotion; approved for Noa so far: bored, happiness,
  surprise, excited; Charon kept for Daniel. Samples: `~/Desktop/emotion_voice_samples/`.
  Not wired into the robot yet.

**Built (plan `docs/superpowers/plans/2026-11-17-opening-script-and-friend-debrief.md`)**
- Website (branch `friend-debrief`, commit eff57d6): migration
  `20261118000000_debrief_pe.sql` (emotion_trigger, pe_reason_result,
  pe_reason_explanation, debrief_moments; phase Debrief), a Debrief turn at the
  end of every plan, friend-toned PE question, reason grade + moments on screen.
- Engine: scripted opening (bridge + fixed question, then small talk);
  2-3 sentence acknowledgement; emotion trigger; reason grade; `debrief.py`.
- Test suite: 355 passed, 5 skipped. Website: plan tests 8/8, DB checks pass.

**Not done / needs the researcher**
- Apply the migration on Supabase and deploy the website branch (the Engine
  writes the new columns; before that, Live sessions on the new code fail).
- No live run yet (needs the above).
- Approve the per-turn PE question wording; choose the friend's face/voice
  (`FRIEND_FACE` / `FRIEND_VOICE` in `.env`).
- The No-Masking guardrail misses "sounded nervous" (it catches "seemed
  nervous"); the pattern list is methodology-locked, so not changed.
- Backlog: `docs/tasks/2026-11-17-feedback-agent-and-interviewer-agent.md`.

**RESUME FROM HERE:** merge/deploy the website branch + migration, then a live
Short session on the virtual robot (opening bridge, longer ack, one PBDI turn
with reason grade, debrief with the friend).

## 2026-11-17 (evening) — Folders organized (researcher's approval)

- Project: `docs/README.md` (a map of all documents), `prompts/README.md`
  (every prompt, what it does, who uses it, which are locked). Website-builder
  prompts moved from `docs/superpowers/specs/base44-prompts/` to
  `docs/website-prompts/`. Large untracked data (mit dataset, archive.zip,
  הקלטות-יובל) moved into the project's own `data/`, still gitignored
  (researcher: data belongs inside the project that needs it, no shared data
  folder); `credentials/` stays (the gitignored place for the STT key).
- Mac, `תואר שני/`: `מאמרים/` with one subfolder per topic (the 7 paper
  folders), `תזה/` (+ the ROMAN talk, מאמר IEEE), `בירוקרטיה/` on its own,
  `פרויקטים/` (furhat, mpi2furhat, srt, tutorials-main). The website folder
  `University/base44/` was renamed `University/lab-website/` (the repo inside
  is still `furhat-insight-lab`). Code didn't reference any of the moved
  folders.

