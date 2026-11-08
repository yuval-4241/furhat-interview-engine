import llm_line


def _fake_llm(monkeypatch, replies):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(llm_line.llm_client, "call_llm", fake)
    return calls


def test_request_line_returns_the_line(monkeypatch):
    _fake_llm(monkeypatch, ['```json\n{"line": "  שלום!  "}\n```'])
    assert llm_line.request_line("sys", "user") == "שלום!"


def test_request_line_retries_once_after_bad_json(monkeypatch):
    calls = _fake_llm(monkeypatch, ["not json", '{"line": "היי"}'])
    assert llm_line.request_line("sys", "user") == "היי"
    assert len(calls) == 2


def test_request_line_gives_up_after_two_failures(monkeypatch):
    calls = _fake_llm(monkeypatch, [TimeoutError("down"), '{"line": ""}'])
    assert llm_line.request_line("sys", "user") is None
    assert len(calls) == 2


def test_request_json_needs_every_required_field(monkeypatch):
    _fake_llm(monkeypatch, ['{"line": "x"}', '{"line": "x", "reason": "y"}'])
    assert llm_line.request_json("sys", "user", required=("line", "reason")) == {"line": "x", "reason": "y"}


def test_language_or_default():
    assert llm_line.language_or_default("en") == "en"
    assert llm_line.language_or_default(None) == "he"
    assert llm_line.language_or_default("fr") == "he"


def test_gender_rule():
    assert llm_line.gender_rule("en", "female", "male") == ""
    assert "feminine form" in llm_line.gender_rule("he", "female")
    assert "masculine form" in llm_line.gender_rule("he", "male")
    assert "unknown" in llm_line.gender_rule("he", None)
    assert "speaks about itself, use the feminine form" in llm_line.gender_rule("he", "male", "female")
