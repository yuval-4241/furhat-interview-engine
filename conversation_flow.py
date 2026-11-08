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
import base44_client as b44
import config
import furhat_client
import hebrew_gender
import llm_client
import small_talk
from worker_common import WORKER_ID, log, now

PBDI_CATEGORY = "Behavioral (PBDI)"
PE_QUESTION = "מה לדעתך הרגשתי, ולמה?"
NOT_HEARD_LINE = "סליחה, לא שמעתי. אפשר לחזור?"
FINISHED = ("done", "skipped")
WAITING_FOR_RESEARCHER = ("awaiting_approval", "awaiting_feedback")
HISTORY_TURNS = 10  # spec: the small-talk prompt sees the last 10 turns

_robot_wait_started = {}  # turn id -> monotonic time the robot was first seen down


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
                return False  # not a Live status (e.g. left over from Simulation)
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


def _say(text: str, session: dict) -> None:
    if not furhat_client.say(text, language=session.get("language"))["sent"]:
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


def dialogue_history(turns: list, turn: dict) -> list:
    """What was said before this turn (last HISTORY_TURNS turns), for the small-talk prompt."""
    earlier = [t for t in sorted(turns, key=_order) if _order(t) < _order(turn)][-HISTORY_TURNS:]
    lines = []
    for t in earlier:
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


def _listen_for(repeat_line: str, session: dict) -> tuple:
    """(text, None), or (None, skip_reason). On silence the robot repeats repeat_line once;
    on unrecognized speech it asks the participant to repeat once (spec "Error handling")."""
    repeated = asked_again = False
    while True:
        heard = furhat_client.listen()
        text = (heard.get("text") or "").strip()
        if heard.get("status") == "ok" and text:
            return text, None
        if heard.get("status") == "no_speech":
            if repeated:
                return None, "no_answer"
            repeated = True
            _say(repeat_line, session)
        else:
            if not furhat_client.health_check():
                raise RobotDown()
            if asked_again:
                return None, "no_recognition"
            asked_again = True
            _say(NOT_HEARD_LINE, session)


# ── Status handlers: each does one step and returns the updated turn ──────

def _start(turn, session, turns, propose):
    """queued (or awaiting_answer, plan decision P7): claim the turn."""
    if not b44.claim("Turn", turn["id"], turn["status"],
                     {"status": "robot_speaking", "claimed_by": WORKER_ID, "claimed_at": now()}):
        return None  # another worker has it
    return {**turn, "status": "robot_speaking", "claimed_by": WORKER_ID}


def _speak(turn, session, turns, propose):
    """robot_speaking: the question (generated for small talk), or, after the answer, the acknowledgement."""
    if turn.get("participant_answer"):
        _say(turn["robot_line"], session)
        return _update(turn, status="done", done_at=now())
    if turn.get("generated_by_engine") and not turn.get("question_text"):
        position, total = _position(turn, turns)
        line = small_talk.generate_line(turn.get("phase"), position, total, turn.get("expects_answer") is not False,
                                        dialogue_history(turns, turn), session.get("language", "he"),
                                        session.get("participant_gender"), session.get("robot_gender"),
                                        session.get("participant_name"))
        turn = _update(turn, question_text=line, engine_model=llm_client.current_model())
    _say(_question_to_say(turn, session), session)
    if turn.get("expects_answer") is False:
        return _update(turn, status="done", done_at=now())
    return _update(turn, status="listening")


def _listen_answer(turn, session, turns, propose):
    """listening: the participant's answer."""
    text, skip_reason = _listen_for(_question_to_say(turn, session), session)
    if skip_reason:
        return _skip(turn, skip_reason)
    return _update(turn, participant_answer=text, answer_submitted_at=now(), status="engine_processing")


def _process(turn, session, turns, propose):
    """engine_processing: small talk is done (the next line is the reply); Main turns get an acknowledgement."""
    if turn.get("generated_by_engine"):
        return _update(turn, status="done", done_at=now())
    ack = acknowledgement.acknowledge(turn.get("question_text", ""), turn["participant_answer"],
                                      session.get("language", "he"), session.get("participant_gender"),
                                      session.get("robot_gender"))
    return _update(turn, robot_line=ack["line"], guardrail_flag=ack["guardrail_flag"],
                   guardrail_reason=ack["guardrail_reason"], engine_model=llm_client.current_model(),
                   status="robot_speaking")


_HANDLERS = {
    "queued": _start,
    "awaiting_answer": _start,
    "robot_speaking": _speak,
    "listening": _listen_answer,
    "engine_processing": _process,
}
