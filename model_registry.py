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
        except b44.RateLimited:
            raise
        except b44.Base44Error as e:
            # can't tell a deleted record from a 5xx/timeout, so treat it as transient: don't cache
            print(f"[model_registry] session model {model_id!r} lookup failed ({e}) — using {config.MODEL_DEFAULT}")
            return config.MODEL_DEFAULT
        key = rec.get("engine_key")
        if not (rec.get("active") and key in config.LLM_MODELS
                and llm_client.provider_has_key(config.LLM_MODELS[key]["provider"])):
            key = None
            print(f"[model_registry] session model {model_id!r} unavailable — using {config.MODEL_DEFAULT}")
        _engine_key_cache[model_id] = key  # definitive answer; warn once
    return _engine_key_cache[model_id] or config.MODEL_DEFAULT
