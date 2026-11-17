import pytest

from evaluation import guardrail
from evaluation.guardrail import GuardrailResult, check_rationale


def test_no_matches_passes_with_zero_score():
    result = check_rationale("The candidate described a specific project and its outcome.")
    assert result.passed is True
    assert result.matched_patterns == []
    assert result.style_leakage_score == 0


def test_matches_fail_with_positive_score():
    result = check_rationale("The candidate lacked eye contact and seemed nervous.")
    assert result.passed is False
    assert result.style_leakage_score == len(result.matched_patterns)
    assert result.style_leakage_score >= 1


def test_as_dict_keeps_existing_keys_unchanged():
    result = check_rationale("Specific and relevant content only.")
    d = result.as_dict()
    assert d["passed"] is True
    assert d["matched_patterns"] == []


def test_as_dict_includes_new_style_leakage_score_key():
    result = check_rationale("The candidate sounded robotic and was too blunt.")
    d = result.as_dict()
    assert "style_leakage_score" in d
    assert d["style_leakage_score"] == len(d["matched_patterns"])


def test_style_leakage_score_always_derived_even_when_constructed_directly():
    """style_leakage_score can't be set independently of matched_patterns —
    it's always recomputed, so the two can never drift out of sync."""
    result = GuardrailResult(passed=False, matched_patterns=["eye contact", "monotone"])
    assert result.style_leakage_score == 2


@pytest.mark.parametrize("line", [
    "תודה. שמתי לב שלא היה קשר עין.",
    "נשמעת לחוצה, אבל נמשיך.",
    "אתה נשמע לחוץ היום.",
    "אתה נראה לחוץ, נמשיך.",
    "אתה נשמע בטוח בעצמך.",
    "תשובה מצוינת! נמשיך.",
    "כדאי לשים לב למבנה התשובה.",
    "התשובה הייתה ארוכה מדי.",
])
def test_hebrew_delivery_and_praise_lines_are_flagged(line):
    assert guardrail.check_rationale(line).passed is False


@pytest.mark.parametrize("line", [
    "תודה, אז היית לחוץ בעבודה הקודמת ולמדת לתעדף משימות. נמשיך.",
    "תודה, אז עבדת שלוש שנים בשירות לקוחות. נמשיך.",
    "בעצם הרגשתי שמחה, כי סיפרת שהצלחת בפרויקט.",
])
def test_hebrew_content_lines_pass(line):
    assert guardrail.check_rationale(line).passed is True
