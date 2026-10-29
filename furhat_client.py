"""
furhat_client.py -- HTTP client for furhat-emotion-study's RemoteControl
bridge, for the live interaction demo (interaction_app.py).

Unlike robot_bridge.py (gated behind config.ROBOT_REACTION_ENABLED, used
by the synthetic-persona pipeline), this module always attempts the
call -- the live-interaction app's whole purpose is talking to a real/
virtual robot. Never raises: a disconnected robot must never break a
live session, it just means the turn continues without a robot reaction
(interaction_app.py surfaces that to the operator).
"""

import json

import requests

import config

TIMEOUT = 2.0  # seconds -- same budget robot_bridge.py uses


def say(text: str) -> dict:
    return _post("/say", {"text": text})


def react(emotion: str, intensity: int, text: str = None) -> dict:
    payload = {"emotion": emotion, "intensity": intensity}
    if text:
        payload["text"] = text
    return _post("/react", payload)


def health_check() -> bool:
    try:
        resp = requests.get(f"{config.ROBOT_BRIDGE_BASE_URL}/health", timeout=TIMEOUT)
        resp.raise_for_status()
        return True
    except (requests.exceptions.RequestException, ConnectionError):
        return False


def _post(path: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        resp = requests.post(
            f"{config.ROBOT_BRIDGE_BASE_URL}{path}",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return {"sent": True, "reason": None}
    except (requests.exceptions.RequestException, ConnectionError) as e:
        return {"sent": False, "reason": str(e)}
