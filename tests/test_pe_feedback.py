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
    assert pe_feedback.generate_feedback("HAPPINESS", "Q", "A", "שמחת", "Correct")["line"] == "בעצם הרגשתי שמחה."
