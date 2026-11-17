"""
Engine worker — polls the Base44 experiment website and does all the work
behind it (the website is frontend + DB only and never calls the Engine).

Live sessions are run by the robot itself through conversation_flow.py
(small talk, questions, listening, reactions, PE). Simulation and Mock keep
the typed-answer flow below. Still deferred: expression_level, question sets
for Baseline/Post/Followup, English response bank, robot reset/stop.

Run by hand on experiment days only, stop with Ctrl+C:
    set -a; source .env; set +a
    python engine_worker.py

See docs/superpowers/specs/2026-11-02-base44-lab-app-integration-design.md.
"""

import threading
import time

import config
import lab_db
from lab_db import client as b44
import conversation_flow
import emotion_classifier
import evaluator
import furhat_client
import guardrail
import llm_client
import llm_line
import model_registry
import pe_check
import reaction_line
from question_bank import QuestionBank
from worker_common import WORKER_ID, log as _log, now as _now

_question_bank = QuestionBank()

# RobotCommand id -> monotonic time it was first seen waiting for the robot
_robot_wait_started = {}

_personas_applied = set()  # session ids whose face/voice were already sent to the robot
_robot_was_connected = False  # last poll's robot state: a restarted skill has lost the persona


def _app_level(level: str) -> str:
    # Engine uses low/medium/high (schemas.py), the website Low/Medium/High
    return level.capitalize()


# ── Heartbeat ───────────────────────────────────────────────────────────────

_heartbeat_id = None  # looked up once, so each heartbeat costs one request


def send_heartbeat(robot_connected: bool) -> None:
    global _heartbeat_id
    fields = {
        "last_seen": _now(),
        "engine_version": config.ENGINE_VERSION,
        "robot_connected": robot_connected,
        "active_model": config.MODEL_DEFAULT,
    }
    if _heartbeat_id is None:
        records = b44.list_records("EngineHeartbeat", {"key": "engine-main"})
        if not records:
            records = [b44.create_record("EngineHeartbeat", {"key": "engine-main", **fields})]
        _heartbeat_id = records[0]["id"]
    b44.update_record("EngineHeartbeat", _heartbeat_id, fields)


def heartbeat_once() -> None:
    try:
        send_heartbeat(furhat_client.health_check())
    except b44.Base44Error as e:  # RateLimited too: the next beat is WORKER_HEARTBEAT_EVERY away anyway
        _log(f"Heartbeat failed: {e}")
    except Exception as e:  # the heartbeat thread must never die silently
        _log(f"Heartbeat failed: {type(e).__name__}: {e}")


def start_heartbeat_thread() -> threading.Thread:
    """Heartbeat on its own thread (plan decision P8): a /listen in the main loop blocks
    for up to ~2.5 min, and the website shows "Engine unavailable" after 60 s without one."""
    def run():
        while True:
            heartbeat_once()
            time.sleep(config.WORKER_HEARTBEAT_EVERY)

    thread = threading.Thread(target=run, name="heartbeat", daemon=True)
    thread.start()
    return thread


# ── Session setup ───────────────────────────────────────────────────────────

def question_set_for(session_type: str) -> int:
    """Training1..Training5 -> question-bank session 1..5. Others default to 1 (open question)."""
    if session_type and session_type.startswith("Training") and session_type[-1].isdigit():
        return int(session_type[-1])
    return 1


def ensure_turns(session: dict) -> None:
    if not lab_db.ENGINE_MANAGES_MODELS_AND_TURNS:
        return  # the new website creates every Turn when a session starts
    if b44.list_records("Turn", {"session": session["id"]}, limit=1):
        return
    questions = _question_bank.session(question_set_for(session.get("session_type")))
    for order, q in enumerate(questions, start=1):
        b44.create_record("Turn", {
            "session": session["id"],
            "order": order,
            "question_text": q["text"],
            "status": "awaiting_answer",
        })
    _log(f"Session {session.get('session_code')}: created {len(questions)} turns")


# ── awaiting_engine -> awaiting_approval ────────────────────────────────────

def build_proposal(question: str, answer: str, mode: str, used_emotions=(), language: str = "he",
                   participant_gender=None, robot_gender=None) -> dict:
    if mode == "Mock":
        emotion, intensity, trigger = "HAPPINESS", 2, ""
        ev_fields = {"evaluation_category": "NEUTRAL", "evaluator_confidence": 1.0,
                     "engine_rationale": "Mock mode — no LLM call."}
        flag, reason = False, ""
    else:
        ev = evaluator.evaluate(question, answer)
        gr = guardrail.check_rationale(ev.rationale)
        reaction = emotion_classifier.classify_emotion(question, answer, used_emotions)
        emotion, intensity = reaction["emotion"], reaction["intensity"]
        trigger = reaction.get("trigger", "")
        ev_fields = {"evaluation_category": ev.category, "evaluator_confidence": ev.confidence,
                     "engine_rationale": ev.rationale}
        flag = not gr.passed
        reason = f"style-bias language in rationale: {gr.matched_patterns}" if flag else ""

    valence = emotion_classifier.derive_valence(emotion)
    arousal = emotion_classifier.derive_arousal(intensity)
    if mode == "Mock":
        reply = reaction_line.FALLBACK_LINES[llm_line.language_or_default(language)][emotion]
    else:  # the spoken reply comes from the same classified emotion as the face
        reply = reaction_line.generate(emotion, intensity, question, answer, language,
                                       participant_gender, robot_gender)
    return {
        **ev_fields,
        "target_emotion": emotion,
        "intensity": intensity,
        "emotion_trigger": trigger,  # what in the answer caused it; the PE reason is graded against it
        "valence": _app_level(valence),
        "arousal": _app_level(arousal),
        "proposed_reply": reply,
        "guardrail_flag": flag,
        "guardrail_reason": reason,
        # answer key for the PE step — shown to the researcher only after the participant answers
        "pe_answer_feeling": emotion,
        "pe_answer_why": ev_fields["engine_rationale"],
    }


def process_turn(turn: dict, session: dict) -> None:
    if not b44.claim("Turn", turn["id"], "awaiting_engine",
                     {"status": "engine_processing", "claimed_by": WORKER_ID, "claimed_at": _now()}):
        return
    try:
        earlier = sorted(b44.list_records("Turn", {"session": session["id"]}, limit=200),
                         key=lambda t: t.get("order") or 0)
        used = [t["target_emotion"] for t in earlier if t["id"] != turn["id"] and t.get("target_emotion")]
        speech = speech_context(session)
        proposal = build_proposal(turn["question_text"], turn.get("participant_answer", ""), session.get("mode"),
                                  used, session.get("language", "he"), speech["participant_gender"],
                                  speech["robot_gender"])
    except Exception as e:
        # stays in engine_processing; the website shows engine_error + a Retry button
        b44.update_record("Turn", turn["id"], {"engine_error": f"{type(e).__name__}: {e}"})
        _log(f"Turn {turn.get('order')}: evaluation failed: {e}")
        return
    b44.update_record("Turn", turn["id"], {
        **proposal,
        "engine_error": "",
        "engine_model": llm_client.current_model("judgment"),
        "status": "awaiting_approval",
        "engine_responded_at": _now(),
    })
    _log(f"Turn {turn.get('order')}: proposed {proposal['target_emotion']} ({proposal['intensity']})")


# ── robot_reacting -> awaiting_pe ───────────────────────────────────────────

def react_turn(turn: dict, session: dict) -> None:
    """Simulation/Mock: no robot, so the approved reaction just moves the turn on to the PE step."""
    b44.update_record("Turn", turn["id"], {"status": "awaiting_pe"})


def execute_command(cmd: dict, robot_connected: bool) -> None:
    """Send one pending RobotCommand — the Engine's own or one the website created (e.g. reading a question)."""
    if cmd.get("type") == "stop":
        # The Kotlin bridge has no /stop endpoint yet — fail loudly instead of pretending
        b44.update_record("RobotCommand", cmd["id"], {
            "status": "error", "error_message": "stop not supported by the robot bridge yet"})
        return
    if not robot_connected:
        started = _robot_wait_started.setdefault(cmd["id"], time.monotonic())
        if time.monotonic() - started < config.ROBOT_WAIT_SECONDS:
            return  # try again next poll
        b44.update_record("RobotCommand", cmd["id"], {
            "status": "error", "error_message": "Robot not reachable for 60s"})
        _log(f"Command {cmd.get('type')}: robot not reachable — giving up")
    else:
        b44.update_record("RobotCommand", cmd["id"], {"status": "sent", "sent_at": _now()})
        if cmd.get("type") == "say":
            result = furhat_client.say(cmd.get("text", ""), language=cmd.get("language"))
        else:
            result = furhat_client.react(cmd["emotion"], int(cmd["intensity"]), text=cmd.get("text"),
                                         language=cmd.get("language"))
        if result["sent"]:
            b44.update_record("RobotCommand", cmd["id"], {"status": "done", "completed_at": _now()})
            _log(f"Robot: {cmd.get('type')} {cmd.get('emotion') or ''} {cmd.get('text', '')[:40]}")
        else:
            b44.update_record("RobotCommand", cmd["id"], {
                "status": "error", "error_message": result["reason"]})
    _robot_wait_started.pop(cmd["id"], None)


# ── awaiting_pe_check -> awaiting_feedback ──────────────────────────────────

def check_pe(turn: dict, session: dict) -> None:
    if session.get("mode") == "Mock":
        graded = {"result": "Correct", "explanation": "Mock mode — no LLM call."}
    else:
        graded = pe_check.grade_pe_answer(turn.get("target_emotion", ""), turn.get("participant_pe_answer", ""),
                                          turn.get("emotion_trigger", ""))
    b44.update_record("Turn", turn["id"], {
        "pe_result": graded["result"],
        "pe_explanation": graded["explanation"],
        "pe_reason_result": graded.get("reason_result", ""),
        "pe_reason_explanation": graded.get("reason_explanation", ""),
        "status": "awaiting_feedback",
    })
    _log(f"Turn {turn.get('order')}: PE {graded['result']}")


# ── Persona ─────────────────────────────────────────────────────────────────

def _debrief_started(session: dict) -> bool:
    """The session's friend debrief has begun (its opener was generated or it moved past queued)."""
    turns = b44.list_records("Turn", {"session": session["id"], "phase": "Debrief"}, limit=5)
    return any(t.get("question_text") or t.get("status") not in ("queued", "awaiting_answer") for t in turns)


def apply_persona(session: dict, robot_connected: bool) -> None:
    """Send the session's Persona face + voice to the robot, once per session.

    Not marked applied while the robot is unreachable, so it is retried on a later poll."""
    if session.get("mode") != "Live" or session["id"] in _personas_applied or not robot_connected:
        return
    if _debrief_started(session) and (config.FRIEND_FACE or config.FRIEND_VOICE):
        # Once the friend appeared the robot never switches back (2026-11-17 spec): after a
        # restart or a robot reconnect, re-send the friend, not the interviewer.
        result = furhat_client.set_persona(config.FRIEND_FACE, config.FRIEND_VOICE, session.get("language"))
        if result["sent"] or result.get("bridge_error"):
            _personas_applied.add(session["id"])
        return
    persona = {}
    if session.get("persona"):
        try:
            persona = b44.get_record("Persona", session["persona"])
        except b44.RateLimited:
            raise
        except b44.Base44Error as e:
            # don't retry every poll; the session just runs with the robot's current persona
            _log(f"Session {session.get('session_code')}: persona lookup failed: {e}")
            _personas_applied.add(session["id"])
            return
    result = furhat_client.set_persona(persona.get("furhat_face"), persona.get("furhat_voice"),
                                       session.get("language"))
    if not result["sent"]:
        _log(f"Session {session.get('session_code')}: persona not applied: {result['reason']}")
    if result["sent"] or result.get("bridge_error"):
        _personas_applied.add(session["id"])  # a bridge refusal (bad voice name) won't fix itself


# ── Hebrew gender of the robot's lines ──────────────────────────────────────

_speech_context = {}  # session id -> {"participant_gender", "robot_gender", "participant_name"}

_PARTICIPANT_GENDERS = {"Male": "male", "Female": "female"}


def speech_context(session: dict) -> dict:
    """The participant's gender (Participant.gender) and the robot's (its Persona voice), for
    Hebrew wording (plan decision P2), and the participant's first name for small talk
    (plan decision P12). Looked up once per session; a lookup error is not cached, so the
    next poll tries again."""
    if session["id"] in _speech_context:
        return _speech_context[session["id"]]
    context = {"participant_gender": None, "robot_gender": None, "participant_name": None}
    try:
        if session.get("participant"):
            participant = b44.get_record("Participant", session["participant"])
            context["participant_gender"] = _PARTICIPANT_GENDERS.get(participant.get("gender"))
            context["participant_name"] = (participant.get("first_name") or "").strip() or None
        if session.get("persona"):
            voice = b44.get_record("Persona", session["persona"]).get("furhat_voice")
            context["robot_gender"] = config.VOICE_GENDERS.get(voice)
    except b44.RateLimited:
        raise
    except b44.Base44Error as e:
        _log(f"Session {session.get('session_code')}: participant/persona lookup failed: {e}")
        return {"participant_gender": None, "robot_gender": None, "participant_name": None}
    _speech_context[session["id"]] = context
    return context


# ── Live sessions: the robot runs the conversation (conversation_flow.py) ──

def run_live_session(session: dict, robot_connected: bool) -> None:
    """Advance the session's current turn. When it finishes, start the next one right away,
    unless the researcher paused or ended the session meanwhile (plan decision P9).
    The flow reads the Hebrew genders from the session dict (plan decision P2)."""
    session = {**session, **speech_context(session)}
    while True:
        turns = b44.list_records("Turn", {"session": session["id"]}, sort="order")
        turn = conversation_flow.current_turn(turns)
        if turn is None or not conversation_flow.advance(turn, session, turns, robot_connected, build_proposal):
            return
        if b44.get_record("Session", session["id"]).get("status") != "Running":
            return


# ── Main loop ───────────────────────────────────────────────────────────────

def poll_once(robot_connected: bool) -> bool:
    """One pass over all Running sessions. Returns True if any session is Running."""
    global _robot_was_connected
    sessions = {s["id"]: s for s in b44.list_records("Session", {"status": "Running"})}

    if robot_connected and not _robot_was_connected and _personas_applied:
        _log("Robot is back: re-applying session personas")
        _personas_applied.clear()
    _robot_was_connected = robot_connected

    # Persona before any command, so a restarted worker re-applies it before speaking.
    for session in sessions.values():
        apply_persona(session, robot_connected)

    # Robot commands next, in order. Only for Running Live sessions — never replay a closed session's backlog.
    pending = b44.list_records("RobotCommand", {"status": "pending"}, sort="sequence")
    for cmd in pending:
        session = sessions.get(cmd.get("session"))
        if session and session.get("mode") == "Live":
            try:
                execute_command(cmd, robot_connected)
            except b44.RateLimited:
                raise
            except b44.Base44Error as e:
                _log(f"Command {cmd.get('type')}: Base44 error: {e}")

    handlers = {"awaiting_engine": process_turn, "awaiting_pe_check": check_pe,
                "robot_reacting": react_turn}
    for session in sessions.values():
        with llm_client.model_override(model_registry.model_for_session(session)):
            try:
                if session.get("mode") == "Live":
                    run_live_session(session, robot_connected)
                    continue
                turns = b44.list_records("Turn", {"session": session["id"]}, sort="order")
                if not turns:
                    ensure_turns(session)
                    continue
                for turn in turns:
                    try:
                        if turn.get("status") in handlers:
                            handlers[turn["status"]](turn, session)
                    except b44.RateLimited:
                        raise
                    except b44.Base44Error as e:
                        _log(f"Turn {turn.get('order')}: Base44 error: {e}")
            except b44.RateLimited:
                raise
            except b44.Base44Error as e:
                _log(f"Session {session.get('session_code')}: Base44 error: {e}")
            except Exception as e:  # one broken session must not stop the others or the worker
                _log(f"Session {session.get('session_code')}: {type(e).__name__}: {e}")
    return bool(sessions)


def main() -> None:
    _log(f"Engine worker {WORKER_ID} started (Ctrl+C to stop)")
    if lab_db.ENGINE_MANAGES_MODELS_AND_TURNS:
        try:
            model_registry.sync_to_base44()
            _log("LLM models synced to the website")
        except b44.Base44Error as e:
            _log(f"Model sync failed (continuing): {e}")
    else:
        _log(f"Website backend: {config.LAB_BACKEND} (it manages the model list)")
    start_heartbeat_thread()
    backoff = 0.0
    while True:
        active = False
        try:
            robot_connected = furhat_client.health_check()
            active = poll_once(robot_connected)
            backoff = 0.0
        except b44.RateLimited:
            backoff = min(backoff * 2 or config.WORKER_BACKOFF_START, config.WORKER_BACKOFF_MAX)
            _log(f"Base44 says too many requests (429) — pausing {backoff:.0f}s")
            time.sleep(backoff)
            continue
        except b44.Base44Error as e:
            _log(f"Base44 unreachable: {e}")
        time.sleep(config.WORKER_POLL_ACTIVE if active else config.WORKER_POLL_IDLE)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _log("Engine worker stopped")
