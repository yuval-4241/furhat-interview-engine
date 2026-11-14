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


def say(text: str, language: str = None, gender: str = None) -> dict:
    payload = {"text": text}
    if language:
        payload["language"] = language
    if gender:
        payload["gender"] = gender
    return _post("/say", payload)


def react(emotion: str, intensity: int, text: str = None, language: str = None, gender: str = None) -> dict:
    payload = {"emotion": emotion, "intensity": intensity}
    if text:
        payload["text"] = text
    if language:
        payload["language"] = language
    if gender:
        payload["gender"] = gender
    payload["wait_seconds"] = config.ROBOT_REACT_WAIT_SECONDS
    # Returns when the robot has finished the reaction and is back at neutral.
    return _post("/react", payload, timeout=config.REACT_TIMEOUT_SECONDS)


def play_gesture(gesture: dict) -> dict:
    """Plays one gesture given as listening_gestures.py JSON (for the researcher's review)."""
    return _post("/gesture", gesture)


def listen(backchannel: bool = True) -> dict:
    """Blocks until the robot finishes listening (up to ~2.5 min). Never raises.
    backchannel: the robot nods/raises its brows now and then while listening;
    off for the PE answer, where a nod could read as "correct"."""
    payload = {
        "timeout": config.LISTEN_TIMEOUT_MS,
        "endSil": config.LISTEN_END_SIL_MS,
        "maxSpeech": config.LISTEN_MAX_SPEECH_MS,
        "backchannel": backchannel,
    }
    wait_s = (config.LISTEN_TIMEOUT_MS + config.LISTEN_MAX_SPEECH_MS) / 1000 + 40
    try:
        resp = requests.post(
            f"{config.ROBOT_BRIDGE_BASE_URL}/listen",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=wait_s,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return {"status": "failed", "text": ""}
        return {"status": data.get("status", "failed"), "text": data.get("text", "")}
    except (requests.exceptions.RequestException, ConnectionError, ValueError):
        return {"status": "failed", "text": ""}


def set_persona(character: str = None, voice: str = None, language: str = None) -> dict:
    """Switch the robot's face (Furhat character) and voice (Furhat voice name). Never raises.

    bridge_error is True only when the bridge answered but refused (e.g. unknown voice) -- retrying
    won't help. A connection failure leaves it False so the caller can retry later.
    """
    payload = {k: v for k, v in {"character": character, "voice": voice, "language": language}.items() if v}
    try:
        resp = requests.post(
            f"{config.ROBOT_BRIDGE_BASE_URL}/persona",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.exceptions.RequestException, ConnectionError, ValueError) as e:
        return {"sent": False, "reason": str(e), "bridge_error": False}
    if not isinstance(data, dict):
        return {"sent": False, "reason": "unexpected bridge response", "bridge_error": False}
    if data.get("status") != "ok":
        return {"sent": False, "reason": data.get("message", "unknown error"), "bridge_error": True}
    return {"sent": True, "reason": None, "bridge_error": False}


def health_check() -> bool:
    try:
        resp = requests.get(f"{config.ROBOT_BRIDGE_BASE_URL}/health", timeout=TIMEOUT)
        resp.raise_for_status()
        return True
    except (requests.exceptions.RequestException, ConnectionError):
        return False


def _post(path: str, payload: dict, timeout: float = TIMEOUT) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        resp = requests.post(
            f"{config.ROBOT_BRIDGE_BASE_URL}{path}",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return {"sent": True, "reason": None}
    except (requests.exceptions.RequestException, ConnectionError) as e:
        return {"sent": False, "reason": str(e)}
