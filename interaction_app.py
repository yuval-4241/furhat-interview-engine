"""
interaction_app.py -- live interaction demo control surface. A human
answers interview questions by voice; the robot reacts (on PE-eligible
questions) and asks a perspective-taking question. See
docs/superpowers/specs/2026-10-28-live-interaction-demo-design.md.
"""

import os

import streamlit as st

import config
import furhat_client

st.set_page_config(page_title="Live Interaction Demo", page_icon="🎙️", layout="wide")

PAGE = st.sidebar.radio("תפריט", ["שיחה חיה", "היסטוריה", "הגדרות"])


def _configured(value: str) -> str:
    return "✅ מוגדר" if value else "❌ לא מוגדר"


if PAGE == "הגדרות":
    st.title("הגדרות")

    st.subheader("מפתחות API")
    st.write(f"**OpenAI API Key:** {_configured(config.OPENAI_API_KEY)}")
    st.write(f"**Lab LLM Token:** {_configured(config.LAB_LLM_TOKEN)}")
    google_creds_set = bool(config.GOOGLE_APPLICATION_CREDENTIALS)
    google_creds_exists = google_creds_set and os.path.isfile(config.GOOGLE_APPLICATION_CREDENTIALS)
    st.write(
        f"**Google credentials:** "
        f"{'✅ מוגדר וקיים' if google_creds_exists else ('⚠️ מוגדר אך הקובץ לא נמצא' if google_creds_set else '❌ לא מוגדר')}"
    )

    st.subheader("חיבורים")
    if st.button("בדוק חיבור לרובוט"):
        if furhat_client.health_check():
            st.success("הרובוט מגיב (http://localhost:8765/health)")
        else:
            st.error("אין תגובה מהרובוט — ודאי שהסקיל רץ")

elif PAGE == "שיחה חיה":
    st.title("שיחה חיה")

    _VALENCE_TO_NUM = {"low": 0, "medium": 1, "high": 2}
    _AROUSAL_TO_NUM = {"low": 0, "medium": 1, "high": 2}

    if "session_id" not in st.session_state:
        st.session_state.session_id = None
        st.session_state.transcript = []
        st.session_state.va_history = []
        st.session_state.question_index = 0
        st.session_state.paused = False
        st.session_state.stopped = False
        st.session_state.pending_pe = None  # holds ground-truth emotion while awaiting a PE answer
        st.session_state.last_announced = (None, None)  # (question_index, stage) already spoken+logged once

    if st.session_state.session_id is None:
        with st.form("start_session"):
            session_code = st.text_input("קוד משתתף (לא שם!)")
            session_number = st.selectbox("מפגש", options=[1, 2, 3, 4, 5])
            st.caption(
                f"ספק פעיל: **{config.LLM_PROVIDER}**, מודל: **{config.MODEL_DEFAULT}** "
                f"(נקבע בהפעלת השרת, לא ניתן לשינוי כאן)"
            )
            started = st.form_submit_button("🟢 התחל שיחה", type="primary")

        if started:
            if not session_code.strip():
                st.error("צריך קוד משתתף כדי להתחיל.")
            else:
                st.session_state.session_id = session_code.strip()
                st.session_state.session_number = session_number
                st.rerun()

    else:
        import time

        import evaluator
        import guardrail
        import emotion_classifier
        import session_flow
        import stt as stt_module
        import pe_check as pe_check_module
        import interaction_log
        from question_bank import QuestionBank

        bank = QuestionBank()
        questions = bank.session(st.session_state.session_number)

        col_a, col_b, col_c, col_d = st.columns(4)
        if col_a.button("🔁 חזור על השאלה"):
            st.session_state.last_announced = (None, None)
            st.rerun()
        if col_b.button("⏭️ דלג"):
            st.session_state.question_index += 1
            st.session_state.pending_pe = None
            st.rerun()
        if col_c.button("⏸️ השהה" if not st.session_state.paused else "▶️ המשך"):
            st.session_state.paused = not st.session_state.paused
        if col_d.button("⏹️ עצור"):
            st.session_state.stopped = True

        for msg in st.session_state.transcript:
            with st.chat_message(msg["role"]):
                st.write(msg["text"])

        if st.session_state.va_history:
            st.line_chart(
                {
                    "valence": [v for v, a in st.session_state.va_history],
                    "arousal": [a for v, a in st.session_state.va_history],
                }
            )

        if st.session_state.stopped:
            st.success("השיחה הסתיימה.")
        elif st.session_state.paused:
            st.warning("השיחה מושהית.")
        elif st.session_state.question_index >= len(questions):
            st.success("כל השאלות נענו.")
        else:
            q = questions[st.session_state.question_index]
            triggers_pe = session_flow.triggers_pe(q["category"])

            if st.session_state.pending_pe is None:
                # ── Interview question turn ──
                if st.session_state.last_announced != (st.session_state.question_index, "interview"):
                    with st.chat_message("assistant"):
                        st.write(q["text"])
                    furhat_client.say(q["text"])
                    st.session_state.transcript.append({"role": "assistant", "text": q["text"]})
                    st.session_state.last_announced = (st.session_state.question_index, "interview")

                audio = st.audio_input("ענה/י בקול", key=f"audio_interview_{st.session_state.question_index}")
                manual_text = st.text_input(
                    "או הקלד/י תשובה (גיבוי אם התמלול נכשל)",
                    key=f"text_interview_{st.session_state.question_index}",
                )

                if audio is not None or manual_text:
                    if st.session_state.get("last_answer_index") != st.session_state.question_index:
                        start = time.time()
                        if manual_text:
                            new_answer_text = manual_text
                            new_stt_corrected = True
                        else:
                            try:
                                new_answer_text = stt_module.transcribe(audio.getvalue())
                                new_stt_corrected = False
                            except stt_module.SttError as e:
                                interaction_log.log_technical("stt", (time.time() - start) * 1000, error=str(e))
                                st.error(f"תמלול נכשל: {e}. אפשר להקליד למטה.")
                                new_answer_text = None
                                new_stt_corrected = None

                        if new_answer_text:
                            st.session_state.transcript.append({"role": "user", "text": new_answer_text})
                            st.session_state.last_answer_index = st.session_state.question_index
                            st.session_state.last_answer_text = new_answer_text
                            st.session_state.last_stt_corrected = new_stt_corrected

                    if st.session_state.get("last_answer_index") == st.session_state.question_index:
                        answer_text = st.session_state.last_answer_text
                        stt_corrected = st.session_state.last_stt_corrected
                    else:
                        answer_text = None
                        stt_corrected = None

                    if answer_text:
                        llm_start = time.time()
                        try:
                            ev = evaluator.evaluate(q["text"], answer_text)
                            gr = guardrail.check_rationale(ev.rationale)
                            consistency = guardrail.check_consistency(ev.category, ev.valence)
                        except Exception as e:
                            interaction_log.log_technical("llm", (time.time() - llm_start) * 1000, error=str(e))
                            st.error(f"ההערכה נכשלה: {e}")
                            if st.button("נסה שוב", key=f"retry_eval_{st.session_state.question_index}"):
                                st.rerun()
                            st.stop()

                        record = {
                            "timestamp": time.time(),
                            "turn": st.session_state.question_index,
                            "question_category": q["category"],
                            "triggers_pe": triggers_pe,
                            "stage": "interview",
                            "question": q["text"],
                            "transcript": answer_text,
                            "stt_corrected": stt_corrected,
                            "evaluation": {
                                "category": ev.category,
                                "confidence": ev.confidence,
                                "rationale": ev.rationale,
                            },
                            "valence": ev.valence,
                            "arousal": ev.arousal,
                            "guardrail": {"passed": gr.passed, "matched_patterns": gr.matched_patterns},
                            "consistency": {"consistent": consistency.consistent, "note": consistency.note},
                            "model": {
                                "provider": config.LLM_PROVIDER,
                                "model": config.MODEL_DEFAULT,
                            },
                        }

                        if triggers_pe:
                            try:
                                reaction = emotion_classifier.classify_emotion(q["text"], answer_text)
                            except Exception as e:
                                interaction_log.log_technical("llm", 0, error=str(e))
                                st.error(f"סיווג הרגש נכשל: {e}")
                                if st.button("נסה שוב", key=f"retry_classify_{st.session_state.question_index}"):
                                    st.rerun()
                                st.stop()

                            derived_valence = emotion_classifier.derive_valence(reaction["emotion"])
                            derived_arousal = emotion_classifier.derive_arousal(reaction["intensity"])
                            record["robot_emotion"] = reaction["emotion"]
                            record["robot_intensity"] = reaction["intensity"]

                            sent = furhat_client.react(reaction["emotion"], reaction["intensity"])
                            if not sent["sent"]:
                                interaction_log.log_technical("robot", 0, error=sent["reason"])
                                st.warning(f"הרובוט לא הגיב: {sent['reason']}")

                            st.session_state.va_history.append(
                                (_VALENCE_TO_NUM.get(derived_valence, 1), _AROUSAL_TO_NUM.get(derived_arousal, 1))
                            )
                            st.session_state.pending_pe = reaction["emotion"]
                        else:
                            sent = furhat_client.say("תודה על התשובה.")
                            if not sent["sent"]:
                                interaction_log.log_technical("robot", 0, error=sent["reason"])
                                st.warning(f"הרובוט לא הגיב: {sent['reason']}")
                            st.session_state.question_index += 1

                        interaction_log.log_turn(st.session_state.session_id, record)
                        st.rerun()

            else:
                # ── PE question turn (only reached when triggers_pe was True) ──
                pe_question = "מה לדעתך הרגשתי? למה?"
                if st.session_state.last_announced != (st.session_state.question_index, "pe"):
                    with st.chat_message("assistant"):
                        st.write(pe_question)
                    furhat_client.say(pe_question)
                    st.session_state.transcript.append({"role": "assistant", "text": pe_question})
                    st.session_state.last_announced = (st.session_state.question_index, "pe")

                pe_audio = st.audio_input(
                    "ענה/י בקול (שאלת פרספקטיבה)",
                    key=f"audio_pe_{st.session_state.question_index}",
                )
                pe_manual_text = st.text_input(
                    "או הקלד/י תשובה", key=f"pe_manual_{st.session_state.question_index}"
                )

                if pe_audio is not None or pe_manual_text:
                    if st.session_state.get("last_pe_answer_index") != st.session_state.question_index:
                        if pe_manual_text:
                            new_pe_answer = pe_manual_text
                        else:
                            try:
                                new_pe_answer = stt_module.transcribe(pe_audio.getvalue())
                            except stt_module.SttError as e:
                                interaction_log.log_technical("stt", 0, error=str(e))
                                st.error(f"תמלול נכשל: {e}. אפשר להקליד למטה.")
                                new_pe_answer = None

                        if new_pe_answer:
                            st.session_state.transcript.append({"role": "user", "text": new_pe_answer})
                            st.session_state.last_pe_answer_index = st.session_state.question_index
                            st.session_state.last_pe_answer_text = new_pe_answer

                    if st.session_state.get("last_pe_answer_index") == st.session_state.question_index:
                        pe_answer = st.session_state.last_pe_answer_text
                    else:
                        pe_answer = None

                    if pe_answer:
                        try:
                            result = pe_check_module.check_pe_answer(st.session_state.pending_pe, pe_answer)
                        except Exception as e:
                            interaction_log.log_technical("llm", 0, error=str(e))
                            st.error(f"בדיקת תשובת הפרספקטיבה נכשלה: {e}")
                            if st.button("נסה שוב", key=f"retry_pe_{st.session_state.question_index}"):
                                st.rerun()
                            st.stop()

                        feedback = (
                            "נכון! " + result["explanation"]
                            if result["match"]
                            else "לא בדיוק. " + result["explanation"]
                        )
                        with st.chat_message("assistant"):
                            st.write(feedback)
                        st.session_state.transcript.append({"role": "assistant", "text": feedback})
                        sent = furhat_client.say(feedback)
                        if not sent["sent"]:
                            interaction_log.log_technical("robot", 0, error=sent["reason"])
                            st.warning(f"הרובוט לא הגיב: {sent['reason']}")

                        interaction_log.log_turn(
                            st.session_state.session_id,
                            {
                                "timestamp": time.time(),
                                "turn": st.session_state.question_index,
                                "question_category": q["category"],
                                "triggers_pe": True,
                                "stage": "pe",
                                "pe_answer": pe_answer,
                                "pe_match": result["match"],
                                "pe_explanation": result["explanation"],
                                "model": {
                                    "provider": config.LLM_PROVIDER,
                                    "model": config.MODEL_DEFAULT,
                                },
                            },
                        )

                        st.session_state.pending_pe = None
                        st.session_state.question_index += 1
                        st.rerun()

elif PAGE == "היסטוריה":
    st.title("היסטוריה")
    st.info("בבנייה — ראו Task 12.")
