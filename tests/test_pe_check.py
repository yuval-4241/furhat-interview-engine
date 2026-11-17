import json

import pytest

from engine import pe_check
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
    graded = pe_check.grade_pe_answer("HAPPINESS", "התלהבת")
    assert graded["result"] == result and graded["explanation"] == "הסבר"


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
    from engine import emotion_classifier
    assert set(WORD_LISTS) == set(emotion_classifier.CORE_EMOTIONS) == set(HEBREW_NAMES)
    for target, lists in WORD_LISTS.items():
        assert lists["correct"], target
        assert target not in lists["partial"], target
        assert set(lists["partial"]) <= set(WORD_LISTS), target


def test_prompt_contains_the_spec_examples():
    assert "מאושר" in PE_CHECK_SYSTEM_PROMPT and "מתלהב" in PE_CHECK_SYSTEM_PROMPT
    assert '"Partial"' in PE_CHECK_SYSTEM_PROMPT


def test_surprise_is_partial_for_fear_but_not_the_other_way():
    """Researcher decision 2026-11-17: on the Furhat face fear reads as surprise
    (expression validation), so "surprised" for FEAR is Partial — one way only."""
    assert "SURPRISE" in WORD_LISTS["FEAR"]["partial"]
    assert "FEAR" not in WORD_LISTS["SURPRISE"]["partial"]
    assert "מופתע" in WORD_LISTS["FEAR"]["partial"]["SURPRISE"]


# ── reason grade (2026-11-17 spec) ───────────────────────────────────────────
def test_reason_grade_parsed(monkeypatch):
    _llm_returns(monkeypatch, json.dumps({"result": "Correct", "explanation": "x",
                                          "reason_result": "Matches", "reason_explanation": "אותה סיבה"}))
    graded = pe_check.grade_pe_answer("SURPRISE", "הופתעת כי סיפרתי משהו חדש", trigger="Told something new.")
    assert graded["reason_result"] == "Matches" and graded["reason_explanation"] == "אותה סיבה"


def test_unknown_reason_value_fails_closed(monkeypatch):
    _llm_returns(monkeypatch, json.dumps({"result": "Correct", "explanation": "x",
                                          "reason_result": "Maybe", "reason_explanation": "?"}))
    graded = pe_check.grade_pe_answer("SURPRISE", "הופתעת", trigger="Told something new.")
    assert graded["result"] == "Correct" and graded["reason_result"] == ""


def test_no_trigger_means_no_reason_grade(monkeypatch):
    seen = _llm_returns(monkeypatch, json.dumps({"result": "Correct", "explanation": "x",
                                                 "reason_result": "Matches", "reason_explanation": "y"}))
    graded = pe_check.grade_pe_answer("SURPRISE", "הופתעת")
    assert graded["reason_result"] == "" and graded["reason_explanation"] == ""
    assert "Recorded cause" not in seen["user_message"]


def test_trigger_goes_into_the_message(monkeypatch):
    seen = _llm_returns(monkeypatch, '{"result": "Correct", "explanation": "x"}')
    pe_check.grade_pe_answer("SURPRISE", "הופתעת", trigger="Told something new.")
    assert "Recorded cause of the reaction: Told something new." in seen["user_message"]


def test_prompt_grades_reason_on_content_only():
    assert all(v in PE_CHECK_SYSTEM_PROMPT for v in ("Matches", "Partly", "Missing"))
    assert "never" in PE_CHECK_SYSTEM_PROMPT.lower() and "wording" in PE_CHECK_SYSTEM_PROMPT


def test_reason_results_constant():
    assert pe_check.REASON_RESULTS == ("Matches", "Partly", "No", "Missing")


def test_check_pe_answer_shape_unchanged(monkeypatch):
    _llm_returns(monkeypatch, '{"result": "Correct", "explanation": "x"}')
    assert set(pe_check.check_pe_answer("HAPPINESS", "שמחת")) == {"match", "explanation", "result"}
