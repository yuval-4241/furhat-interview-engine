"""
model_registry.py — keeps the website's LLMModel list in sync with
config.LLM_MODELS (the one place new models are added), and resolves which
model a Session should run on.
"""

import base44_client as b44
import config
import llm_client

_engine_key_cache = {}  # LLMModel id -> engine_key (saves Base44 list budget)


def sync_to_base44() -> None:
    """Upsert every registry model; active = its provider's key is set. Never deletes."""
    existing = {r.get("engine_key"): r for r in b44.list_records("LLMModel", limit=500)}
    for key, entry in config.LLM_MODELS.items():
        fields = {"engine_key": key, "display_name": entry["display_name"],
                  "active": llm_client.provider_has_key(entry["provider"])}
        if key in existing:
            b44.update_record("LLMModel", existing[key]["id"], fields)
        else:
            b44.create_record("LLMModel", fields)
    for key, rec in existing.items():
        if key not in config.LLM_MODELS and rec.get("active"):
            b44.update_record("LLMModel", rec["id"], {"active": False})


def model_for_session(session: dict) -> str:
    model_id = session.get("llm_model")
    if not model_id:
        return config.MODEL_DEFAULT
    if model_id not in _engine_key_cache:
        try:
            rec = b44.get_record("LLMModel", model_id)
            key = rec.get("engine_key") if rec.get("active") else None
        except b44.RateLimited:
            raise
        except b44.Base44Error:
            key = None  # e.g. the model record was deleted; cache it so we don't retry every poll
        if key not in config.LLM_MODELS:
            key = None
            print(f"[model_registry] session model {model_id!r} unavailable — using {config.MODEL_DEFAULT}")
        _engine_key_cache[model_id] = key
    return _engine_key_cache[model_id] or config.MODEL_DEFAULT
