"""
llm_line.py -- asks the LLM for one spoken robot line, returned as JSON
(e.g. {"line": "..."}). Shared by small_talk.py, acknowledgement.py and
pe_feedback.py.

One retry (spec: "LLM call fails -> one retry"), then None, so each caller
falls back to its own fixed line. Never raises: a failed LLM call must not
stop a live conversation.
"""

import json
import re

import llm_client

LANGUAGE_NAMES = {"he": "Hebrew", "en": "English"}
_FORMS = {"male": "masculine", "female": "feminine"}


def language_or_default(language) -> str:
    return language if language in LANGUAGE_NAMES else "he"


def gender_rule(language, participant_gender=None, robot_gender=None) -> str:
    """Prompt sentence about Hebrew grammatical gender (plan decision P2). Empty for English."""
    if language != "he":
        return ""
    if participant_gender in _FORMS:
        rules = [f"Address the candidate in the {_FORMS[participant_gender]} form."]
    else:
        rules = ["Avoid gender-marked second-person forms (for example \"מה שלומך?\"), "
                 "because the candidate's gender is unknown."]
    if robot_gender in _FORMS:
        rules.append(f"When the robot speaks about itself, use the {_FORMS[robot_gender]} form.")
    return " ".join(rules)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def request_json(system: str, user_message: str, required=("line",), max_tokens: int = 200,
                 temperature: float = 0.8):
    for _ in range(2):
        try:
            raw = llm_client.call_llm(system=system, user_message=user_message,
                                      max_tokens=max_tokens, temperature=temperature, role="lines")
            data = json.loads(_strip_fences(raw))
            values = {key: ("" if data[key] is None else str(data[key])).strip() for key in required}
        except Exception:  # LLM/network error or malformed JSON: retry, then the caller falls back
            continue
        if all(values.values()):
            return values
    return None


def request_line(system: str, user_message: str, max_tokens: int = 200, temperature: float = 0.8):
    data = request_json(system, user_message, ("line",), max_tokens, temperature)
    return data["line"] if data else None
