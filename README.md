# Conversation Engine — Furhat job-interview training (thesis)

The "brain" of a social robot (Furhat) that runs practice job interviews with
autistic adults. The robot asks questions, listens, reacts with an emotion on
its face, voice and words, and then asks the participant what it felt and why
(perspective taking, PE). At the end, a "friend" character asks the
participant how the interview went.

**The thesis's hard rule — No-Masking:** the system judges what the
participant *says* (content), never *how* they say it (tone, eye contact,
fluency, structure). `guardrail.py` and `config.NO_MASKING_FLAG_PATTERNS`
enforce and audit this.

## The three repos

| Repo | What | Where |
|---|---|---|
| **conversation_engine** (this one) | Python: the conversation, the LLM calls, evaluation, PE grading, the friend debrief | `~/Documents/GitHub/conversation_engine` |
| [furhat-emotion-study](https://github.com/yuval-4241/furhat-emotion-study) | Kotlin: the Furhat skill (`interview-skill`), the 33 facial expressions, their validation | `~/Documents/GitHub/furhat-emotion-study` |
| [furhat-insight-lab](https://github.com/yuval-4241/furhat-insight-lab) (private) | The lab website (React + Supabase, on Vercel): sessions, participants, transcripts, export | `~/Documents/Workspace/University/lab-website/furhat-insight-lab` |

The website never calls the Engine: the Engine polls the website's database
for work and writes the results back.

## How a Live session runs

```
opening script (5 fixed questions, a short generated reaction before each)
  -> main questions: robot asks -> listens -> 2-3 sentence acknowledgement
     PBDI questions: emotion on face + voice + words -> PE question
        -> grade: emotion (Correct/Partial/Wrong) + reason (Matches/Partly/No/Missing)
        -> the robot reveals what it felt
  -> closing small talk
  -> friend debrief: another face, open questions; the moments the participant
     tells are extracted and graded
```

## Quick start

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in the keys (never commit .env)

pytest tests/ -q              # the test suite
engine                        # run the Engine worker (shell alias, see CLAUDE.md)
```

A Live session also needs the robot (Furhat launcher + `InterviewSkill-all.skill`)
and the website (New Session). Step by step: `CLAUDE.md`.

## Documents

| Document | What it is for |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Rules for working on the project, full architecture, commands |
| [`SESSION_LOG.md`](SESSION_LOG.md) | Running log of every work session: what was done, decisions, where to resume |
| [`PROJECT_PLAN.md`](PROJECT_PLAN.md) | Week-by-week plan |
| [`docs/README.md`](docs/README.md) | **Map of all documents**: design documents, implementation plans, backlog, literature |
| [`docs/superpowers/specs/`](docs/superpowers/specs) | Design documents (what was built and why, with the researcher's decisions) |
| [`docs/superpowers/plans/`](docs/superpowers/plans) | Implementation plans |
| [`docs/tasks/`](docs/tasks) | Backlog: ideas that need options and academic grounding first |
| [`docs/literature/`](docs/literature) | Literature table, reviews (e.g. acoustic features of emotions in the voice) |
| [`docs/website-prompts/`](docs/website-prompts) | Prompts given to the website builder |
| [`prompts/README.md`](prompts/README.md) | **Every LLM prompt**, what it does, which module uses it, which are methodology-locked |

Papers used in code or design decisions, and for what purpose:
[Notion — thesis paper using in code](https://app.notion.com/p/thesis-paper-using-in-code-41b0701ff8ee8009828ef5ac7705f21c).

## Files — what each one does

### The Live session (robot + website)

| File | Role |
|---|---|
| `engine_worker.py` | The main loop: polls the website, runs sessions, heartbeat, applies the robot persona |
| `conversation_flow.py` | The turn state machine: speak, listen, react, PE question, feedback, debrief |
| `small_talk.py` | Opening/closing small talk, the reaction before each scripted line, follow-ups |
| `acknowledgement.py` | The 2-3 sentence reply after a main answer (content only) |
| `emotion_classifier.py` | Picks the robot's emotion + intensity from the answer, and records what triggered it |
| `reaction_line.py` | What the robot says with its emotional reaction (never names the emotion) |
| `pe_check.py` | Grades the PE answer: emotion and reason |
| `pe_feedback.py` | The robot's line revealing what it felt and why |
| `debrief.py` | The friend debrief: open questions, goodbye, moment extraction |
| `hebrew_gender.py` | Says Hebrew slash forms ("ספר/י") in the participant's gender |
| `llm_line.py` | Shared helper: one spoken line from the LLM, cleaned, with a fallback |
| `furhat_client.py` | Talks to the robot's skill: say, react, listen, persona |
| `session_flow.py` | Which questions get the full reaction + PE cycle |
| `worker_common.py` | Shared worker id, timestamps, log lines |

### Website and models

| File | Role |
|---|---|
| `lab_db.py` | Picks the website client (`LAB_BACKEND` in `.env`) |
| `supabase_client.py` | The website's database (Supabase) — current |
| `base44_client.py` | The old Base44 website — still reachable |
| `llm_client.py` | The only file that calls the LLM provider (OpenAI / OpenRouter / lab server) |
| `model_registry.py` | Keeps the website's model list in sync with `config.LLM_MODELS` |
| `config.py` | All settings: models, thresholds, paths, voices, No-Masking word list |

### Evaluation and research tools

| File | Role |
|---|---|
| `evaluator.py` | Content-only evaluation of an answer (GOOD/NEUTRAL/BAD + valence/arousal) |
| `guardrail.py` | No-Masking guardrail: flags style-bias language |
| `schemas.py` | Validates the evaluator's JSON before it is trusted |
| `personas.py` | Synthetic candidates in different communication styles (bias probe) |
| `graph.py` | The evaluation pipeline as a LangGraph state machine |
| `review_queue.py` | Low-confidence or flagged items for human review |
| `run_demo.py` | Batch run: every persona x every question |
| `ab_test.py` | A/B test of two evaluator prompts (chi-square, SciPy) |
| `bias_check.py` | No-Masking bias check between two personas |
| `question_bank.py` | Loads the interview question set |
| `response_bank.py` | The older valence/arousal reply bank (kept for the research pipeline) |
| `robot_bridge.py` | Sends a reaction to the robot from the research pipeline (off by default) |
| `listening_gestures.py`, `gesture_review_app.py` | Generate and review the robot's listening gestures |

### Demos

| File | Role |
|---|---|
| `demo_app.py` | Streamlit advisor demo of the evaluation pipeline |
| `interaction_app.py`, `interaction_log.py`, `stt.py`, `run.sh` | The earlier live demo (Streamlit + Google speech recognition) |

### Folders

| Folder | What |
|---|---|
| `prompts/` | All prompt text (see its README) |
| `tests/` | The test suite (pytest, with fake website + fake robot in `tests/fakes.py`) |
| `data/` | Question/response banks, run logs, test results; large datasets (`mit dataset`, recordings) are here but gitignored |
| `results/` | Batch-run outputs |
| `credentials/` | Gitignored: the speech-recognition key file |
