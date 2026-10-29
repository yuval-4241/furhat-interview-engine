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
