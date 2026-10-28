# Live Interaction Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A human can sit in front of the (virtual, then physical) Furhat
robot, answer interview questions by voice in Hebrew, and have the robot
react with voice + face on PE-eligible questions — all operated from one
Streamlit app, with every turn logged.

**Architecture:** Python (`conversation_engine`) stays the orchestrator —
picks questions, runs STT/evaluation/classification, decides what to say.
The Furhat skill (`furhat-emotion-study`) stays a thin executor, reached
over the existing local-only HTTP bridge (`RemoteControl.kt`), extended
with two endpoints. No change to how `EmotionsLibrary.kt` builds gestures.

**Tech Stack:** Python 3.10+, Streamlit (`st.audio_input`, `st.chat_message`,
`st.line_chart`), `google-cloud-speech`, existing `llm_client.py`/
`evaluator.py`/`emotion_classifier.py`/`guardrail.py`. Kotlin/Furhat SDK
(`furhat-commons:2.9.3`, already a dependency) for the skill side.

**Spec:** `docs/superpowers/specs/2026-10-28-live-interaction-demo-design.md`

## Global Constraints

- No-Masking: nothing added here scores or trains delivery style — only
  content and perspective-taking correctness. If a new piece of logic
  ever touches tone/eye-contact/posture language, that is a bug.
- PE cycle (robot reaction + perspective-taking question) fires only on
  `behavioral_pbdi`/`self_reflection` questions (`session_flow.py`).
  Every other category gets evaluated + a plain acknowledgement.
- Session identification is a session code, never a participant name —
  this applies to every log record, filename, and UI label.
- A disconnected/slow robot, STT failure, or LLM failure must never
  silently skip a turn — always a visible error + explicit fallback/retry,
  never a silent no-op (this governs every error-handling step below).
- TDD throughout for anything that isn't a live-hardware/UI check: write
  the failing test first, watch it fail for the right reason, then
  implement.

---

### Task 1: Remove dead `EmotionType` enum entries (Kotlin)

**Files:**
- Modify: `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/main/kotlin/furhatos/app/emotionskill/gestures/EmotionsLibrary.kt:73-76`

**Interfaces:**
- Consumes: nothing new.
- Produces: `EmotionType` enum with only the 11 entries `getEmotion()`
  actually handles — later tasks that reference `EmotionType` rely on it
  having no dead entries.

The enum currently is:

```kotlin
    enum class EmotionType {
        HAPPINESS, PRIDE, TENSION, RAGE, FEAR, SADNESS, SURPRISE, DISGUST, CONTEMPT, // base set
        EXCITED, BORED, SLEEPY, CALM // circumplex quadrant fill
    }
```

`PRIDE`, `TENSION`, `RAGE` have no branch in `getEmotion()` — calling
`getEmotion(EmotionType.PRIDE, n)` throws `IllegalArgumentException`
today. They are unused anywhere else in the codebase (confirmed via
`grep -rn "PRIDE\|TENSION\|RAGE" src/`).

- [ ] **Step 1: Confirm nothing else references these three**

Run: `grep -rn "PRIDE\|TENSION\|RAGE" /Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/`
Expected: only the enum declaration line itself.

- [ ] **Step 2: Remove the three dead entries**

```kotlin
    enum class EmotionType {
        HAPPINESS, FEAR, SADNESS, SURPRISE, DISGUST, CONTEMPT, // base set
        EXCITED, BORED, SLEEPY, CALM // circumplex quadrant fill
    }
```

- [ ] **Step 3: Rebuild to confirm nothing else breaks**

Run (from `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study`):
```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 11 2>/dev/null)
./gradlew compileKotlin
```
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 4: Run the existing JUnit suite**

Run: `./gradlew test` (same `JAVA_HOME` as above)
Expected: all existing tests still pass (this change touches no logic
the tests exercise, just removes unused enum constants).

- [ ] **Step 5: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/furhat-emotion-study
git add src/main/kotlin/furhatos/app/emotionskill/gestures/EmotionsLibrary.kt
git commit -m "Remove dead PRIDE/TENSION/RAGE EmotionType entries

Unreachable since getEmotion() never had branches for them -- calling
with any of the three threw IllegalArgumentException. Unused anywhere
else in the codebase."
```

---

### Task 2: Add `/say` and `/health` endpoints to the robot bridge (Kotlin)

**Files:**
- Create: `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/main/kotlin/furhatos/app/emotionskill/remote/SayEvent.kt`
- Modify: `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/main/kotlin/furhatos/app/emotionskill/remote/RemoteControl.kt`
- Modify: `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/main/kotlin/furhatos/app/emotionskill/flow/parent.kt`
- Test: `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/test/kotlin/RemoteControlSmokeTest.kt` (extend)

**Interfaces:**
- Consumes: `furhatos.flow.kotlin.Furhat.say()`, `furhatos.event.Event`
  (same base class `ReactionEvent` already extends).
- Produces: `SayEvent(val text: String) : Event()`. HTTP contract Task 5
  (`furhat_client.py`) relies on:
  - `POST /say` body `{"text": "..."}` -> `200 OK` body `"OK"`, or `400`
    if `text` is missing/blank.
  - `GET /health` -> `200 OK` body `"OK"`, always, with **no** side
    effect on the robot's face or speech (the Settings page calls this
    on every page load).

No automated test framework reaches a live Furhat connection (confirmed
in this repo's existing convention — `OBSSmokeTest.kt`,
`RemoteControlSmokeTest.kt` are manual, run via their own Gradle
`JavaExec` task against a running skill). This task follows the same
pattern: extend the smoke test file, verify by hand against a running
skill, same as `/react` already is.

- [ ] **Step 1: Add `SayEvent`**

```kotlin
package furhatos.app.emotionskill.remote

import furhatos.event.Event

// Carries spoken-only text (no gesture) from RemoteControl's HTTP
// handler into the running Flow's event queue -- same reason
// ReactionEvent exists: `furhat` only resolves inside the Flow DSL,
// not on the HTTP handler's own thread.
class SayEvent(val text: String) : Event()
```

- [ ] **Step 2: Add the `onEvent<SayEvent>` handler in `parent.kt`**

Add alongside the existing `onEvent<ReactionEvent>` block in
`/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/main/kotlin/furhatos/app/emotionskill/flow/parent.kt`:

```kotlin
    // Picked up from RemoteControl's HTTP handler via Flow.addEvent() --
    // plain speech, no gesture change (e.g. warm_up/motivation_fit/
    // closing questions, which never trigger a robot reaction).
    onEvent<SayEvent> {
        furhat.setVoice(Language.HEBREW, Gender.FEMALE)
        furhat.say(it.text)
    }
```

Add the import at the top of `parent.kt`:
```kotlin
import furhatos.app.emotionskill.remote.SayEvent
```

- [ ] **Step 3: Extend `RemoteControl.kt` with the two new endpoints**

Replace the `start()` method and add two new handler classes:

```kotlin
    fun start() {
        val s = HttpServer.create(InetSocketAddress("localhost", port), 0)
        s.createContext("/react", ReactHandler(flow))
        s.createContext("/say", SayHandler(flow))
        s.createContext("/health", HealthHandler())
        s.executor = null // default executor is fine for one-at-a-time local requests
        s.start()
        server = s
        println("[RemoteControl] Listening on http://localhost:$port/react")
        println("[RemoteControl] Listening on http://localhost:$port/say")
        println("[RemoteControl] Listening on http://localhost:$port/health")
    }
```

```kotlin
private class SayHandler(private val flow: Flow) : HttpHandler {
    override fun handle(exchange: HttpExchange) {
        if (exchange.requestMethod != "POST") {
            exchange.sendResponseHeaders(405, -1)
            exchange.close()
            return
        }

        val body = exchange.requestBody.readBytes().toString(Charsets.UTF_8)
        val text = extractStringField(body, "text")

        if (text.isNullOrBlank()) {
            println("[RemoteControl] Bad /say request body: $body")
            val msg = "Expected {\"text\": \"...\"}".toByteArray()
            exchange.sendResponseHeaders(400, msg.size.toLong())
            exchange.responseBody.write(msg)
            exchange.close()
            return
        }

        flow.addEvent(SayEvent(text))
        println("[RemoteControl] Queued speech-only: $text")

        val msg = "OK".toByteArray()
        exchange.sendResponseHeaders(200, msg.size.toLong())
        exchange.responseBody.write(msg)
        exchange.close()
    }
}

// No Flow access needed -- deliberately does not touch the robot's face
// or speech, so the Settings page can poll this on every load without
// making the robot flinch.
private class HealthHandler : HttpHandler {
    override fun handle(exchange: HttpExchange) {
        val msg = "OK".toByteArray()
        exchange.sendResponseHeaders(200, msg.size.toLong())
        exchange.responseBody.write(msg)
        exchange.close()
    }
}
```

- [ ] **Step 4: Rebuild**

```bash
cd /Users/yuvalzohar/Documents/GitHub/furhat-emotion-study
export JAVA_HOME=$(/usr/libexec/java_home -v 11 2>/dev/null)
./rebuild.sh
```
Expected: `BUILD SUCCESSFUL`, skill path copied to clipboard.

- [ ] **Step 5: Extend the smoke test with the two new calls**

Add to `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/test/kotlin/RemoteControlSmokeTest.kt`
(after the existing `/react` smoke calls — read the file first to match
its exact existing structure/imports before appending):

```kotlin
    // /health -- must return 200 without touching the robot's face
    val health = java.net.URI("http://localhost:8765/health").toURL()
        .openConnection() as java.net.HttpURLConnection
    health.requestMethod = "GET"
    println("[SmokeTest] GET /health -> ${health.responseCode}")

    // /say -- speech only, no gesture
    val sayBody = """{"text": "זהו משפט בדיקה בלי רגש"}""".toByteArray(Charsets.UTF_8)
    val say = java.net.URI("http://localhost:8765/say").toURL()
        .openConnection() as java.net.HttpURLConnection
    say.requestMethod = "POST"
    say.doOutput = true
    say.setRequestProperty("Content-Type", "application/json; charset=utf-8")
    say.outputStream.write(sayBody)
    println("[SmokeTest] POST /say -> ${say.responseCode}")
```

- [ ] **Step 6: Manual verification against a running skill**

Load the freshly-built `.skill` file (path already on clipboard from
Step 4) via the Furhat dashboard, start it, confirm the log shows all
three `[RemoteControl] Listening...` lines, then run:

```bash
curl -sS -X POST http://localhost:8765/say -H "Content-Type: application/json" -d '{"text":"בדיקה"}' -w "\n%{http_code}\n"
curl -sS http://localhost:8765/health -w "\n%{http_code}\n"
```
Expected: `200` for both; the robot speaks "בדיקה" with no face change
for the first call; nothing visible happens for the second.

- [ ] **Step 7: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/furhat-emotion-study
git add src/main/kotlin/furhatos/app/emotionskill/remote/SayEvent.kt \
        src/main/kotlin/furhatos/app/emotionskill/remote/RemoteControl.kt \
        src/main/kotlin/furhatos/app/emotionskill/flow/parent.kt \
        src/test/kotlin/RemoteControlSmokeTest.kt
git commit -m "Add /say and /health endpoints to the robot bridge

/say: speech with no gesture change, for questions that don't trigger
a reaction (warm_up/motivation_fit/closing). /health: side-effect-free
liveness check for the Settings page's 'test connection' button --
deliberately does not touch the robot's face."
```

---

### Task 3: New `LiveSession` state, fix `Idle` wiring (Kotlin)

**Files:**
- Create: `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/main/kotlin/furhatos/app/emotionskill/flow/main/LiveSession.kt`
- Modify: `/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study/src/main/kotlin/furhatos/app/emotionskill/flow/main/idle.kt`

**Interfaces:**
- Consumes: `furhatos.flow.kotlin.State`, `NeutralReset()` (from
  `furhatos.app.emotionskill.gestures`, already used elsewhere).
- Produces: `LiveSession: State` — nothing else references it except
  `idle.kt`.

`idle.kt` currently sends every user straight into `Test_AU` (an old
AU-preview test state, unrelated to this flow):

```kotlin
    onUserEnter {
        furhat.attend(it)
        goto(Test_AU)
    }
```

All real interaction logic lives in Python and arrives over the HTTP
bridge regardless of which Flow state is active (confirmed empirically
2026-10-01: `/react` worked while the skill was sitting in `Greeting`).
`LiveSession` only needs to hold a neutral, attentive face and otherwise
do nothing.

- [ ] **Step 1: Create `LiveSession.kt`**

```kotlin
package furhatos.app.emotionskill.flow.main

import furhatos.app.emotionskill.flow.Parent
import furhatos.app.emotionskill.gestures.NeutralReset
import furhatos.flow.kotlin.State
import furhatos.flow.kotlin.furhat
import furhatos.flow.kotlin.state

// Idle state for the Python-orchestrated live interaction demo. All
// real behavior (say/react) arrives via RemoteControl's HTTP bridge --
// this state deliberately does nothing beyond holding a neutral,
// attentive face, since the bridge works regardless of which Flow
// state is active.
val LiveSession: State = state(Parent) {
    onEntry {
        furhat.gesture(NeutralReset(), async = false)
        furhat.setVisibility(true, 0)
    }
}
```

- [ ] **Step 2: Point `idle.kt` at it instead of `Test_AU`**

```kotlin
    onUserEnter {
        furhat.attend(it)
        goto(LiveSession)
    }
```

- [ ] **Step 3: Rebuild**

```bash
cd /Users/yuvalzohar/Documents/GitHub/furhat-emotion-study
export JAVA_HOME=$(/usr/libexec/java_home -v 11 2>/dev/null)
./gradlew compileKotlin
```
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 4: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/furhat-emotion-study
git add src/main/kotlin/furhatos/app/emotionskill/flow/main/LiveSession.kt \
        src/main/kotlin/furhatos/app/emotionskill/flow/main/idle.kt
git commit -m "Add LiveSession state, fix Idle -> Test_AU wiring

Idle previously sent every user into the old AU-preview test state.
LiveSession holds a neutral face and does nothing else -- all real
behavior for the live-interaction demo arrives over RemoteControl's
HTTP bridge regardless of Flow state."
```

---

### Task 4: `session_flow.py` — which questions trigger PE (Python)

**Files:**
- Create: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/session_flow.py`
- Test: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/tests/test_session_flow.py`

**Interfaces:**
- Consumes: nothing (pure function, no imports beyond stdlib).
- Produces: `triggers_pe(category: str) -> bool`, used by Task 11
  (live session view) to decide whether a turn gets a reaction + PE
  question or a plain acknowledgement.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_session_flow.py
import session_flow


def test_behavioral_question_triggers_pe():
    assert session_flow.triggers_pe("behavioral_pbdi") is True


def test_self_reflection_question_triggers_pe():
    assert session_flow.triggers_pe("self_reflection") is True


def test_warm_up_question_does_not_trigger_pe():
    assert session_flow.triggers_pe("warm_up") is False


def test_motivation_fit_question_does_not_trigger_pe():
    assert session_flow.triggers_pe("motivation_fit") is False


def test_closing_question_does_not_trigger_pe():
    assert session_flow.triggers_pe("closing") is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_session_flow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'session_flow'`

- [ ] **Step 3: Implement**

```python
"""
session_flow.py -- decides which questions get the full robot-reaction +
perspective-taking cycle, vs. a plain evaluated acknowledgement.

Per the 2026-10-28 design spec: only "central/significant" questions
(behavioral_pbdi, self_reflection) trigger a reaction + PE question --
not every turn. Decided from question_bank_seed.json's existing
`category` field, no new data needed.
"""

PE_CATEGORIES = {"behavioral_pbdi", "self_reflection"}


def triggers_pe(category: str) -> bool:
    return category in PE_CATEGORIES
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_session_flow.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add session_flow.py tests/test_session_flow.py
git commit -m "Add session_flow.triggers_pe() -- which questions get PE

behavioral_pbdi/self_reflection trigger a robot reaction + PE question;
everything else gets a plain acknowledgement, per the 2026-10-28 spec."
```

---

### Task 5: `furhat_client.py` — HTTP client for the robot bridge (Python)

**Files:**
- Create: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/furhat_client.py`
- Test: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/tests/test_furhat_client.py`
- Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/config.py` (add `ROBOT_BRIDGE_BASE_URL`)

**Interfaces:**
- Consumes: `config.ROBOT_BRIDGE_BASE_URL`, `requests` (already a
  transitive dependency via `robot_bridge.py`'s existing use).
- Produces: `say(text: str) -> dict`, `react(emotion: str, intensity: int,
  text: str = None) -> dict` (both returning `{"sent": bool, "reason":
  str | None}`), `health_check() -> bool`. Task 10 (Settings view) and
  Task 11 (Live session view) call these directly.

Unlike `robot_bridge.py` (gated behind `config.ROBOT_REACTION_ENABLED`,
used by the synthetic-persona pipeline where a robot is usually absent),
this app's whole purpose is talking to a real/virtual robot, so
`furhat_client.py` always attempts the call — gating it behind the same
off-by-default flag would make the live-interaction app unusable by
default. It still never raises on a dead robot (same "never let a
disconnected robot break the pipeline" rule).

- [ ] **Step 1: Add the base URL to `config.py`**

Add near the existing robot-bridge settings:

```python
ROBOT_BRIDGE_BASE_URL = "http://localhost:8765"
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_furhat_client.py
import furhat_client


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_say_sends_text_and_reports_sent(monkeypatch):
    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeResponse(200)

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    result = furhat_client.say("שלום")

    assert result == {"sent": True, "reason": None}
    assert captured["url"].endswith("/say")
    assert "שלום" in captured["data"].decode("utf-8")


def test_react_sends_emotion_intensity_and_optional_text(monkeypatch):
    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeResponse(200)

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    result = furhat_client.react("HAPPINESS", 2, text="טוב")

    assert result == {"sent": True, "reason": None}
    assert captured["url"].endswith("/react")
    assert "HAPPINESS" in captured["data"].decode("utf-8")


def test_say_never_raises_on_connection_failure(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None):
        raise ConnectionError("robot unreachable")

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    result = furhat_client.say("שלום")

    assert result["sent"] is False
    assert "unreachable" in result["reason"]


def test_health_check_true_on_200(monkeypatch):
    monkeypatch.setattr(furhat_client.requests, "get", lambda url, timeout=None: _FakeResponse(200))
    assert furhat_client.health_check() is True


def test_health_check_false_on_connection_failure(monkeypatch):
    def fake_get(url, timeout=None):
        raise ConnectionError("robot unreachable")

    monkeypatch.setattr(furhat_client.requests, "get", fake_get)
    assert furhat_client.health_check() is False
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_furhat_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'furhat_client'`

- [ ] **Step 4: Implement**

```python
"""
furhat_client.py -- HTTP client for furhat-emotion-study's RemoteControl
bridge, for the live interaction demo (interaction_app.py).

Unlike robot_bridge.py (gated behind config.ROBOT_REACTION_ENABLED, used
by the synthetic-persona pipeline), this module always attempts the
call -- the live-interaction app's whole purpose is talking to a real/
virtual robot. Never raises: a disconnected robot must never break a
live session, it just means the turn continues without a robot reaction
(interaction_app.py surfaces that to the operator).
"""

import json

import requests

import config

TIMEOUT = 2.0  # seconds -- same budget robot_bridge.py uses


def say(text: str) -> dict:
    return _post("/say", {"text": text})


def react(emotion: str, intensity: int, text: str = None) -> dict:
    payload = {"emotion": emotion, "intensity": intensity}
    if text:
        payload["text"] = text
    return _post("/react", payload)


def health_check() -> bool:
    try:
        resp = requests.get(f"{config.ROBOT_BRIDGE_BASE_URL}/health", timeout=TIMEOUT)
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False


def _post(path: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        resp = requests.post(
            f"{config.ROBOT_BRIDGE_BASE_URL}{path}",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return {"sent": True, "reason": None}
    except requests.exceptions.RequestException as e:
        return {"sent": False, "reason": str(e)}
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/test_furhat_client.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add furhat_client.py tests/test_furhat_client.py config.py
git commit -m "Add furhat_client.py: HTTP client for the live-demo robot bridge

say()/react()/health_check(), always-on (unlike robot_bridge.py's
opt-in gate) since this app's purpose is talking to a real/virtual
robot. Never raises on a disconnected robot."
```

---

### Task 6: `stt.py` — Google Speech-to-Text wrapper (Python)

**Files:**
- Create: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/stt.py`
- Test: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/tests/test_stt.py`
- Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/requirements.txt` (add `google-cloud-speech`)

**Interfaces:**
- Consumes: `google.cloud.speech` (`SpeechClient`, `RecognitionConfig`,
  `RecognitionAudio`).
- Produces: `transcribe(audio_bytes: bytes, language_code: str = "he-IL")
  -> str`, raising `SttError` on any failure. Task 11 (live session view)
  calls this on the bytes from `st.audio_input`, and falls back to a
  manual text box on `SttError`.

`st.audio_input` returns a `UploadedFile`-like object whose `.getvalue()`
is WAV-encoded audio — `transcribe()` takes raw bytes so it stays testable
without a Streamlit object in the test.

- [ ] **Step 1: Add the dependency**

```
google-cloud-speech
```
(append to `requirements.txt`)

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_stt.py
import pytest

import stt


class _FakeAlternative:
    def __init__(self, transcript):
        self.transcript = transcript


class _FakeResult:
    def __init__(self, transcript):
        self.alternatives = [_FakeAlternative(transcript)]


class _FakeResponse:
    def __init__(self, transcript):
        self.results = [_FakeResult(transcript)] if transcript else []


class _FakeClient:
    def __init__(self, transcript):
        self._transcript = transcript

    def recognize(self, config, audio):
        return _FakeResponse(self._transcript)


def test_transcribe_returns_the_transcript(monkeypatch):
    monkeypatch.setattr(stt, "_get_client", lambda: _FakeClient("שלום עולם"))

    result = stt.transcribe(b"fake-wav-bytes")

    assert result == "שלום עולם"


def test_transcribe_raises_sttError_on_empty_result(monkeypatch):
    monkeypatch.setattr(stt, "_get_client", lambda: _FakeClient(None))

    with pytest.raises(stt.SttError):
        stt.transcribe(b"fake-wav-bytes")


def test_transcribe_raises_sttError_on_client_exception(monkeypatch):
    class _BrokenClient:
        def recognize(self, config, audio):
            raise RuntimeError("quota exceeded")

    monkeypatch.setattr(stt, "_get_client", lambda: _BrokenClient())

    with pytest.raises(stt.SttError):
        stt.transcribe(b"fake-wav-bytes")
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_stt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stt'`

- [ ] **Step 4: Implement**

```python
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
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/test_stt.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add stt.py tests/test_stt.py requirements.txt
git commit -m "Add stt.py: Google Cloud Speech-to-Text wrapper (he-IL)

transcribe() raises a typed SttError on any failure (empty result or
client exception) rather than returning empty/garbage text -- the UI
falls back to a manual text box on this error."
```

---

### Task 7: `pe_check.py` — grade the PE answer against ground truth (Python)

**Files:**
- Create: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/pe_check.py`
- Test: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/tests/test_pe_check.py`

**Interfaces:**
- Consumes: `llm_client.call_llm()`.
- Produces: `check_pe_answer(ground_truth_emotion: str, pe_answer_text:
  str) -> dict`, returning `{"match": bool, "explanation": str}`. Task 11
  calls this after transcribing the participant's PE answer.

One LLM call, same fail-closed shape as `emotion_classifier.py`. Judges
whether the *emotion concept* was named/described correctly — never how
it was said (No-Masking applies here too, even though this isn't the
interview-answer evaluator).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pe_check.py
import json

import pe_check


def test_match_true_when_llm_confirms(monkeypatch):
    def fake_call_llm(system, user_message, max_tokens=150, temperature=0.3, model=None):
        return json.dumps({"match": True, "explanation": "Correctly named anger."})

    monkeypatch.setattr(pe_check.llm_client, "call_llm", fake_call_llm)

    result = pe_check.check_pe_answer("ANGER", "נראה לי שהיית כועס")

    assert result == {"match": True, "explanation": "Correctly named anger."}


def test_match_false_when_llm_denies(monkeypatch):
    def fake_call_llm(system, user_message, max_tokens=150, temperature=0.3, model=None):
        return json.dumps({"match": False, "explanation": "Participant said happy, ground truth was anger."})

    monkeypatch.setattr(pe_check.llm_client, "call_llm", fake_call_llm)

    result = pe_check.check_pe_answer("ANGER", "חשבתי שהיית שמח")

    assert result["match"] is False


def test_fails_closed_on_malformed_response(monkeypatch):
    def fake_call_llm(system, user_message, max_tokens=150, temperature=0.3, model=None):
        return "not json"

    monkeypatch.setattr(pe_check.llm_client, "call_llm", fake_call_llm)

    result = pe_check.check_pe_answer("ANGER", "לא יודעת")

    assert result["match"] is False
    assert result["explanation"]
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_pe_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pe_check'`

- [ ] **Step 3: Implement**

```python
"""
pe_check.py -- grades a participant's perspective-taking (PE) answer
("what did I feel? why?") against the ground-truth emotion the system
itself picked (emotion_classifier.classify_emotion()'s output for that
turn).

One LLM call, same fail-closed shape as emotion_classifier.py. Judges
whether the emotion CONCEPT was correctly named/described -- content,
not delivery -- the No-Masking framing applies here too even though
this isn't the interview-answer evaluator.
"""

import json
import re

import llm_client

_FALLBACK = {"match": False, "explanation": "Could not parse a judgment from the model."}

_SYSTEM_PROMPT = (
    "You are checking whether a participant correctly identified a robot "
    "interviewer's emotional reaction, in a perspective-taking exercise.\n\n"
    "You will be given the GROUND TRUTH emotion the robot actually "
    "displayed, and the participant's free-text answer to \"what do you "
    "think I felt, and why?\". Judge ONLY whether the participant's answer "
    "correctly names or clearly describes the ground-truth emotion concept "
    "-- synonyms and informal phrasing count as correct (e.g. 'annoyed' "
    "for ANGER). Do NOT judge their reasoning quality, wording, or how "
    "they expressed it -- only whether the emotion they named matches.\n\n"
    "Respond with ONLY a JSON object of the exact shape: "
    '{"match": <true or false>, "explanation": "<one sentence, in the '
    'same language as the participant\'s answer>"}'
)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def check_pe_answer(ground_truth_emotion: str, pe_answer_text: str) -> dict:
    user_message = (
        f"Ground truth emotion: {ground_truth_emotion}\n\n"
        f"Participant's answer: {pe_answer_text}"
    )

    raw = llm_client.call_llm(
        system=_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=150,
        temperature=0.3,
    )
    raw = _strip_fences(raw)

    try:
        data = json.loads(raw)
        return {"match": bool(data["match"]), "explanation": str(data["explanation"])}
    except (json.JSONDecodeError, KeyError, TypeError):
        return dict(_FALLBACK)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_pe_check.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add pe_check.py tests/test_pe_check.py
git commit -m "Add pe_check.py: grade PE answers against ground truth

One LLM call, fail-closed (unparseable response -> match=False),
judges only whether the emotion concept was named correctly -- not
delivery, per No-Masking."
```

---

### Task 8: `interaction_log.py` — per-session JSONL logging (Python)

**Files:**
- Create: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/interaction_log.py`
- Test: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/tests/test_interaction_log.py`
- Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/config.py` (add `SESSIONS_DIR`, `TECHNICAL_LOG_PATH`)
- Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/.gitignore` (add `data/sessions/`, `data/technical_log.jsonl`)

**Interfaces:**
- Consumes: `config.SESSIONS_DIR`, `config.TECHNICAL_LOG_PATH`.
- Produces: `log_turn(session_id: str, record: dict) -> None`,
  `log_technical(component: str, elapsed_ms: float, error: str = None)
  -> None`, `list_sessions() -> list[dict]`, `load_session(session_id:
  str) -> list[dict]`. Task 11 calls `log_turn`/`log_technical`; Task 12
  (History view) calls `list_sessions`/`load_session`.

- [ ] **Step 1: Add paths to `config.py`**

```python
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
TECHNICAL_LOG_PATH = os.path.join(DATA_DIR, "technical_log.jsonl")
```

- [ ] **Step 2: Add the two new paths to `.gitignore`**

```
data/sessions/
data/technical_log.jsonl
```

- [ ] **Step 3: Write the failing tests**

```python
# tests/test_interaction_log.py
import json
import os

import config
import interaction_log


def test_log_turn_appends_one_jsonl_record(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", str(tmp_path))

    interaction_log.log_turn("S001", {"turn": 1, "question": "שאלה"})
    interaction_log.log_turn("S001", {"turn": 2, "question": "שאלה 2"})

    path = os.path.join(str(tmp_path), "S001.jsonl")
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]

    assert len(lines) == 2
    assert lines[0]["turn"] == 1
    assert lines[1]["turn"] == 2


def test_log_technical_appends_to_shared_log(tmp_path, monkeypatch):
    log_path = str(tmp_path / "technical_log.jsonl")
    monkeypatch.setattr(config, "TECHNICAL_LOG_PATH", log_path)

    interaction_log.log_technical("stt", 1234.5, error="timeout")

    with open(log_path, encoding="utf-8") as f:
        record = json.loads(f.readline())

    assert record["component"] == "stt"
    assert record["elapsed_ms"] == 1234.5
    assert record["error"] == "timeout"


def test_list_sessions_returns_one_entry_per_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", str(tmp_path))
    interaction_log.log_turn("S001", {"turn": 1})
    interaction_log.log_turn("S002", {"turn": 1})

    sessions = interaction_log.list_sessions()

    assert {s["session_id"] for s in sessions} == {"S001", "S002"}
    assert all(s["turn_count"] == 1 for s in sessions)


def test_load_session_returns_all_records_in_order(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", str(tmp_path))
    interaction_log.log_turn("S001", {"turn": 1})
    interaction_log.log_turn("S001", {"turn": 2})

    records = interaction_log.load_session("S001")

    assert [r["turn"] for r in records] == [1, 2]
```

- [ ] **Step 4: Run to verify failure**

Run: `pytest tests/test_interaction_log.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'interaction_log'`

- [ ] **Step 5: Implement**

```python
"""
interaction_log.py -- per-session JSONL logging for the live interaction
demo, plus a shared technical log for errors/timings. Same "log
everything regardless of outcome" convention graph.py's finalize()
already follows -- every turn gets a record, success or failure.

One file per session (data/sessions/<session_id>.jsonl) rather than one
cumulative file, so a researcher can open/export a single session
without filtering a growing shared log.
"""

import glob
import json
import os

import config


def log_turn(session_id: str, record: dict) -> None:
    os.makedirs(config.SESSIONS_DIR, exist_ok=True)
    path = os.path.join(config.SESSIONS_DIR, f"{session_id}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_technical(component: str, elapsed_ms: float, error: str = None) -> None:
    os.makedirs(os.path.dirname(config.TECHNICAL_LOG_PATH), exist_ok=True)
    record = {"component": component, "elapsed_ms": elapsed_ms, "error": error}
    with open(config.TECHNICAL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_sessions() -> list:
    if not os.path.isdir(config.SESSIONS_DIR):
        return []

    sessions = []
    for path in sorted(glob.glob(os.path.join(config.SESSIONS_DIR, "*.jsonl"))):
        session_id = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            turn_count = sum(1 for _ in f)
        sessions.append({"session_id": session_id, "turn_count": turn_count})
    return sessions


def load_session(session_id: str) -> list:
    path = os.path.join(config.SESSIONS_DIR, f"{session_id}.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]
```

- [ ] **Step 6: Run to verify it passes**

Run: `pytest tests/test_interaction_log.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add interaction_log.py tests/test_interaction_log.py config.py .gitignore
git commit -m "Add interaction_log.py: per-session JSONL + technical log

One file per session (data/sessions/<id>.jsonl) plus a shared
technical_log.jsonl for errors/timings, mirroring graph.py's
finalize()'s 'log everything regardless of outcome' convention."
```

---

### Task 9: API key plumbing — `.env.example`, Google credentials, config checks

**Files:**
- Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/.env.example`
- Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/.gitignore`
- Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `config.GOOGLE_APPLICATION_CREDENTIALS` (path string, may be
  empty), used by Task 10 (Settings view) to report configured/not.

- [ ] **Step 1: Update `.env.example`**

```
# Copy this file to .env and fill in your real values, OR export directly in your shell.
# NEVER commit the real .env or any credentials file to GitHub.

# LLM provider -- "openai" or "lab" (default)
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key_here
LAB_LLM_TOKEN=your_lab_token_here

# Google Cloud Speech-to-Text -- path to a service account JSON file.
# Keep the actual file OUTSIDE this repo, or under credentials/ (gitignored).
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json

# Opt-in: send emotion reactions from the synthetic-persona pipeline
# (run_demo.py / ab_test.py / demo_app.py) to a running Furhat skill.
# The live interaction demo (interaction_app.py) always attempts this,
# regardless of this flag.
ROBOT_REACTION_ENABLED=false
```

- [ ] **Step 2: Add a credentials directory + its gitignore entry**

```bash
mkdir -p /Users/yuvalzohar/Documents/GitHub/conversation_engine/credentials
```

Add to `.gitignore`:
```
credentials/
```

- [ ] **Step 3: Add the config constant**

```python
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
```

- [ ] **Step 4: Verify `.env` itself is still gitignored (already should be)**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && git check-ignore -v .env credentials/anything.json`
Expected: both lines print a matching `.gitignore` rule.

- [ ] **Step 5: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add .env.example .gitignore config.py
git commit -m "Document Google STT credentials + add credentials/ dir

.env.example now lists every key the live demo needs. Service-account
JSON goes under credentials/ (gitignored), referenced via
GOOGLE_APPLICATION_CREDENTIALS."
```

---

### Task 10: Streamlit app shell + Settings view

**Files:**
- Create: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/interaction_app.py`

**Interfaces:**
- Consumes: `furhat_client.health_check()`, `config` (for configured/not
  checks).
- Produces: the `st.sidebar` navigation structure (`"Live session"` /
  `"History"` / `"Settings"`) Tasks 11-12 add their views into — this
  task creates the file and the Settings view; Tasks 11/12 append.

Not unit-testable (Streamlit UI) — verified by running it (Task 14).

- [ ] **Step 1: Create the app shell with Settings view**

```python
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
```

- [ ] **Step 2: Manual check — Settings view renders and the health check works**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
source venv/bin/activate
streamlit run interaction_app.py
```
Open the browser, click "הגדרות", confirm the key statuses render
without crashing (expected `❌ לא מוגדר` for anything not yet set in
`.env`), and click "בדוק חיבור לרובוט" both with and without the Furhat
skill running — confirm it reports success/failure correctly in each
case.

- [ ] **Step 3: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add interaction_app.py
git commit -m "Add interaction_app.py shell + Settings view

Sidebar navigation (Live session / History / Settings). Settings shows
masked configured/not-configured status per key and a robot
'test connection' button using furhat_client.health_check()."
```

---

### Task 11: Live session view — the main turn loop

**Files:**
- Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/interaction_app.py`

**Interfaces:**
- Consumes: `session_flow.triggers_pe`, `furhat_client.say`/`react`,
  `stt.transcribe`/`SttError`, `pe_check.check_pe_answer`,
  `interaction_log.log_turn`/`log_technical`, `evaluator.evaluate`,
  `guardrail.check_rationale`/`check_consistency`,
  `emotion_classifier.classify_emotion`/`derive_valence`/
  `derive_arousal`, `question_bank.QuestionBank`.
- Produces: nothing new for later tasks (this is the main view; Task 12
  is independent).

This is the biggest task — the full per-turn orchestration. Session
state (`st.session_state`) holds: `session_id`, `session_number`,
`question_index`, `transcript` (list of chat messages), `va_history`
(list of `(valence_numeric, arousal_numeric)` for the chart), `paused`,
`stopped`.

- [ ] **Step 1: Replace the "שיחה חיה" placeholder block**

```python
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

    if st.session_state.session_id is None:
        with st.form("start_session"):
            session_code = st.text_input("קוד משתתף (לא שם!)")
            session_number = st.selectbox("מפגש", options=[1, 2, 3, 4, 5])
            provider = st.selectbox("ספק מודל", options=["openai", "lab", "mock"])
            model_name = st.text_input("שם מודל (ריק = ברירת מחדל)")
            started = st.form_submit_button("🟢 התחל שיחה", type="primary")

        if started:
            if not session_code.strip():
                st.error("צריך קוד משתתף כדי להתחיל.")
            else:
                os.environ["LLM_PROVIDER"] = provider
                st.session_state.session_id = session_code.strip()
                st.session_state.session_number = session_number
                st.session_state.model_override = model_name.strip() or None
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
            st.session_state.question_index = max(0, st.session_state.question_index)
        if col_b.button("⏭️ דלג"):
            st.session_state.question_index += 1
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
                with st.chat_message("assistant"):
                    st.write(q["text"])
                st.session_state.transcript.append({"role": "assistant", "text": q["text"]})

                audio = st.audio_input("ענה/י בקול")
                manual_text = st.text_input("או הקלד/י תשובה (גיבוי אם התמלול נכשל)")

                if audio is not None or manual_text:
                    start = time.time()
                    if manual_text:
                        answer_text = manual_text
                        stt_corrected = True
                    else:
                        try:
                            answer_text = stt_module.transcribe(audio.getvalue())
                            stt_corrected = False
                        except stt_module.SttError as e:
                            interaction_log.log_technical("stt", (time.time() - start) * 1000, error=str(e))
                            st.error(f"תמלול נכשל: {e}. אפשר להקליד למטה.")
                            answer_text = None
                            stt_corrected = None

                    if answer_text:
                        st.session_state.transcript.append({"role": "user", "text": answer_text})

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
                                "provider": os.environ.get("LLM_PROVIDER", "lab"),
                                "model": st.session_state.model_override or config.MODEL_DEFAULT,
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
                            furhat_client.say("תודה על התשובה.")

                        interaction_log.log_turn(st.session_state.session_id, record)
                        st.rerun()

            else:
                # ── PE question turn (only reached when triggers_pe was True) ──
                pe_question = "מה לדעתך הרגשתי? למה?"
                with st.chat_message("assistant"):
                    st.write(pe_question)

                pe_audio = st.audio_input("ענה/י בקול (שאלת פרספקטיבה)")
                pe_manual_text = st.text_input("או הקלד/י תשובה", key="pe_manual")

                if pe_audio is not None or pe_manual_text:
                    if pe_manual_text:
                        pe_answer = pe_manual_text
                    else:
                        try:
                            pe_answer = stt_module.transcribe(pe_audio.getvalue())
                        except stt_module.SttError as e:
                            st.error(f"תמלול נכשל: {e}. אפשר להקליד למטה.")
                            pe_answer = None

                    if pe_answer:
                        st.session_state.transcript.append({"role": "user", "text": pe_answer})

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
                        furhat_client.say(feedback)

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
                            },
                        )

                        st.session_state.pending_pe = None
                        st.session_state.question_index += 1
                        st.rerun()
```

- [ ] **Step 2: Manual end-to-end check against Virtual Furhat**

With the skill running (Tasks 1-3 built and loaded):
```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
source venv/bin/activate
export LLM_PROVIDER=openai
streamlit run interaction_app.py
```
Start a session, answer a `warm_up` question by voice — confirm the
robot speaks an acknowledgement with **no** face change and no PE
question follows. Answer a `behavioral_pbdi` question — confirm the
robot reacts (face + voice) and then asks the PE question; answer that
by voice; confirm feedback is spoken and the VA chart gained a point.
Confirm `data/sessions/<code>.jsonl` has one record per stage.

- [ ] **Step 3: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add interaction_app.py
git commit -m "Add live session view: full turn loop with PE cycle

Interview question -> voice answer -> evaluate -> (PE-eligible
questions only) robot reaction -> PE question -> voice answer -> graded
feedback. Logs every turn via interaction_log.log_turn()."
```

---

### Task 12: History view

**Files:**
- Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/interaction_app.py`

**Interfaces:**
- Consumes: `interaction_log.list_sessions`/`load_session`.
- Produces: nothing for later tasks.

- [ ] **Step 1: Replace the "היסטוריה" placeholder block**

```python
elif PAGE == "היסטוריה":
    st.title("היסטוריה")

    import csv
    import io

    import interaction_log

    sessions = interaction_log.list_sessions()
    if not sessions:
        st.info("אין עדיין שיחות שמורות.")
    else:
        labels = [f"{s['session_id']} ({s['turn_count']} תורות)" for s in sessions]
        chosen = st.selectbox("בחר/י שיחה", options=range(len(sessions)), format_func=lambda i: labels[i])
        session_id = sessions[chosen]["session_id"]
        records = interaction_log.load_session(session_id)

        for r in records:
            if "question" in r:
                with st.chat_message("assistant"):
                    st.write(r["question"])
            if "transcript" in r:
                with st.chat_message("user"):
                    st.write(r["transcript"])
            if r.get("stage") == "pe":
                with st.chat_message("user"):
                    st.write(r.get("pe_answer", ""))
                with st.chat_message("assistant"):
                    st.write(r.get("pe_explanation", ""))

        buf = io.StringIO()
        if records:
            writer = csv.DictWriter(buf, fieldnames=sorted({k for r in records for k in r}))
            writer.writeheader()
            for r in records:
                writer.writerow(r)
        st.download_button(
            "ייצוא ל-CSV", data=buf.getvalue(), file_name=f"{session_id}.csv", mime="text/csv"
        )
```

- [ ] **Step 2: Manual check**

Run a session (Task 11), then open "היסטוריה", confirm it lists the
session, replays the transcript, and the CSV download produces a valid
file with every logged field as a column.

- [ ] **Step 3: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add interaction_app.py
git commit -m "Add History view: browse past sessions, export CSV"
```

---

### Task 13: One-command launch + Hebrew README

**Files:**
- Create: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/run.sh`
- Create/Modify: `/Users/yuvalzohar/Documents/GitHub/conversation_engine/README.md`

**Interfaces:**
- Consumes: everything built in Tasks 1-12.
- Produces: nothing (terminal task for the Python side).

Mirrors the pattern already proven 2026-10-01
(`הפעלת הדגמת הרובוט.command`): automate everything automatable, make
the one unavoidable Furhat-GUI step unmissable.

- [ ] **Step 1: Write `run.sh`**

```bash
#!/bin/bash
set -e

FURHAT_DIR="/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study"
CE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== 1/3  בונה את סקיל הרובוט ==="
cd "$FURHAT_DIR"
export JAVA_HOME=$(/usr/libexec/java_home -v 11 2>/dev/null)
./rebuild.sh

echo ""
echo "=== 2/3  בדשבורד של Furhat: טעני את הסקיל (הנתיב ב-clipboard), לחצי Start Skill ==="
echo "    המתיני לשורות:"
echo "    [RemoteControl] Listening on http://localhost:8765/react"
echo "    [RemoteControl] Listening on http://localhost:8765/say"
echo "    [RemoteControl] Listening on http://localhost:8765/health"
read -p "לחצי Enter כשהרובוט מוכן... "

echo ""
echo "=== 3/3  מפעילה את ממשק השיחה ==="
cd "$CE_DIR"
source venv/bin/activate
export LLM_PROVIDER=openai
streamlit run interaction_app.py
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x /Users/yuvalzohar/Documents/GitHub/conversation_engine/run.sh
```

- [ ] **Step 3: Write the Hebrew README section**

Append to `README.md` (create it if it doesn't exist yet — check first):

```markdown
## הדגמת שיחה חיה עם הרובוט

### התקנה (פעם אחת)
\`\`\`bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
\`\`\`
ואז למלא ב-\`.env\`: \`OPENAI_API_KEY\`, ונתיב קובץ ה-service-account של
Google ב-\`GOOGLE_APPLICATION_CREDENTIALS\` (שימי את הקובץ עצמו תחת
\`credentials/\`, שלא עולה ל-git).

### הפעלה
\`\`\`bash
./run.sh
\`\`\`
הסקריפט בונה את הסקיל, מחכה שתטעני ותריצי אותו בדשבורד של Furhat (צעד
ידני — אין דרך לעשות את זה דרך שורת פקודה), ואז פותח את ממשק השיחה.

### מבנה הממשק
- **שיחה חיה** — מתחילים כאן: קוד משתתף + מספר מפגש + בחירת מודל, כפתור
  ירוק להתחלה. שאלות "מרכזיות" (behavioral/self-reflection) מקבלות
  תגובה רגשית מהרובוט ואז שאלת פרספקטיבה; שאר השאלות — רק אישור.
- **היסטוריה** — כל השיחות השמורות, עם ייצוא ל-CSV.
- **הגדרות** — סטטוס מפתחות (בלי לחשוף ערכים) + בדיקת חיבור לרובוט.
```

- [ ] **Step 4: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
chmod +x run.sh
git add run.sh README.md
git commit -m "Add run.sh one-command launcher + Hebrew README section"
```

---

### Task 14: Full end-to-end verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full automated suite**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
source venv/bin/activate
pytest tests/ -v
```
Expected: every test passes, including all new ones from Tasks 4-9.

- [ ] **Step 2: Run `./run.sh` from a clean shell and complete one full session**

Cover, in one real run against Virtual Furhat:
- A `warm_up` question (plain ack, no reaction, no PE).
- A `behavioral_pbdi` question (reaction + PE question + graded
  feedback, both correct and incorrect PE answers if time allows).
- STT fallback: deliberately submit via the manual text box at least
  once.
- Pause, then resume, mid-session.
- Stop, then confirm the session appears correctly in History with a
  working CSV export.
- Settings page's "test connection" button, both with the skill running
  and after stopping it.

- [ ] **Step 3: Report results**

Note in the session log (`SESSION_LOG.md`, conversation_engine): what
ran clean, anything that needed a follow-up fix, and the exact state of
`data/sessions/` afterward (row/turn counts) — same reporting convention
established throughout this project's `SESSION_LOG.md` entries.
