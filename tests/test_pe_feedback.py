import pe_feedback


def _fake_json(monkeypatch, reply):
    seen = {}

    def fake(system, user_message, required=("line",), **kwargs):
        seen.update(system=system, user=user_message, required=required)
        return reply

    monkeypatch.setattr(pe_feedback.llm_line, "request_json", fake)
    return seen


def test_feedback_gets_all_inputs_and_returns_line_and_reason(monkeypatch):
    seen = _fake_json(monkeypatch, {"line": "כמעט! בעצם הרגשתי שמחה, כי סיפרת שהצלחת בפרויקט.",
                                    "reason": "סיפרת שהצלחת בפרויקט"})

    out = pe_feedback.generate_feedback("HAPPINESS", "ספר/י על הצלחה", "הצלחתי בפרויקט גדול",
                                        "התלהבת", "Partial", "he", participant_gender="male")

    assert out == {"line": "כמעט! בעצם הרגשתי שמחה, כי סיפרת שהצלחת בפרויקט.",
                   "reason": "סיפרת שהצלחת בפרויקט"}
    assert set(seen["required"]) == {"line", "reason"}
    for part in ("TARGET: HAPPINESS (שמחה)", "QUESTION: ספר/י על הצלחה",
                 "ANSWER: הצלחתי בפרויקט גדול", "GUESS: התלהבת", "GRADE: Partial"):
        assert part in seen["user"]
    assert "Hebrew" in seen["system"] and "masculine form" in seen["system"]


def test_feedback_falls_back_to_naming_the_emotion(monkeypatch):
    _fake_json(monkeypatch, None)
    assert pe_feedback.generate_feedback("SADNESS", "Q", "A", "שמחת", "Wrong", "he") == {
        "line": "בעצם הרגשתי עצב.", "reason": ""}
    assert pe_feedback.generate_feedback("SADNESS", "Q", "A", "happy", "Wrong", "en") == {
        "line": "I actually felt sadness.", "reason": ""}


def test_flagged_feedback_falls_back(monkeypatch):
    _fake_json(monkeypatch, {"line": "הרגשתי שמחה כי נשמעת בטוחה.", "reason": "נשמעת בטוחה"})
    assert pe_feedback.generate_feedback("HAPPINESS", "Q", "A", "שמחת", "Correct")["line"] == "נכון, הרגשתי שמחה."


def test_fallback_wording_follows_the_grade(monkeypatch):
    _fake_json(monkeypatch, None)
    line = lambda grade, lang="he": pe_feedback.generate_feedback("SADNESS", "Q", "A", "g", grade, lang)["line"]
    assert line("Correct") == "נכון, הרגשתי עצב."
    assert line("Partial") == "קרוב, הרגשתי עצב."
    assert line("Wrong") == "בעצם הרגשתי עצב."
    assert line("???") == "בעצם הרגשתי עצב."  # unknown grade: the Wrong wording
    assert line("Correct", "en") == "That's right, I felt sadness."
    assert line("Partial", "en") == "Close, I actually felt sadness."


def test_feedback_asks_for_enough_tokens_and_bans_praise(monkeypatch):
    seen = {}

    def fake(system, user_message, required=("line",), **kwargs):
        seen.update(kwargs, system=system)
        return None

    monkeypatch.setattr(pe_feedback.llm_line, "request_json", fake)
    pe_feedback.generate_feedback("FEAR", "Q", "A", "g", "Correct")

    assert seen["max_tokens"] == 400
    assert "כל הכבוד" in seen["system"]
