import pytest

import engine_worker
from tests.fakes import FakeBase44, FakeRobot, heard


@pytest.fixture
def fake(monkeypatch):
    store = FakeBase44()
    monkeypatch.setattr(engine_worker, "b44", store)
    monkeypatch.setattr(engine_worker.conversation_flow, "b44", store)
    monkeypatch.setattr(engine_worker, "_robot_wait_started", {})
    monkeypatch.setattr(engine_worker.conversation_flow, "_robot_wait_started", {})
    monkeypatch.setattr(engine_worker.conversation_flow, "_heard", {})
    monkeypatch.setattr(engine_worker, "_robot_was_connected", False)
    monkeypatch.setattr(engine_worker, "_speech_context", {})
    monkeypatch.setattr(engine_worker.reaction_line, "generate",
                        lambda emotion, intensity, q, a, *rest, **k: f"reply:{emotion}")
    return store


def test_build_proposal_reply_comes_from_the_emotion_and_genders(monkeypatch):
    class Ev:
        category, confidence, rationale = "GOOD", 0.9, "Mentions the cancelled trip."

    seen = {}
    monkeypatch.setattr(engine_worker.evaluator, "evaluate", lambda q, a: Ev)
    monkeypatch.setattr(engine_worker.emotion_classifier, "classify_emotion",
                        lambda q, a, used=(): {"emotion": "SADNESS", "intensity": 3})
    monkeypatch.setattr(engine_worker.reaction_line, "generate",
                        lambda emotion, intensity, q, a, language, participant_gender, robot_gender:
                        seen.update(args=(emotion, intensity, language, participant_gender, robot_gender))
                        or "אוי, ביטלו לך את הטיול?")

    proposal = engine_worker.build_proposal("Q", "הטיול בוטל", "Live", participant_gender="female",
                                            robot_gender="male")

    assert proposal["proposed_reply"] == "אוי, ביטלו לך את הטיול?"
    assert seen["args"] == ("SADNESS", 3, "he", "female", "male")


def test_build_proposal_includes_emotion_trigger(monkeypatch):
    class Ev:
        category, confidence, rationale = "GOOD", 0.9, "Mentions the project."

    monkeypatch.setattr(engine_worker.evaluator, "evaluate", lambda q, a: Ev)
    monkeypatch.setattr(engine_worker.emotion_classifier, "classify_emotion",
                        lambda q, a, used=(): {"emotion": "SURPRISE", "intensity": 2,
                                               "trigger": "Led a project alone."})
    monkeypatch.setattr(engine_worker.reaction_line, "generate", lambda *a: "באמת?")
    assert engine_worker.build_proposal("Q", "A", "Live")["emotion_trigger"] == "Led a project alone."
    assert engine_worker.build_proposal("Q", "A", "Mock")["emotion_trigger"] == ""


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


def test_process_turn_passes_emotions_already_shown(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Simulation")
    fake.add("Turn", session=session["id"], order=1, status="done", target_emotion="FEAR")
    turn = fake.add("Turn", session=session["id"], order=2, status="awaiting_engine",
                    question_text="Q", participant_answer="A")
    seen = {}

    class Ev:
        category, confidence, rationale = "GOOD", 0.9, "Mentions concrete project outcomes."

    monkeypatch.setattr(engine_worker.evaluator, "evaluate", lambda q, a: Ev)
    monkeypatch.setattr(engine_worker.emotion_classifier, "classify_emotion",
                        lambda q, a, used=(): seen.update(used=used) or {"emotion": "CALM", "intensity": 2})

    engine_worker.process_turn(turn, session)
    assert seen["used"] == ["FEAR"]


def test_process_turn_writes_proposal_and_moves_to_approval(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    turn = fake.add("Turn", session=session["id"], order=1, status="awaiting_engine",
                    question_text="Q", participant_answer="A")

    class Ev:
        category, confidence, rationale = "GOOD", 0.9, "Mentions concrete project outcomes."

    monkeypatch.setattr(engine_worker.evaluator, "evaluate", lambda q, a: Ev)
    monkeypatch.setattr(engine_worker.emotion_classifier, "classify_emotion",
                        lambda q, a, used=(): {"emotion": "HAPPINESS", "intensity": 3})

    engine_worker.process_turn(turn, session)

    saved = fake.get("Turn", turn["id"])
    assert saved["status"] == "awaiting_approval"
    assert saved["target_emotion"] == "HAPPINESS"
    assert saved["valence"] == "High" and saved["arousal"] == "High"
    assert saved["evaluation_category"] == "GOOD"
    assert saved["proposed_reply"]
    assert saved["guardrail_flag"] is False
    assert saved["engine_model"] == engine_worker.llm_client.current_model()


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


def test_website_say_command_is_spoken(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    fake.add("Turn", session=session["id"], order=1, status="awaiting_answer")
    cmd = fake.add("RobotCommand", session=session["id"], type="say", status="pending",
                   text="מה אתה עושה ביום חופשי?", sequence=1, language="he")
    sent = _fake_robot(monkeypatch)
    monkeypatch.setattr(engine_worker.conversation_flow, "advance", lambda *a: False)

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


def test_react_turn_moves_to_awaiting_pe(fake):
    session = fake.add("Session", status="Running", mode="Simulation")
    turn = fake.add("Turn", session=session["id"], order=1, status="robot_reacting")

    engine_worker.react_turn(turn, session)

    assert fake.list_records("RobotCommand") == []
    assert fake.get("Turn", turn["id"])["status"] == "awaiting_pe"


def test_check_pe_writes_result(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Simulation")
    turn = fake.add("Turn", session=session["id"], order=1, status="awaiting_pe_check",
                    target_emotion="HAPPINESS", participant_pe_answer="התלהבת")
    monkeypatch.setattr(engine_worker.pe_check, "grade_pe_answer",
                        lambda gt, ans, trigger="": {"result": "Partial", "explanation": "קרוב",
                                                     "reason_result": "Partly", "reason_explanation": "בערך"})

    engine_worker.check_pe(turn, session)

    saved = fake.get("Turn", turn["id"])
    assert saved["pe_result"] == "Partial"
    assert saved["pe_explanation"] == "קרוב"
    assert saved["pe_reason_result"] == "Partly" and saved["pe_reason_explanation"] == "בערך"
    assert saved["status"] == "awaiting_feedback"


def test_apply_persona_once_per_session(fake, monkeypatch):
    persona = fake.add("Persona", furhat_face="Isabel", furhat_voice="Asaf")
    session = fake.add("Session", status="Running", mode="Live", language="he", persona=persona["id"])
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda character, voice, language: calls.append((character, voice, language))
                        or {"sent": True, "reason": None})

    engine_worker.apply_persona(session, True)
    engine_worker.apply_persona(session, True)

    assert calls == [("Isabel", "Asaf", "he")]


def test_apply_persona_keeps_the_friend_once_the_debrief_started(fake, monkeypatch):
    """Final review #2: after a restart/reconnect mid-debrief the robot must keep the friend's
    face, never switch back to the interviewer (2026-11-17 spec)."""
    persona = fake.add("Persona", furhat_face="Isabel", furhat_voice="Asaf")
    session = fake.add("Session", status="Running", mode="Live", language="he", persona=persona["id"])
    fake.add("Turn", session=session["id"], order=20, phase="Debrief", status="listening",
             question_text="היי! איך היה?")
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.config, "FRIEND_FACE", "FriendFace")
    monkeypatch.setattr(engine_worker.config, "FRIEND_VOICE", "FriendVoice")
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda character, voice, language: calls.append((character, voice))
                        or {"sent": True, "reason": None})

    engine_worker.apply_persona(session, True)

    assert calls == [("FriendFace", "FriendVoice")]


def test_apply_persona_friend_with_the_interviewers_voice_after_restart(fake, monkeypatch):
    persona = fake.add("Persona", furhat_face="Isabel", furhat_voice="he-IL-Chirp3-HD-Aoede")
    session = fake.add("Session", status="Running", mode="Live", language="he", persona=persona["id"])
    fake.add("Turn", session=session["id"], order=20, phase="Debrief", status="listening", question_text="היי!")
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.config, "FRIEND_FACE", "FriendFace")
    monkeypatch.setattr(engine_worker.config, "FRIEND_VOICE", "")
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda character, voice, language: calls.append((character, voice))
                        or {"sent": True, "reason": None})

    engine_worker.apply_persona(session, True)

    assert calls == [("FriendFace", "he-IL-Chirp3-HD-Aoede")]


def test_apply_persona_uses_the_interviewer_before_the_debrief(fake, monkeypatch):
    persona = fake.add("Persona", furhat_face="Isabel", furhat_voice="Asaf")
    session = fake.add("Session", status="Running", mode="Live", language="he", persona=persona["id"])
    fake.add("Turn", session=session["id"], order=20, phase="Debrief", status="queued", question_text="")
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.config, "FRIEND_FACE", "FriendFace")
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda character, voice, language: calls.append((character, voice))
                        or {"sent": True, "reason": None})

    engine_worker.apply_persona(session, True)

    assert calls == [("Isabel", "Asaf")]


def test_apply_persona_skips_non_live(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Simulation", persona="p1")
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda *a: pytest.fail("no robot in Simulation"))

    engine_worker.apply_persona(session, True)


def test_apply_persona_base44_error_is_logged_and_not_retried(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live", persona="p1")
    monkeypatch.setattr(engine_worker, "_personas_applied", set())

    def boom(entity, record_id):
        raise engine_worker.b44.Base44Error("nope")

    monkeypatch.setattr(fake, "get_record", boom)
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda *a: pytest.fail("persona unknown, nothing to send"))

    engine_worker.apply_persona(session, True)

    assert session["id"] in engine_worker._personas_applied


def test_apply_persona_rate_limit_propagates(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live", persona="p1")
    monkeypatch.setattr(engine_worker, "_personas_applied", set())

    def limited(entity, record_id):
        raise engine_worker.b44.RateLimited("429")

    monkeypatch.setattr(fake, "get_record", limited)

    with pytest.raises(engine_worker.b44.RateLimited):
        engine_worker.apply_persona(session, True)
    assert session["id"] not in engine_worker._personas_applied


def test_apply_persona_robot_down_is_not_marked_then_sent_when_up(fake, monkeypatch):
    persona = fake.add("Persona", furhat_face="Isabel", furhat_voice="Asaf")
    session = fake.add("Session", status="Running", mode="Live", language="he", persona=persona["id"])
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda *a: calls.append(a) or {"sent": True, "reason": None, "bridge_error": False})

    engine_worker.apply_persona(session, False)
    assert calls == [] and session["id"] not in engine_worker._personas_applied

    engine_worker.apply_persona(session, True)
    assert len(calls) == 1 and session["id"] in engine_worker._personas_applied


def test_apply_persona_connection_failure_is_retried(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda *a: calls.append(a) or {"sent": False, "reason": "refused", "bridge_error": False})

    engine_worker.apply_persona(session, True)
    engine_worker.apply_persona(session, True)

    assert len(calls) == 2 and session["id"] not in engine_worker._personas_applied


def test_apply_persona_bridge_error_is_not_retried(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda *a: calls.append(a) or {"sent": False, "reason": "bad voice", "bridge_error": True})

    engine_worker.apply_persona(session, True)
    engine_worker.apply_persona(session, True)

    assert len(calls) == 1 and session["id"] in engine_worker._personas_applied


def test_heartbeat_once_reports_robot_status(fake, monkeypatch):
    monkeypatch.setattr(engine_worker, "_heartbeat_id", None)
    monkeypatch.setattr(engine_worker.furhat_client, "health_check", lambda: True)

    engine_worker.heartbeat_once()

    beat = fake.list_records("EngineHeartbeat", {"key": "engine-main"})
    assert len(beat) == 1 and beat[0]["robot_connected"] is True


def test_heartbeat_once_survives_base44_errors(fake, monkeypatch):
    monkeypatch.setattr(engine_worker, "_heartbeat_id", None)
    monkeypatch.setattr(engine_worker.furhat_client, "health_check", lambda: False)

    def limited(*a, **k):
        raise engine_worker.b44.RateLimited("429")

    monkeypatch.setattr(fake, "list_records", limited)

    engine_worker.heartbeat_once()  # must not raise


def test_speech_context_reads_participant_and_voice_once(fake, monkeypatch):
    participant = fake.add("Participant", gender="Female", first_name=" דנה ")
    persona = fake.add("Persona", furhat_voice="AvriNeural")
    session = fake.add("Session", participant=participant["id"], persona=persona["id"])

    assert engine_worker.speech_context(session) == {
        "participant_gender": "female", "robot_gender": "male", "participant_name": "דנה"}

    monkeypatch.setattr(fake, "get_record", lambda *a: pytest.fail("cached: no second lookup"))
    assert engine_worker.speech_context(session)["participant_gender"] == "female"


def test_speech_context_without_participant_or_persona(fake):
    session = fake.add("Session")
    assert engine_worker.speech_context(session) == {
        "participant_gender": None, "robot_gender": None, "participant_name": None}


def test_speech_context_base44_error_is_not_cached(fake, monkeypatch):
    session = fake.add("Session", participant="p1")

    def boom(entity, record_id):
        raise engine_worker.b44.Base44Error("timeout")

    monkeypatch.setattr(fake, "get_record", boom)
    assert engine_worker.speech_context(session) == {
        "participant_gender": None, "robot_gender": None, "participant_name": None}
    assert session["id"] not in engine_worker._speech_context


def test_live_session_runs_turns_back_to_back(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live", language="he")
    t1 = fake.add("Turn", session=session["id"], order=1, phase="Opening", generated_by_engine=True,
                  expects_answer=True, status="queued", question_text="")
    t2 = fake.add("Turn", session=session["id"], order=2, phase="Closing", generated_by_engine=True,
                  expects_answer=False, status="queued", question_text="")
    robot = FakeRobot(heard=[heard("שלום")])
    monkeypatch.setattr(engine_worker.conversation_flow, "furhat_client", robot)
    monkeypatch.setattr(engine_worker.conversation_flow.small_talk, "generate_line",
                        lambda *a, **k: "שורה")
    monkeypatch.setattr(engine_worker, "_personas_applied", {session["id"]})

    engine_worker.poll_once(robot_connected=True)

    assert fake.get("Turn", t1["id"])["status"] == "done"
    assert fake.get("Turn", t2["id"])["status"] == "done"


def test_live_session_stops_between_turns_when_not_running(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    fake.add("Turn", session=session["id"], order=1, status="queued")
    fake.add("Turn", session=session["id"], order=2, status="queued")
    advanced = []

    def finish_and_pause(turn, s, turns, robot_connected, propose):
        advanced.append(turn["order"])
        fake.update_record("Turn", turn["id"], {"status": "done"})
        fake.update_record("Session", session["id"], {"status": "Paused"})
        return True

    monkeypatch.setattr(engine_worker.conversation_flow, "advance", finish_and_pause)

    engine_worker.run_live_session(session, robot_connected=True)

    assert advanced == [1]


def test_live_session_without_turns_waits_for_the_website(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    monkeypatch.setattr(engine_worker, "_personas_applied", {session["id"]})

    engine_worker.poll_once(robot_connected=True)

    assert fake.list_records("Turn") == []


def test_live_session_adds_speech_context(fake, monkeypatch):
    participant = fake.add("Participant", gender="Female", first_name="דנה")
    persona = fake.add("Persona", furhat_voice="AvriNeural")
    session = fake.add("Session", status="Running", mode="Live", participant=participant["id"],
                       persona=persona["id"])
    fake.add("Turn", session=session["id"], order=1, status="queued")
    seen = {}
    monkeypatch.setattr(engine_worker.conversation_flow, "advance",
                        lambda turn, s, turns, robot_connected, propose: seen.update(session=s) or False)

    engine_worker.run_live_session(session, robot_connected=True)

    assert seen["session"]["participant_gender"] == "female"
    assert seen["session"]["robot_gender"] == "male"
    assert seen["session"]["participant_name"] == "דנה"


def test_live_session_passes_build_proposal(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    fake.add("Turn", session=session["id"], order=1, status="queued")
    seen = {}
    monkeypatch.setattr(engine_worker.conversation_flow, "advance",
                        lambda turn, s, turns, robot_connected, propose: seen.update(propose=propose) or False)

    engine_worker.run_live_session(session, robot_connected=True)

    assert seen["propose"] is engine_worker.build_proposal


def test_heartbeat_once_survives_any_exception(fake, monkeypatch):
    def boom():
        raise ValueError("bridge returned junk")

    monkeypatch.setattr(engine_worker.furhat_client, "health_check", boom)

    engine_worker.heartbeat_once()  # must not raise: the heartbeat thread would die


def test_persona_is_resent_after_the_robot_goes_down_and_up(fake, monkeypatch):
    persona = fake.add("Persona", furhat_face="Isabel", furhat_voice="Asaf")
    fake.add("Session", status="Running", mode="Live", language="he", persona=persona["id"])
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda *a: calls.append(a) or {"sent": True, "reason": None})
    monkeypatch.setattr(engine_worker, "run_live_session", lambda *a: None)

    engine_worker.poll_once(True)
    engine_worker.poll_once(True)
    assert len(calls) == 1
    engine_worker.poll_once(False)
    engine_worker.poll_once(True)

    assert len(calls) == 2


def test_unexpected_error_in_one_session_does_not_stop_the_others(fake, monkeypatch):
    bad = fake.add("Session", status="Running", mode="Live", session_code="BAD")
    good = fake.add("Session", status="Running", mode="Live", session_code="GOOD")
    monkeypatch.setattr(engine_worker, "_personas_applied", {bad["id"], good["id"]})
    seen = []

    def run_live(session, robot_connected):
        seen.append(session["session_code"])
        if session["session_code"] == "BAD":
            raise KeyError("boom")

    monkeypatch.setattr(engine_worker, "run_live_session", run_live)

    assert engine_worker.poll_once(True) is True  # must not raise
    assert seen == ["BAD", "GOOD"]
