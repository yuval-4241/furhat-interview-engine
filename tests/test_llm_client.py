import pytest

import config
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


def test_current_model_follows_override():
    assert llm_client.current_model() == config.MODEL_DEFAULT
    with llm_client.model_override("llama3.1-8b"):
        assert llm_client.current_model() == "llama3.1-8b"
    assert llm_client.current_model() == config.MODEL_DEFAULT


def test_clients_get_timeout_and_retry_limits(monkeypatch):
    built = []

    def fake_openai(**kwargs):
        built.append(kwargs)
        return object()

    monkeypatch.setattr(llm_client, "OpenAI", fake_openai)
    monkeypatch.setattr(llm_client, "_client", None)
    monkeypatch.setattr(llm_client, "_clients", {})
    monkeypatch.setattr(llm_client.config, "LLM_PROVIDER", "lab")
    monkeypatch.setattr(llm_client.config, "LAB_LLM_TOKEN", "t")
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    llm_client.get_client()
    llm_client._client_for("openai")

    assert len(built) == 2
    for kwargs in built:
        assert kwargs["timeout"] == config.LLM_TIMEOUT_SECONDS == 60
        assert kwargs["max_retries"] == config.LLM_MAX_RETRIES == 1


def _capture_kwargs(monkeypatch, content="ok"):
    sent = []

    class Completions:
        def create(self, **kwargs):
            sent.append(kwargs)
            return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": content})()})()]})()

    monkeypatch.setattr(llm_client, "_client_for",
                        lambda provider: type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})())
    return sent


def test_role_model_beats_session_override(monkeypatch):
    sent = _capture_kwargs(monkeypatch)
    monkeypatch.setitem(llm_client.config.LLM_ROLE_MODELS, "judgment", "openai/gpt-5")

    with llm_client.model_override("gpt-4o-mini"):
        llm_client.call_llm("sys", "hi", role="judgment")
        llm_client.call_llm("sys", "hi", role="lines")  # no lines model set -> session model
        assert llm_client.current_model("judgment") == "openai/gpt-5"
        assert llm_client.current_model("lines") == "gpt-4o-mini"

    assert [s["model"] for s in sent] == ["openai/gpt-5", "gpt-4o-mini"]


def test_reasoning_model_drops_temperature_and_gets_thinking_budget(monkeypatch):
    sent = _capture_kwargs(monkeypatch)

    llm_client.call_llm("sys", "hi", model="openai/gpt-5", temperature=0.3, max_tokens=400)

    kwargs = sent[0]
    assert "temperature" not in kwargs
    assert kwargs["max_tokens"] == 400 + config.REASONING_TOKEN_BUDGET
    assert kwargs["extra_body"] == {"reasoning": {"effort": config.REASONING_EFFORT}}


def test_plain_model_keeps_temperature(monkeypatch):
    sent = _capture_kwargs(monkeypatch)
    llm_client.call_llm("sys", "hi", model="gpt-4o-mini", temperature=0.8, max_tokens=200)
    assert sent[0]["temperature"] == 0.8 and sent[0]["max_tokens"] == 200
    assert "extra_body" not in sent[0]


def test_gpt_oss_gets_thinking_budget_but_keeps_temperature(monkeypatch):
    # it thinks too: without the budget a 100-token line came back empty (2026-11-10)
    sent = _capture_kwargs(monkeypatch)
    llm_client.call_llm("sys", "hi", model="openai/gpt-oss-20b", temperature=0.8, max_tokens=100)
    assert sent[0]["temperature"] == 0.8
    assert sent[0]["max_tokens"] == 100 + config.REASONING_TOKEN_BUDGET


def test_empty_content_returns_empty_string(monkeypatch):
    _capture_kwargs(monkeypatch, content=None)
    assert llm_client.call_llm("sys", "hi", model="openai/gpt-5") == ""


def test_openrouter_models_are_registered():
    for key in ("openai/gpt-5", "openai/gpt-oss-20b"):
        assert config.LLM_MODELS[key]["provider"] == "openrouter"
    assert config.LLM_PROVIDERS["openrouter"]["api_key_env"] == "OPENROUTER_API_KEY"
