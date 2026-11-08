import pytest

import conversation_flow as flow
from tests.fakes import FakeBase44, FakeRobot, heard

Q = "ספר/י על עצמך"
Q_SAID = "ספר על עצמך"  # Q as spoken: gender unknown renders the masculine slash form
ACK = {"line": "תודה, אז למדת הנדסה. נמשיך.", "guardrail_flag": False, "guardrail_reason": ""}


@pytest.fixture
def fake(monkeypatch):
    store = FakeBase44()
    monkeypatch.setattr(flow, "b44", store)
    monkeypatch.setattr(flow, "_robot_wait_started", {})
    monkeypatch.setattr(flow.small_talk, "generate_line",
                        lambda phase, position, total, expects_answer, history, language="he", *genders:
                        f"{phase} {position}/{total}")
    monkeypatch.setattr(flow.acknowledgement, "acknowledge", lambda q, a, language="he", *genders: dict(ACK))
    return store


def use_robot(monkeypatch, robot):
    monkeypatch.setattr(flow, "furhat_client", robot)
    return robot


def no_proposal(*args):
    pytest.fail("this turn must not be evaluated")


def run(store, session, turn, robot_connected=True, propose=no_proposal):
    turns = store.list_records("Turn", {"session": session["id"]}, sort="order")
    return flow.advance(store.get_record("Turn", turn["id"]), session, turns, robot_connected, propose)


def live_session(store):
    return store.add("Session", status="Running", mode="Live", language="he")


def test_current_turn_is_first_unfinished_by_order():
    turns = [{"id": "b", "order": 2, "status": "queued"},
             {"id": "a", "order": 1, "status": "done"},
             {"id": "c", "order": 3, "status": "queued"}]
    assert flow.current_turn(turns)["id"] == "b"
    assert flow.current_turn([{"id": "a", "order": 1, "status": "skipped"}]) is None


def test_small_talk_turn_walks_its_statuses(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Opening", generated_by_engine=True,
                 expects_answer=True, status="queued", question_text="")
    fake.add("Turn", session=s["id"], order=2, phase="Opening", generated_by_engine=True,
             expects_answer=True, status="queued", question_text="")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("טוב, אני דנה")]))

    assert run(fake, s, t) is True

    saved = fake.get("Turn", t["id"])
    assert fake.statuses(t["id"]) == ["robot_speaking", "listening", "engine_processing", "done"]
    assert saved["question_text"] == "Opening 1/2"
    assert saved["participant_answer"] == "טוב, אני דנה"
    assert saved["claimed_by"] == flow.WORKER_ID
    assert robot.calls == [("say", "Opening 1/2"), ("listen",)]


def test_goodbye_turn_does_not_listen(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Closing", generated_by_engine=True,
                 expects_answer=False, status="queued", question_text="")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is True

    assert fake.statuses(t["id"]) == ["robot_speaking", "done"]
    assert robot.calls == [("say", "Closing 1/1")]


def test_main_turn_says_question_then_content_only_ack(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Background",
                 question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("למדתי הנדסה")]))

    assert run(fake, s, t) is True

    saved = fake.get("Turn", t["id"])
    assert fake.statuses(t["id"]) == ["robot_speaking", "listening", "engine_processing",
                                       "robot_speaking", "done"]
    assert robot.said() == [Q_SAID, ACK["line"]]
    assert saved["robot_line"] == ACK["line"]
    assert saved["guardrail_flag"] is False
    assert saved["engine_model"]


def test_question_slash_forms_follow_participant_gender(fake, monkeypatch):
    s = fake.add("Session", status="Running", mode="Live", language="he", participant_gender="female")
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text="ספר/י על עצמך", status="queued")
    robot = use_robot(monkeypatch, FakeRobot())

    run(fake, s, t)

    assert robot.said() == ["ספרי על עצמך", "ספרי על עצמך"]  # asked, then repeated after silence
    assert fake.get("Turn", t["id"])["question_text"] == "ספר/י על עצמך"  # the website keeps the bank text


def test_awaiting_answer_is_treated_as_queued(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="awaiting_answer")
    use_robot(monkeypatch, FakeRobot(heard=[heard("כן")]))

    assert run(fake, s, t) is True
    assert fake.get("Turn", t["id"])["status"] == "done"


def test_silence_repeats_question_once_then_skips(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is True

    saved = fake.get("Turn", t["id"])
    assert robot.calls == [("say", Q_SAID), ("listen",), ("say", Q_SAID), ("listen",)]
    assert saved["status"] == "skipped" and saved["skip_reason"] == "no_answer"
    assert saved["skipped"] is True


def test_unrecognized_speech_asks_to_repeat_once_then_skips(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot(heard=[{"status": "failed", "text": ""},
                                                    {"status": "ok", "text": "  "}]))

    assert run(fake, s, t) is True

    assert robot.said() == [Q_SAID, flow.NOT_HEARD_LINE]
    assert fake.get("Turn", t["id"])["skip_reason"] == "no_recognition"


def test_answer_after_repeated_question_is_kept(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="queued")
    use_robot(monkeypatch, FakeRobot(heard=[{"status": "no_speech", "text": ""}, heard("אני מדויקת")]))

    assert run(fake, s, t) is True
    assert fake.get("Turn", t["id"])["participant_answer"] == "אני מדויקת"


def test_robot_down_waits_then_sets_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot())
    clock = [100.0]
    monkeypatch.setattr(flow.time, "monotonic", lambda: clock[0])

    assert run(fake, s, t, robot_connected=False) is False
    assert not fake.get("Turn", t["id"]).get("engine_error")

    clock[0] += flow.config.ROBOT_WAIT_SECONDS + 1
    assert run(fake, s, t, robot_connected=False) is False

    saved = fake.get("Turn", t["id"])
    assert saved["engine_error"] == "robot disconnected"
    assert saved["status"] == "queued"
    assert robot.calls == []


def test_robot_drops_mid_step_sets_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="queued")
    use_robot(monkeypatch, FakeRobot(connected=False))

    assert run(fake, s, t, robot_connected=True) is False
    assert fake.get("Turn", t["id"])["engine_error"] == "robot disconnected"


def test_listen_failure_with_robot_gone_sets_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="listening")
    robot = use_robot(monkeypatch, FakeRobot(connected=False))

    assert run(fake, s, t) is False
    assert robot.calls == [("listen",)]
    assert fake.get("Turn", t["id"])["engine_error"] == "robot disconnected"


def test_turn_with_engine_error_waits_for_retry(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q,
                 status="listening", engine_error="robot disconnected")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is False
    assert robot.calls == []


def test_resume_from_listening_listens_without_asking_again(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="listening")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("עניתי")]))

    assert run(fake, s, t) is True
    assert robot.calls[0] == ("listen",)


def test_resume_from_robot_speaking_after_crash(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Opening", generated_by_engine=True,
                 expects_answer=True, status="robot_speaking", question_text="")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("היי")]))

    assert run(fake, s, t) is True
    assert robot.said() == ["Opening 1/1"]


def test_lost_claim_does_nothing(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot())
    monkeypatch.setattr(fake, "claim", lambda *a: False)

    assert run(fake, s, t) is False
    assert robot.calls == []


def test_base44_error_mid_step_propagates(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="queued")
    use_robot(monkeypatch, FakeRobot())

    def broken(*a):
        raise fake.Base44Error("unknown status value")

    monkeypatch.setattr(fake, "update_record", broken)

    with pytest.raises(fake.Base44Error):
        run(fake, s, t)


def test_small_talk_gets_position_and_history(fake, monkeypatch):
    s = live_session(fake)
    fake.add("Turn", session=s["id"], order=1, phase="Opening", generated_by_engine=True,
             status="done", question_text="היי, מה שלומך?", participant_answer="טוב")
    t = fake.add("Turn", session=s["id"], order=2, phase="Opening", generated_by_engine=True,
                 expects_answer=True, status="queued", question_text="")
    seen = {}
    monkeypatch.setattr(flow.small_talk, "generate_line",
                        lambda phase, position, total, expects_answer, history, language="he", *genders:
                        seen.update(args=(phase, position, total, expects_answer), history=history) or "נחמד")
    use_robot(monkeypatch, FakeRobot(heard=[heard("כן")]))

    run(fake, s, t)

    assert seen["args"] == ("Opening", 2, 2, True)
    assert seen["history"] == [{"speaker": "robot", "text": "היי, מה שלומך?"},
                               {"speaker": "participant", "text": "טוב"}]


def test_dialogue_history_keeps_order_and_skips_empty_lines():
    turns = [
        {"order": 1, "status": "done", "question_text": "היי", "participant_answer": "שלום"},
        {"order": 2, "status": "done", "question_text": "Q2", "participant_answer": "A2", "robot_line": "R2",
         "participant_pe_answer": "PE2", "final_feedback": "FB2"},
        {"order": 3, "status": "skipped", "question_text": "Q3"},
        {"order": 4, "status": "queued", "question_text": ""},
    ]
    lines = flow.dialogue_history(turns, turns[3])
    assert [(l["speaker"], l["text"]) for l in lines] == [
        ("robot", "היי"), ("participant", "שלום"),
        ("robot", "Q2"), ("participant", "A2"), ("robot", "R2"),
        ("robot", flow.PE_QUESTION), ("participant", "PE2"), ("robot", "FB2"),
        ("robot", "Q3"),
    ]
