import acknowledgement
from prompts.acknowledgement_prompt import FALLBACK_LINES


def test_acknowledge_returns_clean_line(monkeypatch):
    seen = {}
    monkeypatch.setattr(acknowledgement.llm_line, "request_line",
                        lambda system, user_message: seen.update(system=system, user=user_message)
                        or "תודה, אז עבדת שלוש שנים בשירות לקוחות. נמשיך.")

    ack = acknowledgement.acknowledge("ספר/י על עצמך", "עבדתי שלוש שנים בשירות לקוחות", "he",
                                      participant_gender="female")

    assert ack == {"line": "תודה, אז עבדת שלוש שנים בשירות לקוחות. נמשיך.",
                   "guardrail_flag": False, "guardrail_reason": ""}
    assert "עבדתי שלוש שנים" in seen["user"]
    assert "feminine form" in seen["system"]


def test_flagged_line_is_replaced_by_fallback(monkeypatch):
    monkeypatch.setattr(acknowledgement.llm_line, "request_line",
                        lambda system, user_message: "תשובה מצוינת, נמשיך.")

    ack = acknowledgement.acknowledge("Q", "A", "he")

    assert ack["line"] == FALLBACK_LINES["he"]
    assert ack["guardrail_flag"] is True
    assert "תשובה מצוינת" in ack["guardrail_reason"]


def test_llm_failure_falls_back_without_flag(monkeypatch):
    monkeypatch.setattr(acknowledgement.llm_line, "request_line", lambda system, user_message: None)

    ack = acknowledgement.acknowledge("Q", "A")

    assert ack == {"line": "תודה, נמשיך.", "guardrail_flag": False, "guardrail_reason": ""}
