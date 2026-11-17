"""
conversation_flow.py -- the Live-mode turn state machine: which step comes
next in a turn. Kept apart from engine_worker.py's polling loop so it can
be tested with a fake website and a fake robot.

engine_worker calls advance() for the session's current turn (the first
one by order that isn't done/skipped). advance() runs that turn as far as
it can go without the researcher: it speaks, listens (blocking, up to
~2.5 min), processes, and stops at awaiting_approval / awaiting_feedback,
at done / skipped, or when it sets engine_error.

The website's Retry button only clears engine_error (plan decision P5); the
next advance() re-runs the turn's current status, so every handler must be
safe to run twice.

See docs/superpowers/specs/2026-11-04-autonomous-robot-conversation-design.md
("Turn flow", "Error handling").
"""

import time

import acknowledgement
from lab_db import client as b44
import config
import furhat_client
import hebrew_gender
import llm_client
import pe_check
import pe_feedback
import small_talk
from worker_common import WORKER_ID, log, now

PBDI_CATEGORY = "Behavioral (PBDI)"
# TODO(researcher): approve wording. Friend-toned per-turn question (2026-11-17 spec);
# must match the website's sessionUtils.PE_QUESTION.
PE_QUESTION = "שמת לב איך הגבתי? מה לדעתך עבר עליי?"
NOT_HEARD_LINE = "סליחה, לא שמעתי. אפשר לחזור?"
FINISHED = ("done", "skipped")
WAITING_FOR_RESEARCHER = ("awaiting_approval", "awaiting_feedback")
HISTORY_TURNS = 10  # spec: the small-talk prompt sees the last 10 turns

_robot_wait_started = {}  # turn id -> monotonic time the robot was first seen down
_heard = {}  # (turn id, "answer" | "pe") -> text heard but not yet saved: a failed save must not lose it


class RobotDown(Exception):
    """The bridge stopped answering in the middle of a step."""


def _order(turn: dict) -> float:
    return turn.get("order") or 0


def current_turn(turns: list):
    """The first turn by order that isn't done or skipped. Turns run strictly in order."""
    for turn in sorted(turns, key=_order):
        if turn.get("status") not in FINISHED:
            return turn
    return None


def advance(turn: dict, session: dict, turns: list, robot_connected: bool, propose) -> bool:
    """Run one Live turn as far as it goes without the researcher. True if it finished."""
    if turn.get("engine_error") or turn.get("status") in WAITING_FOR_RESEARCHER:
        return False
    if not robot_connected:
        _wait_for_robot(turn)
        return False
    _robot_wait_started.pop(turn["id"], None)
    try:
        while turn and not turn.get("engine_error") and turn.get("status") not in FINISHED + WAITING_FOR_RESEARCHER:
            handler = _HANDLERS.get(turn.get("status"))
            if handler is None:
                status = turn.get("status")
                log(f"Turn {turn.get('order')}: unexpected status {status}")
                _update(turn, engine_error=f"unexpected status: {status}")
                return False
            turn = handler(turn, session, turns, propose)
    except RobotDown:
        _update(turn, engine_error="robot disconnected")
        log(f"Turn {turn.get('order')}: robot stopped answering")
        return False
    return bool(turn) and turn.get("status") in FINISHED


def _wait_for_robot(turn: dict) -> None:
    started = _robot_wait_started.setdefault(turn["id"], time.monotonic())
    if time.monotonic() - started >= config.ROBOT_WAIT_SECONDS:
        _update(turn, engine_error="robot disconnected")
        _robot_wait_started.pop(turn["id"], None)
        log(f"Turn {turn.get('order')}: robot not reachable for {config.ROBOT_WAIT_SECONDS:.0f}s")


def _update(turn: dict, **fields) -> dict:
    b44.update_record("Turn", turn["id"], fields)
    return {**turn, **fields}


def _say(text: str, session: dict, gestures: bool = True) -> None:
    if not furhat_client.say(text, language=session.get("language"), gestures=gestures)["sent"]:
        raise RobotDown()


def _skip(turn: dict, reason: str) -> dict:
    log(f"Turn {turn.get('order')}: skipped ({reason})")
    return _update(turn, status="skipped", skipped=True, skip_reason=reason)


def _question_to_say(turn: dict, session: dict) -> str:
    """Question-bank text has slash forms ("ספר/י"); say the participant's form (plan decision P2).
    Generated small-talk lines are already in the right form."""
    text = turn.get("question_text", "")
    return text if turn.get("generated_by_engine") else hebrew_gender.render(text, session.get("participant_gender"))


def _position(turn: dict, turns: list) -> tuple:
    same_phase = [t for t in sorted(turns, key=_order) if t.get("phase") == turn.get("phase")]
    ids = [t["id"] for t in same_phase]
    return (ids.index(turn["id"]) + 1 if turn["id"] in ids else 1), max(len(ids), 1)


def _small_talk_log(turn: dict) -> list:
    """Every line of a small-talk turn's conversation (robot opening, answers, follow-ups)."""
    return turn.get("small_talk_log") or [{"speaker": "robot", "text": turn.get("question_text", "")}]


def _pending_follow_up(turn: dict):
    """The robot's follow-up line when it was decided but not yet answered, else None."""
    log_ = turn.get("small_talk_log") or []
    return log_[-1]["text"] if len(log_) > 1 and log_[-1]["speaker"] == "robot" else None


def _line_to_say(turn: dict, session: dict) -> str:
    return _pending_follow_up(turn) or _question_to_say(turn, session)


def dialogue_history(turns: list, turn: dict) -> list:
    """What was said before this turn (last HISTORY_TURNS turns), for the small-talk prompt."""
    earlier = [t for t in sorted(turns, key=_order) if _order(t) < _order(turn)][-HISTORY_TURNS:]
    lines = []
    for t in earlier:
        if t.get("small_talk_log"):
            lines.extend(t["small_talk_log"])
            continue
        feedback = (t.get("final_feedback") or t.get("proposed_feedback")) if t.get("status") == "done" else None
        for speaker, text in (("robot", t.get("question_text")),
                              ("participant", t.get("participant_answer")),
                              ("robot", t.get("robot_line")),
                              ("robot", PE_QUESTION if t.get("participant_pe_answer") else None),
                              ("participant", t.get("participant_pe_answer")),
                              ("robot", feedback)):
            if text:
                lines.append({"speaker": speaker, "text": text})
    return lines


def _listen_for(repeat_line: str, session: dict, backchannel: bool = True) -> tuple:
    """(text, None), or (None, skip_reason). On silence the robot repeats repeat_line once;
    on unrecognized speech it asks the participant to repeat once (spec "Error handling")."""
    repeated = asked_again = False
    while True:
        heard = furhat_client.listen(backchannel=backchannel)
        text = (heard.get("text") or "").strip()
        if heard.get("status") == "ok" and text:
            return text, None
        if heard.get("status") == "no_speech":
            if repeated:
                return None, "no_answer"
            repeated = True
            _say(repeat_line, session, gestures=backchannel)
        else:
            if not furhat_client.health_check():
                raise RobotDown()
            if asked_again:
                return None, "no_recognition"
            asked_again = True
            _say(NOT_HEARD_LINE, session, gestures=backchannel)


# ── Status handlers: each does one step and returns the updated turn ──────

def _start(turn, session, turns, propose):
    """queued (or awaiting_answer, plan decision P7): claim the turn."""
    if not b44.claim("Turn", turn["id"], turn["status"],
                     {"status": "robot_speaking", "claimed_by": WORKER_ID, "claimed_at": now()}):
        return None  # another worker has it
    return {**turn, "status": "robot_speaking", "claimed_by": WORKER_ID}


def _speak(turn, session, turns, propose):
    """robot_speaking: the question (generated for small talk), a small-talk follow-up, or, after
    the answer, the acknowledgement."""
    follow_up = _pending_follow_up(turn)
    if follow_up:
        _say(follow_up, session)
        return _update(turn, status="listening")
    if turn.get("participant_answer"):
        _say(turn["robot_line"], session)
        return _update(turn, status="done", done_at=now())
    if _is_scripted_opening(turn):
        return _speak_scripted(turn, session, turns)
    if turn.get("generated_by_engine") and not turn.get("question_text"):
        position, total = _position(turn, turns)
        line = small_talk.generate_line(turn.get("phase"), position, total, turn.get("expects_answer") is not False,
                                        dialogue_history(turns, turn), session.get("language", "he"),
                                        session.get("participant_gender"), session.get("robot_gender"),
                                        session.get("participant_name"))
        turn = _update(turn, question_text=line, engine_model=llm_client.current_model("lines"))
    _say(_question_to_say(turn, session), session)
    if turn.get("expects_answer") is False:
        return _update(turn, status="done", done_at=now())
    return _update(turn, status="listening")


def _is_scripted_opening(turn: dict) -> bool:
    """A line of the fixed opening script (website plan, 2026-11-17): said word for word."""
    return (turn.get("phase") == "Opening" and not turn.get("generated_by_engine")
            and bool(turn.get("question_text")))


def _speak_scripted(turn, session, turns):
    """A scripted opening line: a short generated reaction to the last answer (not on the
    first line), then the script question word for word. The line is saved before it is
    said, so a re-run says the same words again."""
    log_ = turn.get("small_talk_log") or []
    if log_ and log_[0]["speaker"] == "robot":
        line = log_[0]["text"]
    else:
        question = _question_to_say(turn, session)
        position, _ = _position(turn, turns)
        reaction = None
        if position > 1:
            reaction = small_talk.bridge(dialogue_history(turns, turn), session.get("language", "he"),
                                         session.get("participant_gender"), session.get("robot_gender"),
                                         session.get("participant_name"))
        line = f"{reaction} {question}" if reaction else question
        turn = _update(turn, small_talk_log=[{"speaker": "robot", "text": line}],
                       engine_model=llm_client.current_model("lines"))
    _say(line, session)
    return _update(turn, status="listening")


def _listen_answer(turn, session, turns, propose):
    """listening: the participant's answer."""
    key = (turn["id"], "answer")
    if key in _heard:  # a retry after a failed save: don't ask the participant again
        text, skip_reason = _heard[key], None
    else:
        text, skip_reason = _listen_for(_line_to_say(turn, session), session)
    if skip_reason and _pending_follow_up(turn):
        return _update(turn, status="done", done_at=now())  # no reply to a follow-up: just move on
    if skip_reason:
        return _skip(turn, skip_reason)
    _heard[key] = text
    log(f"Turn {turn.get('order')}: heard answer: {text}")
    saved = _update(turn, participant_answer=text, answer_submitted_at=now(), status="engine_processing")
    _heard.pop(key, None)
    return saved


def _with_one_retry(call):
    """Spec "Error handling": an LLM step is retried once before the researcher sees engine_error."""
    try:
        return call()
    except Exception:
        return call()


def _fail(turn: dict, error: Exception) -> dict:
    log(f"Turn {turn.get('order')}: {type(error).__name__}: {error}")
    return _update(turn, engine_error=f"{type(error).__name__}: {error}")


def _process(turn, session, turns, propose):
    """engine_processing, three cases: after the PE answer (grade + feedback); after a
    small-talk answer (done: the next line is the reply); after a Main answer (PBDI
    proposal for approval, or a content-only acknowledgement)."""
    if turn.get("participant_pe_answer"):
        return _grade_pe(turn, session)
    if turn.get("generated_by_engine") or _is_scripted_opening(turn):
        return _small_talk_reply(turn, session, turns)
    if turn.get("category") == PBDI_CATEGORY:
        return _propose(turn, session, propose, _emotions_shown(turns, turn))
    ack = acknowledgement.acknowledge(turn.get("question_text", ""), turn["participant_answer"],
                                      session.get("language", "he"), session.get("participant_gender"),
                                      session.get("robot_gender"))
    return _update(turn, robot_line=ack["line"], guardrail_flag=ack["guardrail_flag"],
                   guardrail_reason=ack["guardrail_reason"], engine_model=llm_client.current_model("lines"),
                   status="robot_speaking")


def _emotions_shown(turns: list, turn: dict) -> list:
    """Emotions proposed on earlier turns, so the classifier can vary its pick."""
    return [t["target_emotion"] for t in sorted(turns, key=_order)
            if _order(t) < _order(turn) and t.get("target_emotion")]


def _small_talk_reply(turn, session, turns):
    """After a small-talk answer: a follow-up question (the robot says it next), or move on."""
    convo = _small_talk_log(turn) + [{"speaker": "participant", "text": turn["participant_answer"]}]
    position, total = _position(turn, turns)
    follow_ups = sum(1 for line in convo if line["speaker"] == "robot") - 1
    ready_to_start = (turn.get("phase") == "Opening" and position == total  # the generated "ready to start?"
                      and not _is_scripted_opening(turn))
    may_continue = follow_ups < config.SMALL_TALK_MAX_FOLLOW_UPS and not ready_to_start
    line = None
    if may_continue:
        line = small_talk.follow_up(turn.get("phase"), dialogue_history(turns, turn) + convo,
                                    session.get("language", "he"), session.get("participant_gender"),
                                    session.get("robot_gender"), session.get("participant_name"))
    if line:
        return _update(turn, small_talk_log=convo + [{"speaker": "robot", "text": line}],
                       engine_model=llm_client.current_model("lines"), status="robot_speaking")
    return _update(turn, small_talk_log=convo, status="done", done_at=now())


def _propose(turn, session, propose, used_emotions):
    """PBDI: evaluator + emotion + reply, then wait for the researcher's Approve."""
    try:
        proposal = _with_one_retry(
            lambda: propose(turn.get("question_text", ""), turn["participant_answer"], session.get("mode"),
                            used_emotions=used_emotions, language=session.get("language", "he"),
                            participant_gender=session.get("participant_gender"),
                            robot_gender=session.get("robot_gender")))
    except Exception as e:  # after one retry: engine_error, and the researcher's Retry re-runs this step
        return _fail(turn, e)
    log(f"Turn {turn.get('order')}: proposed {proposal.get('target_emotion')} ({proposal.get('intensity')})")
    return _update(turn, **proposal, engine_model=llm_client.current_model("judgment"), engine_error="",
                   engine_responded_at=now(), status="awaiting_approval")


def _react(turn, session, turns, propose):
    """robot_reacting (set by the researcher's Approve): emotion + reply, then the fixed PE question."""
    done = b44.list_records("RobotCommand", {"turn": turn["id"], "type": "say_with_gesture", "status": "done"}, limit=1)
    if done:
        # Retry after a robot drop on the PE question: the reaction already played, never repeat it (P5).
        _say(PE_QUESTION, session, gestures=False)
        return _update(turn, robot_line=done[0]["text"], status="pe_listening")
    text = turn.get("final_reply") or turn.get("proposed_reply", "")
    count = len(b44.list_records("RobotCommand", {"session": session["id"]}, limit=1000))
    cmd = b44.create_record("RobotCommand", {
        "session": session["id"], "turn": turn["id"], "sequence": count + 1,
        "type": "say_with_gesture", "text": text, "emotion": turn.get("target_emotion"),
        "intensity": turn.get("intensity"), "language": session.get("language", "he"),
        "status": "sent", "sent_at": now(),
    })
    result = furhat_client.react(turn["target_emotion"], int(turn["intensity"]), text=text,
                                 language=session.get("language"))
    if not result["sent"]:
        b44.update_record("RobotCommand", cmd["id"], {"status": "error", "error_message": result["reason"]})
        raise RobotDown()
    b44.update_record("RobotCommand", cmd["id"], {"status": "done", "completed_at": now()})
    _say(PE_QUESTION, session, gestures=False)
    return _update(turn, robot_line=text, status="pe_listening")


def _listen_pe(turn, session, turns, propose):
    """pe_listening: the participant's guess. Silence/bad ASR skips the turn (plan decision P6)."""
    key = (turn["id"], "pe")
    if key in _heard:
        text, skip_reason = _heard[key], None
    else:
        text, skip_reason = _listen_for(PE_QUESTION, session, backchannel=False)
    if skip_reason:
        return _skip(turn, f"pe_{skip_reason}")
    _heard[key] = text
    log(f"Turn {turn.get('order')}: heard PE answer: {text}")
    saved = _update(turn, participant_pe_answer=text, pe_submitted_at=now(), status="engine_processing")
    _heard.pop(key, None)
    return saved


def _grade_pe(turn, session):
    """Correct/Partial/Wrong + the feedback line, then wait for the researcher's Approve."""
    try:
        graded = _with_one_retry(
            lambda: pe_check.grade_pe_answer(turn.get("target_emotion", ""), turn["participant_pe_answer"],
                                             turn.get("emotion_trigger", "")))
    except Exception as e:
        return _fail(turn, e)
    feedback = pe_feedback.generate_feedback(turn.get("target_emotion", ""), turn.get("question_text", ""),
                                             turn.get("participant_answer", ""), turn["participant_pe_answer"],
                                             graded["result"], session.get("language", "he"),
                                             session.get("participant_gender"), session.get("robot_gender"))
    log(f"Turn {turn.get('order')}: PE {graded['result']}")
    return _update(turn, pe_result=graded["result"], pe_explanation=graded["explanation"],
                   pe_reason_result=graded.get("reason_result", ""),
                   pe_reason_explanation=graded.get("reason_explanation", ""),
                   proposed_feedback=feedback["line"], pe_answer_why=feedback["reason"],
                   engine_model=llm_client.current_model("judgment"),
                   engine_responded_at=now(), status="awaiting_feedback")


def _give_feedback(turn, session, turns, propose):
    """robot_feedback (set by the researcher's Approve): the robot reveals what it felt."""
    _say(turn.get("final_feedback") or turn.get("proposed_feedback", ""), session)
    return _update(turn, status="done", done_at=now())


_HANDLERS = {
    "queued": _start,
    "awaiting_answer": _start,
    "robot_speaking": _speak,
    "listening": _listen_answer,
    "engine_processing": _process,
    "robot_reacting": _react,
    "pe_listening": _listen_pe,
    "robot_feedback": _give_feedback,
}
