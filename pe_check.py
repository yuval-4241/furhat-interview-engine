"""
pe_check.py -- grades a participant's perspective-taking (PE) answer
("what did I feel, and why?") against the emotion the robot actually
showed (the turn's target_emotion).

Correct / Partial / Wrong from the emotion (spec decisions 10-11), and,
since 2026-11-17, a separate reason grade -- Matches / Partly / No /
Missing -- against the recorded trigger of the reaction (what in the answer
caused it). The reason never changes the emotion grade; with no trigger
recorded the reason is not graded (''). Content, not delivery: No-Masking applies here too. Prompt and
word lists: prompts/pe_check_prompt.py.

LLM errors propagate so the caller can retry; an unparseable reply fails
closed to "Wrong" with an explanation the researcher sees before approving.
"""

import json
import re

import llm_client
from prompts.pe_check_prompt import PE_CHECK_SYSTEM_PROMPT

RESULTS = ("Correct", "Partial", "Wrong")
REASON_RESULTS = ("Matches", "Partly", "No", "Missing")

_FALLBACK = {"result": "Wrong", "explanation": "Could not parse a judgment from the model."}


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def grade_pe_answer(target_emotion: str, pe_answer_text: str, trigger: str = "") -> dict:
    user_message = f"Target emotion: {target_emotion}\n\nParticipant's answer: {pe_answer_text}"
    if trigger:
        user_message += f"\n\nRecorded cause of the reaction: {trigger}"
    raw = llm_client.call_llm(
        system=PE_CHECK_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=300,
        temperature=0.2,
        role="judgment",
    )
    try:
        data = json.loads(_strip_fences(raw))
        if data["result"] not in RESULTS:
            raise ValueError(f"Unexpected result: {data['result']!r}")
        graded = {"result": data["result"], "explanation": str(data["explanation"])}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        graded = dict(_FALLBACK)
        data = {}
    reason = data.get("reason_result") if isinstance(data, dict) else None
    if trigger and reason in REASON_RESULTS:  # fail closed per field: a bad reason grade is just ungraded
        graded.update(reason_result=reason, reason_explanation=str(data.get("reason_explanation", "")))
    else:
        graded.update(reason_result="", reason_explanation="")
    return graded


def check_pe_answer(ground_truth_emotion: str, pe_answer_text: str) -> dict:
    """The older match/no-match shape, kept for interaction_app.py."""
    graded = grade_pe_answer(ground_truth_emotion, pe_answer_text)
    return {"match": graded["result"] == "Correct", "explanation": graded["explanation"],
            "result": graded["result"]}
