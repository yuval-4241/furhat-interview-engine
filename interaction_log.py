"""
interaction_log.py -- per-session JSONL logging for the live interaction
demo, plus a shared technical log for errors/timings. Same "log
everything regardless of outcome" convention graph.py's finalize()
already follows -- every turn gets a record, success or failure.

One file per session (data/sessions/<session_id>.jsonl) rather than one
cumulative file, so a researcher can open/export a single session
without filtering a growing shared log.
"""

import glob
import json
import os

import config


def log_turn(session_id: str, record: dict) -> None:
    os.makedirs(config.SESSIONS_DIR, exist_ok=True)
    path = os.path.join(config.SESSIONS_DIR, f"{session_id}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_technical(component: str, elapsed_ms: float, error: str = None) -> None:
    os.makedirs(os.path.dirname(config.TECHNICAL_LOG_PATH), exist_ok=True)
    record = {"component": component, "elapsed_ms": elapsed_ms, "error": error}
    with open(config.TECHNICAL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_sessions() -> list:
    if not os.path.isdir(config.SESSIONS_DIR):
        return []

    sessions = []
    for path in sorted(glob.glob(os.path.join(config.SESSIONS_DIR, "*.jsonl"))):
        session_id = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            turn_count = sum(1 for _ in f)
        sessions.append({"session_id": session_id, "turn_count": turn_count})
    return sessions


def load_session(session_id: str) -> list:
    path = os.path.join(config.SESSIONS_DIR, f"{session_id}.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]
