# Two new agents — open tasks (to deepen before design)

Date: 2026-11-17. Status: **backlog**: each task needs options worked out
and academic grounding before it gets a design doc
(`docs/superpowers/specs/`). Nothing here is decided except what the
researcher said, quoted as such.

Related, already approved: the friend debrief and two-grade PE
(`docs/superpowers/specs/2026-11-17-friend-debrief-pe-design.md`), the vocal
features review (`docs/literature/vocal_emotion_features.md`).

---

## Task A — Feedback agent (end of session)

### What the researcher asked for

A **separate agent** whose job is feedback to the participant at the end of
the conversation. It looks at each reaction of the robot and at how the
participant related to it, then asks about specific moments, e.g.:

> Agent: "What do you think I felt when you told me you had been in prison?"
> Participant answers.
> Agent: "Yes, I felt surprised, so my voice changed and I asked more
> questions, because I started to have doubts."

…and gives corrective feedback when the participant's reading was off.

### What it needs as input (already recorded, or recorded once the plan is built)

Per turn: the robot's emotion + intensity, the **trigger** (what in the
answer caused it), the spoken reply, the voice profile used, the
participant's PE answer and its two grades; from the debrief: the moments
the participant mentioned and their grades.

### Open questions (each changes the design)

1. **Who speaks.** The examples are in the interviewer's first person ("I
   felt…"), but the researcher decided (2026-11-17) that after the friend
   appears the robot never switches back to the interviewer's face. Options:
   (a) the friend relays the interviewer's view in the third person ("I think
   he was surprised because…"); (b) a third character, a "coach", with its own
   face, who explains in the interviewer's name; (c) revisit the decision and
   let the interviewer come back for the feedback only.
2. **Which moments to ask about.** All reactions, the strongest, the ones the
   participant misread in the PE step, or the ones missing from the debrief
   story? A cap (2–3?) to keep it short.
3. **Ask first, then tell** (as in the example) vs. tell directly. Asking
   again repeats the per-turn PE question; is the repetition the point
   (consolidation) or a burden?
4. **What "feedback when the answer is not good" means.** Feedback on the
   participant's *reading of the robot* (perspective taking) only — or also
   on the interview answer itself? The latter collides with No-Masking if it
   touches delivery; content-only feedback on answers is a separate decision.
5. **Explaining all three channels** — face, voice, words ("so my voice
   changed and I asked more questions") requires knowing which channels
   actually carried the emotion on that turn (voice only for some emotions).
6. **Sensitive disclosures.** The example (prison) is a sensitive disclosure.
   How does the agent talk about it without judging the participant? This
   needs an ethics line in the protocol and possibly IRB wording.
7. **Relation to the per-turn feedback** — does the end feedback replace it
   (the researcher's "future" direction) or come on top?

### Implementation options to work out

- **A1. One LLM call per moment**: inputs above -> question; participant
  answer -> grade (reuse `pe_check`) -> explanation + corrective line.
- **A2. A planner + a speaker**: one call picks the moments and the order
  (a short feedback plan), then a per-moment conversation; easier to audit.
- **A3. Templates with slots + LLM only for wording**: most controllable,
  most uniform across participants (good for the experiment), least natural.

### Academic grounding to look for (directions, not yet checked)

- Feedback effectiveness: Hattie & Timperley (2007), "The power of
  feedback"; Kluger & DeNisi (1996), feedback intervention theory.
- Debriefing after simulation: e.g. Fanning & Gaba (2007) on debriefing in
  simulation-based learning; structured debriefing models.
- Perspective-taking / theory-of-mind training in autistic adults, and how
  feedback is given there.
- Job-interview training with virtual agents/robots that give feedback:
  VR-JIT (Smith et al.), ViTA, and the robot-mediated interview training
  papers already in `תואר שני/מאמרים/` (by topic).
- Robots explaining their own emotions / explainable HRI.

---

## Task B — Interviewer reasoning agent (non-scripted questions)

### What the researcher asked for

An agent that **reasons like an interviewer** about the candidate's answer
to the harder questions — every question that is not in the opening script.
During an interview, an interviewer runs many scenarios in their head: is
this candidate better than others, could this be a problem, would they be
good for the team, do they fit the company's values. The same agent
**generates the reaction in all three channels**: words, voice and face.

### Open questions (each changes the design)

1. **No-Masking — the main risk.** "Better than others", "fit for the
   team", "fits our values" are exactly where interviewer bias against
   autistic candidates lives (culture-fit judgements often rest on delivery
   and social style). The thesis's hard constraint is that evaluation judges
   content only. The reasoning must be restricted to the content of the
   answer, with its own guardrail and audit — or framed as the *robot's
   simulated reaction* that is never scored or fed back as a judgement.
   This needs the researcher's (and probably the advisor's) decision first.
2. **Relation to what exists.** Today: `evaluator.py` (content category,
   VA stance), `emotion_classifier.py` (emotion + trigger), `reaction_line.py`
   (words), the face library and the voice profiles. Does the new agent
   replace the classifier and reaction line, sit on top of the evaluator, or
   replace both?
3. **What the interviewer knows.** "Fits the company's values" needs a role
   and a company: a fixed fictional job description per session type? Same
   for all participants (comparability)?
4. **Researcher approval.** PBDI turns stop for the researcher's Approve
   today; does the agent's output (reasoning + 3 channels) keep that gate?
5. **Latency.** Reasoning + three channels must still fit the 2-second hold
   window or close to it.
6. **Logging the reasoning** for the thesis: the scenarios the agent
   considered, per turn, as data (and as the input to Task A's explanations).

### Implementation options to work out

- **B1. One structured call:** reasoning (scenarios) + emotion + intensity +
  reply + voice profile in one JSON; one place to guard and log.
- **B2. Pipeline:** reasoning call -> emotion/intensity (classifier
  conditioned on the reasoning) -> words, voice, face from the chosen
  emotion (today's emotion-first path); keeps each piece testable.
- **B3. Two minds:** a hidden "assessment" stream that is logged only, and a
  separate "expression" stream that drives the robot, so the assessment
  never reaches the participant directly (a possible No-Masking safeguard).

### Academic grounding to look for (directions, not yet checked)

- Interviewer cognition and the interview process: Dipboye's model of the
  employment interview; structured interviews (Campion, Palmer & Campion
  1997; Levashina et al. 2014).
- Person–organisation fit and how recruiters judge it: Kristof (1996);
  Cable & Judge (1997).
- Bias against autistic / neurodivergent candidates in interviews (papers
  already in the folder: Maras et al. 2020, Finn et al. 2023, Davies et al.
  2023, Remington).
- LLM agents that reason before acting: chain-of-thought, ReAct (Yao et al.
  2023), generative agents (Park et al. 2023).
- Multimodal expressive response generation for social robots: the
  Expressive Furhat and Xpress papers already in the literature table.

---

## Next step for each task

1. Researcher answers the open questions marked "the main risk" / "who
   speaks" first (A.1, B.1).
2. A literature pass per task (as done for the voice review), with the
   papers saved to the matching topic folder under `תואר שני/מאמרים/`.
3. Then a design doc per agent, and a plan.
