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
    monkeypatch.setattr(flow, "_heard", {})
    monkeypatch.setattr(flow.small_talk, "generate_line",
                        lambda phase, position, total, expects_answer, history, language="he", *genders:
                        f"{phase} {position}/{total}")
    monkeypatch.setattr(flow.acknowledgement, "acknowledge", lambda q, a, language="he", *genders: dict(ACK))
    monkeypatch.setattr(flow.small_talk, "follow_up", lambda *a, **k: None)
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
    assert robot.backchannels == [True]
    assert robot.speech_gestures == [True]


def opening_turns(store, session, count=2):
    return [store.add("Turn", session=session["id"], order=i, phase="Opening", generated_by_engine=True,
                      expects_answer=True, status="queued", question_text="") for i in range(1, count + 1)]


def test_small_talk_follow_up_continues_the_conversation(fake, monkeypatch):
    s = live_session(fake)
    t, _ = opening_turns(fake, s)
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("אפיתי לחם"), heard("יומיים בערך")]))
    lines = ["מחמצת? כמה זמן זה לוקח?", None]
    seen = []
    monkeypatch.setattr(flow.small_talk, "follow_up",
                        lambda phase, history, *a, **k: seen.append(history) or lines.pop(0))

    assert run(fake, s, t) is True

    saved = fake.get("Turn", t["id"])
    assert fake.statuses(t["id"]) == ["robot_speaking", "listening", "engine_processing",
                                       "robot_speaking", "listening", "engine_processing", "done"]
    assert robot.calls == [("say", "Opening 1/2"), ("listen",), ("say", "מחמצת? כמה זמן זה לוקח?"), ("listen",)]
    assert saved["small_talk_log"] == [
        {"speaker": "robot", "text": "Opening 1/2"}, {"speaker": "participant", "text": "אפיתי לחם"},
        {"speaker": "robot", "text": "מחמצת? כמה זמן זה לוקח?"}, {"speaker": "participant", "text": "יומיים בערך"}]
    assert saved["question_text"] == "Opening 1/2" and saved["participant_answer"] == "יומיים בערך"
    assert seen[0][-1] == {"speaker": "participant", "text": "אפיתי לחם"}


def test_small_talk_follow_ups_are_capped(fake, monkeypatch):
    monkeypatch.setattr(flow.config, "SMALL_TALK_MAX_FOLLOW_UPS", 1)
    s = live_session(fake)
    t, _ = opening_turns(fake, s)
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("א"), heard("ב")]))
    calls = []
    monkeypatch.setattr(flow.small_talk, "follow_up", lambda *a, **k: calls.append(1) or "ועוד שאלה?")

    run(fake, s, t)

    assert len(calls) == 1
    assert robot.said() == ["Opening 1/2", "ועוד שאלה?"]
    assert fake.get("Turn", t["id"])["status"] == "done"


def test_ready_to_start_turn_has_no_follow_ups(fake, monkeypatch):
    s = live_session(fake)
    _, last = opening_turns(fake, s)
    use_robot(monkeypatch, FakeRobot(heard=[heard("כן, מוכנה")]))
    monkeypatch.setattr(flow.small_talk, "follow_up", lambda *a, **k: pytest.fail("no follow-up before questions"))

    run(fake, s, last)
    assert fake.get("Turn", last["id"])["status"] == "done"


def test_silence_after_a_follow_up_ends_the_turn_not_skips(fake, monkeypatch):
    s = live_session(fake)
    t, _ = opening_turns(fake, s)
    use_robot(monkeypatch, FakeRobot(heard=[heard("אפיתי לחם")]))
    monkeypatch.setattr(flow.small_talk, "follow_up", lambda *a, **k: "איזה לחם?")

    run(fake, s, t)

    saved = fake.get("Turn", t["id"])
    assert saved["status"] == "done" and not saved.get("skipped")


def test_history_uses_the_small_talk_log():
    turns = [{"id": "a", "order": 1, "status": "done", "question_text": "היי", "participant_answer": "ב",
              "small_talk_log": [{"speaker": "robot", "text": "היי"}, {"speaker": "participant", "text": "א"},
                                 {"speaker": "robot", "text": "באמת?"}, {"speaker": "participant", "text": "ב"}]},
             {"id": "b", "order": 2, "status": "queued"}]
    assert [h["text"] for h in flow.dialogue_history(turns, turns[1])] == ["היי", "א", "באמת?", "ב"]


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


PROPOSAL = {"target_emotion": "HAPPINESS", "intensity": 2, "proposed_reply": "איזה יופי",
            "evaluation_category": "GOOD", "pe_answer_why": "הצלחתי בפרויקט"}


def pbdi_turn(store, session, **fields):
    return store.add("Turn", session=session["id"], order=1, phase="Main", category=flow.PBDI_CATEGORY,
                     question_text="ספר/י על הצלחה", **fields)


def test_pbdi_answer_stops_for_approval(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="queued")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("הצלחתי בפרויקט")]))
    calls = []

    assert run(fake, s, t, propose=lambda q, a, mode, **k: calls.append((q, a, mode)) or dict(PROPOSAL)) is False

    saved = fake.get("Turn", t["id"])
    assert fake.statuses(t["id"]) == ["robot_speaking", "listening", "engine_processing", "awaiting_approval"]
    assert calls == [("ספר/י על הצלחה", "הצלחתי בפרויקט", "Live")]
    assert saved["target_emotion"] == "HAPPINESS" and saved["engine_model"]
    assert robot.said() == ["ספר על הצלחה"]  # no acknowledgement for PBDI; spoken form is rendered


def test_pbdi_passes_emotions_already_shown(fake, monkeypatch):
    s = live_session(fake)
    fake.add("Turn", session=s["id"], order=1, phase="Main", status="done", target_emotion="CALM")
    fake.add("Turn", session=s["id"], order=2, phase="Main", status="skipped", target_emotion="FEAR")
    t = fake.add("Turn", session=s["id"], order=3, phase="Main", category=flow.PBDI_CATEGORY,
                 question_text="שאלה", status="engine_processing", participant_answer="תשובה")
    use_robot(monkeypatch, FakeRobot())
    seen = {}

    run(fake, s, t, propose=lambda q, a, mode, used_emotions=(), **k: seen.update(used=used_emotions, **k) or dict(PROPOSAL))

    assert seen["used"] == ["CALM", "FEAR"]
    assert seen["language"] == "he" and "robot_gender" in seen  # the reply is written in the robot's gender


def test_pbdi_llm_failure_retries_once_then_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="engine_processing", participant_answer="תשובה")
    use_robot(monkeypatch, FakeRobot())
    calls = []

    def boom(q, a, mode, **k):
        calls.append(1)
        raise TimeoutError("LLM down")

    assert run(fake, s, t, propose=boom) is False

    saved = fake.get("Turn", t["id"])
    assert len(calls) == 2
    assert "LLM down" in saved["engine_error"]
    assert saved["status"] == "engine_processing"


def test_pbdi_llm_failure_once_then_success(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="engine_processing", participant_answer="תשובה")
    use_robot(monkeypatch, FakeRobot())
    replies = [TimeoutError("blip"), dict(PROPOSAL)]

    def flaky(q, a, mode, **k):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    run(fake, s, t, propose=flaky)
    assert fake.get("Turn", t["id"])["status"] == "awaiting_approval"


def test_approved_reaction_then_pe_question_then_grade(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_reacting", participant_answer="תשובה", final_reply="איזה יופי!",
                  target_emotion="HAPPINESS", intensity=2, pe_answer_why="הצלחתי בפרויקט")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("התלהבת")]))
    monkeypatch.setattr(flow.pe_check, "grade_pe_answer",
                        lambda target, answer: {"result": "Partial", "explanation": "קרוב"})
    monkeypatch.setattr(flow.pe_feedback, "generate_feedback",
                        lambda target, question, answer, guess, result, language="he", *genders:
                        {"line": f"{target}/{answer}/{guess}/{result}", "reason": "סיפרת שהצלחת"})

    assert run(fake, s, t) is False

    saved = fake.get("Turn", t["id"])
    assert robot.calls == [("react", "HAPPINESS", 2, "איזה יופי!"), ("say", flow.PE_QUESTION), ("listen",)]
    assert robot.backchannels == [False]  # no nods while the participant guesses the emotion
    assert robot.speech_gestures == [False]  # nor while the robot asks the PE question
    assert fake.statuses(t["id"]) == ["pe_listening", "engine_processing", "awaiting_feedback"]
    assert saved["robot_line"] == "איזה יופי!"
    assert saved["participant_pe_answer"] == "התלהבת"
    assert saved["pe_result"] == "Partial" and saved["pe_explanation"] == "קרוב"
    assert saved["proposed_feedback"] == "HAPPINESS/תשובה/התלהבת/Partial"
    assert saved["pe_answer_why"] == "סיפרת שהצלחת"
    [cmd] = fake.list_records("RobotCommand", {"turn": t["id"]})
    assert cmd["status"] == "done" and cmd["emotion"] == "HAPPINESS" and cmd["text"] == "איזה יופי!"


def test_silent_pe_answer_skips_turn(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_reacting", proposed_reply="יופי", target_emotion="CALM", intensity=1)
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is True

    saved = fake.get("Turn", t["id"])
    assert saved["status"] == "skipped" and saved["skip_reason"] == "pe_no_answer"
    assert robot.said() == [flow.PE_QUESTION, flow.PE_QUESTION]
    assert fake.list_records("RobotCommand", {"turn": t["id"]})[0]["status"] == "done"


def test_reaction_fails_when_robot_drops(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_reacting", final_reply="יופי", target_emotion="FEAR", intensity=3)
    use_robot(monkeypatch, FakeRobot(connected=False))

    assert run(fake, s, t) is False

    saved = fake.get("Turn", t["id"])
    assert saved["engine_error"] == "robot disconnected" and saved["status"] == "robot_reacting"
    assert fake.list_records("RobotCommand", {"turn": t["id"]})[0]["status"] == "error"


def test_pe_grading_failure_sets_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="engine_processing", participant_answer="תשובה",
                  participant_pe_answer="שמחת", target_emotion="HAPPINESS")
    use_robot(monkeypatch, FakeRobot())

    def boom(target, answer):
        raise TimeoutError("LLM down")

    monkeypatch.setattr(flow.pe_check, "grade_pe_answer", boom)

    assert run(fake, s, t) is False
    assert "LLM down" in fake.get("Turn", t["id"])["engine_error"]


def test_approved_feedback_is_spoken_then_done(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_feedback", proposed_feedback="הצעה", final_feedback="בעצם הרגשתי רוגע.")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is True

    assert robot.said() == ["בעצם הרגשתי רוגע."]
    assert fake.get("Turn", t["id"])["status"] == "done"


def test_waiting_for_approval_does_nothing(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="awaiting_feedback")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is False
    assert robot.calls == []


def test_retry_after_pe_question_drop_does_not_repeat_reaction(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_reacting", participant_answer="תשובה", final_reply="איזה יופי!",
                  target_emotion="HAPPINESS", intensity=2)

    class DropsOnSay(FakeRobot):
        def say(self, text, language=None, gender=None, gestures=True):
            self.calls.append(("say", text))
            return {"sent": False, "reason": "connection refused"}

    first = use_robot(monkeypatch, DropsOnSay())
    assert run(fake, s, t) is False
    assert fake.get("Turn", t["id"])["engine_error"] == "robot disconnected"
    assert [c["status"] for c in fake.list_records("RobotCommand", {"turn": t["id"]})] == ["done"]
    assert first.calls[0][0] == "react"

    fake.update_record("Turn", t["id"], {"engine_error": ""})
    second = use_robot(monkeypatch, FakeRobot(heard=[heard("שמחת")]))
    monkeypatch.setattr(flow.pe_check, "grade_pe_answer",
                        lambda target, answer: {"result": "Correct", "explanation": "נכון"})
    monkeypatch.setattr(flow.pe_feedback, "generate_feedback",
                        lambda target, question, answer, guess, result, language="he", *genders:
                        {"line": "כן", "reason": "כי"})

    assert run(fake, s, t) is False

    assert not [c for c in second.calls if c[0] == "react"]
    assert second.said() == [flow.PE_QUESTION]
    assert len(fake.list_records("RobotCommand", {"turn": t["id"]})) == 1
    saved = fake.get("Turn", t["id"])
    assert saved["status"] == "awaiting_feedback" and saved["robot_line"] == "איזה יופי!"


def test_done_say_command_does_not_suppress_the_reaction(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_reacting", participant_answer="תשובה", final_reply="איזה יופי!",
                  target_emotion="HAPPINESS", intensity=2)
    fake.add("RobotCommand", session=s["id"], turn=t["id"], type="say", text="קריאה", status="done")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("שמחת")]))
    monkeypatch.setattr(flow.pe_check, "grade_pe_answer",
                        lambda target, answer: {"result": "Correct", "explanation": "נכון"})
    monkeypatch.setattr(flow.pe_feedback, "generate_feedback",
                        lambda *a: {"line": "כן", "reason": "כי"})

    run(fake, s, t)

    assert robot.calls[0] == ("react", "HAPPINESS", 2, "איזה יופי!")


def _fail_next_update(monkeypatch, store, field):
    """update_record raises Base44Error once for a write that sets `field`."""
    real = store.update_record
    state = {"failed": False}

    def flaky(entity, record_id, fields):
        if field in fields and not state["failed"]:
            state["failed"] = True
            raise store.Base44Error("boom")
        return real(entity, record_id, fields)

    monkeypatch.setattr(store, "update_record", flaky)


def test_answer_survives_a_failed_save_and_is_not_asked_again(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Opening", generated_by_engine=True,
                 expects_answer=True, status="listening", question_text="שלום")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("אני דנה")]))
    _fail_next_update(monkeypatch, fake, "participant_answer")

    with pytest.raises(fake.Base44Error):
        run(fake, s, t)
    assert run(fake, s, t) is True

    assert fake.get("Turn", t["id"])["participant_answer"] == "אני דנה"
    assert robot.calls.count(("listen",)) == 1
    assert flow._heard == {}


def test_pe_answer_survives_a_failed_save_and_is_not_asked_again(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="pe_listening", participant_answer="תשובה", target_emotion="FEAR")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("פחדת")]))
    monkeypatch.setattr(flow.pe_check, "grade_pe_answer",
                        lambda target, answer: {"result": "Correct", "explanation": "נכון"})
    monkeypatch.setattr(flow.pe_feedback, "generate_feedback", lambda *a: {"line": "כן", "reason": "כי"})
    _fail_next_update(monkeypatch, fake, "participant_pe_answer")

    with pytest.raises(fake.Base44Error):
        run(fake, s, t)
    run(fake, s, t)

    assert fake.get("Turn", t["id"])["participant_pe_answer"] == "פחדת"
    assert robot.calls.count(("listen",)) == 1


def test_unexpected_status_sets_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, status="awaiting_pe", question_text="Q")
    use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is False

    assert fake.get("Turn", t["id"])["engine_error"] == "unexpected status: awaiting_pe"
