"""
pe_check.py -- grades a participant's perspective-taking (PE) answer
("what did I feel? why?") against the ground-truth emotion the system
itself picked (emotion_classifier.classify_emotion()'s output for that
turn).

One LLM call, same fail-closed shape as emotion_classifier.py. Judges
whether the emotion CONCEPT was correctly named/described -- content,
not delivery -- the No-Masking framing applies here too even though
this isn't the interview-answer evaluator.
"""

import json
import re

import llm_client

_FALLBACK = {"match": False, "explanation": "Could not parse a judgment from the model."}

_SYSTEM_PROMPT = (
    "You are checking whether a participant correctly identified a robot "
    "interviewer's emotional reaction, in a perspective-taking exercise.\n\n"
    "You will be given the GROUND TRUTH emotion the robot actually "
    "displayed, and the participant's free-text answer to \"what do you "
    "think I felt, and why?\". Judge ONLY whether the participant's answer "
    "correctly names or clearly describes the ground-truth emotion concept "
    "-- synonyms and informal phrasing count as correct (e.g. 'annoyed' "
    "for ANGER). Do NOT judge their reasoning quality, wording, or how "
    "they expressed it -- only whether the emotion they named matches.\n\n"
    "Respond with ONLY a JSON object of the exact shape: "
    '{"match": <true or false>, "explanation": "<one sentence, in the '
    'same language as the participant\'s answer>"}'
)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def check_pe_answer(ground_truth_emotion: str, pe_answer_text: str) -> dict:
    user_message = (
        f"Ground truth emotion: {ground_truth_emotion}\n\n"
        f"Participant's answer: {pe_answer_text}"
    )

    raw = llm_client.call_llm(
        system=_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=150,
        temperature=0.3,
    )
    raw = _strip_fences(raw)

    try:
        data = json.loads(raw)
        return {"match": bool(data["match"]), "explanation": str(data["explanation"])}
    except (json.JSONDecodeError, KeyError, TypeError):
        return dict(_FALLBACK)
