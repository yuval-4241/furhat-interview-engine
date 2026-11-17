import reaction_line
from prompts.reaction_line_prompt import FALLBACK_LINES
from emotion_classifier import CORE_EMOTIONS


def _fake(monkeypatch, line, seen=None):
    def fake(system, user_message):
        if seen is not None:
            seen.update(system=system, user=user_message)
        return line
    monkeypatch.setattr(reaction_line.llm_line, "request_line", fake)


def test_returns_the_generated_line_and_sends_emotion_gender_and_answer(monkeypatch):
    seen = {}
    _fake(monkeypatch, "אוי, ביטלו לך את הטיסה לספרד?", seen)

    line = reaction_line.generate("SADNESS", 3, "ספר על אכזבה", "הטיול לספרד בוטל",
                                  "he", participant_gender="female", robot_gender="male")

    assert line == "אוי, ביטלו לך את הטיסה לספרד?"
    assert "SADNESS" in seen["system"] and "strong" in seen["system"]
    assert "masculine form" in seen["system"] and "feminine form" in seen["system"]
    assert "הטיול לספרד בוטל" in seen["user"]


def test_line_that_names_the_emotion_falls_back(monkeypatch):
    """The PE question asks what the robot felt; the line must not give it away."""
    _fake(monkeypatch, "זה ממש עצב לשמוע את זה")
    assert reaction_line.generate("SADNESS", 2, "Q", "A") == FALLBACK_LINES["he"]["SADNESS"]


def test_line_with_an_emotion_word_falls_back(monkeypatch):
    _fake(monkeypatch, "אני ממש שמח בשבילך")
    assert reaction_line.generate("HAPPINESS", 2, "Q", "A") == FALLBACK_LINES["he"]["HAPPINESS"]


def test_flagged_line_falls_back(monkeypatch):
    _fake(monkeypatch, "תשובה מעולה, ספר עוד")
    assert reaction_line.generate("EXCITED", 3, "Q", "A") == FALLBACK_LINES["he"]["EXCITED"]


def test_llm_failure_falls_back(monkeypatch):
    _fake(monkeypatch, None)
    assert reaction_line.generate("FEAR", 2, "Q", "A") == FALLBACK_LINES["he"]["FEAR"]


def test_every_emotion_has_a_fallback_that_does_not_name_it():
    for lang, lines in FALLBACK_LINES.items():
        assert set(lines) == set(CORE_EMOTIONS), lang
    for emotion, line in FALLBACK_LINES["he"].items():
        assert not reaction_line.names_emotion(emotion, line), emotion


def test_prompt_asks_for_two_sentences_and_a_closing_remark_that_is_never_a_question(monkeypatch):
    seen = {}
    _fake(monkeypatch, "line", seen)
    reaction_line.generate("SURPRISE", 2, "Q", "A")
    assert "2 sentences, plus an optional third" in seen["system"]
    assert "Never a question" in seen["system"]
    assert "ONE short sentence" not in seen["system"]
