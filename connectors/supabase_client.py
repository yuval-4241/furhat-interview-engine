"""
Supabase client — talks to the new lab website (Supabase / PostgREST) with
the same functions as base44_client.py, so the worker and the flow don't
change. lab_db.py picks which one is used (config.LAB_BACKEND).

The Engine signs in as its own user (role "engine"); the database enforces
what that account may read and write. Errors RAISE Base44Error/RateLimited
(the same classes as base44_client), because the worker must know a write
failed.

API reference: the website repo's migration/ENGINE_API.md
"""

import threading
import time

import requests

import config
from connectors.base44_client import Base44Error, RateLimited

TABLES = {
    "Session": "sessions",
    "Turn": "turns",
    "RobotCommand": "robot_commands",
    "EngineHeartbeat": "engine_heartbeats",
    "Persona": "personas",
    "LLMModel": "llm_models",
    "Participant": "participants",
}

_session = {"token": None, "expires_at": 0.0}
_lock = threading.Lock()  # the heartbeat thread and the main loop share one token


def _check_config() -> None:
    missing = [n for n in ("SUPABASE_URL", "SUPABASE_KEY", "ENGINE_EMAIL", "ENGINE_PASSWORD")
               if not getattr(config, n)]
    if missing:
        raise Base44Error(f"not set: {', '.join(missing)}")


def _token(force: bool = False) -> str:
    """The Engine user's access token; signs in again when it is about to expire."""
    with _lock:
        if force or not _session["token"] or time.time() >= _session["expires_at"]:
            resp = requests.request(
                "POST", f"{config.SUPABASE_URL}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": config.SUPABASE_KEY, "Content-Type": "application/json"},
                json={"email": config.ENGINE_EMAIL, "password": config.ENGINE_PASSWORD},
                timeout=config.SUPABASE_TIMEOUT,
            )
            try:
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                raise Base44Error(f"Engine sign-in failed: {e}") from e
            data = resp.json()
            _session["token"] = data["access_token"]
            _session["expires_at"] = time.time() + data.get("expires_in", 3600) - 60
        return _session["token"]


def _table(entity: str) -> str:
    if entity not in TABLES:
        raise Base44Error(f"unknown entity {entity!r}")
    return TABLES[entity]


def _request(method: str, entity: str, params: dict = None, json: dict = None):
    _check_config()
    url = f"{config.SUPABASE_URL}/rest/v1/{_table(entity)}"
    for attempt in (1, 2):
        headers = {
            "apikey": config.SUPABASE_KEY,
            "Authorization": f"Bearer {_token(force=attempt == 2)}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        try:
            resp = requests.request(method, url, headers=headers, params=params, json=json,
                                    timeout=config.SUPABASE_TIMEOUT)
            resp.raise_for_status()
            return resp.json() if resp.content else []
        except requests.exceptions.RequestException as e:
            status = getattr(e.response, "status_code", None)
            if status == 401 and attempt == 1:
                continue  # token expired early: sign in again and retry once
            if status == 429:
                raise RateLimited(f"{method} {url} rate-limited (429)") from e
            raise Base44Error(f"{method} {url} failed: {e}") from e


def _filter(value) -> str:
    if value is None:
        return "is.null"
    if isinstance(value, bool):
        return f"is.{str(value).lower()}"
    return f"eq.{value}"


def list_records(entity: str, query: dict = None, sort: str = None, limit: int = 100) -> list:
    """Records matching `query` (exact-match dict, e.g. {"status": "awaiting_engine"})."""
    params = {"select": "*", "limit": limit}
    for field, value in (query or {}).items():
        if field == "order":
            raise Base44Error("can't filter on the 'order' column (it is PostgREST's sort parameter)")
        params[field] = _filter(value)
    if sort:
        params["order"] = f"{sort[1:]}.desc" if sort.startswith("-") else f"{sort}.asc"
    return _request("GET", entity, params=params)


def get_record(entity: str, record_id: str) -> dict:
    rows = _request("GET", entity, params={"select": "*", "id": f"eq.{record_id}"})
    if not rows:
        raise Base44Error(f"{entity} {record_id} not found")
    return rows[0]


def create_record(entity: str, fields: dict) -> dict:
    return _request("POST", entity, json=fields)[0]


def update_record(entity: str, record_id: str, fields: dict) -> dict:
    rows = _request("PATCH", entity, params={"id": f"eq.{record_id}"}, json=fields)
    if not rows:  # no such row, or the database's permissions refused the write
        raise Base44Error(f"{entity} {record_id} not updated (missing or not allowed)")
    return rows[0]


def claim(entity: str, record_id: str, from_status: str, fields: dict) -> bool:
    """
    Compare-and-set: apply `fields` only if the record is still in
    `from_status`. An empty result means another worker got there first.
    """
    rows = _request("PATCH", entity,
                    params={"id": f"eq.{record_id}", "status": f"eq.{from_status}"}, json=fields)
    return bool(rows)
