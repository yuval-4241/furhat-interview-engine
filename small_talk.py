"""
small_talk.py -- the robot's opening/closing small-talk lines (spec
decision 5), generated from the dialogue so far so every session sounds
different. No researcher approval (spec decision 6); every line is still
written to the website as the turn's question_text.

Never raises: after one retry, or if the No-Masking guardrail flags the
line, it falls back to a fixed line in the participant's gender.
"""

import guardrail
import llm_line
from prompts.small_talk_prompt import FALLBACK_LINES, NAME_RULE, ROLES, SMALL_TALK_SYSTEM_PROMPT

_SPEAKER_NAMES = {"robot": "Robot", "participant": "Candidate"}


def role_for(phase: str, position: int, total: int, expects_answer: bool) -> str:
    if phase == "Closing" and not expects_answer:
        return "closing_last"
    prefix = "opening" if phase == "Opening" else "closing"
    if position == 1:
        return f"{prefix}_first"
    if phase == "Opening" and position == total:
        return "opening_last"
    return f"{prefix}_middle"


def format_history(history: list) -> str:
    return "\n".join(f"{_SPEAKER_NAMES[h['speaker']]}: {h['text']}" for h in history)


def _fallback(lang: str, participant_gender, role: str) -> str:
    forms = FALLBACK_LINES[lang]
    return (forms.get(participant_gender) or forms["neutral"])[role]


def generate_line(phase: str, position: int, total: int, expects_answer: bool, history: list,
                  language: str = "he", participant_gender=None, robot_gender=None,
                  participant_name=None) -> str:
    """participant_name is used in small talk only (plan decision P12)."""
    lang = llm_line.language_or_default(language)
    role = role_for(phase, position, total, expects_answer)
    system = SMALL_TALK_SYSTEM_PROMPT.format(
        language=llm_line.LANGUAGE_NAMES[lang], role=ROLES[role],
        gender_rule=llm_line.gender_rule(lang, participant_gender, robot_gender),
        name_rule=NAME_RULE.format(name=participant_name) if participant_name else "")
    user = format_history(history) or "(The conversation has not started yet.)"
    line = llm_line.request_line(system, user)
    if line and guardrail.check_rationale(line).passed:
        return line
    return _fallback(lang, participant_gender, role)
