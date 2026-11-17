import json

import pytest
import requests

from connectors import supabase_client as sb
BASE = "https://proj.supabase.co"


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.content = json.dumps(payload).encode() if payload is not None else b""
        self.text = self.content.decode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}", response=self)

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(sb.config, "SUPABASE_URL", BASE)
    monkeypatch.setattr(sb.config, "SUPABASE_KEY", "pubkey")
    monkeypatch.setattr(sb.config, "ENGINE_EMAIL", "engine@x.test")
    monkeypatch.setattr(sb.config, "ENGINE_PASSWORD", "pw")
    monkeypatch.setattr(sb, "_session", {"token": None, "expires_at": 0.0})


def _server(monkeypatch, *responses):
    """Fake network: sign-in always succeeds; data calls get `responses` in order."""
    calls = []
    queue = list(responses)

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        if "/auth/v1/token" in url:
            return FakeResponse({"access_token": f"tok{len(calls)}", "expires_in": 3600})
        payload, status = queue.pop(0)
        return FakeResponse(payload, status)

    monkeypatch.setattr(sb.requests, "request", fake_request)
    return calls


def _data_calls(calls):
    return [c for c in calls if "/auth/v1/" not in c["url"]]


def test_missing_credentials_raise(monkeypatch):
    monkeypatch.setattr(sb.config, "ENGINE_PASSWORD", "")
    with pytest.raises(sb.Base44Error):
        sb.get_record("Turn", "t1")


def test_signs_in_once_and_sends_both_headers(monkeypatch):
    calls = _server(monkeypatch, ([{"id": "t1"}], 200), ([{"id": "t2"}], 200))

    sb.get_record("Turn", "t1")
    sb.get_record("Turn", "t2")

    auth = [c for c in calls if "/auth/v1/token" in c["url"]]
    assert len(auth) == 1
    assert auth[0]["json"] == {"email": "engine@x.test", "password": "pw"}
    headers = _data_calls(calls)[0]["headers"]
    assert headers["apikey"] == "pubkey"
    assert headers["Authorization"] == "Bearer tok1"


def test_list_maps_entity_to_table_and_builds_filters(monkeypatch):
    calls = _server(monkeypatch, ([{"id": "t1"}], 200))

    result = sb.list_records("Turn", {"status": "awaiting_engine", "generated_by_engine": True},
                             sort="order", limit=5)

    assert result == [{"id": "t1"}]
    call = _data_calls(calls)[0]
    assert call["method"] == "GET"
    assert call["url"] == f"{BASE}/rest/v1/turns"
    assert call["params"]["status"] == "eq.awaiting_engine"
    assert call["params"]["generated_by_engine"] == "is.true"
    assert call["params"]["order"] == "order.asc"
    assert call["params"]["limit"] == 5


def test_descending_sort(monkeypatch):
    calls = _server(monkeypatch, ([], 200))
    sb.list_records("RobotCommand", sort="-sequence")
    call = _data_calls(calls)[0]
    assert call["url"] == f"{BASE}/rest/v1/robot_commands"
    assert call["params"]["order"] == "sequence.desc"


def test_filtering_on_order_column_is_refused(monkeypatch):
    # "order" is also PostgREST's sort parameter, so order=eq.3 would be misread
    _server(monkeypatch)
    with pytest.raises(sb.Base44Error):
        sb.list_records("Turn", {"order": 3})


def test_get_record_not_found_raises(monkeypatch):
    _server(monkeypatch, ([], 200))
    with pytest.raises(sb.Base44Error):
        sb.get_record("Persona", "missing")


def test_create_returns_the_new_row(monkeypatch):
    calls = _server(monkeypatch, ([{"id": "c1", "type": "say"}], 201))

    assert sb.create_record("RobotCommand", {"type": "say"}) == {"id": "c1", "type": "say"}
    call = _data_calls(calls)[0]
    assert call["method"] == "POST"
    assert call["json"] == {"type": "say"}
    assert call["headers"]["Prefer"] == "return=representation"


def test_update_patches_by_id(monkeypatch):
    calls = _server(monkeypatch, ([{"id": "t1", "status": "done"}], 200))

    assert sb.update_record("Turn", "t1", {"status": "done"})["status"] == "done"
    call = _data_calls(calls)[0]
    assert call["method"] == "PATCH"
    assert call["params"] == {"id": "eq.t1"}
    assert call["json"] == {"status": "done"}


def test_update_that_changes_no_row_raises(monkeypatch):
    # missing row, or the database's permissions blocked the write: the worker must know
    _server(monkeypatch, ([], 200))
    with pytest.raises(sb.Base44Error):
        sb.update_record("Turn", "t1", {"status": "done"})


def test_claim_true_when_row_still_in_from_status(monkeypatch):
    calls = _server(monkeypatch, ([{"id": "t1"}], 200))

    assert sb.claim("Turn", "t1", "awaiting_engine", {"status": "engine_processing"})
    call = _data_calls(calls)[0]
    assert call["method"] == "PATCH"
    assert call["params"] == {"id": "eq.t1", "status": "eq.awaiting_engine"}
    assert call["json"] == {"status": "engine_processing"}


def test_claim_false_when_already_taken(monkeypatch):
    _server(monkeypatch, ([], 200))
    assert not sb.claim("Turn", "t1", "awaiting_engine", {"status": "engine_processing"})


def test_expired_token_signs_in_again_and_retries_once(monkeypatch):
    calls = _server(monkeypatch, ({"message": "JWT expired"}, 401), ([{"id": "t1"}], 200))

    assert sb.get_record("Turn", "t1") == {"id": "t1"}
    assert len([c for c in calls if "/auth/v1/token" in c["url"]]) == 2
    assert _data_calls(calls)[1]["headers"]["Authorization"] == "Bearer tok3"


def test_429_raises_rate_limited(monkeypatch):
    _server(monkeypatch, ({"message": "slow down"}, 429))
    with pytest.raises(sb.RateLimited):
        sb.list_records("Session")


def test_http_error_raises_base44_error(monkeypatch):
    _server(monkeypatch, ({"message": "permission denied"}, 403))
    with pytest.raises(sb.Base44Error):
        sb.list_records("Session")
