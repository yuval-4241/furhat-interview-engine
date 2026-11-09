"""
Base44 client — the only file that talks to the lab app's REST API
(Session, Turn, RobotCommand, EngineHeartbeat, ...), the same way
llm_client.py is the only file that imports openai.

The app is frontend + DB only: it never calls the Engine. The Engine polls
entities by status and writes its results back through these functions.

Unlike robot_bridge.py, errors RAISE (Base44Error) instead of being
swallowed — the polling worker has to know a write failed, or a turn could
be left stuck in a status nobody is watching.

API reference: https://docs.base44.com/api-reference
"""

import json

import requests

import config


class Base44Error(Exception):
    pass


class RateLimited(Base44Error):
    """HTTP 429 — Base44 wants us to slow down; the worker backs off."""


def _url(entity: str, suffix: str = "") -> str:
    if not config.BASE44_APP_ID:
        raise Base44Error("BASE44_APP_ID is not set")
    url = f"{config.BASE44_BASE_URL}/{config.BASE44_APP_ID}/entities/{entity}"
    return f"{url}/{suffix}" if suffix else url


def _headers() -> dict:
    if not config.BASE44_API_TOKEN:
        raise Base44Error("BASE44_API_TOKEN is not set")
    return {
        "Authorization": f"Bearer {config.BASE44_API_TOKEN}",
        "Content-Type": "application/json",
    }


def _request(method: str, url: str, **kwargs):
    try:
        resp = requests.request(
            method, url, headers=_headers(), timeout=config.BASE44_TIMEOUT, **kwargs
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        resp = e.response
        if getattr(resp, "status_code", None) == 429 or "rate limit" in getattr(resp, "text", "").lower():
            raise RateLimited(f"{method} {url} rate-limited (429)") from e
        raise Base44Error(f"{method} {url} failed: {e}") from e
    return resp.json() if resp.content else None


def list_records(entity: str, query: dict = None, sort: str = None, limit: int = 100) -> list:
    """Records matching `query` (exact-match dict, e.g. {"status": "awaiting_engine"})."""
    params = {"limit": limit}
    if query:
        params["q"] = json.dumps(query)
    if sort:
        params["sort"] = sort  # e.g. "order" or "-created_date"
    data = _request("GET", _url(entity, "v2/list"), params=params)
    # v2/list may wrap the records; accept either a bare list or {"items": [...]}
    if isinstance(data, dict):
        return data.get("items", [])
    return data or []


def get_record(entity: str, record_id: str) -> dict:
    return _request("GET", _url(entity, record_id))


def create_record(entity: str, fields: dict) -> dict:
    return _request("POST", _url(entity), json=fields)


def update_record(entity: str, record_id: str, fields: dict) -> dict:
    return _request("PUT", _url(entity, record_id), json={"id": record_id, **fields})


def claim(entity: str, record_id: str, from_status: str, fields: dict) -> bool:
    """
    Compare-and-set: apply `fields` only if the record is still in
    `from_status`. Returns True if this call changed it, False if someone
    else got there first. Used to move a Turn awaiting_engine ->
    engine_processing without two Engine instances processing it twice.
    """
    data = _request(
        "PATCH",
        _url(entity, "update-many"),
        json={"query": {"id": record_id, "status": from_status}, "data": {"$set": fields}},
    )
    return bool(data and data.get("updated") == 1)
