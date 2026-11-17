"""
small_talk.py -- the robot's opening/closing small-talk lines (spec
decision 5), generated from the dialogue so far so every session sounds
different. No researcher approval (spec decision 6); every line is still
written to the website as the turn's question_text.

Never raises: after one retry, or if the No-Masking guardrail flags the
line, it falls back to a fixed line in the participant's gender.

follow_up() makes each small-talk turn a short conversation: after an
answer, the LLM either asks a follow-up about what was said, or says NONE
and the conversation moves on (researcher decision 2026-11-14).
"""

import guardrail
import llm_line
from prompts.small_talk_prompt import (BRIDGE_SYSTEM_PROMPT, FALLBACK_LINES, FOLLOW_UP_SYSTEM_PROMPT, NAME_RULE, PHASE_RULES, ROLES,
                                       SMALL_TALK_SYSTEM_PROMPT)

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


def _common_rules(lang: str, participant_gender, robot_gender, participant_name) -> dict:
    return {"language": llm_line.LANGUAGE_NAMES[lang],
            "gender_rule": llm_line.gender_rule(lang, participant_gender, robot_gender),
            "name_rule": NAME_RULE.format(name=participant_name) if participant_name else ""}


def generate_line(phase: str, position: int, total: int, expects_answer: bool, history: list,
                  language: str = "he", participant_gender=None, robot_gender=None,
                  participant_name=None) -> str:
    """participant_name is used in small talk only (plan decision P12)."""
    lang = llm_line.language_or_default(language)
    role = role_for(phase, position, total, expects_answer)
    system = SMALL_TALK_SYSTEM_PROMPT.format(
        role=ROLES[role], **_common_rules(lang, participant_gender, robot_gender, participant_name))
    user = format_history(history) or "(The conversation has not started yet.)"
    line = llm_line.request_line(system, user)
    if line and guardrail.check_rationale(line).passed:
        return line
    return _fallback(lang, participant_gender, role)


def follow_up(phase: str, history: list, language: str = "he", participant_gender=None, robot_gender=None,
              participant_name=None):
    """The robot's follow-up line, or None to move on (also on LLM failure or a guardrail flag)."""
    lang = llm_line.language_or_default(language)
    system = FOLLOW_UP_SYSTEM_PROMPT.format(
        phase_rule=PHASE_RULES.get(phase, PHASE_RULES["Opening"]),
        **_common_rules(lang, participant_gender, robot_gender, participant_name))
    data = llm_line.request_json(system, format_history(history), ("follow_up",))
    line = data["follow_up"] if data else ""
    if not line or line.strip(" .").upper() == "NONE" or not guardrail.check_rationale(line).passed:
        return None
    return line


def bridge(history: list, language: str = "he", participant_gender=None, robot_gender=None,
           participant_name=None):
    """A short reaction before a scripted opening line, or None (LLM failure, a guardrail
    flag, or a line that asks a question: the script supplies the question)."""
    lang = llm_line.language_or_default(language)
    system = BRIDGE_SYSTEM_PROMPT.format(**_common_rules(lang, participant_gender, robot_gender, participant_name))
    line = llm_line.request_line(system, format_history(history))
    if not line or "?" in line or not guardrail.check_rationale(line).passed:
        return None
    return line
