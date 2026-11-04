import itertools

import pytest

import engine_worker


class FakeBase44:
    """In-memory stand-in for base44_client: exact-match queries, compare-and-set claim."""

    Base44Error = engine_worker.b44.Base44Error
    RateLimited = engine_worker.b44.RateLimited

    def __init__(self):
        self.records = {}
        self._ids = itertools.count(1)

    def add(self, entity, **fields):
        rec = {"id": f"{entity}-{next(self._ids)}", **fields}
        self.records.setdefault(entity, []).append(rec)
        return rec

    def list_records(self, entity, query=None, sort=None, limit=100):
        rows = [r for r in self.records.get(entity, [])
                if all(r.get(k) == v for k, v in (query or {}).items())]
        if sort:
            rows.sort(key=lambda r: r.get(sort))
        return [dict(r) for r in rows[:limit]]

    def get(self, entity, record_id):
        return next(r for r in self.records[entity] if r["id"] == record_id)

    get_record = get  # real client's name, so model_registry can use this fake too

    def create_record(self, entity, fields):
        return dict(self.add(entity, **fields))

    def update_record(self, entity, record_id, fields):
        self.get(entity, record_id).update(fields)
        return dict(self.get(entity, record_id))

    def claim(self, entity, record_id, from_status, fields):
        rec = self.get(entity, record_id)
        if rec.get("status") != from_status:
            return False
        rec.update(fields)
        return True


@pytest.fixture
def fake(monkeypatch):
    store = FakeBase44()
    monkeypatch.setattr(engine_worker, "b44", store)
    monkeypatch.setattr(engine_worker, "_robot_wait_started", {})
    return store


def test_question_set_for_training_and_default():
    assert engine_worker.question_set_for("Training3") == 3
    assert engine_worker.question_set_for("Baseline") == 1
    assert engine_worker.question_set_for(None) == 1


def test_ensure_turns_creates_six_once(fake):
    session = fake.add("Session", status="Running", session_type="Training2")
    engine_worker.ensure_turns(session)
    engine_worker.ensure_turns(session)

    turns = fake.list_records("Turn", {"session": session["id"]})
    assert len(turns) == 6
    assert [t["order"] for t in turns] == [1, 2, 3, 4, 5, 6]
    assert all(t["status"] == "awaiting_answer" for t in turns)


def test_process_turn_writes_proposal_and_moves_to_approval(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    turn = fake.add("Turn", session=session["id"], order=1, status="awaiting_engine",
                    question_text="Q", participant_answer="A")

    class Ev:
        category, confidence, rationale = "GOOD", 0.9, "Mentions concrete project outcomes."

    monkeypatch.setattr(engine_worker.evaluator, "evaluate", lambda q, a: Ev)
    monkeypatch.setattr(engine_worker.emotion_classifier, "classify_emotion",
                        lambda q, a: {"emotion": "HAPPINESS", "intensity": 3})

    engine_worker.process_turn(turn, session)

    saved = fake.get("Turn", turn["id"])
    assert saved["status"] == "awaiting_approval"
    assert saved["target_emotion"] == "HAPPINESS"
    assert saved["valence"] == "High" and saved["arousal"] == "High"
    assert saved["evaluation_category"] == "GOOD"
    assert saved["proposed_reply"]
    assert saved["guardrail_flag"] is False


def test_process_turn_skips_turn_already_claimed(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    turn = fake.add("Turn", session=session["id"], order=1, status="engine_processing")
    monkeypatch.setattr(engine_worker.evaluator, "evaluate",
                        lambda q, a: pytest.fail("must not evaluate a turn it didn't claim"))

    engine_worker.process_turn({**turn, "status": "awaiting_engine"}, session)

    assert fake.get("Turn", turn["id"])["status"] == "engine_processing"


def test_process_turn_failure_sets_engine_error_and_stays_processing(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    turn = fake.add("Turn", session=session["id"], order=1, status="awaiting_engine",
                    question_text="Q", participant_answer="A")

    def boom(q, a):
        raise TimeoutError("LLM down")

    monkeypatch.setattr(engine_worker.evaluator, "evaluate", boom)

    engine_worker.process_turn(turn, session)

    saved = fake.get("Turn", turn["id"])
    assert saved["status"] == "engine_processing"
    assert "LLM down" in saved["engine_error"]


def _fake_robot(monkeypatch):
    sent = []
    monkeypatch.setattr(engine_worker.furhat_client, "react",
                        lambda emotion, intensity, text=None, language=None:
                        sent.append(("react", emotion, intensity, text)) or {"sent": True, "reason": None})
    monkeypatch.setattr(engine_worker.furhat_client, "say",
                        lambda text, language=None:
                        sent.append(("say", text)) or {"sent": True, "reason": None})
    return sent


def test_live_turn_reaction_is_sent_then_turn_advances(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live", language="he")
    turn = fake.add("Turn", session=session["id"], order=1, status="robot_reacting",
                    final_reply="שלום", target_emotion="SADNESS", intensity=2)
    sent = _fake_robot(monkeypatch)

    engine_worker.poll_once(robot_connected=True)  # creates the command
    engine_worker.poll_once(robot_connected=True)  # sends it, then advances the turn

    assert sent == [("react", "SADNESS", 2, "שלום")]
    cmd = fake.list_records("RobotCommand", {"turn": turn["id"]})
    assert len(cmd) == 1 and cmd[0]["status"] == "done" and cmd[0]["sequence"] == 1
    assert fake.get("Turn", turn["id"])["status"] == "awaiting_pe"


def test_website_say_command_is_spoken(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    fake.add("Turn", session=session["id"], order=1, status="awaiting_answer")
    cmd = fake.add("RobotCommand", session=session["id"], type="say", status="pending",
                   text="מה אתה עושה ביום חופשי?", sequence=1, language="he")
    sent = _fake_robot(monkeypatch)

    engine_worker.poll_once(robot_connected=True)

    assert sent == [("say", "מה אתה עושה ביום חופשי?")]
    assert fake.get("RobotCommand", cmd["id"])["status"] == "done"


def test_commands_of_closed_sessions_are_not_replayed(fake, monkeypatch):
    session = fake.add("Session", status="Completed", mode="Live")
    cmd = fake.add("RobotCommand", session=session["id"], type="say", status="pending", text="old")
    sent = _fake_robot(monkeypatch)

    engine_worker.poll_once(robot_connected=True)

    assert sent == []
    assert fake.get("RobotCommand", cmd["id"])["status"] == "pending"


def test_command_waits_for_robot_then_errors_after_timeout(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    cmd = fake.add("RobotCommand", session=session["id"], type="say_with_gesture", status="pending",
                   emotion="FEAR", intensity=1, text="x")
    clock = [100.0]
    monkeypatch.setattr(engine_worker.time, "monotonic", lambda: clock[0])

    engine_worker.execute_command(cmd, robot_connected=False)
    assert fake.get("RobotCommand", cmd["id"])["status"] == "pending"

    clock[0] += engine_worker.config.ROBOT_WAIT_SECONDS + 1
    engine_worker.execute_command(cmd, robot_connected=False)
    assert fake.get("RobotCommand", cmd["id"])["status"] == "error"


def test_react_turn_simulation_creates_no_robot_command(fake):
    session = fake.add("Session", status="Running", mode="Simulation")
    turn = fake.add("Turn", session=session["id"], order=1, status="robot_reacting")

    engine_worker.react_turn(turn, session)

    assert fake.list_records("RobotCommand") == []
    assert fake.get("Turn", turn["id"])["status"] == "awaiting_pe"


def test_check_pe_writes_result(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    turn = fake.add("Turn", session=session["id"], order=1, status="awaiting_pe_check",
                    target_emotion="ANGER", participant_pe_answer="הוא נראה כועס")
    monkeypatch.setattr(engine_worker.pe_check, "check_pe_answer",
                        lambda gt, ans: {"match": True, "explanation": "זיהוי נכון"})

    engine_worker.check_pe(turn, session)

    saved = fake.get("Turn", turn["id"])
    assert saved["pe_result"] == "Correct"
    assert saved["status"] == "awaiting_feedback"


def test_apply_persona_once_per_session(fake, monkeypatch):
    persona = fake.add("Persona", furhat_face="Isabel", furhat_voice="Asaf")
    session = fake.add("Session", status="Running", mode="Live", language="he", persona=persona["id"])
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda character, voice, language: calls.append((character, voice, language))
                        or {"sent": True, "reason": None})

    engine_worker.apply_persona(session)
    engine_worker.apply_persona(session)

    assert calls == [("Isabel", "Asaf", "he")]


def test_apply_persona_skips_non_live(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Simulation", persona="p1")
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda *a: pytest.fail("no robot in Simulation"))

    engine_worker.apply_persona(session)


def test_apply_persona_base44_error_is_logged_and_not_retried(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live", persona="p1")
    monkeypatch.setattr(engine_worker, "_personas_applied", set())

    def boom(entity, record_id):
        raise engine_worker.b44.Base44Error("nope")

    monkeypatch.setattr(fake, "get_record", boom)
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda *a: pytest.fail("persona unknown, nothing to send"))

    engine_worker.apply_persona(session)

    assert session["id"] in engine_worker._personas_applied


def test_apply_persona_rate_limit_propagates(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live", persona="p1")
    monkeypatch.setattr(engine_worker, "_personas_applied", set())

    def limited(entity, record_id):
        raise engine_worker.b44.RateLimited("429")

    monkeypatch.setattr(fake, "get_record", limited)

    with pytest.raises(engine_worker.b44.RateLimited):
        engine_worker.apply_persona(session)
    assert session["id"] not in engine_worker._personas_applied
