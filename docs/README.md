# Documents — map

Where everything about the project is written, and what each kind of
document is for.

## Progress and decisions (read these first)

| Where | What |
|---|---|
| `../SESSION_LOG.md` | Running log of every work session: what was done, decisions, **RESUME FROM HERE** |
| `../PROJECT_PLAN.md` | Week-by-week plan |
| `../CLAUDE.md` | Rules for working on the project, architecture, commands |
| `tasks/` | Backlog: ideas that still need options and academic grounding before a design (e.g. the feedback agent and the interviewer agent) |

## Design and implementation

| Where | What |
|---|---|
| `superpowers/specs/` | **Design documents** — what is built and why, with the researcher's decisions. Named `YYYY-MM-DD-<topic>-design.md` |
| `superpowers/plans/` | **Implementation plans** — the step-by-step plan that built each design |
| `unified_architecture.md` | Gap analysis against the broader academic pipeline |
| `website-prompts/` | Prompts given to the website builder (Base44 era) |

| Date | Design document | Plan |
|---|---|---|
| 2026-08-09 | Schema guard + style-leakage score | `plans/2026-08-09-schema-guard-and-style-leakage-score.md` |
| 2026-08-11 | `2026-08-11-consistency-check-design.md` | `2026-08-11-consistency-check-routing.md` |
| 2026-08-11 | `2026-08-11-robot-reaction-bridge-design.md` | — |
| 2026-08-16 | `2026-08-16-emotion-first-classification-design.md` | `2026-08-16-emotion-first-classification.md` |
| 2026-08-19 | `2026-08-19-emotion-classifier-variety-design.md` | `2026-08-19-emotion-classifier-variety.md` |
| 2026-10-28 | `2026-10-28-live-interaction-demo-design.md` | `2026-10-28-live-interaction-demo.md` |
| 2026-11-02 | `2026-11-02-base44-lab-app-integration-design.md` | — |
| 2026-11-04 | `2026-11-04-autonomous-robot-conversation-design.md` | `2026-11-04-robot-foundations.md`, `2026-11-08-autonomous-conversation.md` |
| 2026-11-17 | `2026-11-17-fixed-opening-script-design.md`, `2026-11-17-friend-debrief-pe-design.md` | `2026-11-17-opening-script-and-friend-debrief.md` |
| 2026-11-18 | `2026-11-18-cue-to-emotion-mapping-design.md` | — |

## Literature

| Where | What |
|---|---|
| `literature/literature_review.xlsx` | The literature table |
| `literature/vocal_emotion_features.md` | Review: acoustic features per emotion (16 papers) |
| Notion: [thesis paper using in code](https://app.notion.com/p/thesis-paper-using-in-code-41b0701ff8ee8009828ef5ac7705f21c) | Every paper used in code or a design decision, and for what purpose |
| `~/Documents/Workspace/University/תואר שני/מאמרים/` | The PDFs, by topic |

## Prompts

`../prompts/README.md` — every LLM prompt, what it does, which module uses it,
and which are methodology-locked.

## Elsewhere

- Robot expressions and their validation: `furhat-emotion-study/expression_validation/README.md`
- Website contract with the Engine: `furhat-insight-lab/ENGINE_INTEGRATION.md`, `migration/ENGINE_API.md`
- Large data this project needs, kept out of git: `../data/mit dataset/`, `../data/archive.zip`, `../data/הקלטות-יובל/`
- The website repo: `~/Documents/Workspace/University/lab-website/furhat-insight-lab`
- Other projects (Furhat tools, srt, tutorials): `~/Documents/Workspace/University/תואר שני/פרויקטים/`
