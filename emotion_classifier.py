"""
Emotion Classifier — direct emotion classification for the Furhat
face+voice reaction, independent of evaluator.py.

One LLM call, sees only (question, answer_text) -- not the evaluator's
rationale or category -- so this stays a genuinely separate read on the
answer's emotional content rather than a restatement of the evaluator's
own judgment. Picks freely among Ekman's 7 core emotions plus 4 more
circumplex-quadrant-fill emotions (EXCITED, BORED, SLEEPY, CALM) that
EmotionsLibrary.kt also has gestures for -- no register restriction
(unlike the earlier VA-keyed emotion_bank.py, which excluded
ANGER/CONTEMPT/DISGUST as "too hostile" -- that restriction was a
property of the old mechanism, deliberately dropped here). See
docs/superpowers/specs/2026-08-16-emotion-first-classification-design.md.

response_bank.py still needs a (valence, arousal) pair to pick spoken
text, so this module also derives one from the classification result --
valence from a fixed emotion lookup, arousal from intensity -- rather
than reusing evaluator.py's own valence/arousal. Face (the classified
emotion) and text (the derived-VA response) both trace back to this one
classify_emotion() call, preserving the "one source of truth" coherence
guarantee from the original VA-first design.
"""

import json
import re
import config
import guardrail
import llm_client

CORE_EMOTIONS = [
    "ANGER", "CONTEMPT", "DISGUST", "FEAR", "HAPPINESS", "SADNESS", "SURPRISE",
    "EXCITED", "BORED", "SLEEPY", "CALM",
]

# Grounded in Schneider et al. (2025)'s circumplex quadrants: HAPPINESS/
# EXCITED/CALM in the positive-valence quadrants (high- and low-arousal
# respectively), the rest in the negative-valence quadrants, SURPRISE
# conventionally placed near-neutral valence at high arousal. BORED/
# SLEEPY are the low-arousal negative-valence quadrant's fill emotions --
# not Ekman emotions, added later purely to give EmotionsLibrary.kt's AU
# calibration sweep gesture coverage in that quadrant too.
EMOTION_TO_VALENCE = {
    "HAPPINESS": "high",
    "SURPRISE": "medium",
    "ANGER": "low",
    "CONTEMPT": "low",
    "DISGUST": "low",
    "FEAR": "low",
    "SADNESS": "low",
    "EXCITED": "high",
    "CALM": "high",
    "BORED": "low",
    "SLEEPY": "low",
}

# Arousal is derived from intensity, NOT fixed per emotion -- fixing both
# per emotion would make most of response_bank.py's 9 VA cells permanently
# unreachable (e.g. HAPPINESS always landing on high/high). This keeps all
# 9 cells reachable via at least one emotion at some intensity.
INTENSITY_TO_AROUSAL = {1: "low", 2: "medium", 3: "high"}

# Fail-closed default when the LLM returns something unparseable/invalid --
# same "fail closed" philosophy as emotion_bank.pick_emotion_llm()'s
# candidates[0] fallback. SURPRISE/2 is the mid-valence, mid-intensity
# cell: a parsing failure implies neither a positive nor a negative read.
_FALLBACK = {"emotion": "SURPRISE", "intensity": 2, "trigger": ""}

_SYSTEM_PROMPT = (
    "You are classifying the emotional content of a job interview answer, "
    "independent of how good or bad the answer is.\n\n"
    "First, find the specific word or phrase in the answer that most "
    "signals an emotion -- not the overall tone of a confident or "
    "professional-sounding answer, just what's actually there. Generic "
    "confident or professional phrasing on its own is not a signal of "
    "happiness -- do not default to HAPPINESS just because an answer "
    "sounds competent or matter-of-fact.\n\n"
    "Then pick exactly one of these emotions that best fits: "
    "ANGER, CONTEMPT, DISGUST, FEAR, HAPPINESS, SADNESS, SURPRISE, "
    "EXCITED, BORED, SLEEPY, CALM. "
    "Use the whole range: if the message lists emotions already shown in "
    "this session, prefer one that is not on that list, as long as it still "
    "fits the answer. "
    "Also rate its intensity: 2 (clear) or 3 (strong) -- the robot's face "
    "must show the reaction visibly, so never 1.\n\n"
    "Respond with ONLY a JSON object of the exact shape: "
    '{"cue": "<the word or phrase, or \\"none\\" if truly nothing '
    'stands out>", "emotion": "<ONE_OF_THE_11_WORDS_ABOVE>", '
    '"intensity": <2 or 3>, "trigger": "<one short sentence: what in the '
    'CONTENT of the answer led to this emotion, e.g. \\"The candidate led a '
    'project alone as a junior.\\" Never about how they spoke.>"}'
)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


# Reactions must be clearly visible on the face (researcher decision,
# 2026-11-14): intensity 1 is raised to 2. So the low-arousal VA cells of
# response_bank.py are no longer reached from here.
MIN_INTENSITY = 2


def classify_emotion(question: str, answer_text: str, recent_emotions: list[str] | None = None) -> dict:
    """recent_emotions: the robot's last (up to 2) shown emotions, so the pick varies."""
    user_message = f"Interview question: {question}\n\nCandidate answer: {answer_text}"
    recent = list(dict.fromkeys(recent_emotions or []))  # unique, in order
    if recent:
        user_message += (f"\n\nRecent emotions you already showed: {', '.join(recent)}. "
                         "Prefer a different emotion unless this answer strongly demands the same one.")

    raw = llm_client.call_llm(
        system=_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=160,  # room for the trigger sentence
        temperature=0.8,  # variety over reproducibility -- see spec
        role="judgment",
    )
    raw = _strip_fences(raw)

    try:
        data = json.loads(raw)
        emotion = data["emotion"]
        intensity = int(data["intensity"])
        if emotion not in EMOTION_TO_VALENCE or intensity not in INTENSITY_TO_AROUSAL:
            raise ValueError(f"Unexpected emotion/intensity: {data!r}")
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return dict(_FALLBACK)

    # What in the answer caused the reaction (2026-11-17 spec): graded against the
    # participant's "why" later, never spoken. Dropped if it talks about delivery.
    trigger = str(data.get("trigger") or "").strip()
    if trigger and not guardrail.check_rationale(trigger).passed:
        trigger = ""
    return {"emotion": emotion, "intensity": max(intensity, MIN_INTENSITY), "trigger": trigger}


def derive_valence(emotion: str) -> str:
    return EMOTION_TO_VALENCE[emotion]


def derive_arousal(intensity: int) -> str:
    return INTENSITY_TO_AROUSAL[intensity]
