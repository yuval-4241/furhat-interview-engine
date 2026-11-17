"""
reaction_line.py -- the 2-3 sentences the robot says with its emotional
reaction (PBDI turns). One LLM line from the classified emotion + the answer's
content, in the robot's and the participant's grammatical gender. Falls back
to a fixed line per emotion when the LLM fails twice, when the No-Masking
guardrail flags the line, or when the line names the emotion (that would
give away the PE answer). Never raises.

Replaces response_bank.py's placeholder lines as the spoken reply; the
derived valence/arousal are still recorded on the turn.
"""

import guardrail
import llm_line
from prompts.pe_check_prompt import HEBREW_NAMES, WORD_LISTS
from prompts.reaction_line_prompt import FALLBACK_LINES, REACTION_LINE_SYSTEM_PROMPT, STRENGTHS


def names_emotion(emotion: str, line: str) -> bool:
    """True if the line contains the emotion's Hebrew name or one of its PE answer words."""
    words = [HEBREW_NAMES.get(emotion, "")] + WORD_LISTS.get(emotion, {}).get("correct", [])
    return any(w and w in line for w in words)


def generate(emotion: str, intensity: int, question: str, answer: str, language: str = "he",
             participant_gender=None, robot_gender=None) -> str:
    lang = llm_line.language_or_default(language)
    system = REACTION_LINE_SYSTEM_PROMPT.format(
        emotion=emotion, strength=STRENGTHS.get(intensity, "clear"),
        language=llm_line.LANGUAGE_NAMES[lang],
        gender_rule=llm_line.gender_rule(lang, participant_gender, robot_gender))
    # TODO: verify Furhat /react hold time covers full speech duration
    # (check furhat-emotion-study repo)
    # NOTE: longer reactions give more emotional signal -- may reduce PE
    # task difficulty. Documented as design trade-off in thesis.
    line = llm_line.request_line(system, f"Interview question: {question}\n\nCandidate answer: {answer}")
    if not line or not guardrail.check_rationale(line).passed or names_emotion(emotion, line):
        return FALLBACK_LINES[lang][emotion]
    return line
