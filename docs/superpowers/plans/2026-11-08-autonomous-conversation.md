# Autonomous Robot Conversation (Plan 2 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In `Live` sessions the robot runs the whole interview itself: small
talk, questions, listening, content-only acknowledgements, and, for PBDI
questions, an emotional reaction, the PE question, the PE grade and the
feedback. The researcher only clicks Approve on the two emotional moments.

**Architecture:**

- A new `conversation_flow.py` owns the Live turn state machine. It is
  separate from `engine_worker.py`'s polling loop, so it can be tested with
  a fake website and a fake robot.
- `engine_worker.py` hands every `Live` session to `conversation_flow`.
  `Simulation` and `Mock` keep today's typed-answer flow.
- Three new line generators (`small_talk.py`, `acknowledgement.py`,
  `pe_feedback.py`) share one helper (`llm_line.py`). Each has one retry and
  a fixed fallback line, and none of them ever raises.
- `pe_check.py` grades `Correct` / `Partial` / `Wrong` using Hebrew word
  lists built on Shaver et al. (1987).
- The heartbeat moves to its own thread, because `/listen` blocks the main
  loop for up to about 2.5 minutes.
- Hebrew lines follow the participant's gender, from a new website field
  `Participant.gender`. The question bank's slash forms ("ספר/י") are
  resolved before the robot says them.
- The Base44 website gets the new statuses and fields from a prompt the
  researcher pastes (Task 1).

**Tech Stack:** Python 3.10+, `requests`, `openai` (OpenAI-compatible client
via `llm_client.py`), `pytest`. Base44 REST API. Kotlin 1.8 + Furhat SDK
2.9.3 (Gradle, Java 11), for one bridge fix only.

**Spec:** `docs/superpowers/specs/2026-11-04-autonomous-robot-conversation-design.md`.
That includes its "Feasibility results (2026-11-08)": the gate passed, there
is no ~20 s ASR cap, so no listen chaining is needed, and a 3 s `endSil`
does not cut off a 2 s pause.

Also read: `docs/superpowers/specs/2026-11-02-base44-lab-app-integration-design.md`
(the website contract and Turn fields).

## Global Constraints

- Methodology-locked content: `PERSONAS` (`prompts/persona_prompts.py`) and
  `EVALUATOR_SYSTEM_PROMPT_A`/`_B` stay untouched. The one approved change
  is Task 4's Hebrew additions to `config.NO_MASKING_FLAG_PATTERNS`
  (decision P3). Existing entries are never edited or removed. The
  evaluator, the emotion classifier, the guardrail's code and the response
  bank are unchanged.
- No-Masking: every generated line refers to answer **content**. It never
  comments on delivery (tone, confidence, eye contact, structure, length,
  directness) and never grades quality ("great answer").
- Approval (spec decision 2): before every emotional reaction and every PE
  feedback line. None for small talk or non-PBDI acknowledgements.
- PBDI means `Turn.category == "Behavioral (PBDI)"` exactly (spec decision 4).
- Fixed lines from the spec, verbatim:
  - PE question: `"מה לדעתך הרגשתי, ולמה?"`
  - Not heard: `"סליחה, לא שמעתי. אפשר לחזור?"`
  - Acknowledgement fallback: `"תודה, נמשיך."`
- Listening (spec decision 3, already in `config.py`): `LISTEN_TIMEOUT_MS = 10000`,
  `LISTEN_END_SIL_MS = 3000`, `LISTEN_MAX_SPEECH_MS = 120000`. One `/listen`
  call per answer.
- Error handling (spec table):
  - Empty or failed ASR: say "not heard" and listen once more, then `skipped`
    with `skip_reason = "no_recognition"`.
  - Silence: repeat the question once, then `skipped` with `skip_reason = "no_answer"`.
  - LLM failure: one retry. Small talk and acknowledgements fall back to a
    fixed line. PBDI steps set `engine_error` and wait for the researcher's
    Retry.
  - Robot down: wait up to `config.ROBOT_WAIT_SECONDS` (60 s), then set
    `engine_error = "robot disconnected"`.
- The Engine never writes `Session.status`, `final_reply`, `final_feedback`
  or `edited_by_researcher`.
- `furhat_client` never raises. `base44_client` raises `Base44Error` /
  `RateLimited`. The worker keeps list requests near 30/min.
- Use `config.MODEL_FAST` for any real-LLM run while building. Never use 70B+
  models. Never commit `.env` or any key.
- `interview-skill` changes: stop the skill in the Furhat launcher **before**
  rebuilding. Rebuilding a running `.skill` crashes the JVM (`SIGBUS`). The
  `.skill` must stay under 31,457,280 bytes.

## Decisions this plan makes (the researcher reviews them with the plan)

| # | Decision | Why | Cost if wrong |
|---|---|---|---|
| P1 | The robot's "why" in the PE feedback is written by the feedback LLM call, from the question and the participant's answer (the researcher's choice, 2026-11-08). The same call returns the reason separately; it is stored in `pe_answer_why` at grading time (Live only). The emotion classifier is unchanged. | The researcher prefers a fluent reason. | The reason is written after the fact, so it may not be what actually triggered the classifier's choice. The prompt points the reason at answer content only, the guardrail checks it, and the researcher approves every line. |
| P2 | Hebrew gender follows the participant (the researcher's choice, 2026-11-08). New website field `Participant.gender` (`Male`/`Female`). Generated lines use the matching form. The question bank's slash forms (`ספר/י`, `מתמודד/ת`) are resolved before the robot says them. When the gender is empty, generated lines avoid gendered forms, and slash forms use the first (masculine) form. The robot speaks about itself in its voice's gender (`config.VOICE_GENDERS`: AvriNeural = male, Hila voices = female). | The participant should be addressed correctly, and a spoken "ספר/י" sounds broken. | The slash-form rule (Task 7) is rule-based, so an unusual form may come out wrong (e.g. "את/ה", written feminine-first). The researcher hears it in the live check. |
| P3 | Hebrew phrases are added to `config.NO_MASKING_FLAG_PATTERNS` (the researcher's choice, 2026-11-08). **The exact list is in Task 4, and the researcher approves the words with this plan.** Every generated spoken line (small talk, acknowledgement, feedback) is checked, and a flagged line falls back to a fixed line. | Without Hebrew patterns, the guardrail barely checks Hebrew lines. | A methodology-locked list changes. The phrases never match the evaluator's English rationale, so `graph.py` routing is unaffected. |
| P12 | The participant's first name (new optional website field `Participant.first_name`) is used **only in small talk** (the researcher's choice, 2026-11-08). With a name, the robot doesn't ask for it. | A personal opening and closing, while interview questions, acknowledgements and feedback stay identical in form for every participant. | A first name is identifying data. **The researcher checks that the ethics approval allows storing it in Base44.** |
| P4 | `Live` = autonomous. The old typed-answer `Live` path (researcher types, then `robot_reacting` → RobotCommand → `awaiting_pe`) is removed. `Simulation` keeps the typed flow. | There must be one Live behaviour. | Testing without hardware happens in `Simulation`, as the spec says. |
| P5 | Retry = the website clears `engine_error`. The Engine then re-runs the turn's current status, so every status handler is safe to run twice. | One uniform rule for LLM failures and robot failures. | A Retry during `listening` makes the robot listen again (no re-ask). If the participant stays silent, the silence rule re-asks the question. |
| P6 | Silence or bad ASR on the PE question → `skipped`, with `skip_reason = "pe_no_answer"` / `"pe_no_recognition"` (confirmed by the researcher, 2026-11-08). The reaction already given stays logged. | The spec covers answers but not the PE question. | That turn has no PE data. |
| P7 | In `Live`, a turn in `awaiting_answer` is treated like `queued`. | The website creates turns as `awaiting_answer` until the Task 1 prompt is pasted, so the flow works either way. | None. |
| P8 | The heartbeat runs on its own thread. | `/listen` blocks the loop for up to about 2.5 min, and the website shows "Engine unavailable" after 60 s without a heartbeat. | One extra thread. Its Base44 errors are logged, not backed off. |
| P9 | After a turn finishes, the worker starts the next turn right away, but first re-reads `Session.status` and stops if the session is no longer `Running`. | Avoids a 6 s gap between questions, and Pause still works between turns. | One `get_record` per finished turn. |
| P10 | A new Turn field `engine_model` records the model each LLM step used. | Deferred from Plan 1: a fallback to the default model mid-session is otherwise invisible. | One more website field (Task 1). |
| P11 | The PE word lists in Task 5 are a **draft for the researcher's review** (spec, "New prompts" 4). | No Hebrew emotion-lexicon study was found. | Grades depend on these lists. Review them before any participant session. |

Out of scope (recorded in the spec's feasibility results, left for later):

- ASR sometimes gluing two words together.
- Server-side validation of face and voice names. The website uses closed
  dropdowns instead.
- English Live sessions: the fixed lines and the response bank are Hebrew.
- Gendered words outside slash forms in the question bank (for example "לך"
  without vowels): the TTS picks one reading.
- A PE confidence rating.

## Review Focus

- **A website write fails in the middle of a step** (for example, a new
  status that Base44 doesn't know yet because Task 1 wasn't pasted).
  Expected: the `Base44Error` reaches `poll_once` and is logged. It is never
  swallowed, and the turn is never marked done. Pinned by
  `test_base44_error_mid_step_propagates` (Task 8).
- **The researcher pauses the session in the middle of the interview.**
  Expected: the current step finishes, and the next turn does not start.
  Pinned by `test_live_session_stops_between_turns_when_not_running` (Task 10).
- **The worker restarts while a turn is in `listening` or `robot_speaking`.**
  Expected: the turn resumes from that status, with no lost claim and no
  crash. Pinned by `test_resume_from_listening_listens_without_asking_again`
  and `test_resume_from_robot_speaking_after_crash` (Task 8).
- **LLM text with quotes, newlines or backslashes is sent to `/say`.**
  Expected: the robot speaks exactly that text. Pinned by the Kotlin
  `ParseTest` cases (Task 2).
- **The participant is silent on the PE question.** Expected: the turn is
  `skipped` (`pe_no_answer`), the reaction stays logged, and the next turn
  starts. Pinned by `test_silent_pe_answer_skips_turn` (Task 9).

---

### Task 1: Base44 prompt for the Live statuses and fields (researcher pastes)

**Files:**
- Create: `docs/website-prompts/2026-11-08-live-conversation.md`

**Interfaces:**
- Produces: `Participant.gender` (`Male` / `Female`, optional), `Participant.first_name` (string, optional). Turn statuses `queued`, `robot_speaking`, `listening`,
  `pe_listening`, `robot_feedback` and `skipped`; Turn fields `skip_reason`,
  `robot_line` and `engine_model` (strings); `pe_result` value `Partial`.
  Tasks 8–10 write all of these.

- [ ] **Step 1: Write the prompt file** with exactly this content:

````markdown
# Base44 prompt — Live sessions run by the robot (2026-11-08)

Paste everything inside the fence into Base44's AI builder. Skip section 6
if the Persona dropdowns are already in place.

```
In Live sessions the robot now runs the conversation itself: it says each line, listens to the participant through its own speech recognition, and the external Engine writes the transcripts. Keep the rule that this app is frontend + database only. Simulation and Mock sessions must keep their current flow exactly as it is today.

## 1. New Turn fields
- `skip_reason`: string
- `robot_line`: string (what the robot said after the participant's answer)
- `engine_model`: string (which language model the Engine used for this turn)
In Live sessions the Engine now writes `participant_answer` and `participant_pe_answer` (speech-recognition transcripts) and `question_text` for Opening/Closing turns.

## 2. Turn.status values
Add these values to the Turn.status enum and keep every existing value: `queued`, `robot_speaking`, `listening`, `pe_listening`, `robot_feedback`, `skipped`.
Make sure `pe_result` allows `Correct`, `Partial`, `Wrong`.

## 3. Creating turns
When a Live session starts, create its turns exactly as today, but with status `queued` instead of `awaiting_answer`. Simulation and Mock: unchanged.

## 4. Live session screen (Live mode only)
- The researcher does not type answers in Live mode. Hide the answer and PE-answer text boxes and the "Send to Engine" button. Show `participant_answer` and `participant_pe_answer` read-only as "What the participant said".
- Do not create `say` RobotCommands in Live sessions, and hide any "read question aloud" button: the Engine makes the robot say every line itself.
- Status labels:
  queued = "Waiting", robot_speaking = "Robot is speaking", listening = "Robot is listening", engine_processing = "Processing", awaiting_approval = "Needs your approval", robot_reacting = "Robot is reacting", pe_listening = "Listening for the PE answer", awaiting_feedback = "Feedback needs your approval", robot_feedback = "Robot is giving feedback", done = "Done", skipped = "Skipped".
- awaiting_approval: as today. Show the transcript, the emotion and the editable reply. Approve sets `final_reply` and status `robot_reacting`.
- awaiting_feedback: show `participant_pe_answer`, `pe_result` (the researcher may change it to Correct / Partial / Wrong), `pe_explanation`, and an editable `final_feedback` prefilled from `proposed_feedback`. In Live mode, Approve sets `final_feedback` and status `robot_feedback`. In Simulation it stays as today.
- skipped: show the turn greyed out with the reason in plain words: no_answer = "No answer (silence)", no_recognition = "Speech not recognized", pe_no_answer = "No answer to the PE question", pe_no_recognition = "PE answer not recognized", researcher = "Skipped by researcher".
- If `engine_error` is not empty, show it in red with a Retry button. Retry sets `engine_error` to an empty string and does NOT change the status.
- Add a "Skip this turn" button on the current Live turn when its status is `queued`, `awaiting_approval` or `awaiting_feedback`, or when `engine_error` is not empty. It sets status `skipped`, `skipped = true`, `skip_reason = "researcher"`.
- Show `robot_line` under the transcript as "Robot said", and `engine_model` as a small grey label.

## 5. Participant gender and first name
Add two optional fields to the Participant entity:
- `gender`: enum `Male`, `Female`. Label: "Gender (how the robot addresses the participant)".
- `first_name`: string. Label: "First name (the robot uses it in small talk only)".
Show both in the participant form and the participant list. Existing participants keep them empty until the researcher fills them in.

## 6. Persona (skip if already done)
In the Persona form, make `furhat_voice` a dropdown: AvriNeural ("Avri – male"), HilaNeural ("Hila – female"), Hila:DragonLatestNeural ("Hila HD – female"). Make `furhat_face` a dropdown: Alex, Brooklyn, Chen, Dorothy, Expresivo, Fedora, Fernando, Gyeong, Hayden, Isabel, James, Jamie, Jane, Kione, Lamin, Marty, Maurice, Nazar, Omar, Patricia, Rania, Samuel, Titan, Vinnie, Yi, Yumi, Zhen. Both are optional (empty = robot default). Values are stored as plain strings with the same field names.

## 7. Documentation
Regenerate the OpenAPI file and give me the updated field table for Turn (exact field names, types and enum values).
```
````

- [ ] **Step 2: Commit**

```bash
git add docs/website-prompts/2026-11-08-live-conversation.md
git commit -m "Add Base44 prompt for Live statuses and fields"
```

- [ ] **Step 3 (researcher, manual): paste and verify.** Paste the prompt into
  Base44. Make sure `engine_worker.py` is **not** running. Create and start
  one Live session, then run this read-only check:

```bash
set -a; source .env; set +a
python -c "import base44_client as b; s=b.list_records('Session', {}, sort='-created_date', limit=1)[0]; print(s['mode'], [t['status'] for t in b.list_records('Turn', {'session': s['id']}, sort='order')])"
```

Expected: `Live ['queued', 'queued', ...]`. Compare the Base44 field table
with Interfaces → Produces above. Then abort that test session on the
website.

---

### Task 2: Kotlin bridge decodes every JSON escape (`interview-skill`)

Repo: `../furhat-emotion-study`, branch `interview-skill`.

**Files:**
- Modify: `interview-skill/src/main/kotlin/furhatos/app/interviewskill/remote/RemoteControl.kt` (`extractStringField`, `jsonString`)
- Test: `interview-skill/src/test/kotlin/ParseTest.kt`

**Interfaces:**
- Produces: `fun unescapeJson(raw: String): String`. `extractStringField`
  returns fully decoded text. `jsonString` escapes every control character.

Why: today `extractStringField` replaces escapes one after another, so
`"C:\\new"` turns into `C:\` + newline + `ew`, and `\t` / `\uXXXX` are not
decoded. LLM text reaches `/say` starting with this plan. Also, `jsonString`
leaves `\t` and `\r` raw, and Python's `json` rejects raw control characters,
so `listen()` would return `failed`.

- [ ] **Step 1: Add failing tests** to `ParseTest.kt` (inside the class):

```kotlin
    @Test
    fun `string field decodes newline, tab, backslash and unicode escapes`() {
        val body = """{"text": "שורה\nשנייה\tטאב \\ סוף \u05e9"}"""
        assertEquals("שורה\nשנייה\tטאב \\ סוף ש", extractStringField(body, "text"))
    }

    @Test
    fun `escaped backslash followed by n stays a backslash and an n`() {
        val body = """{"text": "C:\\new"}"""
        assertEquals("C:\\new", extractStringField(body, "text"))
    }

    @Test
    fun `jsonString escapes tabs, carriage returns and other control characters`() {
        assertEquals("\"a\\tb\\rc\\u0001\"", jsonString("a\tb\rc\u0001"))
    }
```

- [ ] **Step 2: Run them to see them fail**

```bash
cd ../furhat-emotion-study
JAVA_HOME=$(/usr/libexec/java_home -v 11) ./gradlew :interview-skill:test
```

Expected: the three new tests FAIL, and the three old ones pass.

- [ ] **Step 3: Implement.** In `RemoteControl.kt`, replace `extractStringField`
  and `jsonString` with:

```kotlin
// Captures a JSON string value between quotes, honoring \" and \\ escapes.
fun extractStringField(body: String, field: String): String? {
    val pattern = "\"$field\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"".toRegex()
    val raw = pattern.find(body)?.groupValues?.get(1) ?: return null
    return unescapeJson(raw)
}

// One left-to-right pass, so "\\n" decodes to a backslash + n, never a newline.
fun unescapeJson(raw: String): String {
    val out = StringBuilder(raw.length)
    var i = 0
    while (i < raw.length) {
        val c = raw[i]
        if (c != '\\' || i + 1 == raw.length) {
            out.append(c)
            i += 1
            continue
        }
        val e = raw[i + 1]
        val hex = if (e == 'u' && i + 6 <= raw.length) raw.substring(i + 2, i + 6).toIntOrNull(16) else null
        if (hex != null) {
            out.append(hex.toChar())
            i += 6
        } else {
            out.append(when (e) {
                'n' -> '\n'
                't' -> '\t'
                'r' -> '\r'
                'b' -> '\b'
                'f' -> '\u000C'
                else -> e // \" \\ \/
            })
            i += 2
        }
    }
    return out.toString()
}

fun jsonString(s: String): String {
    val sb = StringBuilder("\"")
    for (c in s) {
        when {
            c == '"' -> sb.append("\\\"")
            c == '\\' -> sb.append("\\\\")
            c == '\n' -> sb.append("\\n")
            c == '\r' -> sb.append("\\r")
            c == '\t' -> sb.append("\\t")
            c < ' ' -> sb.append(String.format("\\u%04x", c.code))
            else -> sb.append(c)
        }
    }
    return sb.append('"').toString()
}
```

- [ ] **Step 4: Run the tests and see them all pass.** Same command. Expected: 6 tests PASS.

- [ ] **Step 5: Rebuild the skill and check its size.** Ask the researcher to
  stop `InterviewSkill` in the launcher first.

```bash
./interview-skill/rebuild.sh && stat -f %z interview-skill/build/libs/InterviewSkill-all.skill
```

Expected: `Build successful!` and a size of at most 31457280.

- [ ] **Step 6: Commit** (in `furhat-emotion-study`)

```bash
git add interview-skill/src/main/kotlin/furhatos/app/interviewskill/remote/RemoteControl.kt interview-skill/src/test/kotlin/ParseTest.kt
git commit -m "Decode all JSON escapes in the bridge and escape control characters in replies"
```

---

### Task 3: `llm_line.py` and the small-talk generator

**Files:**
- Create: `llm_line.py`, `prompts/small_talk_prompt.py`, `small_talk.py`
- Test: `tests/test_llm_line.py`, `tests/test_small_talk.py`

**Interfaces:**
- Consumes:
  - `llm_client.call_llm(system, user_message, model=None, temperature=0.7, max_tokens=500) -> str`
  - `guardrail.check_rationale(text) -> GuardrailResult` (`.passed`)
- Produces:
  - `llm_line.LANGUAGE_NAMES: dict`
  - `llm_line.language_or_default(language) -> str`: returns `"he"` or `"en"`
  - `llm_line.gender_rule(language, participant_gender=None, robot_gender=None) -> str`.
    Genders are `"male"`, `"female"` or `None`.
  - `llm_line.request_json(system, user_message, required=("line",), max_tokens=200, temperature=0.8) -> dict | None`
  - `llm_line.request_line(system, user_message, max_tokens=200, temperature=0.8) -> str | None`
  - `small_talk.role_for(phase: str, position: int, total: int, expects_answer: bool) -> str`
  - `small_talk.generate_line(phase, position, total, expects_answer, history, language="he", participant_gender=None, robot_gender=None, participant_name=None) -> str`.
    Each `history` item is `{"speaker": "robot" | "participant", "text": str}`.

- [ ] **Step 1: Write the failing tests.** `tests/test_llm_line.py`:

```python
import llm_line


def _fake_llm(monkeypatch, replies):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(llm_line.llm_client, "call_llm", fake)
    return calls


def test_request_line_returns_the_line(monkeypatch):
    _fake_llm(monkeypatch, ['```json\n{"line": "  שלום!  "}\n```'])
    assert llm_line.request_line("sys", "user") == "שלום!"


def test_request_line_retries_once_after_bad_json(monkeypatch):
    calls = _fake_llm(monkeypatch, ["not json", '{"line": "היי"}'])
    assert llm_line.request_line("sys", "user") == "היי"
    assert len(calls) == 2


def test_request_line_gives_up_after_two_failures(monkeypatch):
    calls = _fake_llm(monkeypatch, [TimeoutError("down"), '{"line": ""}'])
    assert llm_line.request_line("sys", "user") is None
    assert len(calls) == 2


def test_request_json_needs_every_required_field(monkeypatch):
    _fake_llm(monkeypatch, ['{"line": "x"}', '{"line": "x", "reason": "y"}'])
    assert llm_line.request_json("sys", "user", required=("line", "reason")) == {"line": "x", "reason": "y"}


def test_language_or_default():
    assert llm_line.language_or_default("en") == "en"
    assert llm_line.language_or_default(None) == "he"
    assert llm_line.language_or_default("fr") == "he"


def test_gender_rule():
    assert llm_line.gender_rule("en", "female", "male") == ""
    assert "feminine form" in llm_line.gender_rule("he", "female")
    assert "masculine form" in llm_line.gender_rule("he", "male")
    assert "unknown" in llm_line.gender_rule("he", None)
    assert "speaks about itself, use the feminine form" in llm_line.gender_rule("he", "male", "female")
```

`tests/test_small_talk.py`:

```python
import pytest

import small_talk
from prompts.small_talk_prompt import FALLBACK_LINES


@pytest.mark.parametrize("phase,position,total,expects_answer,role", [
    ("Opening", 1, 3, True, "opening_first"),
    ("Opening", 2, 3, True, "opening_middle"),
    ("Opening", 3, 3, True, "opening_last"),
    ("Closing", 1, 2, True, "closing_first"),
    ("Closing", 2, 3, True, "closing_middle"),
    ("Closing", 2, 2, False, "closing_last"),
])
def test_role_for(phase, position, total, expects_answer, role):
    assert small_talk.role_for(phase, position, total, expects_answer) == role


def test_generate_line_sends_role_gender_and_history(monkeypatch):
    seen = {}

    def fake(system, user_message):
        seen.update(system=system, user=user_message)
        return "נעים מאוד, דנה!"

    monkeypatch.setattr(small_talk.llm_line, "request_line", fake)
    history = [{"speaker": "robot", "text": "היי, איך קוראים לך?"},
               {"speaker": "participant", "text": "דנה"}]

    line = small_talk.generate_line("Opening", 2, 3, True, history, "he", participant_gender="female")

    assert line == "נעים מאוד, דנה!"
    assert "Hebrew" in seen["system"]
    assert "Continue the small talk" in seen["system"]
    assert "feminine form" in seen["system"]
    assert seen["user"] == "Robot: היי, איך קוראים לך?\nCandidate: דנה"


def test_first_name_goes_into_the_prompt_only_when_known(monkeypatch):
    seen = []
    monkeypatch.setattr(small_talk.llm_line, "request_line",
                        lambda system, user_message: seen.append(system) or "שלום")
    small_talk.generate_line("Opening", 1, 2, True, [], "he", participant_name="דנה")
    small_talk.generate_line("Opening", 1, 2, True, [], "he")
    assert "first name is דנה" in seen[0] and "never ask for their name" in seen[0]
    assert "first name" not in seen[1]


def test_generate_line_empty_history_says_so(monkeypatch):
    seen = {}
    monkeypatch.setattr(small_talk.llm_line, "request_line",
                        lambda system, user_message: seen.update(user=user_message) or "שלום")
    small_talk.generate_line("Opening", 1, 2, True, [], "he")
    assert seen["user"] == "(The conversation has not started yet.)"


def test_generate_line_falls_back_by_gender_when_llm_fails(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_line", lambda system, user_message: None)
    assert small_talk.generate_line("Opening", 2, 3, True, [], "he", "female") == \
        FALLBACK_LINES["he"]["female"]["opening_middle"]
    assert small_talk.generate_line("Opening", 2, 3, True, [], "he", None) == \
        FALLBACK_LINES["he"]["neutral"]["opening_middle"]
    assert small_talk.generate_line("Opening", 1, 2, True, [], "en", "male") == \
        FALLBACK_LINES["en"]["neutral"]["opening_first"]


def test_flagged_line_falls_back(monkeypatch):
    monkeypatch.setattr(small_talk.llm_line, "request_line",
                        lambda system, user_message: "You seemed nervous, but welcome!")
    assert small_talk.generate_line("Opening", 1, 2, True, [], "en") == FALLBACK_LINES["en"]["neutral"]["opening_first"]


def test_every_gender_has_every_role():
    for lang, forms in FALLBACK_LINES.items():
        assert "neutral" in forms, lang
        for form, lines in forms.items():
            assert set(lines) == set(small_talk.ROLES), (lang, form)
```

- [ ] **Step 2: Run them to see them fail**

Run: `pytest tests/test_llm_line.py tests/test_small_talk.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm_line'`.

- [ ] **Step 3: Implement.** `llm_line.py`:

```python
"""
llm_line.py -- asks the LLM for one spoken robot line, returned as JSON
(e.g. {"line": "..."}). Shared by small_talk.py, acknowledgement.py and
pe_feedback.py.

One retry (spec: "LLM call fails -> one retry"), then None, so each caller
falls back to its own fixed line. Never raises: a failed LLM call must not
stop a live conversation.
"""

import json
import re

import llm_client

LANGUAGE_NAMES = {"he": "Hebrew", "en": "English"}
_FORMS = {"male": "masculine", "female": "feminine"}


def language_or_default(language) -> str:
    return language if language in LANGUAGE_NAMES else "he"


def gender_rule(language, participant_gender=None, robot_gender=None) -> str:
    """Prompt sentence about Hebrew grammatical gender (plan decision P2). Empty for English."""
    if language != "he":
        return ""
    if participant_gender in _FORMS:
        rules = [f"Address the candidate in the {_FORMS[participant_gender]} form."]
    else:
        rules = ["Avoid gender-marked second-person forms (for example \"מה שלומך?\"), "
                 "because the candidate's gender is unknown."]
    if robot_gender in _FORMS:
        rules.append(f"When the robot speaks about itself, use the {_FORMS[robot_gender]} form.")
    return " ".join(rules)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def request_json(system: str, user_message: str, required=("line",), max_tokens: int = 200,
                 temperature: float = 0.8):
    for _ in range(2):
        try:
            raw = llm_client.call_llm(system=system, user_message=user_message,
                                      max_tokens=max_tokens, temperature=temperature)
            data = json.loads(_strip_fences(raw))
            values = {key: str(data[key]).strip() for key in required}
        except Exception:  # LLM/network error or malformed JSON: retry, then the caller falls back
            continue
        if all(values.values()):
            return values
    return None


def request_line(system: str, user_message: str, max_tokens: int = 200, temperature: float = 0.8):
    data = request_json(system, user_message, ("line",), max_tokens, temperature)
    return data["line"] if data else None
```

`prompts/small_talk_prompt.py`:

```python
"""
Small-talk prompt: the robot's opening and closing lines, generated fresh
every session from the dialogue so far (spec decision 5). Not
methodology-locked, but No-Masking still applies: the robot never comments
on how the candidate speaks.

FALLBACK_LINES are spoken when the LLM fails twice or the guardrail flags
the line. Hebrew has a version per participant gender (plan decision P2);
"neutral" is used when the gender is unknown. Researcher review: these
exact lines.
"""

SMALL_TALK_SYSTEM_PROMPT = """You are a friendly social robot who is about to interview, or has just interviewed, a candidate in a practice job interview. The candidate is an autistic adult practicing job interviews.

Write ONLY the robot's next line of small talk.
Rules:
- 1-2 short sentences, warm and casual, in {language}.
- If the candidate just said something, respond to what they said.
- Never evaluate the candidate, and never comment on how they speak (tone, confidence, eye contact, length, clarity, structure).
- Avoid sensitive topics: health, family, politics, religion, money.
- No emoji, no stage directions, no quotation marks around the line.
{gender_rule}
{name_rule}

This line's job: {role}

Respond with ONLY a JSON object: {{"line": "<the robot's line>"}}"""

NAME_RULE = "The candidate's first name is {name}. You may use it now and then, and never ask for their name."

ROLES = {
    "opening_first": "Open the session: greet the candidate and ask one easy, friendly question (for example, how their day is going).",
    "opening_middle": "Continue the small talk with one easy, friendly question.",
    "opening_last": "React briefly, say the interview questions are about to start, and ask whether they are ready to begin.",
    "closing_first": "The interview questions are over. Thank the candidate and ask whether they have any questions for you.",
    "closing_middle": "Briefly respond to what they said and ask whether there is anything else.",
    "closing_last": "Say a short, warm goodbye. Do not ask a question.",
}

FALLBACK_LINES = {
    "he": {
        "neutral": {
            "opening_first": "שלום, נעים מאוד. מה שלומך היום?",
            "opening_middle": "נעים מאוד, נמשיך.",
            "opening_last": "עוד מעט נתחיל בשאלות הראיון. אפשר להתחיל?",
            "closing_first": "תודה רבה על הראיון. יש שאלות שתרצו לשאול אותי?",
            "closing_middle": "תודה. יש עוד משהו?",
            "closing_last": "תודה רבה, היה נעים מאוד. להתראות!",
        },
        "male": {
            "opening_first": "שלום, נעים מאוד. איך אתה מרגיש היום?",
            "opening_middle": "נעים מאוד, בוא נמשיך.",
            "opening_last": "עוד מעט נתחיל בשאלות הראיון. אתה מוכן?",
            "closing_first": "תודה רבה על הראיון. יש לך שאלות אליי?",
            "closing_middle": "תודה. יש עוד משהו שתרצה לשאול?",
            "closing_last": "תודה רבה, היה נעים מאוד. להתראות!",
        },
        "female": {
            "opening_first": "שלום, נעים מאוד. איך את מרגישה היום?",
            "opening_middle": "נעים מאוד, בואי נמשיך.",
            "opening_last": "עוד מעט נתחיל בשאלות הראיון. את מוכנה?",
            "closing_first": "תודה רבה על הראיון. יש לך שאלות אליי?",
            "closing_middle": "תודה. יש עוד משהו שתרצי לשאול?",
            "closing_last": "תודה רבה, היה נעים מאוד. להתראות!",
        },
    },
    "en": {
        "neutral": {
            "opening_first": "Hello, nice to meet you. How is your day going?",
            "opening_middle": "Nice to meet you. Let's continue.",
            "opening_last": "We'll start the interview questions soon. Ready to begin?",
            "closing_first": "Thank you for the interview. Do you have any questions for me?",
            "closing_middle": "Thank you. Is there anything else?",
            "closing_last": "Thank you, it was nice talking with you. Goodbye!",
        },
    },
}
```

`small_talk.py`:

```python
"""
small_talk.py -- the robot's opening/closing small-talk lines (spec
decision 5), generated from the dialogue so far so every session sounds
different. No researcher approval (spec decision 6); every line is still
written to the website as the turn's question_text.

Never raises: after one retry, or if the No-Masking guardrail flags the
line, it falls back to a fixed line in the participant's gender.
"""

import guardrail
import llm_line
from prompts.small_talk_prompt import FALLBACK_LINES, NAME_RULE, ROLES, SMALL_TALK_SYSTEM_PROMPT

_SPEAKER_NAMES = {"robot": "Robot", "participant": "Candidate"}


def role_for(phase: str, position: int, total: int, expects_answer: bool) -> str:
    if phase == "Closing" and not expects_answer:
        return "closing_last"
    prefix = "opening" if phase == "Opening" else "closing"
    if position == 1:
        return f"{prefix}_first"
    if phase == "Opening" and position == total:
        return "opening_last"
    return f"{prefix}_middle"


def format_history(history: list) -> str:
    return "\n".join(f"{_SPEAKER_NAMES[h['speaker']]}: {h['text']}" for h in history)


def _fallback(lang: str, participant_gender, role: str) -> str:
    forms = FALLBACK_LINES[lang]
    return (forms.get(participant_gender) or forms["neutral"])[role]


def generate_line(phase: str, position: int, total: int, expects_answer: bool, history: list,
                  language: str = "he", participant_gender=None, robot_gender=None,
                  participant_name=None) -> str:
    """participant_name is used in small talk only (plan decision P12)."""
    lang = llm_line.language_or_default(language)
    role = role_for(phase, position, total, expects_answer)
    system = SMALL_TALK_SYSTEM_PROMPT.format(
        language=llm_line.LANGUAGE_NAMES[lang], role=ROLES[role],
        gender_rule=llm_line.gender_rule(lang, participant_gender, robot_gender),
        name_rule=NAME_RULE.format(name=participant_name) if participant_name else "")
    user = format_history(history) or "(The conversation has not started yet.)"
    line = llm_line.request_line(system, user)
    if line and guardrail.check_rationale(line).passed:
        return line
    return _fallback(lang, participant_gender, role)
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `pytest tests/test_llm_line.py tests/test_small_talk.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add llm_line.py prompts/small_talk_prompt.py small_talk.py tests/test_llm_line.py tests/test_small_talk.py
git commit -m "Add small-talk line generator with gendered Hebrew fallbacks"
```

---

### Task 4: Hebrew guardrail phrases, and the content-only acknowledgement

**Files:**
- Modify: `config.py` (`NO_MASKING_FLAG_PATTERNS`, methodology-locked; the researcher approves the exact words below with this plan)
- Create: `prompts/acknowledgement_prompt.py`, `acknowledgement.py`
- Test: `tests/test_guardrail.py` (add tests), `tests/test_acknowledgement.py`

**Interfaces:**
- Consumes: `llm_line.request_line`, `llm_line.language_or_default`, `llm_line.LANGUAGE_NAMES`, `llm_line.gender_rule` (Task 3), `guardrail.check_rationale(text) -> GuardrailResult`
- Produces: `acknowledgement.acknowledge(question: str, answer: str, language: str = "he", participant_gender=None, robot_gender=None) -> {"line": str, "guardrail_flag": bool, "guardrail_reason": str}`

The Hebrew phrases (plan decision P3) describe **delivery** or **grade the
answer**, like the English list. They are whole phrases, not single words,
because the guardrail is a literal substring match. A robot line that
repeats the participant's own content (for example "you were stressed at
work") must not be flagged. Both gender forms are listed where they differ.
They never match the evaluator's English rationale, so the existing routing
in `graph.py` is unaffected.

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_guardrail.py`:

```python
import pytest

import guardrail


@pytest.mark.parametrize("line", [
    "תודה. שמתי לב שלא היה קשר עין.",
    "נשמעת לחוצה, אבל נמשיך.",
    "תשובה מצוינת! נמשיך.",
    "כדאי לשים לב למבנה התשובה.",
    "התשובה הייתה ארוכה מדי.",
])
def test_hebrew_delivery_and_praise_lines_are_flagged(line):
    assert guardrail.check_rationale(line).passed is False


@pytest.mark.parametrize("line", [
    "תודה, אז היית לחוץ בעבודה הקודמת ולמדת לתעדף משימות. נמשיך.",
    "תודה, אז עבדת שלוש שנים בשירות לקוחות. נמשיך.",
    "בעצם הרגשתי שמחה, כי סיפרת שהצלחת בפרויקט.",
])
def test_hebrew_content_lines_pass(line):
    assert guardrail.check_rationale(line).passed is True
```

`tests/test_acknowledgement.py`:

```python
import acknowledgement
from prompts.acknowledgement_prompt import FALLBACK_LINES


def test_acknowledge_returns_clean_line(monkeypatch):
    seen = {}
    monkeypatch.setattr(acknowledgement.llm_line, "request_line",
                        lambda system, user_message: seen.update(system=system, user=user_message)
                        or "תודה, אז עבדת שלוש שנים בשירות לקוחות. נמשיך.")

    ack = acknowledgement.acknowledge("ספר/י על עצמך", "עבדתי שלוש שנים בשירות לקוחות", "he",
                                      participant_gender="female")

    assert ack == {"line": "תודה, אז עבדת שלוש שנים בשירות לקוחות. נמשיך.",
                   "guardrail_flag": False, "guardrail_reason": ""}
    assert "עבדתי שלוש שנים" in seen["user"]
    assert "feminine form" in seen["system"]


def test_flagged_line_is_replaced_by_fallback(monkeypatch):
    monkeypatch.setattr(acknowledgement.llm_line, "request_line",
                        lambda system, user_message: "תשובה מצוינת, נמשיך.")

    ack = acknowledgement.acknowledge("Q", "A", "he")

    assert ack["line"] == FALLBACK_LINES["he"]
    assert ack["guardrail_flag"] is True
    assert "תשובה מצוינת" in ack["guardrail_reason"]


def test_llm_failure_falls_back_without_flag(monkeypatch):
    monkeypatch.setattr(acknowledgement.llm_line, "request_line", lambda system, user_message: None)

    ack = acknowledgement.acknowledge("Q", "A")

    assert ack == {"line": "תודה, נמשיך.", "guardrail_flag": False, "guardrail_reason": ""}
```

- [ ] **Step 2: Run them to see them fail**

Run: `pytest tests/test_guardrail.py tests/test_acknowledgement.py -v`
Expected: FAIL. The Hebrew lines are not flagged yet, and the
`acknowledgement` module doesn't exist.

- [ ] **Step 3: Implement.** In `config.py`, append these entries at the end of
  `NO_MASKING_FLAG_PATTERNS`, before the closing `]`, and keep every
  existing entry:

```python
    # Hebrew equivalents, approved by the researcher on 2026-11-08 (Plan 2,
    # decision P3). Whole phrases, because matching is literal-substring:
    # a robot line that repeats the participant's own content ("היית לחוץ
    # בעבודה") must not be flagged. Both gender forms where they differ.
    "קשר עין",
    "שפת גוף",
    "טון הדיבור",
    "מונוטוני",
    "נשמעת לחוץ", "נשמעת לחוצה",
    "נראית לחוץ", "נראית לחוצה",
    "נשמעת בטוח", "נשמעת בטוחה",
    "חוסר התלהבות",
    "ישיר מדי", "ישירה מדי",
    "בוטה מדי",
    "מבנה התשובה",
    "לא בפורמט STAR",
    "ארוכה מדי", "קצרה מדי",
    "לא הרחבת מספיק",
    "נשמעת רובוטי",
    "גמגום",
    "תשובה מצוינת", "תשובה טובה", "תשובה מעולה", "כל הכבוד",
```

`prompts/acknowledgement_prompt.py`:

```python
"""
Acknowledgement prompt: the robot's short reply after a non-PBDI Main
answer (spec decision 7). No emotion, no approval. No-Masking applies in
full: content only, never delivery, never a grade. The line is also passed
through guardrail.check_rationale(); flagged lines are replaced by the
fixed fallback.
"""

ACKNOWLEDGEMENT_SYSTEM_PROMPT = """You are a social robot interviewing a candidate in a practice job interview. The candidate is an autistic adult practicing job interviews.

The candidate just answered an interview question. Write ONE short sentence in {language} that mentions something specific from the CONTENT of their answer, then moves on. Example: "Thanks, so you worked three years in customer service. Let's continue."

Strict rules:
- Never comment on HOW they answered: confidence, tone, structure, length, clarity, eye contact, directness, enthusiasm.
- Never grade or praise the answer (no "great answer", "good point", "excellent").
- No advice, no follow-up question, no emoji.
{gender_rule}

Respond with ONLY a JSON object: {{"line": "<the robot's line>"}}"""

FALLBACK_LINES = {"he": "תודה, נמשיך.", "en": "Thank you, let's continue."}
```

`acknowledgement.py`:

```python
"""
acknowledgement.py -- content-only robot reply after a non-PBDI Main answer
(spec decision 7). One LLM line, checked by the No-Masking guardrail
(English and Hebrew phrases, plan decision P3); if the guardrail flags it,
or the LLM fails twice, the robot says the fixed fallback. Never raises.
"""

import guardrail
import llm_line
from prompts.acknowledgement_prompt import ACKNOWLEDGEMENT_SYSTEM_PROMPT, FALLBACK_LINES


def acknowledge(question: str, answer: str, language: str = "he",
                participant_gender=None, robot_gender=None) -> dict:
    lang = llm_line.language_or_default(language)
    system = ACKNOWLEDGEMENT_SYSTEM_PROMPT.format(
        language=llm_line.LANGUAGE_NAMES[lang],
        gender_rule=llm_line.gender_rule(lang, participant_gender, robot_gender))
    line = llm_line.request_line(system, f"Interview question: {question}\n\nCandidate answer: {answer}")
    if line is None:
        return {"line": FALLBACK_LINES[lang], "guardrail_flag": False, "guardrail_reason": ""}
    check = guardrail.check_rationale(line)
    if not check.passed:
        return {"line": FALLBACK_LINES[lang], "guardrail_flag": True,
                "guardrail_reason": f"style-bias language in acknowledgement: {check.matched_patterns}"}
    return {"line": line, "guardrail_flag": False, "guardrail_reason": ""}
```

- [ ] **Step 4: Run all tests and see them pass**

Run: `pytest tests/ -q`
Expected: all PASS. If an existing guardrail or graph test counts the
pattern list's length, update its expected number. Never remove an
existing pattern.

- [ ] **Step 5: Commit**

```bash
git add config.py prompts/acknowledgement_prompt.py acknowledgement.py tests/test_guardrail.py tests/test_acknowledgement.py
git commit -m "Add researcher-approved Hebrew guardrail phrases and content-only acknowledgement"
```

---

### Task 5: PE judge grades Correct / Partial / Wrong

**Files:**
- Create: `prompts/pe_check_prompt.py`
- Modify: `pe_check.py` (whole file), `engine_worker.py` (`check_pe`)
- Test: `tests/test_pe_check.py` (rewrite), `tests/test_engine_worker.py` (`test_check_pe_writes_result`)

**Interfaces:**
- Consumes: `llm_client.call_llm`
- Produces:
  - `pe_check.RESULTS = ("Correct", "Partial", "Wrong")`
  - `pe_check.grade_pe_answer(target_emotion: str, pe_answer_text: str) -> {"result": str, "explanation": str}`.
    LLM errors propagate (the caller retries). Unparseable output returns
    `Wrong` with an explanation.
  - `pe_check.check_pe_answer(...)` keeps its old shape for
    `interaction_app.py`: `{"match": result == "Correct", "explanation", "result"}`.
  - `prompts.pe_check_prompt.HEBREW_NAMES: dict[str, str]` (also used by Task 6).

- [ ] **Step 1: Write the failing tests.** Replace `tests/test_pe_check.py` with:

```python
import json

import pytest

import pe_check
from prompts.pe_check_prompt import HEBREW_NAMES, PE_CHECK_SYSTEM_PROMPT, WORD_LISTS


def _llm_returns(monkeypatch, text):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return text

    monkeypatch.setattr(pe_check.llm_client, "call_llm", fake)
    return seen


@pytest.mark.parametrize("result", ["Correct", "Partial", "Wrong"])
def test_grade_returns_each_result(monkeypatch, result):
    _llm_returns(monkeypatch, json.dumps({"result": result, "explanation": "הסבר"}))
    assert pe_check.grade_pe_answer("HAPPINESS", "התלהבת") == {"result": result, "explanation": "הסבר"}


def test_grade_sends_target_and_answer(monkeypatch):
    seen = _llm_returns(monkeypatch, '{"result": "Correct", "explanation": "x"}')
    pe_check.grade_pe_answer("ANGER", "נראה לי שכעסת")
    assert "Target emotion: ANGER" in seen["user_message"]
    assert "נראה לי שכעסת" in seen["user_message"]


@pytest.mark.parametrize("raw", ["not json", '{"result": "Maybe", "explanation": "x"}', '{"explanation": "x"}'])
def test_grade_fails_closed_to_wrong(monkeypatch, raw):
    _llm_returns(monkeypatch, raw)
    graded = pe_check.grade_pe_answer("ANGER", "לא יודעת")
    assert graded["result"] == "Wrong" and graded["explanation"]


def test_grade_lets_llm_errors_propagate(monkeypatch):
    def boom(**kwargs):
        raise TimeoutError("LLM down")

    monkeypatch.setattr(pe_check.llm_client, "call_llm", boom)
    with pytest.raises(TimeoutError):
        pe_check.grade_pe_answer("ANGER", "כועס")


def test_check_pe_answer_keeps_match_shape(monkeypatch):
    _llm_returns(monkeypatch, '{"result": "Partial", "explanation": "קרוב"}')
    assert pe_check.check_pe_answer("HAPPINESS", "התלהבת") == {
        "match": False, "explanation": "קרוב", "result": "Partial"}


def test_word_lists_cover_every_displayable_emotion():
    import emotion_classifier
    assert set(WORD_LISTS) == set(emotion_classifier.CORE_EMOTIONS) == set(HEBREW_NAMES)
    for target, lists in WORD_LISTS.items():
        assert lists["correct"], target
        assert target not in lists["partial"], target
        assert set(lists["partial"]) <= set(WORD_LISTS), target


def test_prompt_contains_the_spec_examples():
    assert "מאושר" in PE_CHECK_SYSTEM_PROMPT and "מתלהב" in PE_CHECK_SYSTEM_PROMPT
    assert '"Partial"' in PE_CHECK_SYSTEM_PROMPT
```

In `tests/test_engine_worker.py`, replace `test_check_pe_writes_result` with:

```python
def test_check_pe_writes_result(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Simulation")
    turn = fake.add("Turn", session=session["id"], order=1, status="awaiting_pe_check",
                    target_emotion="HAPPINESS", participant_pe_answer="התלהבת")
    monkeypatch.setattr(engine_worker.pe_check, "grade_pe_answer",
                        lambda gt, ans: {"result": "Partial", "explanation": "קרוב"})

    engine_worker.check_pe(turn, session)

    saved = fake.get("Turn", turn["id"])
    assert saved["pe_result"] == "Partial"
    assert saved["pe_explanation"] == "קרוב"
    assert saved["status"] == "awaiting_feedback"
```

- [ ] **Step 2: Run them to see them fail**

Run: `pytest tests/test_pe_check.py tests/test_engine_worker.py::test_check_pe_writes_result -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prompts.pe_check_prompt'`.

- [ ] **Step 3: Implement.** `prompts/pe_check_prompt.py`:

```python
"""
PE judge prompt (spec, "New prompts" 4; integration spec "PE grading of
near-synonyms"). Grades the emotion the participant named, not their
reason and not their wording.

Families follow Shaver, Schwartz, Kirson & O'Connor (1987): HAPPINESS,
EXCITED and CALM share the joy family; ANGER, CONTEMPT and DISGUST share
the anger family. BORED and SLEEPY are not in Shaver; they are treated as
one low-energy family. A word in the target's family that sits closer to
a DIFFERENT emotion the robot can show is Partial.

DRAFT word lists -- the researcher must review them before any participant
session (plan decision P11). The lists are examples, not exhaustive.
"""

HEBREW_NAMES = {
    "ANGER": "כעס", "CONTEMPT": "בוז", "DISGUST": "גועל", "FEAR": "פחד",
    "HAPPINESS": "שמחה", "SADNESS": "עצב", "SURPRISE": "הפתעה",
    "EXCITED": "התלהבות", "BORED": "שעמום", "SLEEPY": "עייפות", "CALM": "רוגע",
}

WORD_LISTS = {
    "HAPPINESS": {"correct": ["שמח", "מאושר", "נהנה", "מרוצה", "טוב לך", "חייכת", "גאה"],
                  "partial": {"EXCITED": ["מתלהב", "נלהב", "נרגש"], "CALM": ["רגוע", "שליו", "נינוח"]}},
    "EXCITED": {"correct": ["מתלהב", "נלהב", "נרגש", "להוט", "מלא אנרגיה"],
                "partial": {"HAPPINESS": ["שמח", "מאושר", "מרוצה"]}},
    "CALM": {"correct": ["רגוע", "שליו", "נינוח", "בנחת", "משוחרר"],
             "partial": {"HAPPINESS": ["שמח", "מרוצה"]}},
    "ANGER": {"correct": ["כועס", "עצבני", "מתוסכל", "מרוגז", "זועם", "נרגז"],
              "partial": {"CONTEMPT": ["מזלזל", "בז"], "DISGUST": ["נגעל"]}},
    "CONTEMPT": {"correct": ["בוז", "מזלזל", "מתנשא", "לא העריך", "בז"],
                 "partial": {"ANGER": ["כועס", "עצבני"], "DISGUST": ["נגעל"]}},
    "DISGUST": {"correct": ["נגעל", "גועל", "סלידה", "דחייה", "מגעיל"],
                "partial": {"CONTEMPT": ["מזלזל", "בז"], "ANGER": ["כועס"]}},
    "FEAR": {"correct": ["פוחד", "מפחד", "חושש", "דואג", "לחוץ", "מודאג", "חרד", "נבהל"],
             "partial": {}},
    "SADNESS": {"correct": ["עצוב", "מאוכזב", "מצטער", "מדוכדך", "מבואס", "אכזבה"],
                "partial": {}},
    "SURPRISE": {"correct": ["מופתע", "הופתע", "נדהם", "המום", "לא ציפה"],
                 "partial": {}},
    "BORED": {"correct": ["משועמם", "שעמום", "לא מעניין", "אדיש", "חוסר עניין"],
              "partial": {"SLEEPY": ["עייף", "ישנוני"]}},
    "SLEEPY": {"correct": ["עייף", "ישנוני", "מנומנם", "רדום", "מותש"],
               "partial": {"BORED": ["משועמם", "אדיש"]}},
}


def _word_list_text() -> str:
    lines = []
    for target, lists in WORD_LISTS.items():
        line = f"- {target} ({HEBREW_NAMES[target]}): Correct: {', '.join(lists['correct'])}"
        if lists["partial"]:
            closer = "; ".join(f"{', '.join(words)} (closer to {other})"
                               for other, words in lists["partial"].items())
            line += f" | Partial: {closer}"
        lines.append(line)
    return "\n".join(lines)


PE_CHECK_SYSTEM_PROMPT = (
    "You grade a perspective-taking exercise. A social robot interviewer showed an emotion "
    "on its face. The participant was asked \"What do you think I felt, and why?\" and "
    "answered freely, usually in Hebrew.\n\n"
    "Grade ONLY the emotion the participant named or described, against the TARGET emotion:\n"
    "- \"Correct\": the core word for the target, a clear synonym, or a description of the "
    "target emotion through what happened (for example \"you smiled because I said I "
    "succeeded\" for HAPPINESS).\n"
    "- \"Partial\": a word in the target's family that is closer to a DIFFERENT emotion this "
    "robot can show (see the lists below).\n"
    "- \"Wrong\": a different emotion family, or no emotion named.\n"
    "Both grammatical genders count the same (כועס = כועסת). Informal phrasing counts.\n"
    "The participant's reason (\"why\") does NOT change the grade: comment on it in the "
    "explanation only. Never judge wording, spelling, length or how the answer was "
    "expressed.\n\n"
    "The robot can show: ANGER, CONTEMPT, DISGUST, FEAR, HAPPINESS, SADNESS, SURPRISE, "
    "EXCITED, BORED, SLEEPY, CALM.\n\n"
    "Hebrew word lists (examples, not exhaustive):\n"
    + _word_list_text()
    + "\n\nRespond with ONLY a JSON object of the exact shape: "
    "{\"result\": \"Correct\" | \"Partial\" | \"Wrong\", \"explanation\": \"<one or two "
    "sentences, in the same language as the participant's answer: why this grade, and a "
    "short comment on their reason>\"}"
)
```

Replace `pe_check.py` with:

```python
"""
pe_check.py -- grades a participant's perspective-taking (PE) answer
("what did I feel, and why?") against the emotion the robot actually
showed (the turn's target_emotion).

Correct / Partial / Wrong from the emotion only (spec decisions 10-11);
the reason is commented on in the explanation but never changes the
grade. Content, not delivery: No-Masking applies here too. Prompt and
word lists: prompts/pe_check_prompt.py.

LLM errors propagate so the caller can retry; an unparseable reply fails
closed to "Wrong" with an explanation the researcher sees before approving.
"""

import json
import re

import llm_client
from prompts.pe_check_prompt import PE_CHECK_SYSTEM_PROMPT

RESULTS = ("Correct", "Partial", "Wrong")

_FALLBACK = {"result": "Wrong", "explanation": "Could not parse a judgment from the model."}


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def grade_pe_answer(target_emotion: str, pe_answer_text: str) -> dict:
    raw = llm_client.call_llm(
        system=PE_CHECK_SYSTEM_PROMPT,
        user_message=f"Target emotion: {target_emotion}\n\nParticipant's answer: {pe_answer_text}",
        max_tokens=200,
        temperature=0.2,
    )
    try:
        data = json.loads(_strip_fences(raw))
        if data["result"] not in RESULTS:
            raise ValueError(f"Unexpected result: {data['result']!r}")
        return {"result": data["result"], "explanation": str(data["explanation"])}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return dict(_FALLBACK)


def check_pe_answer(ground_truth_emotion: str, pe_answer_text: str) -> dict:
    """The older match/no-match shape, kept for interaction_app.py."""
    graded = grade_pe_answer(ground_truth_emotion, pe_answer_text)
    return {"match": graded["result"] == "Correct", "explanation": graded["explanation"],
            "result": graded["result"]}
```

In `engine_worker.py`, replace `check_pe` with:

```python
def check_pe(turn: dict, session: dict) -> None:
    if session.get("mode") == "Mock":
        graded = {"result": "Correct", "explanation": "Mock mode — no LLM call."}
    else:
        graded = pe_check.grade_pe_answer(turn.get("target_emotion", ""), turn.get("participant_pe_answer", ""))
    b44.update_record("Turn", turn["id"], {
        "pe_result": graded["result"],
        "pe_explanation": graded["explanation"],
        "status": "awaiting_feedback",
    })
    _log(f"Turn {turn.get('order')}: PE {graded['result']}")
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `pytest tests/test_pe_check.py tests/test_engine_worker.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add prompts/pe_check_prompt.py pe_check.py engine_worker.py tests/test_pe_check.py tests/test_engine_worker.py
git commit -m "Grade PE answers Correct/Partial/Wrong with Shaver-family Hebrew word lists"
```

---

### Task 6: PE feedback line with an LLM-written reason

**Files:**
- Create: `prompts/pe_feedback_prompt.py`, `pe_feedback.py`, `tests/test_llm_smoke.py`
- Test: `tests/test_pe_feedback.py`

**Interfaces:**
- Consumes: `llm_line` (Task 3), `prompts.pe_check_prompt.HEBREW_NAMES` (Task 5), `guardrail.check_rationale`
- Produces: `pe_feedback.generate_feedback(target_emotion: str, question: str, answer: str, guess: str, result: str, language: str = "he", participant_gender=None, robot_gender=None) -> {"line": str, "reason": str}`.
  Never raises. On fallback, `reason` is `""`.

Plan decision P1: the same LLM call writes the reason (what in the
participant's answer made the robot feel this) and the spoken line. Task 9
stores the reason in `Turn.pe_answer_why` at grading time, so the researcher
sees it next to the feedback. The emotion classifier is not changed.

- [ ] **Step 1: Write the failing tests.** `tests/test_pe_feedback.py`:

```python
import pe_feedback


def _fake_json(monkeypatch, reply):
    seen = {}

    def fake(system, user_message, required=("line",), **kwargs):
        seen.update(system=system, user=user_message, required=required)
        return reply

    monkeypatch.setattr(pe_feedback.llm_line, "request_json", fake)
    return seen


def test_feedback_gets_all_inputs_and_returns_line_and_reason(monkeypatch):
    seen = _fake_json(monkeypatch, {"line": "כמעט! בעצם הרגשתי שמחה, כי סיפרת שהצלחת בפרויקט.",
                                    "reason": "סיפרת שהצלחת בפרויקט"})

    out = pe_feedback.generate_feedback("HAPPINESS", "ספר/י על הצלחה", "הצלחתי בפרויקט גדול",
                                        "התלהבת", "Partial", "he", participant_gender="male")

    assert out == {"line": "כמעט! בעצם הרגשתי שמחה, כי סיפרת שהצלחת בפרויקט.",
                   "reason": "סיפרת שהצלחת בפרויקט"}
    assert set(seen["required"]) == {"line", "reason"}
    for part in ("TARGET: HAPPINESS (שמחה)", "QUESTION: ספר/י על הצלחה",
                 "ANSWER: הצלחתי בפרויקט גדול", "GUESS: התלהבת", "GRADE: Partial"):
        assert part in seen["user"]
    assert "Hebrew" in seen["system"] and "masculine form" in seen["system"]


def test_feedback_falls_back_to_naming_the_emotion(monkeypatch):
    _fake_json(monkeypatch, None)
    assert pe_feedback.generate_feedback("SADNESS", "Q", "A", "שמחת", "Wrong", "he") == {
        "line": "בעצם הרגשתי עצב.", "reason": ""}
    assert pe_feedback.generate_feedback("SADNESS", "Q", "A", "happy", "Wrong", "en") == {
        "line": "I actually felt sadness.", "reason": ""}


def test_flagged_feedback_falls_back(monkeypatch):
    _fake_json(monkeypatch, {"line": "הרגשתי שמחה כי נשמעת בטוחה.", "reason": "נשמעת בטוחה"})
    assert pe_feedback.generate_feedback("HAPPINESS", "Q", "A", "שמחת", "Correct")["line"] == "בעצם הרגשתי שמחה."
```

- [ ] **Step 2: Run them to see them fail**

Run: `pytest tests/test_pe_feedback.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pe_feedback'`.

- [ ] **Step 3: Implement.** `prompts/pe_feedback_prompt.py`:

```python
"""
PE feedback prompt: after the participant guesses what the robot felt,
the robot reveals the emotion and why (spec decision 8). The reason is
written by this call from the question and the participant's answer
(plan decision P1) and must point to WHAT the participant said, never HOW
(No-Masking). The researcher approves every line before the robot says it.
"""

PE_FEEDBACK_SYSTEM_PROMPT = """You are a social robot interviewer in a practice job interview with an autistic adult. After you reacted to their answer, you asked "What do you think I felt, and why?". Now you tell them what you actually felt, and why.

You get: the interview QUESTION, the candidate's ANSWER, the emotion you actually showed (TARGET, with its Hebrew name), the candidate's GUESS, and the GRADE (Correct / Partial / Wrong).

1. "reason": a short phrase in {language} naming what in the candidate's ANSWER made you feel the TARGET emotion. It must point to WHAT they said (the content), never to HOW they said it (tone, confidence, eye contact, length, structure).
2. "line": 1-2 short spoken sentences in {language}, in the first person:
   - Correct: confirm warmly, name the emotion, and give the reason.
   - Partial: say they were close, name the emotion you actually felt, and give the reason.
   - Wrong: kindly say what you actually felt, and give the reason.
   Do not grade their interview answer. No emoji.
{gender_rule}

Respond with ONLY a JSON object: {{"reason": "<the reason>", "line": "<the robot's line>"}}"""

FALLBACK_TEMPLATES = {"he": "בעצם הרגשתי {name}.", "en": "I actually felt {name}."}
```

`pe_feedback.py`:

```python
"""
pe_feedback.py -- the robot's line revealing what it actually felt and
why, after the participant's PE guess (spec decision 8). The line goes to
Turn.proposed_feedback and the reason to Turn.pe_answer_why; the
researcher edits/approves the line as final_feedback before the robot
says it.

Never raises: if the LLM fails twice, or the No-Masking guardrail flags
the line or the reason, it falls back to just naming the emotion.
"""

import guardrail
import llm_line
from prompts.pe_check_prompt import HEBREW_NAMES
from prompts.pe_feedback_prompt import FALLBACK_TEMPLATES, PE_FEEDBACK_SYSTEM_PROMPT


def generate_feedback(target_emotion: str, question: str, answer: str, guess: str, result: str,
                      language: str = "he", participant_gender=None, robot_gender=None) -> dict:
    lang = llm_line.language_or_default(language)
    hebrew = HEBREW_NAMES.get(target_emotion, target_emotion)
    system = PE_FEEDBACK_SYSTEM_PROMPT.format(
        language=llm_line.LANGUAGE_NAMES[lang],
        gender_rule=llm_line.gender_rule(lang, participant_gender, robot_gender))
    user = (f"QUESTION: {question}\n"
            f"ANSWER: {answer}\n"
            f"TARGET: {target_emotion} ({hebrew})\n"
            f"GUESS: {guess}\n"
            f"GRADE: {result}")
    out = llm_line.request_json(system, user, required=("line", "reason"))
    if out and guardrail.check_rationale(f"{out['line']} {out['reason']}").passed:
        return {"line": out["line"], "reason": out["reason"]}
    name = hebrew if lang == "he" else target_emotion.lower()
    return {"line": FALLBACK_TEMPLATES[lang].format(name=name), "reason": ""}
```

`tests/test_llm_smoke.py` (real LLM, skipped unless asked):

```python
"""Real-LLM smoke checks for the new prompts (spec "Testing"). Skipped by
default; run with: RUN_LLM_SMOKE=1 pytest tests/test_llm_smoke.py -v"""

import os

import pytest

import acknowledgement
import config
import llm_client
import pe_check
from prompts.acknowledgement_prompt import FALLBACK_LINES

pytestmark = pytest.mark.skipif(os.environ.get("RUN_LLM_SMOKE") != "1",
                                reason="real LLM calls; set RUN_LLM_SMOKE=1")

SAMPLE_ANSWERS = [
    ("Tell me about yourself.", "I studied industrial engineering and worked two years in logistics."),
    ("What are your strengths?", "I'm very precise. I check every number twice."),
    ("Why do you want this job?", "Um. I don't know. Money, I guess."),
]


@pytest.fixture(autouse=True)
def fast_model():
    with llm_client.model_override(config.MODEL_FAST):
        yield


@pytest.mark.parametrize("question,answer", SAMPLE_ANSWERS)
def test_acknowledgement_is_generated_and_passes_guardrail(question, answer):
    ack = acknowledgement.acknowledge(question, answer, language="en")
    assert ack["line"] != FALLBACK_LINES["en"]
    assert ack["guardrail_flag"] is False


@pytest.mark.parametrize("answer,expected", [("כמה מאושר", "Correct"), ("התלהבת", "Partial")])
def test_pe_check_spec_examples(answer, expected):
    assert pe_check.grade_pe_answer("HAPPINESS", answer)["result"] == expected
```

- [ ] **Step 4: Run all tests and see them pass**

Run: `pytest tests/ -q`
Expected: everything PASSES. The smoke tests show as skipped.

- [ ] **Step 5: Commit**

```bash
git add prompts/pe_feedback_prompt.py pe_feedback.py tests/test_pe_feedback.py tests/test_llm_smoke.py
git commit -m "Add PE feedback line with an LLM-written, content-only reason"
```

---

### Task 7: Worker plumbing: shared helpers, shared fakes, heartbeat thread, current model

**Files:**
- Create: `worker_common.py`, `tests/fakes.py`, `hebrew_gender.py`
- Modify: `engine_worker.py` (helpers, heartbeat, `main`, `speech_context`), `llm_client.py` (`current_model`), `config.py` (`VOICE_GENDERS`)
- Test: `tests/test_engine_worker.py` (use the shared fakes, add heartbeat and speech-context tests), `tests/test_llm_client.py` (add a test), `tests/test_hebrew_gender.py`

**Interfaces:**
- Produces:
  - `worker_common.WORKER_ID: str`, `worker_common.now() -> str` (UTC ISO),
    `worker_common.log(msg) -> None`
  - `llm_client.current_model() -> str`
  - `engine_worker.heartbeat_once() -> None` (never raises `Base44Error`)
  - `engine_worker.start_heartbeat_thread() -> threading.Thread`
  - `engine_worker.speech_context(session) -> {"participant_gender": "male"|"female"|None, "robot_gender": "male"|"female"|None, "participant_name": str|None}`.
    Cached per session.
  - `hebrew_gender.render(text: str, gender=None) -> str`
  - `config.VOICE_GENDERS: dict[str, str]`
  - `tests/fakes.py`: `FakeBase44` (as before, plus `statuses(record_id) -> list[str]`),
    `FakeRobot(heard=(), connected=True)` with `say`, `react`, `listen`,
    `health_check`, `.calls` and `said()`, and `heard(text) -> dict`.

- [ ] **Step 1: Create `tests/fakes.py`.** Move `FakeBase44` here from
  `tests/test_engine_worker.py` and add the status log and `FakeRobot`:

```python
"""Shared fakes for the worker tests: an in-memory Base44 and a scripted robot."""

import itertools

import base44_client


class FakeBase44:
    """In-memory stand-in for base44_client: exact-match queries, compare-and-set claim.

    Every status write is logged, so tests can check a turn walked its statuses in order."""

    Base44Error = base44_client.Base44Error
    RateLimited = base44_client.RateLimited

    def __init__(self):
        self.records = {}
        self.status_log = []
        self._ids = itertools.count(1)

    def add(self, entity, **fields):
        rec = {"id": f"{entity}-{next(self._ids)}", **fields}
        self.records.setdefault(entity, []).append(rec)
        return rec

    def list_records(self, entity, query=None, sort=None, limit=100):
        rows = [r for r in self.records.get(entity, [])
                if all(r.get(k) == v for k, v in (query or {}).items())]
        if sort:
            rows.sort(key=lambda r: r.get(sort))
        return [dict(r) for r in rows[:limit]]

    def get(self, entity, record_id):
        return next(r for r in self.records[entity] if r["id"] == record_id)

    def get_record(self, entity, record_id):  # real client's name
        return dict(self.get(entity, record_id))

    def create_record(self, entity, fields):
        return dict(self.add(entity, **fields))

    def update_record(self, entity, record_id, fields):
        self.get(entity, record_id).update(fields)
        if "status" in fields:
            self.status_log.append((record_id, fields["status"]))
        return dict(self.get(entity, record_id))

    def claim(self, entity, record_id, from_status, fields):
        rec = self.get(entity, record_id)
        if rec.get("status") != from_status:
            return False
        rec.update(fields)
        if "status" in fields:
            self.status_log.append((record_id, fields["status"]))
        return True

    def statuses(self, record_id):
        return [status for rid, status in self.status_log if rid == record_id]


def heard(text):
    return {"status": "ok", "text": text}


class FakeRobot:
    """Scripted stand-in for furhat_client. `heard` is the queue of listen() results;
    an empty queue means silence."""

    def __init__(self, heard=(), connected=True):
        self.heard = list(heard)
        self.connected = connected
        self.calls = []

    def _sent(self):
        return {"sent": self.connected, "reason": None if self.connected else "connection refused"}

    def say(self, text, language=None, gender=None):
        self.calls.append(("say", text))
        return self._sent()

    def react(self, emotion, intensity, text=None, language=None, gender=None):
        self.calls.append(("react", emotion, intensity, text))
        return self._sent()

    def listen(self):
        self.calls.append(("listen",))
        if not self.connected:
            return {"status": "failed", "text": ""}
        return self.heard.pop(0) if self.heard else {"status": "no_speech", "text": ""}

    def health_check(self):
        return self.connected

    def said(self):
        return [c[1] for c in self.calls if c[0] == "say"]
```

In `tests/test_engine_worker.py`:
- Delete the `FakeBase44` class and the `import itertools` line.
- Add `from tests.fakes import FakeBase44`.
- Keep the `fake` fixture as it is.

Note: the old fake's `get_record = get` returned the live record. The new one
returns a copy, which is what the real client does.

In `tests/test_model_registry.py`, change `from tests.test_engine_worker import FakeBase44`
to `from tests.fakes import FakeBase44`.

- [ ] **Step 2: Run the worker tests.** They must still pass with the moved fake.

Run: `pytest tests/test_engine_worker.py tests/test_model_registry.py -v`
Expected: all PASS.

- [ ] **Step 3: Write the failing tests.** Add to `tests/test_engine_worker.py`:

```python
def test_heartbeat_once_reports_robot_status(fake, monkeypatch):
    monkeypatch.setattr(engine_worker, "_heartbeat_id", None)
    monkeypatch.setattr(engine_worker.furhat_client, "health_check", lambda: True)

    engine_worker.heartbeat_once()

    beat = fake.list_records("EngineHeartbeat", {"key": "engine-main"})
    assert len(beat) == 1 and beat[0]["robot_connected"] is True


def test_heartbeat_once_survives_base44_errors(fake, monkeypatch):
    monkeypatch.setattr(engine_worker, "_heartbeat_id", None)
    monkeypatch.setattr(engine_worker.furhat_client, "health_check", lambda: False)

    def limited(*a, **k):
        raise engine_worker.b44.RateLimited("429")

    monkeypatch.setattr(fake, "list_records", limited)

    engine_worker.heartbeat_once()  # must not raise
```

Add to `tests/test_llm_client.py`:

```python
def test_current_model_follows_override():
    assert llm_client.current_model() == config.MODEL_DEFAULT
    with llm_client.model_override("llama3.1-8b"):
        assert llm_client.current_model() == "llama3.1-8b"
    assert llm_client.current_model() == config.MODEL_DEFAULT
```

(Import `config` at the top of `tests/test_llm_client.py` if it isn't imported yet.)

- [ ] **Step 4: Run them to see them fail**

Run: `pytest tests/test_engine_worker.py tests/test_llm_client.py -v`
Expected: FAIL with `AttributeError` for `heartbeat_once` and `current_model`.

- [ ] **Step 5: Implement.** `worker_common.py`:

```python
"""Shared by engine_worker.py and conversation_flow.py: the worker's id,
timestamps in the website's format, and log lines."""

import socket
from datetime import datetime, timezone

import config

WORKER_ID = f"{socket.gethostname()}-{config.ENGINE_VERSION}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)
```

In `llm_client.py`, add this function after `model_override`, and make
`call_llm` resolve its model with `model = model or current_model()`:

```python
def current_model() -> str:
    """The model call_llm() would use right now, for recording which model produced a turn."""
    return _model_override.get() or config.MODEL_DEFAULT
```

In `engine_worker.py`:
- Delete `WORKER_ID`, `_now` and `_log`, and the `socket` and `datetime`
  imports if nothing else uses them.
- Add `import threading` and
  `from worker_common import WORKER_ID, log as _log, now as _now`.
- Add after `send_heartbeat`:

```python
def heartbeat_once() -> None:
    try:
        send_heartbeat(furhat_client.health_check())
    except b44.Base44Error as e:  # RateLimited too: the next beat is WORKER_HEARTBEAT_EVERY away anyway
        _log(f"Heartbeat failed: {e}")


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
```

In `main()`:
- Delete `last_heartbeat` and the `if time.monotonic() - last_heartbeat ...`
  block.
- Call `start_heartbeat_thread()` right after the model-sync `try`/`except`.
- The loop keeps `robot_connected = furhat_client.health_check()` for
  `poll_once`.

- [ ] **Step 6: Write the failing tests for the Hebrew gender helpers.** In
  `tests/test_engine_worker.py`, add `monkeypatch.setattr(engine_worker, "_speech_context", {})`
  to the `fake` fixture, then add:

```python
def test_speech_context_reads_participant_and_voice_once(fake, monkeypatch):
    participant = fake.add("Participant", gender="Female", first_name=" דנה ")
    persona = fake.add("Persona", furhat_voice="AvriNeural")
    session = fake.add("Session", participant=participant["id"], persona=persona["id"])

    assert engine_worker.speech_context(session) == {
        "participant_gender": "female", "robot_gender": "male", "participant_name": "דנה"}

    monkeypatch.setattr(fake, "get_record", lambda *a: pytest.fail("cached: no second lookup"))
    assert engine_worker.speech_context(session)["participant_gender"] == "female"


def test_speech_context_without_participant_or_persona(fake):
    session = fake.add("Session")
    assert engine_worker.speech_context(session) == {
        "participant_gender": None, "robot_gender": None, "participant_name": None}


def test_speech_context_base44_error_is_not_cached(fake, monkeypatch):
    session = fake.add("Session", participant="p1")

    def boom(entity, record_id):
        raise engine_worker.b44.Base44Error("timeout")

    monkeypatch.setattr(fake, "get_record", boom)
    assert engine_worker.speech_context(session) == {
        "participant_gender": None, "robot_gender": None, "participant_name": None}
    assert session["id"] not in engine_worker._speech_context
```

`tests/test_hebrew_gender.py`:

```python
import pytest

import hebrew_gender


@pytest.mark.parametrize("text,male,female", [
    ("ספר/י על עצמך", "ספר על עצמך", "ספרי על עצמך"),
    ("מה תעשה/י אם המנהל יבקש", "מה תעשה אם המנהל יבקש", "מה תעשי אם המנהל יבקש"),
    ("איך היית מתמודד/ת עם לקוח?", "איך היית מתמודד עם לקוח?", "איך היית מתמודדת עם לקוח?"),
    ("האם את/ה מוכן/ה?", "האם את מוכן?", "האם אתה מוכנה?"),
    ("אתה/את מוכן/ה?", "אתה מוכן?", "את מוכנה?"),
    ("עבודה ו/או לימודים", "עבודה ו/או לימודים", "עבודה ו/או לימודים"),
    ("שאלה בלי לוכסן", "שאלה בלי לוכסן", "שאלה בלי לוכסן"),
])
def test_render(text, male, female):
    assert hebrew_gender.render(text, "male") == male
    assert hebrew_gender.render(text, "female") == female
    assert hebrew_gender.render(text, None) == male  # unknown gender: first form, as written
```

Note: `"את/ה"` is written with the feminine form first. The rule can't tell,
so it comes out reversed (`"אתה"` for a female participant). The test pins this known limit. If
the real question bank uses `"את/ה"`, the researcher should rewrite it as
`"אתה/את"`. The live check (Task 11) catches any others.

Run: `pytest tests/test_hebrew_gender.py tests/test_engine_worker.py -v`
Expected: FAIL. `hebrew_gender` and `speech_context` don't exist yet.

- [ ] **Step 7: Implement.** `hebrew_gender.py`:

```python
"""
hebrew_gender.py -- resolves the question bank's slash forms ("ספר/י",
"מתמודד/ת", "אתה/את") into one spoken form for the participant's gender
(plan decision P2), so the robot never reads a slash aloud.

Rule-based: in "<base>/<alt>", an alt in _SUFFIXES is a feminine suffix
(base + suffix; a base ending in ה drops it before a י suffix: תעשה/י ->
תעשי; a final letter turns regular: מוכן/ה -> מוכנה). Any other alt is a
whole alternative word (אתה/את). "ו/או" (and/or) is left alone.
Unknown gender -> the first form, as written.
"""

import re

_SLASH_FORM = re.compile(r"([א-ת]+)/([א-ת]+)")
_FINAL_TO_REGULAR = str.maketrans("ךםןףץ", "כמנפצ")
_SUFFIXES = ("י", "ת", "ה", "ית")


def _feminine(base: str, alt: str) -> str:
    if alt not in _SUFFIXES:
        return alt
    if alt == "י" and base.endswith("ה"):
        return base[:-1] + "י"
    return base[:-1] + base[-1].translate(_FINAL_TO_REGULAR) + alt


def render(text: str, gender=None) -> str:
    def pick(match):
        base, alt = match.group(1), match.group(2)
        if alt == "או":
            return match.group(0)
        return _feminine(base, alt) if gender == "female" else base

    return _SLASH_FORM.sub(pick, text)
```

In `config.py`, after `LISTEN_MAX_SPEECH_MS`, add:

```python
# Grammatical gender of each Furhat Hebrew voice: the robot speaks about
# itself in this form (Plan 2, decision P2). Voices not listed -> neutral.
VOICE_GENDERS = {"AvriNeural": "male", "HilaNeural": "female", "Hila:DragonLatestNeural": "female"}
```

In `engine_worker.py`, add after `apply_persona`:

```python
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
```

- [ ] **Step 8: Run all tests and see them pass**

Run: `pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add worker_common.py tests/fakes.py hebrew_gender.py config.py engine_worker.py llm_client.py tests/test_engine_worker.py tests/test_llm_client.py tests/test_model_registry.py tests/test_hebrew_gender.py
git commit -m "Move heartbeat to its own thread; share worker helpers and test fakes; add Hebrew gender helpers"
```

---

### Task 8: `conversation_flow.py`: small talk and non-PBDI turns

**Files:**
- Create: `conversation_flow.py`
- Test: `tests/test_conversation_flow.py`

**Interfaces:**
- Consumes:
  - `small_talk.generate_line(phase, position, total, expects_answer, history, language, participant_gender, robot_gender)` (Task 3)
  - `acknowledgement.acknowledge(question, answer, language, participant_gender, robot_gender) -> {"line", "guardrail_flag", "guardrail_reason"}` (Task 4)
  - `hebrew_gender.render(text, gender)` (Task 7). The `session` dict passed to `advance()` carries `participant_gender` / `robot_gender` / `participant_name` (added by Task 10's `run_live_session`). Only small talk receives the name (plan decision P12).
  - `furhat_client.say(text, language=None) -> {"sent", "reason"}`
  - `furhat_client.listen() -> {"status": "ok" | "no_speech" | "failed", "text"}`
  - `furhat_client.health_check() -> bool`
  - `b44.claim`, `b44.update_record`, `b44.create_record`, `b44.list_records`
  - `worker_common.WORKER_ID / now / log` and `llm_client.current_model()` (Task 7)
- Produces (Task 10 uses these):
  - `conversation_flow.current_turn(turns: list[dict]) -> dict | None`
  - `conversation_flow.advance(turn: dict, session: dict, turns: list[dict], robot_connected: bool, propose) -> bool`:
    True when the turn finished (`done` / `skipped`). `propose(question, answer, mode) -> dict`
    is `engine_worker.build_proposal`.
  - `conversation_flow.dialogue_history(turns, turn) -> list[{"speaker", "text"}]`
  - Constants `PBDI_CATEGORY`, `PE_QUESTION`, `NOT_HEARD_LINE`.

How it works: `advance()` runs a loop of status handlers. Each handler does
one step, writes the next status, and returns the updated turn dict. The loop
stops at `done` / `skipped`, at `awaiting_approval` / `awaiting_feedback`,
when `engine_error` is set, or when a claim is lost. In this task, every Main
turn is handled as non-PBDI. Task 9 adds the PBDI branch.

- [ ] **Step 1: Write the failing tests.** `tests/test_conversation_flow.py`:

```python
import pytest

import conversation_flow as flow
from tests.fakes import FakeBase44, FakeRobot, heard

Q = "ספר/י על עצמך"
ACK = {"line": "תודה, אז למדת הנדסה. נמשיך.", "guardrail_flag": False, "guardrail_reason": ""}


@pytest.fixture
def fake(monkeypatch):
    store = FakeBase44()
    monkeypatch.setattr(flow, "b44", store)
    monkeypatch.setattr(flow, "_robot_wait_started", {})
    monkeypatch.setattr(flow.small_talk, "generate_line",
                        lambda phase, position, total, expects_answer, history, language="he", *genders:
                        f"{phase} {position}/{total}")
    monkeypatch.setattr(flow.acknowledgement, "acknowledge", lambda q, a, language="he", *genders: dict(ACK))
    return store


def use_robot(monkeypatch, robot):
    monkeypatch.setattr(flow, "furhat_client", robot)
    return robot


def no_proposal(*args):
    pytest.fail("this turn must not be evaluated")


def run(store, session, turn, robot_connected=True, propose=no_proposal):
    turns = store.list_records("Turn", {"session": session["id"]}, sort="order")
    return flow.advance(store.get_record("Turn", turn["id"]), session, turns, robot_connected, propose)


def live_session(store):
    return store.add("Session", status="Running", mode="Live", language="he")


def test_current_turn_is_first_unfinished_by_order():
    turns = [{"id": "b", "order": 2, "status": "queued"},
             {"id": "a", "order": 1, "status": "done"},
             {"id": "c", "order": 3, "status": "queued"}]
    assert flow.current_turn(turns)["id"] == "b"
    assert flow.current_turn([{"id": "a", "order": 1, "status": "skipped"}]) is None


def test_small_talk_turn_walks_its_statuses(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Opening", generated_by_engine=True,
                 expects_answer=True, status="queued", question_text="")
    fake.add("Turn", session=s["id"], order=2, phase="Opening", generated_by_engine=True,
             expects_answer=True, status="queued", question_text="")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("טוב, אני דנה")]))

    assert run(fake, s, t) is True

    saved = fake.get("Turn", t["id"])
    assert fake.statuses(t["id"]) == ["robot_speaking", "listening", "engine_processing", "done"]
    assert saved["question_text"] == "Opening 1/2"
    assert saved["participant_answer"] == "טוב, אני דנה"
    assert saved["claimed_by"] == flow.WORKER_ID
    assert robot.calls == [("say", "Opening 1/2"), ("listen",)]


def test_goodbye_turn_does_not_listen(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Closing", generated_by_engine=True,
                 expects_answer=False, status="queued", question_text="")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is True

    assert fake.statuses(t["id"]) == ["robot_speaking", "done"]
    assert robot.calls == [("say", "Closing 1/1")]


def test_main_turn_says_question_then_content_only_ack(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Background",
                 question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("למדתי הנדסה")]))

    assert run(fake, s, t) is True

    saved = fake.get("Turn", t["id"])
    assert fake.statuses(t["id"]) == ["robot_speaking", "listening", "engine_processing",
                                       "robot_speaking", "done"]
    assert robot.said() == [Q, ACK["line"]]
    assert saved["robot_line"] == ACK["line"]
    assert saved["guardrail_flag"] is False
    assert saved["engine_model"]


def test_question_slash_forms_follow_participant_gender(fake, monkeypatch):
    s = fake.add("Session", status="Running", mode="Live", language="he", participant_gender="female")
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text="ספר/י על עצמך", status="queued")
    robot = use_robot(monkeypatch, FakeRobot())

    run(fake, s, t)

    assert robot.said() == ["ספרי על עצמך", "ספרי על עצמך"]  # asked, then repeated after silence
    assert fake.get("Turn", t["id"])["question_text"] == "ספר/י על עצמך"  # the website keeps the bank text


def test_awaiting_answer_is_treated_as_queued(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="awaiting_answer")
    use_robot(monkeypatch, FakeRobot(heard=[heard("כן")]))

    assert run(fake, s, t) is True
    assert fake.get("Turn", t["id"])["status"] == "done"


def test_silence_repeats_question_once_then_skips(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is True

    saved = fake.get("Turn", t["id"])
    assert robot.calls == [("say", Q), ("listen",), ("say", Q), ("listen",)]
    assert saved["status"] == "skipped" and saved["skip_reason"] == "no_answer"
    assert saved["skipped"] is True


def test_unrecognized_speech_asks_to_repeat_once_then_skips(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot(heard=[{"status": "failed", "text": ""},
                                                    {"status": "ok", "text": "  "}]))

    assert run(fake, s, t) is True

    assert robot.said() == [Q, flow.NOT_HEARD_LINE]
    assert fake.get("Turn", t["id"])["skip_reason"] == "no_recognition"


def test_answer_after_repeated_question_is_kept(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="queued")
    use_robot(monkeypatch, FakeRobot(heard=[{"status": "no_speech", "text": ""}, heard("אני מדויקת")]))

    assert run(fake, s, t) is True
    assert fake.get("Turn", t["id"])["participant_answer"] == "אני מדויקת"


def test_robot_down_waits_then_sets_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot())
    clock = [100.0]
    monkeypatch.setattr(flow.time, "monotonic", lambda: clock[0])

    assert run(fake, s, t, robot_connected=False) is False
    assert not fake.get("Turn", t["id"]).get("engine_error")

    clock[0] += flow.config.ROBOT_WAIT_SECONDS + 1
    assert run(fake, s, t, robot_connected=False) is False

    saved = fake.get("Turn", t["id"])
    assert saved["engine_error"] == "robot disconnected"
    assert saved["status"] == "queued"
    assert robot.calls == []


def test_robot_drops_mid_step_sets_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="queued")
    use_robot(monkeypatch, FakeRobot(connected=False))

    assert run(fake, s, t, robot_connected=True) is False
    assert fake.get("Turn", t["id"])["engine_error"] == "robot disconnected"


def test_listen_failure_with_robot_gone_sets_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="listening")
    robot = use_robot(monkeypatch, FakeRobot(connected=False))

    assert run(fake, s, t) is False
    assert robot.calls == [("listen",)]
    assert fake.get("Turn", t["id"])["engine_error"] == "robot disconnected"


def test_turn_with_engine_error_waits_for_retry(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q,
                 status="listening", engine_error="robot disconnected")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is False
    assert robot.calls == []


def test_resume_from_listening_listens_without_asking_again(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", category="Skills",
                 question_text=Q, status="listening")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("עניתי")]))

    assert run(fake, s, t) is True
    assert robot.calls[0] == ("listen",)


def test_resume_from_robot_speaking_after_crash(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Opening", generated_by_engine=True,
                 expects_answer=True, status="robot_speaking", question_text="")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("היי")]))

    assert run(fake, s, t) is True
    assert robot.said() == ["Opening 1/1"]


def test_lost_claim_does_nothing(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="queued")
    robot = use_robot(monkeypatch, FakeRobot())
    monkeypatch.setattr(fake, "claim", lambda *a: False)

    assert run(fake, s, t) is False
    assert robot.calls == []


def test_base44_error_mid_step_propagates(fake, monkeypatch):
    s = live_session(fake)
    t = fake.add("Turn", session=s["id"], order=1, phase="Main", question_text=Q, status="queued")
    use_robot(monkeypatch, FakeRobot())

    def broken(*a):
        raise fake.Base44Error("unknown status value")

    monkeypatch.setattr(fake, "update_record", broken)

    with pytest.raises(fake.Base44Error):
        run(fake, s, t)


def test_small_talk_gets_position_and_history(fake, monkeypatch):
    s = live_session(fake)
    fake.add("Turn", session=s["id"], order=1, phase="Opening", generated_by_engine=True,
             status="done", question_text="היי, מה שלומך?", participant_answer="טוב")
    t = fake.add("Turn", session=s["id"], order=2, phase="Opening", generated_by_engine=True,
                 expects_answer=True, status="queued", question_text="")
    seen = {}
    monkeypatch.setattr(flow.small_talk, "generate_line",
                        lambda phase, position, total, expects_answer, history, language="he", *genders:
                        seen.update(args=(phase, position, total, expects_answer), history=history) or "נחמד")
    use_robot(monkeypatch, FakeRobot(heard=[heard("כן")]))

    run(fake, s, t)

    assert seen["args"] == ("Opening", 2, 2, True)
    assert seen["history"] == [{"speaker": "robot", "text": "היי, מה שלומך?"},
                               {"speaker": "participant", "text": "טוב"}]


def test_dialogue_history_keeps_order_and_skips_empty_lines():
    turns = [
        {"order": 1, "status": "done", "question_text": "היי", "participant_answer": "שלום"},
        {"order": 2, "status": "done", "question_text": "Q2", "participant_answer": "A2", "robot_line": "R2",
         "participant_pe_answer": "PE2", "final_feedback": "FB2"},
        {"order": 3, "status": "skipped", "question_text": "Q3"},
        {"order": 4, "status": "queued", "question_text": ""},
    ]
    lines = flow.dialogue_history(turns, turns[3])
    assert [(l["speaker"], l["text"]) for l in lines] == [
        ("robot", "היי"), ("participant", "שלום"),
        ("robot", "Q2"), ("participant", "A2"), ("robot", "R2"),
        ("robot", flow.PE_QUESTION), ("participant", "PE2"), ("robot", "FB2"),
        ("robot", "Q3"),
    ]
```

- [ ] **Step 2: Run them to see them fail**

Run: `pytest tests/test_conversation_flow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'conversation_flow'`.

- [ ] **Step 3: Implement.** `conversation_flow.py`:

```python
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
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `pytest tests/test_conversation_flow.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add conversation_flow.py tests/test_conversation_flow.py
git commit -m "Add Live turn state machine for small talk and non-PBDI questions"
```

---

### Task 9: `conversation_flow.py`: the PBDI turn

**Files:**
- Modify: `conversation_flow.py`
- Test: `tests/test_conversation_flow.py` (add tests)

**Interfaces:**
- Consumes:
  - `propose(question, answer, mode) -> dict` (= `engine_worker.build_proposal`; may raise)
  - `pe_check.grade_pe_answer(target, answer) -> {"result", "explanation"}` (Task 5; may raise)
  - `pe_feedback.generate_feedback(target, question, answer, guess, result, language, participant_gender, robot_gender) -> {"line", "reason"}` (Task 6)
  - `furhat_client.react(emotion, intensity, text=None, language=None) -> {"sent", "reason"}`
- Produces: the full PBDI path:
  `engine_processing → awaiting_approval → [Approve] robot_reacting → pe_listening → engine_processing → awaiting_feedback → [Approve] robot_feedback → done`.
  One `RobotCommand` per reaction attempt, as the audit record.

- [ ] **Step 1: Write the failing tests.** Add to `tests/test_conversation_flow.py`:

```python
PROPOSAL = {"target_emotion": "HAPPINESS", "intensity": 2, "proposed_reply": "איזה יופי",
            "evaluation_category": "GOOD", "pe_answer_why": "הצלחתי בפרויקט"}


def pbdi_turn(store, session, **fields):
    return store.add("Turn", session=session["id"], order=1, phase="Main", category=flow.PBDI_CATEGORY,
                     question_text="ספר/י על הצלחה", **fields)


def test_pbdi_answer_stops_for_approval(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="queued")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("הצלחתי בפרויקט")]))
    calls = []

    assert run(fake, s, t, propose=lambda q, a, mode: calls.append((q, a, mode)) or dict(PROPOSAL)) is False

    saved = fake.get("Turn", t["id"])
    assert fake.statuses(t["id"]) == ["robot_speaking", "listening", "engine_processing", "awaiting_approval"]
    assert calls == [("ספר/י על הצלחה", "הצלחתי בפרויקט", "Live")]
    assert saved["target_emotion"] == "HAPPINESS" and saved["engine_model"]
    assert robot.said() == ["ספר/י על הצלחה"]  # no acknowledgement for PBDI


def test_pbdi_llm_failure_retries_once_then_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="engine_processing", participant_answer="תשובה")
    use_robot(monkeypatch, FakeRobot())
    calls = []

    def boom(q, a, mode):
        calls.append(1)
        raise TimeoutError("LLM down")

    assert run(fake, s, t, propose=boom) is False

    saved = fake.get("Turn", t["id"])
    assert len(calls) == 2
    assert "LLM down" in saved["engine_error"]
    assert saved["status"] == "engine_processing"


def test_pbdi_llm_failure_once_then_success(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="engine_processing", participant_answer="תשובה")
    use_robot(monkeypatch, FakeRobot())
    replies = [TimeoutError("blip"), dict(PROPOSAL)]

    def flaky(q, a, mode):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    run(fake, s, t, propose=flaky)
    assert fake.get("Turn", t["id"])["status"] == "awaiting_approval"


def test_approved_reaction_then_pe_question_then_grade(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_reacting", participant_answer="תשובה", final_reply="איזה יופי!",
                  target_emotion="HAPPINESS", intensity=2, pe_answer_why="הצלחתי בפרויקט")
    robot = use_robot(monkeypatch, FakeRobot(heard=[heard("התלהבת")]))
    monkeypatch.setattr(flow.pe_check, "grade_pe_answer",
                        lambda target, answer: {"result": "Partial", "explanation": "קרוב"})
    monkeypatch.setattr(flow.pe_feedback, "generate_feedback",
                        lambda target, question, answer, guess, result, language="he", *genders:
                        {"line": f"{target}/{answer}/{guess}/{result}", "reason": "סיפרת שהצלחת"})

    assert run(fake, s, t) is False

    saved = fake.get("Turn", t["id"])
    assert robot.calls == [("react", "HAPPINESS", 2, "איזה יופי!"), ("say", flow.PE_QUESTION), ("listen",)]
    assert fake.statuses(t["id"]) == ["pe_listening", "engine_processing", "awaiting_feedback"]
    assert saved["robot_line"] == "איזה יופי!"
    assert saved["participant_pe_answer"] == "התלהבת"
    assert saved["pe_result"] == "Partial" and saved["pe_explanation"] == "קרוב"
    assert saved["proposed_feedback"] == "HAPPINESS/תשובה/התלהבת/Partial"
    assert saved["pe_answer_why"] == "סיפרת שהצלחת"
    [cmd] = fake.list_records("RobotCommand", {"turn": t["id"]})
    assert cmd["status"] == "done" and cmd["emotion"] == "HAPPINESS" and cmd["text"] == "איזה יופי!"


def test_silent_pe_answer_skips_turn(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_reacting", proposed_reply="יופי", target_emotion="CALM", intensity=1)
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is True

    saved = fake.get("Turn", t["id"])
    assert saved["status"] == "skipped" and saved["skip_reason"] == "pe_no_answer"
    assert robot.said() == [flow.PE_QUESTION, flow.PE_QUESTION]
    assert fake.list_records("RobotCommand", {"turn": t["id"]})[0]["status"] == "done"


def test_reaction_fails_when_robot_drops(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_reacting", final_reply="יופי", target_emotion="FEAR", intensity=3)
    use_robot(monkeypatch, FakeRobot(connected=False))

    assert run(fake, s, t) is False

    saved = fake.get("Turn", t["id"])
    assert saved["engine_error"] == "robot disconnected" and saved["status"] == "robot_reacting"
    assert fake.list_records("RobotCommand", {"turn": t["id"]})[0]["status"] == "error"


def test_pe_grading_failure_sets_engine_error(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="engine_processing", participant_answer="תשובה",
                  participant_pe_answer="שמחת", target_emotion="HAPPINESS")
    use_robot(monkeypatch, FakeRobot())

    def boom(target, answer):
        raise TimeoutError("LLM down")

    monkeypatch.setattr(flow.pe_check, "grade_pe_answer", boom)

    assert run(fake, s, t) is False
    assert "LLM down" in fake.get("Turn", t["id"])["engine_error"]


def test_approved_feedback_is_spoken_then_done(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="robot_feedback", proposed_feedback="הצעה", final_feedback="בעצם הרגשתי רוגע.")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is True

    assert robot.said() == ["בעצם הרגשתי רוגע."]
    assert fake.get("Turn", t["id"])["status"] == "done"


def test_waiting_for_approval_does_nothing(fake, monkeypatch):
    s = live_session(fake)
    t = pbdi_turn(fake, s, status="awaiting_feedback")
    robot = use_robot(monkeypatch, FakeRobot())

    assert run(fake, s, t) is False
    assert robot.calls == []
```

- [ ] **Step 2: Run them to see them fail**

Run: `pytest tests/test_conversation_flow.py -v`
Expected: the new tests FAIL. For example, PBDI turns get an acknowledgement
(`no_proposal` fails the test), and `robot_reacting` has no handler.

- [ ] **Step 3: Implement.** In `conversation_flow.py`:
- Add `import pe_check` and `import pe_feedback` to the imports.
- Replace `_process` with the version below.
- Add the new handlers.
- Extend `_HANDLERS`.

```python
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
    if turn.get("generated_by_engine"):
        return _update(turn, status="done", done_at=now())
    if turn.get("category") == PBDI_CATEGORY:
        return _propose(turn, session, propose)
    ack = acknowledgement.acknowledge(turn.get("question_text", ""), turn["participant_answer"],
                                      session.get("language", "he"), session.get("participant_gender"),
                                      session.get("robot_gender"))
    return _update(turn, robot_line=ack["line"], guardrail_flag=ack["guardrail_flag"],
                   guardrail_reason=ack["guardrail_reason"], engine_model=llm_client.current_model(),
                   status="robot_speaking")


def _propose(turn, session, propose):
    """PBDI: evaluator + emotion + reply, then wait for the researcher's Approve."""
    try:
        proposal = _with_one_retry(
            lambda: propose(turn.get("question_text", ""), turn["participant_answer"], session.get("mode")))
    except Exception as e:  # after one retry: engine_error, and the researcher's Retry re-runs this step
        return _fail(turn, e)
    log(f"Turn {turn.get('order')}: proposed {proposal.get('target_emotion')} ({proposal.get('intensity')})")
    return _update(turn, **proposal, engine_model=llm_client.current_model(), engine_error="",
                   engine_responded_at=now(), status="awaiting_approval")


def _react(turn, session, turns, propose):
    """robot_reacting (set by the researcher's Approve): emotion + reply, then the fixed PE question."""
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
    _say(PE_QUESTION, session)
    return _update(turn, robot_line=text, status="pe_listening")


def _listen_pe(turn, session, turns, propose):
    """pe_listening: the participant's guess. Silence/bad ASR skips the turn (plan decision P6)."""
    text, skip_reason = _listen_for(PE_QUESTION, session)
    if skip_reason:
        return _skip(turn, f"pe_{skip_reason}")
    return _update(turn, participant_pe_answer=text, pe_submitted_at=now(), status="engine_processing")


def _grade_pe(turn, session):
    """Correct/Partial/Wrong + the feedback line, then wait for the researcher's Approve."""
    try:
        graded = _with_one_retry(
            lambda: pe_check.grade_pe_answer(turn.get("target_emotion", ""), turn["participant_pe_answer"]))
    except Exception as e:
        return _fail(turn, e)
    feedback = pe_feedback.generate_feedback(turn.get("target_emotion", ""), turn.get("question_text", ""),
                                             turn.get("participant_answer", ""), turn["participant_pe_answer"],
                                             graded["result"], session.get("language", "he"),
                                             session.get("participant_gender"), session.get("robot_gender"))
    log(f"Turn {turn.get('order')}: PE {graded['result']}")
    return _update(turn, pe_result=graded["result"], pe_explanation=graded["explanation"],
                   proposed_feedback=feedback["line"], pe_answer_why=feedback["reason"],
                   engine_model=llm_client.current_model(),
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
```

Note: the `_process` from Task 8 is replaced by this one. Remove the Task 8
version; don't keep two definitions.

- [ ] **Step 4: Run all tests and see them pass**

Run: `pytest tests/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add conversation_flow.py tests/test_conversation_flow.py
git commit -m "Add PBDI path: approval, reaction, PE question, PE grade, feedback"
```

---

### Task 10: Wire Live sessions into the worker, record the model, update docs

**Files:**
- Modify: `engine_worker.py` (`poll_once`, new `run_live_session`, `react_turn`, `process_turn`; delete `_command_for`)
- Modify: `CLAUDE.md`, `SESSION_LOG.md`, `PROJECT_PLAN.md`, `docs/superpowers/specs/2026-11-04-autonomous-robot-conversation-design.md` (status line), `docs/superpowers/specs/2026-11-02-base44-lab-app-integration-design.md` (decisions log)
- Test: `tests/test_engine_worker.py`

**Interfaces:**
- Consumes: `conversation_flow.current_turn`, `conversation_flow.advance` (Tasks 8–9), `llm_client.current_model()` (Task 7)
- Produces: `engine_worker.run_live_session(session: dict, robot_connected: bool) -> None`

- [ ] **Step 1: Write the failing tests.** In `tests/test_engine_worker.py`:

Update the `fake` fixture so the flow uses the same fake website:

```python
@pytest.fixture
def fake(monkeypatch):
    store = FakeBase44()
    monkeypatch.setattr(engine_worker, "b44", store)
    monkeypatch.setattr(engine_worker.conversation_flow, "b44", store)
    monkeypatch.setattr(engine_worker, "_robot_wait_started", {})
    monkeypatch.setattr(engine_worker.conversation_flow, "_robot_wait_started", {})
    monkeypatch.setattr(engine_worker, "_speech_context", {})
    return store
```

Delete `test_live_turn_reaction_is_sent_then_turn_advances`. Its behaviour now
lives in `test_approved_reaction_then_pe_question_then_grade` (Task 9).

In `test_website_say_command_is_spoken`, add this line before
`engine_worker.poll_once(...)`, so the Live flow doesn't run the
`awaiting_answer` turn:

```python
    monkeypatch.setattr(engine_worker.conversation_flow, "advance", lambda *a: False)
```

Change `test_react_turn_simulation_creates_no_robot_command`. Rename it to
`test_react_turn_moves_to_awaiting_pe`; its body stays the same.

Add:

```python
from tests.fakes import FakeRobot, heard


def test_live_session_runs_turns_back_to_back(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live", language="he")
    t1 = fake.add("Turn", session=session["id"], order=1, phase="Opening", generated_by_engine=True,
                  expects_answer=True, status="queued", question_text="")
    t2 = fake.add("Turn", session=session["id"], order=2, phase="Closing", generated_by_engine=True,
                  expects_answer=False, status="queued", question_text="")
    robot = FakeRobot(heard=[heard("שלום")])
    monkeypatch.setattr(engine_worker.conversation_flow, "furhat_client", robot)
    monkeypatch.setattr(engine_worker.conversation_flow.small_talk, "generate_line",
                        lambda *a, **k: "שורה")
    monkeypatch.setattr(engine_worker, "_personas_applied", {session["id"]})

    engine_worker.poll_once(robot_connected=True)

    assert fake.get("Turn", t1["id"])["status"] == "done"
    assert fake.get("Turn", t2["id"])["status"] == "done"


def test_live_session_stops_between_turns_when_not_running(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    fake.add("Turn", session=session["id"], order=1, status="queued")
    fake.add("Turn", session=session["id"], order=2, status="queued")
    advanced = []

    def finish_and_pause(turn, s, turns, robot_connected, propose):
        advanced.append(turn["order"])
        fake.update_record("Turn", turn["id"], {"status": "done"})
        fake.update_record("Session", session["id"], {"status": "Paused"})
        return True

    monkeypatch.setattr(engine_worker.conversation_flow, "advance", finish_and_pause)

    engine_worker.run_live_session(session, robot_connected=True)

    assert advanced == [1]


def test_live_session_without_turns_waits_for_the_website(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    monkeypatch.setattr(engine_worker, "_personas_applied", {session["id"]})

    engine_worker.poll_once(robot_connected=True)

    assert fake.list_records("Turn") == []


def test_live_session_adds_speech_context(fake, monkeypatch):
    participant = fake.add("Participant", gender="Female", first_name="דנה")
    persona = fake.add("Persona", furhat_voice="AvriNeural")
    session = fake.add("Session", status="Running", mode="Live", participant=participant["id"],
                       persona=persona["id"])
    fake.add("Turn", session=session["id"], order=1, status="queued")
    seen = {}
    monkeypatch.setattr(engine_worker.conversation_flow, "advance",
                        lambda turn, s, turns, robot_connected, propose: seen.update(session=s) or False)

    engine_worker.run_live_session(session, robot_connected=True)

    assert seen["session"]["participant_gender"] == "female"
    assert seen["session"]["robot_gender"] == "male"
    assert seen["session"]["participant_name"] == "דנה"


def test_live_session_passes_build_proposal(fake, monkeypatch):
    session = fake.add("Session", status="Running", mode="Live")
    fake.add("Turn", session=session["id"], order=1, status="queued")
    seen = {}
    monkeypatch.setattr(engine_worker.conversation_flow, "advance",
                        lambda turn, s, turns, robot_connected, propose: seen.update(propose=propose) or False)

    engine_worker.run_live_session(session, robot_connected=True)

    assert seen["propose"] is engine_worker.build_proposal
```

In `test_process_turn_writes_proposal_and_moves_to_approval`, add:

```python
    assert saved["engine_model"] == engine_worker.llm_client.current_model()
```

- [ ] **Step 2: Run them to see them fail**

Run: `pytest tests/test_engine_worker.py -v`
Expected: FAIL. `run_live_session` is missing, Live turns are not run, and
`engine_model` is missing.

- [ ] **Step 3: Implement** in `engine_worker.py`:

1. Add `import conversation_flow` to the imports.
2. Add this section before `# ── Main loop`:

```python
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
```

3. Replace the turn loop at the end of `poll_once` (from
   `handlers = {...}` to `return bool(sessions)`) with:

```python
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
    return bool(sessions)
```

4. Simplify `react_turn`. It now runs only for `Simulation` and `Mock`, since
   Live reactions live in `conversation_flow`. Delete `_command_for`. Keep
   `execute_command`: it still runs RobotCommands the website creates.

```python
def react_turn(turn: dict, session: dict) -> None:
    """Simulation/Mock: no robot, so the approved reaction just moves the turn on to the PE step."""
    b44.update_record("Turn", turn["id"], {"status": "awaiting_pe"})
```

5. In `process_turn`, add `"engine_model": llm_client.current_model(),` to the
   `update_record` fields of the success path.

6. Update the module docstring's "MVP scope" paragraph to:

```
Live sessions are run by the robot itself through conversation_flow.py
(small talk, questions, listening, reactions, PE). Simulation and Mock keep
the typed-answer flow below. Still deferred: expression_level, question sets
for Baseline/Post/Followup, English response bank, robot reset/stop.
```

- [ ] **Step 4: Run all tests and see them pass**

Run: `pytest tests/ -q`
Expected: all PASS. Write down the count it reports.

- [ ] **Step 5: Update the docs.**
  - **`CLAUDE.md`:**
    - In "Architecture", add one entry each for `conversation_flow.py`,
      `small_talk.py`, `acknowledgement.py`, `pe_feedback.py`, `llm_line.py`
      and `worker_common.py`. Match the style of the existing entries.
    - Update the `pe_check.py` description to Correct/Partial/Wrong, and the
      `engine_worker.py` entry: Live → `conversation_flow`, heartbeat thread.
    - Update the test count in "Commands" to the number from Step 4.
    - Add the smoke command
      `RUN_LLM_SMOKE=1 pytest tests/test_llm_smoke.py -v`.
  - **`SESSION_LOG.md`:** add a 2026-11-08 entry: Plan 2 built; what to run
    next (Task 11 live check); open questions P3 (Hebrew guardrail patterns)
    and P11 (word-list review).
  - **`PROJECT_PLAN.md`:** mark "Autonomous robot conversation" built and
    pending the live check.
  - **Autonomous spec status line:** "Built (Plan 2, 2026-11-08); live check
    pending."
  - **Integration spec decisions log:** add "Live sessions are autonomous
    (2026-11-08): see the autonomous-conversation spec. The typed-answer flow
    remains for Simulation/Mock."

- [ ] **Step 6: Commit**

```bash
git add engine_worker.py tests/test_engine_worker.py CLAUDE.md SESSION_LOG.md PROJECT_PLAN.md docs/superpowers/specs/2026-11-04-autonomous-robot-conversation-design.md docs/superpowers/specs/2026-11-02-base44-lab-app-integration-design.md
git commit -m "Run Live sessions through conversation_flow; record engine_model per turn"
```

---

### Task 11: Live check with the robot (researcher, manual)

Prerequisites:
- Task 1's prompt has been pasted and verified.
- The `InterviewSkill` built in Task 2 is loaded and shows
  `Listening on http://localhost:8765`.
- The researcher has reviewed the PE word lists (Task 5).
- **Only one** `engine_worker.py` is running.

- [ ] **Step 1: Smoke-test the prompts on the fast model**

```bash
set -a; source .env; set +a
RUN_LLM_SMOKE=1 pytest tests/test_llm_smoke.py -v
```

Expected: 5 PASS. If a PE example fails, adjust the word lists with the
researcher before going on.

- [ ] **Step 2: Start the worker** with `python engine_worker.py`. Expected:
  "LLM models synced", and the website shows the Engine as available (the
  heartbeat thread is running).

- [ ] **Step 3: Small talk.** On the website, set your participant's Gender and First name,
  then create a **Short** Live session with a Persona (for example Isabel +
  AvriNeural) and start it. Expected (also: the robot addresses you in the
  right gender and uses your name in small talk without asking for it, and
  questions with "/" are read as one form):
  - The face and voice change.
  - The robot greets you and asks an easy question.
  - Your answer appears on the website as "What the participant said".
  - The next line responds to it.
  - After the second opening turn, the first Main question starts without a
    long gap.

- [ ] **Step 4: A non-PBDI question.** Answer it. Expected: one short sentence
  that mentions what you said, with no praise and no comment on how you
  said it. Then the next question.

- [ ] **Step 5: A PBDI question.** Answer it. Expected:
  - The turn stops at "Needs your approval", showing the transcript, the
    emotion and the reply.
  - After Approve: the robot's face shows the emotion, it says the reply,
    then "מה לדעתך הרגשתי, ולמה?".
  - Answer it. The turn stops at "Feedback needs your approval", showing
    the grade and a feedback line.
  - After Approve: the robot says the feedback, and the next turn starts.

- [ ] **Step 6: Error paths.**
  - Stay silent on one question. Expected: the robot repeats it once, then
    the turn is Skipped ("No answer (silence)").
  - Stop the skill in the launcher during a question. Expected: within
    about 60 s the turn shows "robot disconnected" with Retry. Restart the
    skill and press Retry. Expected: the turn continues.

- [ ] **Step 7: Closing.** Expected: the robot thanks you, asks if you have
  questions, then says goodbye without listening. Complete the session on
  the website.

- [ ] **Step 8: Record results** in the autonomous spec under
  `## Live check results (date)`: what worked, wording problems in generated
  lines, and any Hebrew No-Masking issues for decision P3. Commit:

```bash
git add docs/superpowers/specs/2026-11-04-autonomous-robot-conversation-design.md
git commit -m "Record Plan 2 live check results"
```
