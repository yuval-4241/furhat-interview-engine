import pytest

import stt


class _FakeAlternative:
    def __init__(self, transcript):
        self.transcript = transcript


class _FakeResult:
    def __init__(self, transcript):
        self.alternatives = [_FakeAlternative(transcript)]


class _FakeResponse:
    def __init__(self, transcript):
        self.results = [_FakeResult(transcript)] if transcript else []


class _FakeClient:
    def __init__(self, transcript):
        self._transcript = transcript

    def recognize(self, config, audio):
        return _FakeResponse(self._transcript)


def test_transcribe_returns_the_transcript(monkeypatch):
    monkeypatch.setattr(stt, "_get_client", lambda: _FakeClient("שלום עולם"))

    result = stt.transcribe(b"fake-wav-bytes")

    assert result == "שלום עולם"


def test_transcribe_raises_sttError_on_empty_result(monkeypatch):
    monkeypatch.setattr(stt, "_get_client", lambda: _FakeClient(None))

    with pytest.raises(stt.SttError):
        stt.transcribe(b"fake-wav-bytes")


def test_transcribe_raises_sttError_on_client_exception(monkeypatch):
    class _BrokenClient:
        def recognize(self, config, audio):
            raise RuntimeError("quota exceeded")

    monkeypatch.setattr(stt, "_get_client", lambda: _BrokenClient())

    with pytest.raises(stt.SttError):
        stt.transcribe(b"fake-wav-bytes")
