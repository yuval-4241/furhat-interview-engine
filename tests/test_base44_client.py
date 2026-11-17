import json

import pytest
import requests

from connectors import base44_client
class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.content = json.dumps(payload).encode() if payload is not None else b""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(base44_client.config, "BASE44_APP_ID", "app123")
    monkeypatch.setattr(base44_client.config, "BASE44_API_TOKEN", "tok")


def _capture(monkeypatch, payload, status=200):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse(payload, status)

    monkeypatch.setattr(base44_client.requests, "request", fake_request)
    return calls


def test_missing_token_raises(monkeypatch):
    monkeypatch.setattr(base44_client.config, "BASE44_APP_ID", "app123")
    monkeypatch.setattr(base44_client.config, "BASE44_API_TOKEN", "")
    with pytest.raises(base44_client.Base44Error):
        base44_client.get_record("Turn", "t1")


def test_list_sends_bearer_and_json_filter(configured, monkeypatch):
    calls = _capture(monkeypatch, [{"id": "t1"}])

    result = base44_client.list_records("Turn", {"status": "awaiting_engine"}, sort="order")

    assert result == [{"id": "t1"}]
    call = calls[0]
    assert call["url"] == "https://app.base44.com/api/apps/app123/entities/Turn/v2/list"
    assert call["headers"]["Authorization"] == "Bearer tok"
    assert json.loads(call["params"]["q"]) == {"status": "awaiting_engine"}
    assert call["params"]["sort"] == "order"


def test_list_accepts_wrapped_items(configured, monkeypatch):
    _capture(monkeypatch, {"items": [{"id": "t1"}]})
    assert base44_client.list_records("Turn") == [{"id": "t1"}]


def test_claim_true_only_when_exactly_one_record_updated(configured, monkeypatch):
    calls = _capture(monkeypatch, {"success": True, "updated": 1})

    assert base44_client.claim("Turn", "t1", "awaiting_engine", {"status": "engine_processing"})
    body = calls[0]["json"]
    assert body["query"] == {"id": "t1", "status": "awaiting_engine"}
    assert body["data"] == {"$set": {"status": "engine_processing"}}


def test_claim_false_when_already_taken(configured, monkeypatch):
    _capture(monkeypatch, {"success": True, "updated": 0})
    assert not base44_client.claim("Turn", "t1", "awaiting_engine", {"status": "engine_processing"})


def test_http_error_raises_base44_error(configured, monkeypatch):
    _capture(monkeypatch, {"error": "nope"}, status=401)
    with pytest.raises(base44_client.Base44Error):
        base44_client.update_record("Turn", "t1", {"proposed_reply": "x"})


def test_429_raises_rate_limited(configured, monkeypatch):
    class Resp429(FakeResponse):
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("429", response=self)

    monkeypatch.setattr(base44_client.requests, "request",
                        lambda *a, **k: Resp429({"error": "slow down"}, 429))
    with pytest.raises(base44_client.RateLimited):
        base44_client.list_records("Turn")
