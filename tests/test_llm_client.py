import pytest

import llm_client


class _FakeCompletions:
    def __init__(self, sink):
        self.sink = sink

    def create(self, **kwargs):
        self.sink.append(kwargs["model"])

        class R:
            choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]

        return R()


def _install(monkeypatch, calls, providers_seen):
    def fake_client_for(provider):
        providers_seen.append(provider)
        return type("Client", (), {"chat": type("Chat", (), {"completions": _FakeCompletions(calls)})()})()

    monkeypatch.setattr(llm_client, "_client_for", fake_client_for)


def test_override_routes_model_and_provider(monkeypatch):
    calls, providers = [], []
    _install(monkeypatch, calls, providers)
    monkeypatch.setitem(llm_client.config.LLM_MODELS, "test-model", {"provider": "openai", "display_name": "T"})

    with llm_client.model_override("test-model"):
        llm_client.call_llm("sys", "hi")
    llm_client.call_llm("sys", "hi")  # outside: back to default

    assert calls == ["test-model", llm_client.config.MODEL_DEFAULT]
    assert providers[0] == "openai"


def test_explicit_model_beats_override(monkeypatch):
    calls, providers = [], []
    _install(monkeypatch, calls, providers)

    with llm_client.model_override("gpt-4o-mini"):
        llm_client.call_llm("sys", "hi", model="llama3.1-8b")

    assert calls == ["llama3.1-8b"]


def test_provider_has_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.delenv("LAB_LLM_TOKEN", raising=False)
    assert llm_client.provider_has_key("openai") is True
    assert llm_client.provider_has_key("lab") is False


def test_client_for_missing_key_raises_helpful_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm_client._clients.pop("openai", None)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        llm_client._client_for("openai")
    assert "openai" not in llm_client._clients  # failure must not be cached
