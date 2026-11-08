"""
pe_feedback.py -- the robot's line revealing what it actually felt and
why, after the participant's PE guess (spec decision 8). The line goes to
Turn.proposed_feedback and the reason to Turn.pe_answer_why; the
researcher edits/approves the line as final_feedback before the robot
says it.

Never raises: if the LLM fails twice, or the No-Masking guardrail flags
the line or the reason, it falls back to just naming the emotion.
"""

import guardrail
import llm_line
from prompts.pe_check_prompt import HEBREW_NAMES
from prompts.pe_feedback_prompt import FALLBACK_TEMPLATES, PE_FEEDBACK_SYSTEM_PROMPT


def generate_feedback(target_emotion: str, question: str, answer: str, guess: str, result: str,
                      language: str = "he", participant_gender=None, robot_gender=None) -> dict:
    lang = llm_line.language_or_default(language)
    hebrew = HEBREW_NAMES.get(target_emotion, target_emotion)
    system = PE_FEEDBACK_SYSTEM_PROMPT.format(
        language=llm_line.LANGUAGE_NAMES[lang],
        gender_rule=llm_line.gender_rule(lang, participant_gender, robot_gender))
    user = (f"QUESTION: {question}\n"
            f"ANSWER: {answer}\n"
            f"TARGET: {target_emotion} ({hebrew})\n"
            f"GUESS: {guess}\n"
            f"GRADE: {result}")
    out = llm_line.request_json(system, user, required=("line", "reason"), max_tokens=400)
    if out and guardrail.check_rationale(f"{out['line']} {out['reason']}").passed:
        return {"line": out["line"], "reason": out["reason"]}
    name = hebrew if lang == "he" else target_emotion.lower()
    template = FALLBACK_TEMPLATES[lang].get(result, FALLBACK_TEMPLATES[lang]["Wrong"])
    return {"line": template.format(name=name), "reason": ""}
