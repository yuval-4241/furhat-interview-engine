"""
pe_check.py -- grades a participant's perspective-taking (PE) answer
("what did I feel, and why?") against the emotion the robot actually
showed (the turn's target_emotion).

Correct / Partial / Wrong from the emotion only (spec decisions 10-11);
the reason is commented on in the explanation but never changes the
grade. Content, not delivery: No-Masking applies here too. Prompt and
word lists: prompts/pe_check_prompt.py.

LLM errors propagate so the caller can retry; an unparseable reply fails
closed to "Wrong" with an explanation the researcher sees before approving.
"""

import json
import re

import llm_client
from prompts.pe_check_prompt import PE_CHECK_SYSTEM_PROMPT

RESULTS = ("Correct", "Partial", "Wrong")

_FALLBACK = {"result": "Wrong", "explanation": "Could not parse a judgment from the model."}


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def grade_pe_answer(target_emotion: str, pe_answer_text: str) -> dict:
    raw = llm_client.call_llm(
        system=PE_CHECK_SYSTEM_PROMPT,
        user_message=f"Target emotion: {target_emotion}\n\nParticipant's answer: {pe_answer_text}",
        max_tokens=200,
        temperature=0.2,
        role="judgment",
    )
    try:
        data = json.loads(_strip_fences(raw))
        if data["result"] not in RESULTS:
            raise ValueError(f"Unexpected result: {data['result']!r}")
        return {"result": data["result"], "explanation": str(data["explanation"])}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return dict(_FALLBACK)


def check_pe_answer(ground_truth_emotion: str, pe_answer_text: str) -> dict:
    """The older match/no-match shape, kept for interaction_app.py."""
    graded = grade_pe_answer(ground_truth_emotion, pe_answer_text)
    return {"match": graded["result"] == "Correct", "explanation": graded["explanation"],
            "result": graded["result"]}
