import json
import os

import config
import interaction_log


def test_log_turn_appends_one_jsonl_record(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", str(tmp_path))

    interaction_log.log_turn("S001", {"turn": 1, "question": "שאלה"})
    interaction_log.log_turn("S001", {"turn": 2, "question": "שאלה 2"})

    path = os.path.join(str(tmp_path), "S001.jsonl")
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]

    assert len(lines) == 2
    assert lines[0]["turn"] == 1
    assert lines[1]["turn"] == 2


def test_log_technical_appends_to_shared_log(tmp_path, monkeypatch):
    log_path = str(tmp_path / "technical_log.jsonl")
    monkeypatch.setattr(config, "TECHNICAL_LOG_PATH", log_path)

    interaction_log.log_technical("stt", 1234.5, error="timeout")

    with open(log_path, encoding="utf-8") as f:
        record = json.loads(f.readline())

    assert record["component"] == "stt"
    assert record["elapsed_ms"] == 1234.5
    assert record["error"] == "timeout"


def test_list_sessions_returns_one_entry_per_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", str(tmp_path))
    interaction_log.log_turn("S001", {"turn": 1})
    interaction_log.log_turn("S002", {"turn": 1})

    sessions = interaction_log.list_sessions()

    assert {s["session_id"] for s in sessions} == {"S001", "S002"}
    assert all(s["turn_count"] == 1 for s in sessions)


def test_load_session_returns_all_records_in_order(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", str(tmp_path))
    interaction_log.log_turn("S001", {"turn": 1})
    interaction_log.log_turn("S001", {"turn": 2})

    records = interaction_log.load_session("S001")

    assert [r["turn"] for r in records] == [1, 2]
