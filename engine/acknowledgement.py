"""
acknowledgement.py -- content-only robot reply after a non-PBDI Main answer
(spec decision 7). One LLM line, checked by the No-Masking guardrail
(English and Hebrew phrases, plan decision P3); if the guardrail flags it,
or the LLM fails twice, the robot says the fixed fallback. Never raises.
"""

from evaluation import guardrail
from engine import llm_line
from prompts.acknowledgement_prompt import ACKNOWLEDGEMENT_SYSTEM_PROMPT, FALLBACK_LINES


def acknowledge(question: str, answer: str, language: str = "he",
                participant_gender=None, robot_gender=None) -> dict:
    lang = llm_line.language_or_default(language)
    system = ACKNOWLEDGEMENT_SYSTEM_PROMPT.format(
        language=llm_line.LANGUAGE_NAMES[lang],
        gender_rule=llm_line.gender_rule(lang, participant_gender, robot_gender))
    line = llm_line.request_line(system, f"Interview question: {question}\n\nCandidate answer: {answer}")
    if line is None:
        return {"line": FALLBACK_LINES[lang], "guardrail_flag": False, "guardrail_reason": ""}
    check = guardrail.check_rationale(line)
    if not check.passed:
        return {"line": FALLBACK_LINES[lang], "guardrail_flag": True,
                "guardrail_reason": f"style-bias language in acknowledgement: {check.matched_patterns}"}
    return {"line": line, "guardrail_flag": False, "guardrail_reason": ""}
