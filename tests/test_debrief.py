import json

import pytest

from engine import debrief
from prompts import debrief_prompt


# ── friend lines never name or hint an emotion ───────────────────────────────
@pytest.mark.parametrize("line", ["נראה לי שהוא היה מופתע, לא?", "Was he surprised?", "הוא כעס עליך?"])
def test_mentions_emotion(line):
    assert debrief.mentions_emotion(line)


def test_neutral_line_mentions_no_emotion():
    assert not debrief.mentions_emotion("נו, איך היה? ספר לי מה קרה שם.")


def test_friend_line_naming_an_emotion_falls_back(monkeypatch):
    monkeypatch.setattr(debrief.llm_line, "request_line", lambda system, user_message: "הוא היה מופתע, נכון?")
    assert debrief.opener("he") == debrief_prompt.FALLBACK_LINES["he"]["neutral"]["opener"]


def test_opener_returns_a_clean_line(monkeypatch):
    monkeypatch.setattr(debrief.llm_line, "request_line", lambda system, user_message: "היי! איך היה הראיון?")
    assert debrief.opener("he") == "היי! איך היה הראיון?"


def test_follow_up_none_on_NONE_or_failure_fallback_on_flag(monkeypatch):
    history = [{"speaker": "robot", "text": "איך היה?"}, {"speaker": "participant", "text": "היה בסדר"}]
    monkeypatch.setattr(debrief.llm_line, "request_json", lambda *a, **k: {"follow_up": "NONE"})
    assert debrief.follow_up(history) is None
    monkeypatch.setattr(debrief.llm_line, "request_json", lambda *a, **k: None)  # LLM failure
    assert debrief.follow_up(history) is None
    monkeypatch.setattr(debrief.llm_line, "request_json", lambda *a, **k: {"follow_up": "You seemed nervous, then?"})
    assert debrief.follow_up(history, "en") == debrief_prompt.FALLBACK_LINES["en"]["neutral"]["follow_up"]


def test_follow_up_returns_an_open_question(monkeypatch):
    history = [{"speaker": "robot", "text": "איך היה?"}, {"speaker": "participant", "text": "סיפרתי על הפרויקט"}]
    monkeypatch.setattr(debrief.llm_line, "request_json", lambda *a, **k: {"follow_up": "ומה קרה כשסיפרת על הפרויקט?"})
    assert debrief.follow_up(history) == "ומה קרה כשסיפרת על הפרויקט?"


def test_friend_prompts_contain_no_emotion_words():
    for prompt in (debrief_prompt.OPENER_SYSTEM_PROMPT, debrief_prompt.FOLLOW_UP_SYSTEM_PROMPT,
                   debrief_prompt.GOODBYE_SYSTEM_PROMPT):
        assert not debrief.mentions_emotion(prompt), prompt[:80]


# ── extraction of the moments the participant told ───────────────────────────
STORY = [{"speaker": "robot", "text": "איך היה?"},
         {"speaker": "participant", "text": "כשסיפרתי על הכלא הוא הופתע, כי הוא לא ציפה לזה"}]
TURNS = [{"order": 7, "phase": "Main", "question_text": "ספר על עצמך", "participant_answer": "ישבתי בכלא",
          "target_emotion": "SURPRISE", "emotion_trigger": "Told about prison."}]


def test_extract_moments_maps_to_turn_and_grades(monkeypatch):
    seen = {}
    moments = [{"turn_order": 7, "emotion_named": "הופתע", "reason_given": "לא ציפה לזה", "quote": "הוא הופתע",
                "emotion_result": "Correct", "reason_result": "Matches"},
               {"turn_order": 99, "emotion_named": "שמח", "reason_given": "", "quote": "שמח",
                "emotion_result": "Maybe", "reason_result": "Missing"}]
    monkeypatch.setattr(debrief.llm_client, "call_llm",
                        lambda **k: seen.update(k) or json.dumps({"moments": moments}))
    got = debrief.extract_moments(STORY, TURNS)
    keys = {"turn_order", "emotion_named", "reason_given", "quote", "emotion_result", "reason_result"}
    assert all(set(m) == keys for m in got)
    assert got[0]["turn_order"] == 7 and got[0]["emotion_result"] == "Correct"
    assert got[1]["turn_order"] is None and got[1]["emotion_result"] == ""  # unknown turn / value -> empty
    assert "Told about prison." in seen["user_message"] and seen["role"] == "judgment"


def test_extract_moments_empty_story_returns_empty_list(monkeypatch):
    monkeypatch.setattr(debrief.llm_client, "call_llm", lambda **k: pytest.fail("no LLM call without a story"))
    assert debrief.extract_moments([{"speaker": "robot", "text": "איך היה?"}], TURNS) == []


def test_extract_moments_unparseable_reply_returns_empty_list(monkeypatch):
    monkeypatch.setattr(debrief.llm_client, "call_llm", lambda **k: "not json")
    assert debrief.extract_moments(STORY, TURNS) == []


# ── final review #3: whole words only, and a filtered follow-up falls back ────
@pytest.mark.parametrize("line", ["ומה קרה בזמן שסיפרת על הפרויקט?", "בזכות מה התקבלת?",
                                  "ומה הוא שאל אחרי זה?"])
def test_ordinary_words_are_not_emotions(line):
    assert not debrief.mentions_emotion(line)


@pytest.mark.parametrize("line", ["והוא כעס?", "הוא היה מופתע?", "Was he angry?", "he looked bored",
                                  "ונראה שהוא שמח"])
def test_emotion_words_with_prefixes_still_caught(line):
    assert debrief.mentions_emotion(line)


def test_filtered_follow_up_falls_back_to_an_open_question(monkeypatch):
    history = [{"speaker": "robot", "text": "איך היה?"}, {"speaker": "participant", "text": "סיפרתי על הפרויקט"}]
    monkeypatch.setattr(debrief.llm_line, "request_json", lambda *a, **k: {"follow_up": "והוא כעס?"})
    assert debrief.follow_up(history) == debrief_prompt.FALLBACK_LINES["he"]["neutral"]["follow_up"]
