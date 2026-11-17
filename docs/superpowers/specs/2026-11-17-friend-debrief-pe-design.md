# Perspective-taking as a conversation with a friend — design

Date: 2026-11-17. Status: approved by the researcher 2026-11-17.
Repos: `conversation_engine` (Engine), `furhat-insight-lab` (website),
`furhat-emotion-study` (only if the friend needs a new face/voice asset).

## Intent

Today the robot reacts with an emotion and then asks a quiz-like question,
"מה לדעתך הרגשתי, ולמה?", graded on the emotion only. The researcher wants
the perspective-taking (PE) part to feel like real life: **a person who
finished a job interview and tells a friend how it went** — "when I told him
about the project he looked surprised, I think he didn't expect a junior to
lead something like that". What matters most is that the participant links
the interviewer's reaction to **what they said** (emotion + reason); the
voice need not carry every emotion.

## Researcher decisions (2026-11-17)

- **Timing: both (C).** A short, friend-toned question after each reaction
  (as today, reworded), **and** a full "telling a friend" conversation at the
  end of the interview (debrief).
- **The friend: a different character on the same robot (B)** — another face
  and voice, introduced as a friend, so talking about the interviewer in the
  third person ("he was surprised") is natural. Its look is **the same for
  all participants**; the researcher chooses it later.
- **Future (not in this design):** the feedback on what the interviewer really
  felt moves from after each turn to the end, inside the friend conversation.
  Researcher decision 2026-11-17: that feedback part stays **with the
  friend's face** — once the friend appears, the robot never switches back to
  the interviewer's face for the rest of the session.
- **Voice:** the robot's voice need not carry every emotion; it supports the
  ones where it works (`docs/literature/vocal_emotion_features.md`, profiles
  approved so far: bored, happiness, surprise, excited).

## Goals

- The participant's account of each reaction yields an emotion **and** a
  reason, both graded.
- An end-of-interview debrief, with the friend, in which the participant
  freely retells the interview; the moments they mention are extracted and
  matched to the turns they describe.
- Analysis can compare: per-turn answers vs. the debrief story; which
  reactions were remembered at all.

## Non-goals

- Moving the per-turn feedback to the debrief (future, see above).
- Changing which emotions the robot shows or how they are chosen.
- Choosing the friend's face/voice (researcher, later).

## Anti-goals

- The friend **leading** the participant: naming emotions, hinting ("he
  looked a bit worried, right?") or summarising the interview for them. The
  friend only asks open questions; the participant tells.
- Grading **how** the participant tells it (fluency, length, wording) —
  No-Masking applies to the debrief too.
- A reason grade that checks the participant against something the robot
  never recorded (today the classifier keeps no "why").

## Approaches considered

Timing: A once at the end (most natural, relies on memory, hard to tie to
turns) / B per turn only, reworded (precise, still quiz-like) / **C both —
chosen.** The friend: A the interviewer switching role (simple, but odd to
tell the interviewer about himself) / **B another character on the same
robot — chosen** / C a website screen or the researcher (clean separation,
no longer a conversation with the robot).

## Design

### 1. The reaction's cause is recorded (`emotion_classifier.py`)

`classify_emotion()` also returns **`trigger`**: one short sentence, content
only, on what in the answer led to the emotion ("the candidate described
leading a project alone as a junior"). Stored on the turn
(`turns.emotion_trigger`, new column). Guardrail-checked like other
generated text; never spoken to the participant. Without it a reason can't
be graded.

### 2. Per-turn question, friend-toned (`conversation_flow.py`)

`PE_QUESTION` changes wording, e.g. "שמת לב איך הגבתי? מה לדעתך עבר עליי?"
(**proposal — the researcher approves the final wording**). Rest of the
turn flow unchanged.

### 3. Two grades per PE answer (`pe_check.py`, `prompts/pe_check_prompt.py`)

- **Emotion grade** — unchanged: Correct / Partial / Wrong (incl. the
  2026-11-17 FEAR->SURPRISE Partial).
- **Reason grade** — new: **Matches / Partly / No / Missing** — does the
  participant's reason point to the same content as `emotion_trigger`?
  Judged on content only, never on wording.
- Stored separately (`turns.pe_reason_result`, `turns.pe_reason_explanation`,
  new columns); `pe_result` keeps its meaning, so earlier data stays
  comparable.

### 4. The debrief with the friend (new phase)

- **Website plan:** after the Closing turns, one turn with `phase: 'Debrief'`
  (`interviewPlan.js`; both Full and Short).
- **Engine:** a Debrief turn runs like a small-talk conversation
  (`small_talk_log`), with its own prompt:
  1. switch persona to the friend (`furhat_client.set_persona` with the
     friend's face/voice — one setting for all sessions, e.g.
     `config.FRIEND_FACE` / `config.FRIEND_VOICE` until the researcher picks
     them); the friend greets and asks how the interview went and how the
     interviewer reacted;
  2. the participant tells; the friend asks **at most 2** open follow-ups
     ("and then?", "what happened when you talked about X?" — X only from
     what the participant already said), never naming or hinting emotions;
  3. the friend closes warmly; persona switches back is not needed (the
     session ends).
- **Extraction (after the debrief):** one LLM call turns the story into a
  list of moments `[{turn_order, emotion_named, reason_given, quote}]`,
  matching each moment to the interview turn it describes (by content), and
  grades each moment's emotion and reason against that turn's
  `target_emotion` / `emotion_trigger` with the same rules as section 3.
  Stored on the Debrief turn (`turns.debrief_moments`, JSON, new column).
- **Website:** the researcher's screens show the debrief transcript and the
  extracted moments next to the turns they refer to.

### 5. Contract and docs

`ENGINE_INTEGRATION.md` / `migration/ENGINE_API.md`: the new columns, the
Debrief phase. `SESSION_LOG.md`; spec decisions 10–11 (grading on the emotion
only) are amended by section 3.

## Testing

- Classifier: `trigger` present, guardrail fallback.
- PE check: reason grades for matching / partly / unrelated / missing
  reasons (mocked LLM); emotion grade unchanged.
- Debrief: persona switch call, follow-up cap (2), the friend prompt never
  contains emotion names; extraction maps moments to turns; empty story ->
  no moments, no crash.
- One live run on the virtual robot.

## Left to the builder

- Prompt wording within the rules above (researcher reviews: per-turn
  question, friend's lines, extraction prompt).
- Column names; migration file.

## Open for the researcher

- The per-turn question's final wording.
- The friend's face and voice.
- Whether the debrief also asks about the participant's own feelings
  ("and how did you feel?") — not in this design.
