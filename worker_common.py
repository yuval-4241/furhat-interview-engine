"""Shared by engine_worker.py and conversation_flow.py: the worker's id,
timestamps in the website's format, and log lines."""

import socket
from datetime import datetime, timezone

import config

WORKER_ID = f"{socket.gethostname()}-{config.ENGINE_VERSION}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)
