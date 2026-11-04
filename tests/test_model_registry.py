import pytest

import model_registry
from tests.test_engine_worker import FakeBase44


@pytest.fixture
def fake(monkeypatch):
    store = FakeBase44()
    monkeypatch.setattr(model_registry, "b44", store)
    monkeypatch.setattr(model_registry, "_engine_key_cache", {})
    monkeypatch.setattr(model_registry.config, "LLM_MODELS", {
        "gpt-4o-mini": {"provider": "openai", "display_name": "GPT-4o mini"},
        "llama3.1-8b": {"provider": "lab", "display_name": "Llama 3.1 8B"},
    })
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.delenv("LAB_LLM_TOKEN", raising=False)
    return store


def test_sync_creates_records_with_active_flag(fake):
    model_registry.sync_to_base44()

    rows = {r["engine_key"]: r for r in fake.list_records("LLMModel")}
    assert rows["gpt-4o-mini"]["active"] is True
    assert rows["llama3.1-8b"]["active"] is False
    assert rows["gpt-4o-mini"]["display_name"] == "GPT-4o mini"


def test_sync_deactivates_models_without_key(fake):
    old = fake.add("LLMModel", engine_key="removed-model", display_name="Old", active=True)

    model_registry.sync_to_base44()
    model_registry.sync_to_base44()  # idempotent: no duplicates

    assert fake.get("LLMModel", old["id"])["active"] is False
    assert len(fake.list_records("LLMModel", {"engine_key": "gpt-4o-mini"})) == 1


def test_model_for_session_uses_chosen_model(fake):
    m = fake.add("LLMModel", engine_key="gpt-4o-mini", display_name="GPT-4o mini", active=True)
    assert model_registry.model_for_session({"llm_model": m["id"]}) == "gpt-4o-mini"


def test_model_for_session_falls_back_when_key_missing(fake):
    m = fake.add("LLMModel", engine_key="llama3.1-8b", display_name="Llama", active=False)
    assert model_registry.model_for_session({"llm_model": m["id"]}) == model_registry.config.MODEL_DEFAULT
    assert model_registry.model_for_session({}) == model_registry.config.MODEL_DEFAULT
