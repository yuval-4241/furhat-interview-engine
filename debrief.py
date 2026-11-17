"""
debrief.py -- the friend debrief at the end of a Live session
(docs/superpowers/specs/2026-11-17-friend-debrief-pe-design.md).

The robot, now a friend character, asks the candidate how the interview
went; the candidate tells it freely. The friend's lines (opener, at most
config.DEBRIEF_MAX_FOLLOW_UPS follow-ups, goodbye) never name or hint a
feeling: a generated line that mentions one is replaced by a fixed line.
Afterwards extract_moments() turns the story into the moments the candidate
told, each matched to an interview turn and graded like a PE answer
(emotion: Correct/Partial/Wrong; reason: Matches/Partly/No/Missing).

Line functions never raise. extract_moments() lets LLM errors propagate so
conversation_flow can retry once and then set engine_error.
"""

import json
import re

import guardrail
import llm_client
import llm_line
import pe_check
from prompts.debrief_prompt import (EXTRACT_SYSTEM_PROMPT, FALLBACK_LINES, FOLLOW_UP_SYSTEM_PROMPT,
                                    GOODBYE_SYSTEM_PROMPT, OPENER_SYSTEM_PROMPT)
from prompts.pe_check_prompt import HEBREW_NAMES, WORD_LISTS

_ENGLISH_WORDS = ("anger", "angry", "contempt", "disgust", "fear", "afraid", "scared", "happy", "happiness",
                  "sad", "surprise", "excited", "bored", "sleepy", "calm", "upset", "worried", "nervous")


def _emotion_words() -> set:
    words = set(HEBREW_NAMES.values()) | set(_ENGLISH_WORDS)
    for lists in WORD_LISTS.values():
        words.update(lists["correct"])
        for partial in lists["partial"].values():
            words.update(partial)
    return {w.lower() for w in words}


EMOTION_WORDS = _emotion_words()


def mentions_emotion(line: str) -> bool:
    """True if the line names a feeling (Hebrew word lists of the PE check, or English names)."""
    text = line.lower()
    return any(word in text for word in EMOTION_WORDS)


def _rules(language, participant_gender, friend_gender) -> tuple:
    lang = llm_line.language_or_default(language)
    return lang, {"language": llm_line.LANGUAGE_NAMES[lang],
                  "gender_rule": llm_line.gender_rule(lang, participant_gender, friend_gender)}


def _fallback(lang: str, participant_gender, which: str) -> str:
    forms = FALLBACK_LINES[lang]
    return (forms.get(participant_gender) or forms["neutral"])[which]


def _clean(line) -> bool:
    return bool(line) and not mentions_emotion(line) and guardrail.check_rationale(line).passed


def _line(system_prompt: str, which: str, language, participant_gender, friend_gender, history=()) -> str:
    lang, rules = _rules(language, participant_gender, friend_gender)
    user = _format(history) or "(The conversation has not started yet.)"
    line = llm_line.request_line(system_prompt.format(**rules), user)
    return line if _clean(line) else _fallback(lang, participant_gender, which)


def _format(history) -> str:
    names = {"robot": "Friend", "participant": "Candidate"}
    return "\n".join(f"{names[h['speaker']]}: {h['text']}" for h in history)


def opener(language: str = "he", participant_gender=None, friend_gender=None) -> str:
    return _line(OPENER_SYSTEM_PROMPT, "opener", language, participant_gender, friend_gender)


def goodbye(history=(), language: str = "he", participant_gender=None, friend_gender=None) -> str:
    return _line(GOODBYE_SYSTEM_PROMPT, "goodbye", language, participant_gender, friend_gender, history)


def follow_up(history: list, language: str = "he", participant_gender=None, friend_gender=None):
    """The friend's next open question, or None to close (also on failure or a filtered line)."""
    _, rules = _rules(language, participant_gender, friend_gender)
    data = llm_line.request_json(FOLLOW_UP_SYSTEM_PROMPT.format(**rules), _format(history), ("follow_up",))
    line = data["follow_up"] if data else ""
    if not line or line.strip(" .").upper() == "NONE" or not _clean(line):
        return None
    return line


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(json)?", "", text.strip()).strip()
    return re.sub(r"```$", "", text).strip()


_MOMENT_KEYS = ("turn_order", "emotion_named", "reason_given", "quote", "emotion_result", "reason_result")


def extract_moments(story: list, turns: list) -> list:
    """The moments the candidate told the friend, matched to turns and graded. [] when the
    candidate said nothing or the reply can't be parsed."""
    if not any(line["speaker"] == "participant" for line in story):
        return []
    reacted = [t for t in turns if t.get("target_emotion")]
    listing = "\n".join(
        f"- turn {t.get('order')}: question: {t.get('question_text', '')} | answer: {t.get('participant_answer', '')}"
        f" | TARGET: {t['target_emotion']} | recorded cause: {t.get('emotion_trigger') or '(none)'}"
        for t in reacted)
    raw = llm_client.call_llm(system=EXTRACT_SYSTEM_PROMPT,
                              user_message=f"Conversation with the friend:\n{_format(story)}\n\nTurns:\n{listing}",
                              max_tokens=1200, temperature=0.2, role="judgment")
    try:
        items = json.loads(_strip_fences(raw))["moments"]
        if not isinstance(items, list):
            return []
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
    orders = {t.get("order") for t in reacted}
    moments = []
    for item in items:
        if not isinstance(item, dict):
            continue
        m = {k: item.get(k, "") or "" for k in _MOMENT_KEYS}
        m["turn_order"] = item.get("turn_order") if item.get("turn_order") in orders else None
        if m["turn_order"] is None or m["emotion_result"] not in pe_check.RESULTS:
            m["emotion_result"] = ""
        if m["turn_order"] is None or m["reason_result"] not in pe_check.REASON_RESULTS:
            m["reason_result"] = ""
        moments.append(m)
    return moments
