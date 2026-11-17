import pytest

import small_talk
from prompts.small_talk_prompt import FALLBACK_LINES


@pytest.mark.parametrize("phase,position,total,expects_answer,role", [
    ("Opening", 1, 3, True, "opening_first"),
    ("Opening", 2, 3, True, "opening_middle"),
    ("Opening", 3, 3, True, "opening_last"),
    ("Closing", 1, 2, True, "closing_first"),
    ("Closing", 2, 3, True, "closing_middle"),
    ("Closing", 2, 2, False, "closing_last"),
])
def test_role_for(phase, position, total, expects_answer, role):
    assert small_talk.role_for(phase, position, total, expects_answer) == role


def test_generate_line_sends_role_gender_and_history(monkeypatch):
    seen = {}

    def fake(system, user_message):
        seen.update(system=system, user=user_message)
        return "נעים מאוד, דנה!"

    monkeypatch.setattr(small_talk.llm_line, "request_line", fake)
    history = [{"speaker": "robot", "text": "היי, איך קוראים לך?"},
               {"speaker": "participant", "text": "דנה"}]

    line = small_talk.generate_line("Opening", 2, 3, True, history, "he", participant_gender="female")

    assert line == "נעים מאוד, דנה!"
    assert "Hebrew" in seen["system"]
    assert "Continue the small talk" in seen["system"]
    assert "feminine form" in seen["system"]
    assert seen["user"] == "Robot: היי, איך קוראים לך?\nCandidate: דנה"


def test_first_name_goes_into_the_prompt_only_when_known(monkeypatch):
    seen = []
    monkeypatch.setattr(small_talk.llm_line, "request_line",
                        lambda system, user_message: seen.append(system) or "שלום")
    small_talk.generate_line("Opening", 1, 2, True, [], "he", participant_name="דנה")
    small_talk.generate_line("Opening", 1, 2, True, [], "he")
    assert "first name is דנה" in seen[0] and "never ask for their name" in seen[0]
    assert "first name" not in seen[1]


def test_generate_line_empty_history_says_so(monkeypatch):
    seen = {}
    monkeypatch.setattr(small_talk.llm_line, "request_line",
                        lambda system, user_message: seen.update(user=user_message) or "שלום")
    small_talk.generate_line("Opening", 1, 2, True, [], "he")
    assert seen["user"] == "(The conversation has not started yet.)"


def test_generate_line_falls_back_by_gender_when_llm_fails(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_line", lambda system, user_message: None)
    assert small_talk.generate_line("Opening", 2, 3, True, [], "he", "female") == \
        FALLBACK_LINES["he"]["female"]["opening_middle"]
    assert small_talk.generate_line("Opening", 2, 3, True, [], "he", None) == \
        FALLBACK_LINES["he"]["neutral"]["opening_middle"]
    assert small_talk.generate_line("Opening", 1, 2, True, [], "en", "male") == \
        FALLBACK_LINES["en"]["neutral"]["opening_first"]


def test_flagged_line_falls_back(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_line",
                        lambda system, user_message: "You seemed nervous, but welcome!")
    assert small_talk.generate_line("Opening", 1, 2, True, [], "en") == FALLBACK_LINES["en"]["neutral"]["opening_first"]


def test_every_gender_has_every_role():
    for lang, forms in FALLBACK_LINES.items():
        assert "neutral" in forms, lang
        for form, lines in forms.items():
            assert set(lines) == set(small_talk.ROLES), (lang, form)


HISTORY = [{"speaker": "robot", "text": "מה עשית בסוף השבוע?"},
           {"speaker": "participant", "text": "אפיתי לחם מחמצת"}]


def test_follow_up_returns_the_line_and_sends_history(monkeypatch):
    seen = {}

    def fake(system, user_message, required, *a, **k):
        seen.update(system=system, user=user_message, required=required)
        return {"follow_up": "וואו, מחמצת! כמה זמן לוקח להכין אותה?"}

    monkeypatch.setattr(small_talk.llm_line, "request_json", fake)

    line = small_talk.follow_up("Opening", HISTORY, "he", participant_gender="female")

    assert line == "וואו, מחמצת! כמה זמן לוקח להכין אותה?"
    assert seen["required"] == ("follow_up",)
    assert "feel at ease" in seen["system"] and "feminine form" in seen["system"]
    assert seen["user"].endswith("Candidate: אפיתי לחם מחמצת")


def test_follow_up_none_means_move_on(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_json", lambda *a, **k: {"follow_up": "NONE"})
    assert small_talk.follow_up("Opening", HISTORY) is None


def test_follow_up_llm_failure_moves_on(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_json", lambda *a, **k: None)
    assert small_talk.follow_up("Opening", HISTORY) is None


def test_flagged_follow_up_moves_on(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_json",
                        lambda *a, **k: {"follow_up": "כל הכבוד, ספר עוד"})
    assert small_talk.follow_up("Opening", HISTORY) is None


def test_closing_follow_up_answers_their_questions(monkeypatch):
    seen = {}
    monkeypatch.setattr(small_talk.llm_line, "request_json",
                        lambda system, *a, **k: seen.update(system=system) or {"follow_up": "NONE"})
    small_talk.follow_up("Closing", HISTORY)
    assert "If the candidate asked you a question, answer it" in seen["system"]


def test_small_talk_prompt_aims_to_reduce_stress():
    from prompts.small_talk_prompt import SMALL_TALK_SYSTEM_PROMPT
    assert "feel at ease" in SMALL_TALK_SYSTEM_PROMPT
    assert "follow-up" in SMALL_TALK_SYSTEM_PROMPT


# ── bridge: the reaction before a scripted opening line ──────────────────────
def test_bridge_returns_the_line(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_line", lambda system, user_message: "פקקים זה מתיש.")
    assert small_talk.bridge(HISTORY) == "פקקים זה מתיש."


def test_bridge_returns_none_when_guardrail_flags(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_line",
                        lambda system, user_message: "You seemed nervous, but welcome.")
    assert small_talk.bridge(HISTORY, "en") is None


def test_bridge_rejects_a_question(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_line", lambda system, user_message: "איך הייתה הדרך?")
    assert small_talk.bridge(HISTORY) is None


def test_bridge_none_when_llm_fails(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_line", lambda system, user_message: None)
    assert small_talk.bridge(HISTORY) is None


def test_follow_up_prompt_allows_two_to_three_sentences():
    from prompts.small_talk_prompt import FOLLOW_UP_SYSTEM_PROMPT
    assert "2-3 sentences" in FOLLOW_UP_SYSTEM_PROMPT
