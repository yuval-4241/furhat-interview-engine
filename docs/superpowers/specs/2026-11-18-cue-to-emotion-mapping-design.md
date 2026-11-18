# Content-triggered emotional reaction — cue → emotion mapping

Date: 2026-11-18. Status: reference table approved by the researcher
2026-11-18; SLEEPY **pending**, the "none" threshold to be tuned after live
runs. Repos: `conversation_engine` (Engine; `emotion_classifier.py`,
`reaction_line.py`), `furhat-emotion-study` (the `emotion-library` the face
is drawn from).

## Intent

The robot reacts emotionally to **what the candidate says**, like a real
interviewer, so the candidate can practice reading those reactions. The goal
is general **perspective-taking** training, not evaluation. The reaction is
**content-triggered**, not scheduled per question: the robot listens through
the interview body and reacts when something in the answer is *notable* —
something off, an incorrect statement, something especially good, something
intriguing / surprising / different. Opening, small talk and the ending
(debrief) carry no such reactions.

This table is the reference for which content cue maps to which of the 11
emotions already in `emotion_classifier.CORE_EMOTIONS` /
`furhat-emotion-study`'s `EmotionsLibrary.kt`. It guides, and will be used to
refine, the `emotion_classifier` prompt (which already finds a **cue** in the
answer and may return `"none"`).

## No-Masking boundary

No-Masking forbids judging **delivery style** (tone, eye contact, STAR
structure, directness). Every cue below is about the **content** of the
answer — the substance of what was said, or its relevance to the question —
never how it was delivered. The spoken `reaction_line` must still never grade
quality ("great answer") and never name the emotion (the PE question asks the
candidate to guess it). These are enforced by `guardrail.check_rationale` and
the reaction-line prompt rules.

## Cue → emotion table

| Content cue (what was said) | Interview example | Emotion | Intensity | Note |
|---|---|---|---|---|
| Strong achievement / positive outcome | "I led a project that saved 30%" | HAPPINESS | 2 | ordinary positive reaction |
| Standout / especially relevant achievement | "I built a face-recognising robot at home" | EXCITED | 3 | **extra emphasis** — genuinely engaging |
| Steady, reassuring answer | an orderly solution to a hard problem | CALM | 2 | positive, low arousal |
| Unexpected / different / a twist | a surprising career switch | SURPRISE | 2 | fires even if the info may be inaccurate |
| Worrying disclosure / red flag | "I wiped a whole day's data" | FEAR | 3 | concern about fit / risk |
| Difficult / unfortunate story | a personal hardship, a loss | SADNESS | 2 | empathy |
| A described injustice | "they fired me with no notice" | ANGER | 2 | anger *on behalf of* the candidate, never at them |
| Dismissive / unprofessional content | badmouthing a former employer | CONTEMPT | 2 | sensitive — must not sound like a verdict |
| Distasteful / inappropriate content | an inappropriate admission | DISGUST | 2 | rare in an interview |
| Answer is about a different topic than asked | asked about birds, answered about dogs | BORED | 2 | **question↔answer topic mismatch (content relevance), not length or style** |
| — | — | SLEEPY | — | **PENDING — see open questions** |

### BORED — scoped and documented

BORED fires on a **topic mismatch between question and answer** (the robot did
not get an answer to what it asked), *not* on length, pace or "directness".
This is a content-relevance cue, kept deliberately distinct from the style
dimensions No-Masking excludes. It is a perspective-taking stimulus only: the
**evaluator** and any performance scoring continue to ignore topic relevance,
so the No-Masking manipulation stays intact at the evaluation layer.

### `cue = "none"` → no reaction

When nothing in the answer stands out, `emotion_classifier` returns `"none"`
and the robot gives a light neutral acknowledgement with **no PE question** —
this prevents an artificial PE probe on flat answers.

## Open questions for the researcher

1. **SLEEPY.** Defined as the robot arriving tired / preoccupied / spacing
   out — an **internal state, not a reaction to the answer**. Pedagogically
   rich (reading a state that is *not about you*) but it breaks the current PE
   logic, which grades the candidate's "why" against a content `emotion_trigger`
   that SLEEPY has none of. Options: (a) a **session-level mood** set at the
   start, with a reworded PE ("how do I seem right now?"); (b) occasional,
   decoupled from content; (c) drop. Decision deferred.
2. **The "none" threshold.** Too high → few reactions, little training; too
   low → the robot reacts to everything and the PE loses meaning. A tuning
   parameter to set after a few live runs.

## Implementation touch points (no code written yet)

- `emotion_classifier.py` — the prompt already finds a cue and can return
  `"none"`; refine its wording against this table and wire the `"none"` →
  no-PE path.
- `reaction_line.py` — unchanged rules (never grade, never name the emotion).
- BORED / SLEEPY are already in `CORE_EMOTIONS`; no library change needed.
