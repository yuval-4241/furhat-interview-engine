"""
llm_client.py — Provider abstraction layer.

Every module that needs an LLM calls call_llm() from here.
Nothing else in the project imports `openai` directly.

Why this file exists: today it's the lab server. If that changes (real
OpenAI, Anthropic, a different lab box) — this is the ONE file that changes.
Everything else (personas.py, evaluator.py, ...) stays untouched.

This is an "OpenAI-compatible" client: the lab server speaks the same API
shape as OpenAI's, just with a different base_url and token.
"""

import contextlib
import contextvars
import os
from openai import OpenAI
import config

_client = None
_clients = {}  # provider name -> OpenAI client, built on first use
_model_override = contextvars.ContextVar("model_override", default=None)


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if config.LLM_PROVIDER == "openai":
            if not config.OPENAI_API_KEY:
                raise RuntimeError(
                    "OPENAI_API_KEY not set. Add it to .env (see .env.example)."
                )
            _client = OpenAI(api_key=config.OPENAI_API_KEY)
        else:
            if not config.LAB_LLM_TOKEN:
                raise RuntimeError(
                    "LAB_LLM_TOKEN not set. Run: export LAB_LLM_TOKEN='your_token' "
                    "(see .env.example)"
                )
            _client = OpenAI(
                base_url=config.LAB_LLM_BASE_URL,
                api_key=config.LAB_LLM_TOKEN,
            )
    return _client


def provider_has_key(provider: str) -> bool:
    return bool(os.environ.get(config.LLM_PROVIDERS[provider]["api_key_env"], ""))


def _client_for(provider: str) -> OpenAI:
    if provider not in _clients:
        p = config.LLM_PROVIDERS[provider]
        key = os.environ.get(p["api_key_env"], "")
        if not key:
            raise RuntimeError(
                f"{p['api_key_env']} not set. Add it to .env (see .env.example)."
            )
        kwargs = {"api_key": key}
        if p["base_url"]:
            kwargs["base_url"] = p["base_url"]
        _clients[provider] = OpenAI(**kwargs)
    return _clients[provider]


@contextlib.contextmanager
def model_override(engine_key: str):
    """Every call_llm(model=None) inside this block uses engine_key (the session's chosen model)."""
    token = _model_override.set(engine_key)
    try:
        yield
    finally:
        _model_override.reset(token)


def call_llm(
    system: str,
    user_message: str,
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    """
    Single-turn call. Returns plain text response.
    model=None -> uses config.MODEL_DEFAULT.
    """
    model = model or _model_override.get() or config.MODEL_DEFAULT
    entry = config.LLM_MODELS.get(model)
    client = _client_for(entry["provider"]) if entry else get_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content
