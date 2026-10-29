"""
stt.py -- Google Cloud Speech-to-Text wrapper for the live interaction
demo. Takes raw audio bytes (from st.audio_input's WAV output), returns
the transcript. Never returns an empty/garbage transcript silently --
any failure is a typed SttError, so the caller (interaction_app.py)
can fall back to a manual text box, per the spec's stated STT fallback.
"""

from google.cloud import speech


class SttError(Exception):
    pass


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = speech.SpeechClient()
    return _client


def transcribe(audio_bytes: bytes, language_code: str = "he-IL") -> str:
    client = _get_client()
    recognition_config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        language_code=language_code,
    )
    audio = speech.RecognitionAudio(content=audio_bytes)

    try:
        response = client.recognize(config=recognition_config, audio=audio)
    except Exception as e:
        raise SttError(f"Speech-to-Text request failed: {e}") from e

    if not response.results:
        raise SttError("No speech detected in the recording.")

    return response.results[0].alternatives[0].transcript
