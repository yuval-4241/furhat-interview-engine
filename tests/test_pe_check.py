import json

import pytest

import pe_check
from prompts.pe_check_prompt import HEBREW_NAMES, PE_CHECK_SYSTEM_PROMPT, WORD_LISTS


def _llm_returns(monkeypatch, text):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return text

    monkeypatch.setattr(pe_check.llm_client, "call_llm", fake)
    return seen


@pytest.mark.parametrize("result", ["Correct", "Partial", "Wrong"])
def test_grade_returns_each_result(monkeypatch, result):
    _llm_returns(monkeypatch, json.dumps({"result": result, "explanation": "הסבר"}))
    assert pe_check.grade_pe_answer("HAPPINESS", "התלהבת") == {"result": result, "explanation": "הסבר"}


def test_grade_sends_target_and_answer(monkeypatch):
    seen = _llm_returns(monkeypatch, '{"result": "Correct", "explanation": "x"}')
    pe_check.grade_pe_answer("ANGER", "נראה לי שכעסת")
    assert "Target emotion: ANGER" in seen["user_message"]
    assert "נראה לי שכעסת" in seen["user_message"]


@pytest.mark.parametrize("raw", ["not json", '{"result": "Maybe", "explanation": "x"}', '{"explanation": "x"}'])
def test_grade_fails_closed_to_wrong(monkeypatch, raw):
    _llm_returns(monkeypatch, raw)
    graded = pe_check.grade_pe_answer("ANGER", "לא יודעת")
    assert graded["result"] == "Wrong" and graded["explanation"]


def test_grade_lets_llm_errors_propagate(monkeypatch):
    def boom(**kwargs):
        raise TimeoutError("LLM down")

    monkeypatch.setattr(pe_check.llm_client, "call_llm", boom)
    with pytest.raises(TimeoutError):
        pe_check.grade_pe_answer("ANGER", "כועס")


def test_check_pe_answer_keeps_match_shape(monkeypatch):
    _llm_returns(monkeypatch, '{"result": "Partial", "explanation": "קרוב"}')
    assert pe_check.check_pe_answer("HAPPINESS", "התלהבת") == {
        "match": False, "explanation": "קרוב", "result": "Partial"}


def test_word_lists_cover_every_displayable_emotion():
    import emotion_classifier
    assert set(WORD_LISTS) == set(emotion_classifier.CORE_EMOTIONS) == set(HEBREW_NAMES)
    for target, lists in WORD_LISTS.items():
        assert lists["correct"], target
        assert target not in lists["partial"], target
        assert set(lists["partial"]) <= set(WORD_LISTS), target


def test_prompt_contains_the_spec_examples():
    assert "מאושר" in PE_CHECK_SYSTEM_PROMPT and "מתלהב" in PE_CHECK_SYSTEM_PROMPT
    assert '"Partial"' in PE_CHECK_SYSTEM_PROMPT
