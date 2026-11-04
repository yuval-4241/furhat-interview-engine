# Robot Foundations (Plan 1 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the engine everything the autonomous conversation needs from
the robot side, and a model choice that flows from the website:

- a separate `interview-skill` that can speak, react, **listen**, and switch
  **character (face) and voice**;
- a feasibility check of Hebrew listening;
- an LLM model registry whose models appear on the website automatically.

**Architecture:**

- `furhat-emotion-study` becomes a multi-module Gradle build. A shared
  `emotion-library` module holds the calibrated faces. The calibration
  `EmotionSkill` stays the root project. A new `interview-skill` module owns
  the HTTP bridge (`/say`, `/react`, `/listen`, `/persona`, `/health`).
- On the Python side, `furhat_client.py` gains `listen()` and
  `set_persona()`.
- `config.LLM_MODELS` becomes the single place to add models. The worker
  syncs it to Base44's `LLMModel` entity at startup and runs each session on
  the model the researcher picked.

**Plan 2** (written after Task 3's feasibility gate) covers
`conversation_flow.py`, the new prompts, the PE judge, and the new Base44
status flow.

**Tech Stack:** Kotlin 1.8 + Furhat SDK `furhat-commons:2.9.3` + Gradle
(shadowJar), Java 11 for builds. Python 3.10+, `requests`, `openai`
(OpenAI-compatible client), `pytest`, Base44 REST API.

**Spec:** `docs/superpowers/specs/2026-11-04-autonomous-robot-conversation-design.md`.
Additions requested on 2026-11-04 after spec approval (recorded in Task 7):

- per-session robot face and voice from the website `Persona`;
- an LLM model registry synced to the website.

## Global Constraints

- Never use 70B+ models. Every model in `LLM_MODELS` must be smaller (CLAUDE.md).
- Never hardcode or commit keys. Every key is read with
  `os.environ.get(..., "")` and lives only in `.env`.
- Methodology-locked content is untouched: `NO_MASKING_FLAG_PATTERNS`,
  `PERSONAS`, `EVALUATOR_SYSTEM_PROMPT_A`/`_B`.
- Listening parameters: `endSil = 3000` ms, `maxSpeech = 120000` ms,
  `timeout = 10000` ms (spec decision 3).
- Bridge port `8765` on `localhost`. `furhat_client` never raises: a dead
  robot must not break a session.
- `base44_client` raises (`Base44Error` / `RateLimited`). The worker keeps
  list requests near 30/min (shared 70/min Base44 budget).
- Furhat `.skill` files must stay under the launcher's 30 MB limit.
- `EmotionSkill` (the calibration study) must keep behaving exactly as before,
  except that it no longer hosts the bridge.

## Review Focus

- **`/listen` called while the robot is already speaking or listening.**
  Expected: the new call waits its turn in the flow queue and still returns
  a result. It must never hang forever. Pinned by the HTTP-side timeout in
  Task 2 and `test_listen_timeout_returns_failed` in Task 4.
- **Persona voice name that doesn't exist on this Furhat** (typo on the
  website). Expected: the robot keeps its previous voice, the bridge returns
  an error string, and the session continues. Pinned in Task 2 (try/catch)
  and `test_set_persona_bridge_error_is_reported` in Task 4.
- **Session whose `llm_model` points to a model with no key set.**
  Expected: fall back to `MODEL_DEFAULT` with a log line, not a crash
  mid-turn. Pinned by `test_model_for_session_falls_back_when_key_missing`
  in Task 6.
- **A model removed from `LLM_MODELS`, or its key deleted.** Expected: its
  `LLMModel` record is set `active = false` on the next startup, not
  deleted, because old sessions still reference it. Pinned by
  `test_sync_deactivates_models_without_key` in Task 6.
- **Hebrew text with commas, quotes, or newlines** in `/say` and `/persona`.
  Expected: it reaches the robot intact (raw UTF-8, quote-aware parser).
  Pinned by `test_set_persona_sends_raw_utf8` in Task 4.

---

## File Structure

**`furhat-emotion-study` (Kotlin):**

- `settings.gradle`: modify. Include `emotion-library` and `interview-skill`.
- `emotion-library/build.gradle`: create. Kotlin library, depends on `furhat-commons`.
- `emotion-library/src/main/kotlin/furhatos/app/emotionskill/gestures/EmotionsLibrary.kt`
  and `Interpolation.kt`: moved with `git mv`. **Package unchanged**, so no
  imports change.
- `build.gradle` (root, `EmotionSkill`): modify. Add
  `implementation project(':emotion-library')`.
- `src/main/kotlin/.../remote/*`: moved to `interview-skill`.
- `src/main/kotlin/.../flow/parent.kt`: modify. Drop the `ReactionEvent` and
  `SayEvent` handlers, since `EmotionSkill` no longer has a bridge.
- `src/main/kotlin/.../main.kt`: modify. Drop `RemoteControl(flow).start()`.
- `interview-skill/build.gradle`, `interview-skill/skill.properties`: create.
- `interview-skill/src/main/kotlin/furhatos/app/interviewskill/`:
  - `InterviewSkill.kt`: skill entrypoint, starts the bridge.
  - `flow/Init.kt`: goes straight to `LiveSession`, no `isVirtual()`.
  - `flow/LiveSession.kt`: all bridge event handlers.
  - `remote/RemoteControl.kt`, `remote/Events.kt`: bridge plus event classes.
- `interview-skill/rebuild.sh`: create.

**`conversation_engine` (Python):**

- `furhat_client.py`: modify. Add `listen()` and `set_persona()`.
- `config.py`: modify. Add `LLM_PROVIDERS`, `LLM_MODELS`, and the listen
  constants.
- `llm_client.py`: modify. Per-provider clients and a `model_override()`
  context manager.
- `model_registry.py`: create. `available_models()`,
  `sync_to_base44()`, `model_for_session()`.
- `engine_worker.py`: modify. Sync models at startup, apply the persona and
  model per session.
- Tests:
  - `tests/test_furhat_client.py`: extend.
  - `tests/test_llm_client.py`: create.
  - `tests/test_model_registry.py`: create.
  - `tests/test_engine_worker.py`: extend.

---

### Task 0: Protect uncommitted work in `furhat-emotion-study`

The Kotlin repo has uncommitted edits (`greeting.kt`, `Photosession.kt`,
`OBSControlle.kt`, `skill.properties`, and the gradle wrapper). Moving
files around them risks losing work.

- [ ] **Step 1: Show the researcher the pending changes**

Run: `cd ../furhat-emotion-study && git status --short | grep -v '^.. .gradle\|build/'`

- [ ] **Step 2: Ask the researcher** whether to commit those edits as-is
  (e.g. "WIP calibration tweaks") or stash them. Do not proceed until she
  answers. Then create the branch:

```bash
cd ../furhat-emotion-study
git checkout -b interview-skill
```

---

### Task 1: Extract `emotion-library` (EmotionSkill unchanged in behaviour)

**Files:**
- Create: `../furhat-emotion-study/emotion-library/build.gradle`
- Move: `src/main/kotlin/furhatos/app/emotionskill/gestures/EmotionsLibrary.kt`
  and `Interpolation.kt` to
  `emotion-library/src/main/kotlin/furhatos/app/emotionskill/gestures/`
- Delete: `src/main/kotlin/furhatos/app/emotionskill/gestures/emotions.kt`
  (0 lines)
- Modify: `settings.gradle`, `build.gradle`

**Interfaces:**
- Produces: `furhatos.app.emotionskill.gestures.EmotionLibrary.getEmotion(type: String, intensity: Int): Gesture`
  and `NeutralReset(): Gesture`, unchanged and now in module `:emotion-library`.

- [ ] **Step 1: Move the files (keeps history)**

```bash
cd ../furhat-emotion-study
mkdir -p emotion-library/src/main/kotlin/furhatos/app/emotionskill/gestures
git mv src/main/kotlin/furhatos/app/emotionskill/gestures/EmotionsLibrary.kt emotion-library/src/main/kotlin/furhatos/app/emotionskill/gestures/
git mv src/main/kotlin/furhatos/app/emotionskill/gestures/Interpolation.kt emotion-library/src/main/kotlin/furhatos/app/emotionskill/gestures/
git rm src/main/kotlin/furhatos/app/emotionskill/gestures/emotions.kt
```

- [ ] **Step 2: Create `emotion-library/build.gradle`**

```groovy
plugins {
    id 'org.jetbrains.kotlin.jvm'
}

sourceCompatibility = 1.8

compileKotlin {
    kotlinOptions {
        jvmTarget = "1.8"
        apiVersion = "1.8"
        languageVersion = "1.8"
    }
}

repositories {
    mavenLocal()
    mavenCentral()
    maven { url "https://s3-eu-west-1.amazonaws.com/furhat-maven/releases" }
}

dependencies {
    implementation 'com.furhatrobotics.furhatos:furhat-commons:2.9.3'
}
```

- [ ] **Step 3: Wire it into the build**

`settings.gradle` becomes:

```groovy
rootProject.name = 'EmotionSkill'
include 'emotion-library'
include 'interview-skill'
```

In the root `build.gradle`, add this line inside the existing `dependencies { ... }` block:

```groovy
    implementation project(':emotion-library')
```

(`interview-skill` is included now so Task 2 doesn't touch settings again.
Create an empty `interview-skill/build.gradle` containing only
`plugins { id 'org.jetbrains.kotlin.jvm' }` so the build configures.)

- [ ] **Step 4: Build EmotionSkill and verify it still compiles and fits the size limit**

Run: `./rebuild.sh && ls -la build/libs/EmotionSkill-all.skill`
Expected: `Build successful!`, file size under 30 MB.

- [ ] **Step 5: Smoke-check calibration behaviour is unchanged.** Load
  `EmotionSkill-all.skill` in the launcher. The emotion preview must play as
  before ("Emotion preview…" … "Preview done").

- [ ] **Step 6: Commit**

```bash
git add settings.gradle build.gradle emotion-library interview-skill/build.gradle
git commit -m "Extract EmotionLibrary into a shared emotion-library module"
```

---

### Task 2: Create `interview-skill` with `/say`, `/react`, `/listen`, `/persona`, `/health`

**Files:**
- Move: `src/main/kotlin/furhatos/app/emotionskill/remote/{RemoteControl,ReactionEvent,SayEvent}.kt`
  to `interview-skill`, rewritten into `remote/RemoteControl.kt` + `remote/Events.kt`
- Modify (EmotionSkill): `src/main/kotlin/furhatos/app/emotionskill/main.kt`, `flow/parent.kt`
- Create: `interview-skill/build.gradle`, `interview-skill/skill.properties`,
  `interview-skill/rebuild.sh`, `InterviewSkill.kt`, `flow/Init.kt`, `flow/LiveSession.kt`
- Test: `interview-skill/src/test/kotlin/ParseTest.kt`

**Interfaces (HTTP, all JSON, UTF-8):**
- `POST /say` `{"text","language"?,"gender"?}` → `200 OK`
- `POST /react` `{"emotion","intensity","text"?,"language"?,"gender"?}` → `200 OK`
- `POST /listen` `{"timeout"?,"endSil"?,"maxSpeech"?}` → `200 {"status":"ok"|"no_speech"|"failed","text":"..."}`.
  This call blocks until the robot finishes listening.
- `POST /persona` `{"character"?,"voice"?,"language"?}` → `200 {"status":"ok"}`
  or `200 {"status":"error","message":"..."}`
- `GET /health` → `200 OK`

- [ ] **Step 1: Remove the bridge from EmotionSkill.** In `main.kt`, delete
  the line `RemoteControl(flow).start()` and its import. In `flow/parent.kt`,
  delete the `onEvent<ReactionEvent> { ... }` and `onEvent<SayEvent> { ... }`
  blocks, the `resolveLanguage`/`resolveGender` helpers, and their imports.
  Then delete the three files under `src/main/kotlin/.../remote/` with `git rm`.

- [ ] **Step 2: Write the failing parser test**
  `interview-skill/src/test/kotlin/ParseTest.kt`:

```kotlin
import furhatos.app.interviewskill.remote.extractIntField
import furhatos.app.interviewskill.remote.extractStringField
import furhatos.app.interviewskill.remote.jsonString
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class ParseTest {
    @Test
    fun `string field keeps commas and escaped quotes`() {
        val body = """{"text": "שלום, מה \"נשמע\"?", "voice": "Asaf"}"""
        assertEquals("שלום, מה \"נשמע\"?", extractStringField(body, "text"))
        assertEquals("Asaf", extractStringField(body, "voice"))
    }

    @Test
    fun `missing int field is null`() {
        assertEquals(null, extractIntField("""{"endSil": 3000}""", "maxSpeech"))
        assertEquals(3000, extractIntField("""{"endSil": 3000}""", "endSil"))
    }

    @Test
    fun `jsonString escapes quotes, backslashes and newlines`() {
        assertEquals("\"a \\\"b\\\" \\\\ c\\nd\"", jsonString("a \"b\" \\ c\nd"))
    }
}
```

- [ ] **Step 3: `interview-skill/build.gradle`.** Copy the root `build.gradle`
  as-is, then make three changes:
  1. Add `implementation project(':emotion-library')` to `dependencies`.
  2. Delete the three `tasks.register(...)` blocks at the end (OBS and smoke
     tests belong to EmotionSkill).
  3. Do **not** change the `shadowJar` excludes.

  ASR runs in the Furhat server, not inside the skill, so the excluded cloud
  SDKs are still unused. Step 8 verifies this.

- [ ] **Step 4: `interview-skill/skill.properties`**

```properties
name = InterviewSkill
mainclass = furhatos.app.interviewskill.InterviewSkill
version = 1.0.0
language = he-IL
logLevel = INFO
requiresVersion = false
requiresCamera = false
requiresSpeaker = true
requiresMicrophone = true
requiresRecognizer = true
```

- [ ] **Step 5: Events and bridge.**

`interview-skill/src/main/kotlin/furhatos/app/interviewskill/remote/Events.kt`:

```kotlin
package furhatos.app.interviewskill.remote

import furhatos.event.Event
import java.util.concurrent.CompletableFuture

// Queued from RemoteControl's HTTP threads via Flow.addEvent(); handled in
// LiveSession, the only place furhat.* calls can run. language/gender are
// null when the caller didn't send them.
class SayEvent(val text: String, val language: String?, val gender: String?) : Event()

class ReactionEvent(
    val emotion: String, val intensity: Int, val text: String?,
    val language: String?, val gender: String?,
) : Event()

data class ListenResult(val status: String, val text: String)

// The HTTP handler blocks on `result` until LiveSession's onResponse /
// onNoResponse / onResponseFailed completes it.
class ListenEvent(
    val timeout: Int, val endSil: Int, val maxSpeech: Int,
    val result: CompletableFuture<ListenResult> = CompletableFuture(),
) : Event()

class PersonaEvent(
    val character: String?, val voice: String?, val language: String?,
    val result: CompletableFuture<String> = CompletableFuture(),
) : Event()
```

`interview-skill/src/main/kotlin/furhatos/app/interviewskill/remote/RemoteControl.kt`:

```kotlin
package furhatos.app.interviewskill.remote

import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpHandler
import com.sun.net.httpserver.HttpServer
import furhatos.flow.kotlin.Flow
import java.net.InetSocketAddress
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

// HTTP bridge for conversation_engine (Python). Hand-rolled JSON field
// extraction, no JSON library — the engine sends raw UTF-8, not \uXXXX
// escapes, so plain regex extraction works for Hebrew.
class RemoteControl(private val flow: Flow, private val port: Int = 8765) {
    fun start() {
        val s = HttpServer.create(InetSocketAddress("localhost", port), 0)
        s.createContext("/say") { ex -> handlePost(ex) { body ->
            val text = extractStringField(body, "text")
            if (text.isNullOrBlank()) 400 to "Expected {\"text\": \"...\"}"
            else {
                flow.addEvent(SayEvent(text, extractStringField(body, "language"), extractStringField(body, "gender")))
                200 to "OK"
            }
        } }
        s.createContext("/react") { ex -> handlePost(ex) { body ->
            val emotion = extractStringField(body, "emotion")
            val intensity = extractIntField(body, "intensity")
            if (emotion == null || intensity == null) 400 to "Expected {\"emotion\": \"ANGER\", \"intensity\": 2}"
            else {
                flow.addEvent(ReactionEvent(emotion, intensity, extractStringField(body, "text"),
                    extractStringField(body, "language"), extractStringField(body, "gender")))
                200 to "OK"
            }
        } }
        s.createContext("/listen") { ex -> handlePost(ex) { body ->
            val event = ListenEvent(
                timeout = extractIntField(body, "timeout") ?: 10000,
                endSil = extractIntField(body, "endSil") ?: 3000,
                maxSpeech = extractIntField(body, "maxSpeech") ?: 120000,
            )
            flow.addEvent(event)
            // Never hang forever: allow the full listen window plus 30 s for queueing.
            val waitMs = event.timeout.toLong() + event.maxSpeech + 30000
            val r = try { event.result.get(waitMs, TimeUnit.MILLISECONDS) }
                    catch (e: Exception) { ListenResult("failed", "") }
            200 to "{\"status\": ${jsonString(r.status)}, \"text\": ${jsonString(r.text)}}"
        } }
        s.createContext("/persona") { ex -> handlePost(ex) { body ->
            val event = PersonaEvent(extractStringField(body, "character"),
                extractStringField(body, "voice"), extractStringField(body, "language"))
            flow.addEvent(event)
            val err = try { event.result.get(15, TimeUnit.SECONDS) } catch (e: Exception) { "timeout" }
            if (err.isEmpty()) 200 to "{\"status\": \"ok\"}"
            else 200 to "{\"status\": \"error\", \"message\": ${jsonString(err)}}"
        } }
        s.createContext("/health") { ex -> respond(ex, 200, "OK") }
        // /listen blocks for up to ~2.5 min, so handlers need their own threads.
        s.executor = Executors.newCachedThreadPool()
        s.start()
        println("[RemoteControl] Listening on http://localhost:$port (/say /react /listen /persona /health)")
    }
}

private fun handlePost(ex: HttpExchange, handler: (String) -> Pair<Int, String>) {
    if (ex.requestMethod != "POST") { ex.sendResponseHeaders(405, -1); ex.close(); return }
    val body = ex.requestBody.readBytes().toString(Charsets.UTF_8)
    val (code, msg) = handler(body)
    respond(ex, code, msg)
}

private fun respond(ex: HttpExchange, code: Int, msg: String) {
    val bytes = msg.toByteArray(Charsets.UTF_8)
    ex.responseHeaders.add("Content-Type", "application/json; charset=utf-8")
    ex.sendResponseHeaders(code, bytes.size.toLong())
    ex.responseBody.write(bytes)
    ex.close()
}

// Captures a JSON string value between quotes, honoring \" and \\ escapes.
fun extractStringField(body: String, field: String): String? {
    val pattern = "\"$field\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"".toRegex()
    val raw = pattern.find(body)?.groupValues?.get(1) ?: return null
    return raw.replace("\\\"", "\"").replace("\\n", "\n").replace("\\\\", "\\")
}

fun extractIntField(body: String, field: String): Int? =
    "\"$field\"\\s*:\\s*(-?\\d+)".toRegex().find(body)?.groupValues?.get(1)?.toIntOrNull()

fun jsonString(s: String): String =
    "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n") + "\""
```

- [ ] **Step 6: Flow and entrypoint.**

`flow/Init.kt`:

```kotlin
package furhatos.app.interviewskill.flow

import furhatos.flow.kotlin.State
import furhatos.flow.kotlin.state

// Straight to LiveSession: no furhat.isVirtual() call. That call crashed
// EmotionSkill with an NPE on 2026-11-04 when the skill started before the
// Furhat server was ready, leaving the bridge accepting requests nobody ran.
val Init: State = state {
    onEntry { goto(LiveSession) }
}
```

`flow/LiveSession.kt`:

```kotlin
package furhatos.app.interviewskill.flow

import furhatos.app.emotionskill.gestures.EmotionLibrary
import furhatos.app.emotionskill.gestures.NeutralReset
import furhatos.app.interviewskill.remote.*
import furhatos.event.actions.ActionConfigFace
import furhatos.flow.kotlin.*
import furhatos.util.Gender
import furhatos.util.Language
import java.util.concurrent.CompletableFuture

// Set by a /persona call. While set, /say and /react do NOT override the
// voice with language+gender, so the researcher's persona voice sticks.
private var personaVoiceSet = false
private var pendingListen: CompletableFuture<ListenResult>? = null

val LiveSession: State = state {
    onEntry {
        furhat.gesture(NeutralReset(), async = false)
    }

    onEvent<PersonaEvent> {
        val errors = mutableListOf<String>()
        it.character?.takeIf { c -> c.isNotBlank() }?.let { c ->
            try { send(ActionConfigFace.Builder().character(c).buildEvent()) }
            catch (e: Exception) { errors.add("character '$c': ${e.message}") }
        }
        it.voice?.takeIf { v -> v.isNotBlank() }?.let { v ->
            try { furhat.setVoice(resolveLanguage(it.language), v); personaVoiceSet = true }
            catch (e: Exception) { errors.add("voice '$v': ${e.message}") }
        }
        it.result.complete(errors.joinToString("; "))
    }

    onEvent<SayEvent> {
        applyFallbackVoice(it.language, it.gender)
        furhat.say(it.text)
    }

    onEvent<ReactionEvent> {
        try {
            furhat.gesture(EmotionLibrary.getEmotion(it.emotion, it.intensity), async = true)
            val text = it.text
            if (!text.isNullOrBlank()) {
                applyFallbackVoice(it.language, it.gender)
                furhat.say(text)
            }
        } catch (e: IllegalArgumentException) {
            println("[RemoteControl] ${e.message}")
        }
    }

    onEvent<ListenEvent> {
        pendingListen = it.result
        furhat.listen(timeout = it.timeout, endSil = it.endSil, maxSpeech = it.maxSpeech)
    }

    onResponse {
        pendingListen?.complete(ListenResult("ok", it.text)); pendingListen = null
    }
    onNoResponse {
        pendingListen?.complete(ListenResult("no_speech", "")); pendingListen = null
    }
    onResponseFailed {
        pendingListen?.complete(ListenResult("failed", "")); pendingListen = null
    }
}

private fun FlowControlRunner.applyFallbackVoice(language: String?, gender: String?) {
    if (personaVoiceSet || language == null) return
    furhat.setVoice(resolveLanguage(language), resolveGender(gender))
}

private fun resolveLanguage(language: String?): Language = when (language?.uppercase()) {
    "ENGLISH", "EN" -> Language.ENGLISH_US
    else -> Language.HEBREW
}

private fun resolveGender(gender: String?): Gender =
    if (gender?.uppercase() == "MALE") Gender.MALE else Gender.FEMALE
```

`InterviewSkill.kt`:

```kotlin
package furhatos.app.interviewskill

import furhatos.app.interviewskill.flow.Init
import furhatos.app.interviewskill.remote.RemoteControl
import furhatos.flow.kotlin.Flow
import furhatos.skills.Skill

class InterviewSkill : Skill() {
    override fun start() {
        val flow = Flow()
        RemoteControl(flow).start()
        flow.run(Init)
    }
}

fun main(args: Array<String>) {
    Skill.main(args)
}
```

Check the existing `main.kt` for how it builds and runs the `Flow`
(`EmotionskillSkill.start()`), and mirror it exactly if it differs from the
code above.

- [ ] **Step 7: Run the parser tests**

Run: `cd ../furhat-emotion-study && ./gradlew :interview-skill:test`
Expected: 3 tests PASS. If a compile error names a Furhat API (e.g. the
`listen` parameter names, `onResponseFailed`, or `setVoice(Language, String)`),
check it against `javap -cp ~/.gradle/caches/.../furhat-commons-2.9.3.jar furhatos.flow.kotlin.Furhat`.
These were verified on 2026-11-04: `listen(timeout, endSil, maxSpeech)` and
`setVoice(Language, String)` both exist.

- [ ] **Step 8: Build both skills**

`interview-skill/rebuild.sh`: copy the root `rebuild.sh`. Set
`SKILL_FILE="$PROJECT_DIR/build/libs/InterviewSkill-all.skill"`, run
`cd "$PROJECT_DIR/.." && ./gradlew :interview-skill:shadowJar`, and change
the echo text to "InterviewSkill".

Run: `./rebuild.sh && interview-skill/rebuild.sh && ls -la build/libs interview-skill/build/libs`
Expected: both `.skill` files exist and each is under 30 MB.

- [ ] **Step 9: Commit**

```bash
git add -A interview-skill src/main/kotlin build.gradle
git commit -m "Add interview-skill with say/react/listen/persona bridge; drop bridge from EmotionSkill"
```

---

### Task 3: Feasibility gate (manual, with the robot)

This is the spike from spec build-step 1. **Plan 2 is written only after
this gate passes.**

- [ ] **Step 1: Load `InterviewSkill-all.skill` in the launcher.** Wait for
  the log line `[RemoteControl] Listening on http://localhost:8765`. Confirm
  there's no `isVirtual` NPE in the skill log.

- [ ] **Step 2: Persona and speech**

```bash
cd ../conversation_engine && source venv/bin/activate
curl -s -X POST localhost:8765/persona -d '{"character": "Isabel", "voice": "Asaf", "language": "he"}'
curl -s -X POST localhost:8765/say -d '{"text": "שלום, אני הרובוט"}'
```

Expected: `{"status": "ok"}`, the face changes to Isabel, and Hebrew speech
is heard in the Asaf voice. Record the result.

- [ ] **Step 3: Hebrew listening, three probes.** Run
  `curl -s -X POST localhost:8765/listen -d '{}'` and, while it waits:
  1. Say a 10 s Hebrew answer with a 2 s pause in the middle. The pause
     must NOT end it. Expect `"status": "ok"` with the whole text.
  2. Say a 40 s answer. This checks for a ~20 s per-utterance cap: is the
     text cut off around 20 s?
  3. Say nothing. Expect `"status": "no_speech"` after about 10 s.

- [ ] **Step 4: Record the results** in
  `docs/superpowers/specs/2026-11-04-autonomous-robot-conversation-design.md`
  under a new heading `## Feasibility results (date)`. Include accuracy
  notes and the cap (yes/no, at how many seconds).

- [ ] **Step 5: Gate decision with the researcher**

  - **All pass:** write Plan 2 as specced.
  - **A cap exists:** in Plan 2, chain listens (Furhat "listening extended"
    pattern) until 3 s of silence.
  - **Hebrew accuracy is poor:** stop, and revisit approach 2 (Python
    `stt.py`).

---

### Task 4: `furhat_client.listen()` and `set_persona()`

**Files:**
- Modify: `furhat_client.py`
- Modify: `config.py`. Add:

```python
LISTEN_TIMEOUT_MS = 10000
LISTEN_END_SIL_MS = 3000
LISTEN_MAX_SPEECH_MS = 120000
```

- Test: `tests/test_furhat_client.py` (extend)

**Interfaces:**
- Produces: `furhat_client.listen() -> dict`, returning
  `{"status": "ok"|"no_speech"|"failed", "text": str}`. It never raises.
- Produces: `furhat_client.set_persona(character: str | None, voice: str | None, language: str | None) -> dict`,
  returning `{"sent": bool, "reason": str | None}`. It never raises.

- [ ] **Step 1: Write failing tests** (append to `tests/test_furhat_client.py`):

```python
import json

import requests

import furhat_client


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_listen_returns_bridge_result(monkeypatch):
    seen = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        seen.update(url=url, body=json.loads(data), timeout=timeout)
        return _Resp({"status": "ok", "text": "שלום"})

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    assert furhat_client.listen() == {"status": "ok", "text": "שלום"}
    assert seen["url"].endswith("/listen")
    assert seen["body"] == {"timeout": 10000, "endSil": 3000, "maxSpeech": 120000}
    assert seen["timeout"] > (10000 + 120000) / 1000  # HTTP wait covers the whole listen window


def test_listen_timeout_returns_failed(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ReadTimeout("slow")

    monkeypatch.setattr(furhat_client.requests, "post", boom)

    assert furhat_client.listen() == {"status": "failed", "text": ""}


def test_set_persona_sends_raw_utf8(monkeypatch):
    seen = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        seen["raw"] = data
        return _Resp({"status": "ok"})

    monkeypatch.setattr(furhat_client.requests, "post", fake_post)

    assert furhat_client.set_persona("Isabel", "Asaf", "he") == {"sent": True, "reason": None}
    assert "Asaf".encode() in seen["raw"] and "\\u" not in seen["raw"].decode("utf-8")


def test_set_persona_bridge_error_is_reported(monkeypatch):
    monkeypatch.setattr(furhat_client.requests, "post",
                        lambda *a, **k: _Resp({"status": "error", "message": "voice 'Asf': not found"}))

    result = furhat_client.set_persona("Isabel", "Asf", "he")

    assert result["sent"] is False and "Asf" in result["reason"]
```

- [ ] **Step 2: Run to verify the tests fail**

Run: `pytest tests/test_furhat_client.py -v`
Expected: the 4 new tests FAIL with `AttributeError: module 'furhat_client' has no attribute 'listen'`.

- [ ] **Step 3: Implement** (add to `furhat_client.py`, below `react`):

```python
def listen() -> dict:
    """Blocks until the robot finishes listening (up to ~2.5 min). Never raises."""
    payload = {
        "timeout": config.LISTEN_TIMEOUT_MS,
        "endSil": config.LISTEN_END_SIL_MS,
        "maxSpeech": config.LISTEN_MAX_SPEECH_MS,
    }
    wait_s = (config.LISTEN_TIMEOUT_MS + config.LISTEN_MAX_SPEECH_MS) / 1000 + 40
    try:
        resp = requests.post(
            f"{config.ROBOT_BRIDGE_BASE_URL}/listen",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=wait_s,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"status": data.get("status", "failed"), "text": data.get("text", "")}
    except (requests.exceptions.RequestException, ConnectionError, ValueError):
        return {"status": "failed", "text": ""}


def set_persona(character: str = None, voice: str = None, language: str = None) -> dict:
    """Switch the robot's face (Furhat character) and voice (Furhat voice name). Never raises."""
    payload = {k: v for k, v in {"character": character, "voice": voice, "language": language}.items() if v}
    try:
        resp = requests.post(
            f"{config.ROBOT_BRIDGE_BASE_URL}/persona",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.exceptions.RequestException, ConnectionError, ValueError) as e:
        return {"sent": False, "reason": str(e)}
    if data.get("status") != "ok":
        return {"sent": False, "reason": data.get("message", "unknown error")}
    return {"sent": True, "reason": None}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_furhat_client.py -v && pytest tests -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add furhat_client.py config.py tests/test_furhat_client.py
git commit -m "Add furhat_client.listen() and set_persona() for interview-skill bridge"
```

---

### Task 5: LLM model registry and per-call model override

This is where new models and keys get added. The researcher asked for this
location to be clearly marked in the code.

**Files:**
- Modify: `config.py`, `llm_client.py`
- Test: `tests/test_llm_client.py` (create)

**Interfaces:**
- Produces: `config.LLM_PROVIDERS: dict[str, dict]`, mapping a provider
  name to `{"base_url": str | None, "api_key_env": str}`.
- Produces: `config.LLM_MODELS: dict[str, dict]`, mapping an `engine_key`
  to `{"provider": str, "display_name": str}`.
- Produces: `llm_client.model_override(engine_key: str)`, a context
  manager. Inside it, `call_llm(model=None)` uses `engine_key` and that
  model's provider.
- Produces: `llm_client.provider_has_key(provider: str) -> bool`.

- [ ] **Step 1: Write failing tests** `tests/test_llm_client.py`:

```python
import llm_client


class _FakeCompletions:
    def __init__(self, sink):
        self.sink = sink

    def create(self, **kwargs):
        self.sink.append(kwargs["model"])

        class R:
            choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]

        return R()


def _install(monkeypatch, calls, providers_seen):
    def fake_client_for(provider):
        providers_seen.append(provider)
        return type("Client", (), {"chat": type("Chat", (), {"completions": _FakeCompletions(calls)})()})()

    monkeypatch.setattr(llm_client, "_client_for", fake_client_for)


def test_override_routes_model_and_provider(monkeypatch):
    calls, providers = [], []
    _install(monkeypatch, calls, providers)
    monkeypatch.setitem(llm_client.config.LLM_MODELS, "test-model", {"provider": "openai", "display_name": "T"})

    with llm_client.model_override("test-model"):
        llm_client.call_llm("sys", "hi")
    llm_client.call_llm("sys", "hi")  # outside: back to default

    assert calls == ["test-model", llm_client.config.MODEL_DEFAULT]
    assert providers[0] == "openai"


def test_explicit_model_beats_override(monkeypatch):
    calls, providers = [], []
    _install(monkeypatch, calls, providers)

    with llm_client.model_override("gpt-4o-mini"):
        llm_client.call_llm("sys", "hi", model="llama3.1-8b")

    assert calls == ["llama3.1-8b"]


def test_provider_has_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.delenv("LAB_LLM_TOKEN", raising=False)
    assert llm_client.provider_has_key("openai") is True
    assert llm_client.provider_has_key("lab") is False
```

- [ ] **Step 2: Run to verify the tests fail**

Run: `pytest tests/test_llm_client.py -v`
Expected: FAIL with `AttributeError: ... '_client_for'` / `'model_override'`.

- [ ] **Step 3: Add the registry to `config.py`**, directly below the
  existing `MODEL = MODEL_DEFAULT` line:

```python
# ════════════════════════════════════════════════════════════════════════════
# ▶▶ ADD NEW LLM MODELS HERE ◀◀
#
# 1. If the model's provider isn't in LLM_PROVIDERS yet, add it (any
#    OpenAI-compatible API: base_url + the env var holding its key).
# 2. Put the key in .env under that env var name (never in this file).
# 3. Add the model to LLM_MODELS: engine_key -> provider + display name.
#    The engine_key is the exact model id the provider expects.
# 4. Restart engine_worker.py: it syncs this list to the website's LLMModel
#    entity, so the model shows up in the New Session dropdown automatically
#    (models whose key is missing are shown as inactive).
# Never add 70B+ models (CLAUDE.md).
# ════════════════════════════════════════════════════════════════════════════
LLM_PROVIDERS = {
    "lab":    {"base_url": LAB_LLM_BASE_URL, "api_key_env": "LAB_LLM_TOKEN"},
    "openai": {"base_url": None,             "api_key_env": "OPENAI_API_KEY"},
    # e.g. "groq": {"base_url": "https://api.groq.com/openai/v1", "api_key_env": "GROQ_API_KEY"},
}

LLM_MODELS = {
    "llama3.1-8b":  {"provider": "lab",    "display_name": "Llama 3.1 8B (fast)"},
    "gpt-oss-20b":  {"provider": "lab",    "display_name": "GPT-OSS 20B (default)"},
    "dictalm3-12b": {"provider": "lab",    "display_name": "DictaLM 3 12B (Hebrew)"},
    "gpt-4o-mini":  {"provider": "openai", "display_name": "GPT-4o mini"},
}
```

- [ ] **Step 4: Implement in `llm_client.py`.** Keep `get_client()` working
  for existing callers, and add:

```python
import contextlib
import contextvars
import os

_clients = {}
_model_override = contextvars.ContextVar("model_override", default=None)


def provider_has_key(provider: str) -> bool:
    return bool(os.environ.get(config.LLM_PROVIDERS[provider]["api_key_env"], ""))


def _client_for(provider: str) -> OpenAI:
    if provider not in _clients:
        p = config.LLM_PROVIDERS[provider]
        kwargs = {"api_key": os.environ.get(p["api_key_env"], "")}
        if p["base_url"]:
            kwargs["base_url"] = p["base_url"]
        _clients[provider] = OpenAI(**kwargs)
    return _clients[provider]


@contextlib.contextmanager
def model_override(engine_key: str):
    """Every call_llm(model=None) inside this block uses engine_key (the session's chosen model)."""
    token = _model_override.set(engine_key)
    try:
        yield
    finally:
        _model_override.reset(token)
```

Change the start of `call_llm` so it picks the model and client like this
(keep the rest of the function as it is):

```python
    model = model or _model_override.get() or config.MODEL_DEFAULT
    entry = config.LLM_MODELS.get(model)
    client = _client_for(entry["provider"]) if entry else get_client()
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_llm_client.py -v && pytest tests -q`
Expected: all PASS. Existing callers are unchanged, because with no
override and no registry hit, `get_client()` is used as before.

- [ ] **Step 6: Commit**

```bash
git add config.py llm_client.py tests/test_llm_client.py
git commit -m "Add LLM model registry and per-session model override"
```

---

### Task 6: Sync models to the website; apply persona and model per session

**Files:**
- Create: `model_registry.py`
- Modify: `engine_worker.py`
- Test: `tests/test_model_registry.py` (create), `tests/test_engine_worker.py` (extend)

**Interfaces:**
- Consumes: `config.LLM_MODELS`, `llm_client.provider_has_key`,
  `llm_client.model_override` (Task 5); `furhat_client.set_persona`
  (Task 4); `base44_client.list_records/create_record/update_record/get_record`.
- Produces: `model_registry.sync_to_base44() -> None`.
- Produces: `model_registry.model_for_session(session: dict) -> str`, the
  engine_key.
- Produces: `engine_worker.apply_persona(session: dict) -> None`, which
  runs at most once per session id.

- [ ] **Step 1: Write failing tests** `tests/test_model_registry.py`
  (reuses the `FakeBase44` from `tests/test_engine_worker.py`):

```python
import pytest

import model_registry
from tests.test_engine_worker import FakeBase44


@pytest.fixture
def fake(monkeypatch):
    store = FakeBase44()
    monkeypatch.setattr(model_registry, "b44", store)
    monkeypatch.setattr(model_registry.config, "LLM_MODELS", {
        "gpt-4o-mini": {"provider": "openai", "display_name": "GPT-4o mini"},
        "llama3.1-8b": {"provider": "lab", "display_name": "Llama 3.1 8B"},
    })
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.delenv("LAB_LLM_TOKEN", raising=False)
    return store


def test_sync_creates_records_with_active_flag(fake):
    model_registry.sync_to_base44()

    rows = {r["engine_key"]: r for r in fake.list_records("LLMModel")}
    assert rows["gpt-4o-mini"]["active"] is True
    assert rows["llama3.1-8b"]["active"] is False
    assert rows["gpt-4o-mini"]["display_name"] == "GPT-4o mini"


def test_sync_deactivates_models_without_key(fake):
    old = fake.add("LLMModel", engine_key="removed-model", display_name="Old", active=True)

    model_registry.sync_to_base44()
    model_registry.sync_to_base44()  # idempotent: no duplicates

    assert fake.get("LLMModel", old["id"])["active"] is False
    assert len(fake.list_records("LLMModel", {"engine_key": "gpt-4o-mini"})) == 1


def test_model_for_session_uses_chosen_model(fake):
    m = fake.add("LLMModel", engine_key="gpt-4o-mini", display_name="GPT-4o mini", active=True)
    assert model_registry.model_for_session({"llm_model": m["id"]}) == "gpt-4o-mini"


def test_model_for_session_falls_back_when_key_missing(fake):
    m = fake.add("LLMModel", engine_key="llama3.1-8b", display_name="Llama", active=False)
    assert model_registry.model_for_session({"llm_model": m["id"]}) == model_registry.config.MODEL_DEFAULT
    assert model_registry.model_for_session({}) == model_registry.config.MODEL_DEFAULT
```

Append to `tests/test_engine_worker.py`:

```python
def test_apply_persona_once_per_session(fake, monkeypatch):
    persona = fake.add("Persona", furhat_face="Isabel", furhat_voice="Asaf")
    session = fake.add("Session", status="Running", mode="Live", language="he", persona=persona["id"])
    calls = []
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda character, voice, language: calls.append((character, voice, language))
                        or {"sent": True, "reason": None})

    engine_worker.apply_persona(session)
    engine_worker.apply_persona(session)

    assert calls == [("Isabel", "Asaf", "he")]


def test_apply_persona_skips_non_live(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Simulation", persona="p1")
    monkeypatch.setattr(engine_worker, "_personas_applied", set())
    monkeypatch.setattr(engine_worker.furhat_client, "set_persona",
                        lambda *a: pytest.fail("no robot in Simulation"))

    engine_worker.apply_persona(session)
```

- [ ] **Step 2: Run to verify the tests fail**

Run: `pytest tests/test_model_registry.py tests/test_engine_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: model_registry` and
`AttributeError: ... 'apply_persona'`.

- [ ] **Step 3: Implement `model_registry.py`**

```python
"""
model_registry.py — keeps the website's LLMModel list in sync with
config.LLM_MODELS (the one place new models are added), and resolves which
model a Session should run on.
"""

import base44_client as b44
import config
import llm_client

_engine_key_cache = {}  # LLMModel id -> engine_key (saves Base44 list budget)


def sync_to_base44() -> None:
    """Upsert every registry model; active = its provider's key is set. Never deletes."""
    existing = {r.get("engine_key"): r for r in b44.list_records("LLMModel", limit=500)}
    for key, entry in config.LLM_MODELS.items():
        fields = {"engine_key": key, "display_name": entry["display_name"],
                  "active": llm_client.provider_has_key(entry["provider"])}
        if key in existing:
            b44.update_record("LLMModel", existing[key]["id"], fields)
        else:
            b44.create_record("LLMModel", fields)
    for key, rec in existing.items():
        if key not in config.LLM_MODELS and rec.get("active"):
            b44.update_record("LLMModel", rec["id"], {"active": False})


def model_for_session(session: dict) -> str:
    model_id = session.get("llm_model")
    if not model_id:
        return config.MODEL_DEFAULT
    if model_id not in _engine_key_cache:
        rec = b44.get_record("LLMModel", model_id)
        _engine_key_cache[model_id] = rec.get("engine_key") if rec.get("active") else None
    key = _engine_key_cache[model_id]
    if key not in config.LLM_MODELS:
        print(f"[model_registry] session model {model_id!r} unavailable — using {config.MODEL_DEFAULT}")
        return config.MODEL_DEFAULT
    return key
```

Note: `FakeBase44.get` (tests) and `b44.get_record` (real client) differ in
name. Add `get_record = get` inside the `FakeBase44` class in
`tests/test_engine_worker.py` so the same fake works for both test files.

- [ ] **Step 4: Wire into `engine_worker.py`**

At the top, add:
```python
import llm_client
import model_registry
```
and next to `_robot_wait_started`:
```python
_personas_applied = set()  # session ids whose face/voice were already sent to the robot
```

Add the function (above `poll_once`):

```python
def apply_persona(session: dict) -> None:
    """Send the session's Persona face + voice to the robot, once per session."""
    if session.get("mode") != "Live" or session["id"] in _personas_applied:
        return
    persona = b44.get_record("Persona", session["persona"]) if session.get("persona") else {}
    result = furhat_client.set_persona(persona.get("furhat_face"), persona.get("furhat_voice"),
                                       session.get("language"))
    if not result["sent"]:
        _log(f"Session {session.get('session_code')}: persona not applied: {result['reason']}")
    _personas_applied.add(session["id"])
```

In `poll_once`, inside `for session in sessions.values():`, before the turns
are listed, add:

```python
        apply_persona(session)
```

and wrap the turn-handling loop body so turns run on the session's model:

```python
        with llm_client.model_override(model_registry.model_for_session(session)):
            for turn in turns:
                ...  # existing body unchanged
```

In `main()`, before the `while True:` loop:

```python
    try:
        model_registry.sync_to_base44()
        _log("LLM models synced to the website")
    except b44.Base44Error as e:
        _log(f"Model sync failed (continuing): {e}")
```

Also change `send_heartbeat` so `active_model` reports what is actually
running. Set it to `config.MODEL_DEFAULT` when idle. (Per-session models are
logged per turn in Plan 2.)

- [ ] **Step 5: Run tests**

Run: `pytest tests -q`
Expected: all PASS.

- [ ] **Step 6: Live check.** Restart the worker with `.env` loaded. On the
  website, the New Session model dropdown lists the registry models, and the
  lab models show as inactive if `LAB_LLM_TOKEN` is unset. Start a Live
  session with a Persona whose face and voice are set. The robot switches
  face and voice within one poll.

- [ ] **Step 7: Commit**

```bash
git add model_registry.py engine_worker.py tests/test_model_registry.py tests/test_engine_worker.py
git commit -m "Sync LLM models to the website and apply session persona + model"
```

---

### Task 7: Docs

**Files:** `CLAUDE.md`,
`docs/superpowers/specs/2026-11-04-autonomous-robot-conversation-design.md`,
`SESSION_LOG.md`, `../furhat-emotion-study/README.md`

- [ ] **Step 1: Spec.** Add decisions 14 and 15 to the decisions table:
  - **14:** per-session face and voice come from the website `Persona`
    (`furhat_face` = Furhat character name, `furhat_voice` = Furhat voice
    name), applied through `/persona`. Once set, `/say` and `/react` no
    longer override the voice.
  - **15:** `config.LLM_MODELS` is the single model registry, synced to
    `LLMModel` at worker startup.

- [ ] **Step 2: CLAUDE.md.**
  - Add `model_registry.py` and `interview-skill` to the architecture list.
  - Add a "To add a model: see the ▶▶ ADD NEW LLM MODELS HERE ◀◀ block in
    `config.py`" line to Commands.
  - Update the test count.

- [ ] **Step 3: furhat-emotion-study README.** Add a "Two skills" section:
  - `EmotionSkill`: calibration study, built with `./rebuild.sh`.
  - `InterviewSkill`: experiment bridge, built with
    `interview-skill/rebuild.sh`. Load this one for experiments.

- [ ] **Step 4: SESSION_LOG entry** with the feasibility results and a
  RESUME FROM HERE that says "write Plan 2".

- [ ] **Step 5: Commit both repos**

```bash
git add CLAUDE.md SESSION_LOG.md docs/superpowers/specs/2026-11-04-autonomous-robot-conversation-design.md
git commit -m "Document interview-skill, persona voices and model registry"
cd ../furhat-emotion-study && git add README.md && git commit -m "Document EmotionSkill vs InterviewSkill"
```
