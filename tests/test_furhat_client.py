import json

import requests

import furhat_client


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_say_sends_text_and_reports_sent(monkeypatch):
    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeResponse(200)

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    result = furhat_client.say("שלום")

    assert result == {"sent": True, "reason": None}
    assert captured["url"].endswith("/say")
    assert "שלום" in captured["data"].decode("utf-8")


def test_react_sends_emotion_intensity_and_optional_text(monkeypatch):
    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeResponse(200)

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    result = furhat_client.react("HAPPINESS", 2, text="טוב")

    assert result == {"sent": True, "reason": None}
    assert captured["url"].endswith("/react")
    assert "HAPPINESS" in captured["data"].decode("utf-8")


def test_say_omits_language_and_gender_when_not_given(monkeypatch):
    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["data"] = data
        return _FakeResponse(200)

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)
    furhat_client.say("שלום")

    body = json.loads(captured["data"].decode("utf-8"))
    assert "language" not in body
    assert "gender" not in body


def test_say_includes_language_and_gender_when_given(monkeypatch):
    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["data"] = data
        return _FakeResponse(200)

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)
    furhat_client.say("Hello", language="ENGLISH", gender="MALE")

    body = json.loads(captured["data"].decode("utf-8"))
    assert body["language"] == "ENGLISH"
    assert body["gender"] == "MALE"


def test_react_includes_language_and_gender_when_given(monkeypatch):
    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["data"] = data
        return _FakeResponse(200)

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)
    furhat_client.react("HAPPINESS", 2, language="HEBREW", gender="FEMALE")

    body = json.loads(captured["data"].decode("utf-8"))
    assert body["language"] == "HEBREW"
    assert body["gender"] == "FEMALE"


def test_say_never_raises_on_connection_failure(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None):
        raise ConnectionError("robot unreachable")

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    result = furhat_client.say("שלום")

    assert result["sent"] is False
    assert "unreachable" in result["reason"]


def test_health_check_true_on_200(monkeypatch):
    monkeypatch.setattr(furhat_client.requests, "get", lambda url, timeout=None: _FakeResponse(200))
    assert furhat_client.health_check() is True


def test_health_check_false_on_connection_failure(monkeypatch):
    def fake_get(url, timeout=None):
        raise ConnectionError("robot unreachable")

    monkeypatch.setattr(furhat_client.requests, "get", fake_get)
    assert furhat_client.health_check() is False


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_listen_returns_bridge_result(monkeypatch):
    seen = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        seen.update(url=url, body=json.loads(data), timeout=timeout)
        return _Resp({"status": "ok", "text": "שלום"})

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    assert furhat_client.listen() == {"status": "ok", "text": "שלום"}
    assert seen["url"].endswith("/listen")
    assert seen["body"] == {"timeout": 10000, "endSil": 3000, "maxSpeech": 120000}
    assert seen["timeout"] > (10000 + 120000) / 1000  # HTTP wait covers the whole listen window


def test_listen_timeout_returns_failed(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ReadTimeout("slow")

    monkeypatch.setattr(furhat_client.requests, "post", boom)

    assert furhat_client.listen() == {"status": "failed", "text": ""}


def test_set_persona_sends_raw_utf8(monkeypatch):
    seen = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        seen["raw"] = data
        return _Resp({"status": "ok"})

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    assert furhat_client.set_persona("Isabel", "Asaf", "he") == {"sent": True, "reason": None, "bridge_error": False}
    assert "Asaf".encode() in seen["raw"] and "\\u" not in seen["raw"].decode("utf-8")


def test_set_persona_bridge_error_is_reported(monkeypatch):
    monkeypatch.setattr(furhat_client.requests, "post",
                        lambda *a, **k: _Resp({"status": "error", "message": "voice 'Asf': not found"}))

    result = furhat_client.set_persona("Isabel", "Asf", "he")

    assert result["sent"] is False and "Asf" in result["reason"]
    assert result["bridge_error"] is True  # the bridge answered, so retrying is pointless


def test_set_persona_connection_failure_is_not_a_bridge_error(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(furhat_client.requests, "post", boom)

    result = furhat_client.set_persona("Isabel", "Asaf", "he")

    assert result["sent"] is False and result["bridge_error"] is False


def test_set_persona_non_dict_json_is_not_sent(monkeypatch):
    monkeypatch.setattr(furhat_client.requests, "post", lambda *a, **k: _Resp(["oops"]))

    result = furhat_client.set_persona("Isabel", "Asaf", "he")

    assert result["sent"] is False and result["bridge_error"] is False


def test_listen_non_dict_json_returns_failed(monkeypatch):
    monkeypatch.setattr(furhat_client.requests, "post", lambda *a, **k: _Resp(None))

    assert furhat_client.listen() == {"status": "failed", "text": ""}
