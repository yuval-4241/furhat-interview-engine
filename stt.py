"""
stt.py -- Google Cloud Speech-to-Text wrapper for the live interaction
demo. Takes raw audio bytes (from st.audio_input's WAV output), returns
the transcript. Never returns an empty/garbage transcript silently --
any failure is a typed SttError, so the caller (interaction_app.py)
can fall back to a manual text box, per the spec's stated STT fallback.

Uses the plain REST API with an API key (not the google-cloud-speech
client library's service-account auth) -- the project's Google Cloud
org disables service-account key creation (iam.disableServiceAccountKeyCreation),
so an API key via GOOGLE_SPEECH_API_KEY is the only auth path available.
"""

import base64

import requests

import config

_RECOGNIZE_URL = "https://speech.googleapis.com/v1/speech:recognize"


class SttError(Exception):
    pass


def transcribe(audio_bytes: bytes, language_code: str = "he-IL") -> str:
    payload = {
        "config": {
            "encoding": "LINEAR16",
            "languageCode": language_code,
        },
        "audio": {
            "content": base64.b64encode(audio_bytes).decode("ascii"),
        },
    }

    url = f"{_RECOGNIZE_URL}?key={config.GOOGLE_SPEECH_API_KEY}"

    try:
        response = requests.post(url, json=payload, timeout=30)
    except requests.exceptions.RequestException as e:
        raise SttError(f"Speech-to-Text request failed: {e}") from e

    if response.status_code >= 400:
        raise SttError(f"Speech-to-Text request failed: HTTP {response.status_code}")

    results = response.json().get("results")
    if not results:
        raise SttError("No speech detected in the recording.")

    return results[0]["alternatives"][0]["transcript"]
