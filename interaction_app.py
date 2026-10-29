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
    st.info("בבנייה — ראו Task 11.")

elif PAGE == "היסטוריה":
    st.title("היסטוריה")
    st.info("בבנייה — ראו Task 12.")
