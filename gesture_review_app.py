"""
gesture_review_app.py -- the researcher reviews the LLM-generated listening
gestures on the robot: play each one, keep or drop it, and leave a note.
Decisions are saved as you go (data/listening_gestures_review.json); the kept
gestures are written for the skill, which uses them after a rebuild.

    streamlit run gesture_review_app.py

Needs the InterviewSkill running (it plays gestures via /gesture).
"""

import json

import streamlit as st

import furhat_client
import listening_gestures as lg

st.set_page_config(page_title="Listening gestures review", layout="wide")
st.title("Listening gestures review")

try:
    with open(lg.CANDIDATES_PATH, encoding="utf-8") as f:
        candidates = json.load(f)
except FileNotFoundError:
    st.error("No candidates yet. Run: python listening_gestures.py generate --n 40")
    st.stop()

if "decisions" not in st.session_state:
    st.session_state.decisions = lg.load_review()
decisions = st.session_state.decisions

if not furhat_client.health_check():
    st.warning("The robot skill isn't reachable on localhost:8765 - start InterviewSkill to play gestures.")

kept = sum(1 for d in decisions.values() if d.get("decision") == "keep")
dropped = sum(1 for d in decisions.values() if d.get("decision") == "drop")
st.write(f"{len(candidates)} gestures · kept {kept} · dropped {dropped} · "
         f"left {len(candidates) - kept - dropped}")

categories = sorted({g["category"] for g in candidates})
show = st.multiselect("Categories", categories, default=categories)

CHOICES = {"": "—", "keep": "keep", "drop": "drop"}

for g in candidates:
    if g["category"] not in show:
        continue
    d = decisions.setdefault(g["name"], {"decision": "", "note": ""})
    with st.container(border=True):
        left, right = st.columns([3, 2])
        with left:
            st.markdown(f"**{g['name']}** · `{g['category']}` · {g['reset']}s")
            st.write(g["description"])
            st.caption(" → ".join(", ".join(f"{k} {v}" for k, v in f["params"].items()) for f in g["frames"]))
        with right:
            if st.button("▶ play on robot", key=f"play-{g['name']}"):
                result = furhat_client.play_gesture(g)
                if not result["sent"]:
                    st.error(f"not sent: {result['reason']}")
            d["decision"] = st.radio("decision", list(CHOICES), index=list(CHOICES).index(d["decision"]),
                                     format_func=CHOICES.get, horizontal=True, key=f"dec-{g['name']}",
                                     label_visibility="collapsed")
            d["note"] = st.text_input("note", d["note"], key=f"note-{g['name']}",
                                      placeholder="what's good / what's not", label_visibility="collapsed")

lg.save_review(candidates, decisions)
st.success(f"Saved. {kept} kept gestures are ready for the skill - rebuild it to use them.")
