import json

import pe_check


def test_match_true_when_llm_confirms(monkeypatch):
    def fake_call_llm(system, user_message, max_tokens=150, temperature=0.3, model=None):
        return json.dumps({"match": True, "explanation": "Correctly named anger."})

    monkeypatch.setattr(pe_check.llm_client, "call_llm", fake_call_llm)

    result = pe_check.check_pe_answer("ANGER", "נראה לי שהיית כועס")

    assert result == {"match": True, "explanation": "Correctly named anger."}


def test_match_false_when_llm_denies(monkeypatch):
    def fake_call_llm(system, user_message, max_tokens=150, temperature=0.3, model=None):
        return json.dumps({"match": False, "explanation": "Participant said happy, ground truth was anger."})

    monkeypatch.setattr(pe_check.llm_client, "call_llm", fake_call_llm)

    result = pe_check.check_pe_answer("ANGER", "חשבתי שהיית שמח")

    assert result["match"] is False


def test_fails_closed_on_malformed_response(monkeypatch):
    def fake_call_llm(system, user_message, max_tokens=150, temperature=0.3, model=None):
        return "not json"

    monkeypatch.setattr(pe_check.llm_client, "call_llm", fake_call_llm)

    result = pe_check.check_pe_answer("ANGER", "לא יודעת")

    assert result["match"] is False
    assert result["explanation"]
