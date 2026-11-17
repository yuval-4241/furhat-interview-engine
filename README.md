# furhat-interview-engine — Furhat job-interview training (thesis)

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
| [**furhat-interview-engine**](https://github.com/yuval-4241/furhat-interview-engine) (this one; local folder `conversation_engine`) | Python: the conversation, the LLM calls, evaluation, PE grading, the friend debrief | `~/Documents/GitHub/conversation_engine` |
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
engine                        # run the Engine worker: python -m engine.engine_worker (alias, see CLAUDE.md)
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

## Folders — what is where

Each folder has its own README listing every file and what it does.

| Folder | What |
|---|---|
| [`engine/`](engine) | The Live session: the worker loop, the turn state machine, the robot's lines, emotion, PE grading, the friend debrief |
| [`connectors/`](connectors) | Connections to the outside: LLM providers, the website's database, the robot, speech recognition |
| [`evaluation/`](evaluation) | Content-only evaluation, the No-Masking guardrail, synthetic candidates, the research pipeline |
| [`scripts/`](scripts) | Things you run: batch runs, A/B test, bias check, listening gestures (`python -m scripts.<name>`) |
| [`apps/`](apps) | Streamlit screens (`streamlit run apps/<name>.py`) |
| [`prompts/`](prompts) | Every LLM prompt, and which are methodology-locked |
| [`data/`](data) | Inputs (`seeds/`) and working data; large datasets gitignored |
| [`results/`](results) | Outputs of the research scripts |
| [`tests/`](tests) | The test suite |
| [`docs/`](docs) | Design documents, plans, backlog, literature (map: `docs/README.md`) |
| `config.py` | All settings: models, thresholds, paths, voices, the No-Masking word list |
| `credentials/` | Gitignored: the speech-recognition key file |
