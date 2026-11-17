import base64
import json

import pytest

from connectors import stt
class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_transcribe_returns_the_transcript(monkeypatch):
    payload = {"results": [{"alternatives": [{"transcript": "שלום עולם"}]}]}
    monkeypatch.setattr(stt.requests, "post", lambda *a, **k: _FakeResponse(payload))

    result = stt.transcribe(b"fake-wav-bytes")

    assert result == "שלום עולם"


def test_transcribe_sends_api_key_and_base64_audio(monkeypatch):
    captured = {}
    payload = {"results": [{"alternatives": [{"transcript": "כן"}]}]}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(payload)

    monkeypatch.setattr(stt.requests, "post", fake_post)
    monkeypatch.setattr(stt.config, "GOOGLE_SPEECH_API_KEY", "fake-key")

    stt.transcribe(b"fake-wav-bytes", language_code="he-IL")

    assert captured["url"] == "https://speech.googleapis.com/v1/speech:recognize?key=fake-key"
    assert captured["json"]["config"]["languageCode"] == "he-IL"
    assert captured["json"]["config"]["encoding"] == "LINEAR16"
    assert captured["json"]["audio"]["content"] == base64.b64encode(b"fake-wav-bytes").decode("ascii")


def test_transcribe_raises_sttError_on_empty_result(monkeypatch):
    monkeypatch.setattr(stt.requests, "post", lambda *a, **k: _FakeResponse({"results": []}))

    with pytest.raises(stt.SttError):
        stt.transcribe(b"fake-wav-bytes")


def test_transcribe_raises_sttError_on_missing_results_key(monkeypatch):
    monkeypatch.setattr(stt.requests, "post", lambda *a, **k: _FakeResponse({}))

    with pytest.raises(stt.SttError):
        stt.transcribe(b"fake-wav-bytes")


def test_transcribe_raises_sttError_on_request_exception(monkeypatch):
    def fake_post(*a, **k):
        raise stt.requests.exceptions.RequestException("network down")

    monkeypatch.setattr(stt.requests, "post", fake_post)

    with pytest.raises(stt.SttError):
        stt.transcribe(b"fake-wav-bytes")


def test_transcribe_raises_sttError_on_http_error_status(monkeypatch):
    monkeypatch.setattr(stt.requests, "post", lambda *a, **k: _FakeResponse({}, status_code=403))

    with pytest.raises(stt.SttError):
        stt.transcribe(b"fake-wav-bytes")
