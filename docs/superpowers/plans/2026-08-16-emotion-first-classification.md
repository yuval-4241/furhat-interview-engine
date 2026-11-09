# Emotion-First Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the VA-first `emotion_bank.py` candidate-list mechanism with a new `emotion_classifier.py` that picks the robot's Ekman emotion directly from answer content, then derives `(valence, arousal)` from that pick for `response_bank.py`, instead of the other way around.

**Architecture:** A new module, `emotion_classifier.py`, makes one LLM call (`classify_emotion(question, answer_text)`) returning `{"emotion": ..., "intensity": ...}` from all 7 of Ekman's core emotions, independent of `evaluator.py`. `graph.py`'s `select_response()` calls it, derives `(valence, arousal)` via two fixed lookup tables (`emotion_classifier.derive_valence()`, `derive_arousal()`), and uses that derived pair — not the evaluator's own `valence`/`arousal` — to pick the spoken reply from `response_bank.py`. The classified `{emotion, intensity}` goes straight to `robot_bridge.send_reaction()` for the face. `evaluator.py` stays completely untouched; its own valence/arousal keep being logged and keep driving `guardrail.check_consistency()`, so two valence signals now coexist and can diverge — an accepted, measurable consequence, not a bug. `emotion_bank.py` and its supporting seed file, tests, and config flag are deleted (confirmed with the user) since this mechanism fully supersedes them.

**Tech Stack:** Python 3.10+, `llm_client.call_llm()` (OpenAI-compatible client), pytest with `monkeypatch`.

## Global Constraints

- `evaluator.py` must not be modified — methodology-locked, and the spec requires it stay untouched.
- No new config flag for this mechanism — it replaces `EMOTION_LLM_SELECTION_ENABLED` outright rather than adding a second toggle (per spec §5).
- `classify_emotion()` must fail closed on any malformed/unexpected LLM response — same philosophy as `emotion_bank.pick_emotion_llm()`'s `candidates[0]` fallback.
- Use `config.MODEL_FAST` semantics already baked into `llm_client.call_llm()`'s default (`model=None` → `config.MODEL_DEFAULT`) — don't pass an explicit model, matching `evaluator.evaluate()`'s existing pattern.
- Follow the project's TDD convention already used throughout this repo: write the failing test, watch it fail, implement, watch it pass, commit.

---

### Task 1: `emotion_classifier.py` — direct Ekman-emotion classification

**Files:**
- Create: `emotion_classifier.py`
- Test: `tests/test_emotion_classifier.py`

**Interfaces:**
- Consumes: `llm_client.call_llm(system, user_message, model=None, temperature=0.7, max_tokens=500) -> str` (existing, `llm_client.py`). `config.VALENCE_LEVELS = ["low", "medium", "high"]` (existing, `config.py`).
- Produces:
  - `CORE_EMOTIONS: list[str]` — `["ANGER", "CONTEMPT", "DISGUST", "FEAR", "HAPPINESS", "SADNESS", "SURPRISE"]`
  - `classify_emotion(question: str, answer_text: str) -> dict` — returns `{"emotion": str, "intensity": int}`, `emotion` always one of `CORE_EMOTIONS`, `intensity` always `1`, `2`, or `3`.
  - `derive_valence(emotion: str) -> str` — returns a value in `config.VALENCE_LEVELS`.
  - `derive_arousal(intensity: int) -> str` — returns a value in `config.VALENCE_LEVELS` (same 3-level scale, reused for arousal as elsewhere in this codebase).

These three names (`classify_emotion`, `derive_valence`, `derive_arousal`) are what Task 2's `graph.py` wiring calls directly — keep the signatures exact.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_emotion_classifier.py`:

```python
import config
import emotion_classifier
from emotion_classifier import classify_emotion, derive_valence, derive_arousal, CORE_EMOTIONS


def test_classify_emotion_parses_valid_llm_response(monkeypatch):
    monkeypatch.setattr(
        emotion_classifier.llm_client, "call_llm",
        lambda **k: '{"emotion": "FEAR", "intensity": 2}'
    )
    result = classify_emotion("Tell me about a challenge", "I was scared I'd miss the deadline.")
    assert result == {"emotion": "FEAR", "intensity": 2}


def test_classify_emotion_strips_code_fences(monkeypatch):
    monkeypatch.setattr(
        emotion_classifier.llm_client, "call_llm",
        lambda **k: '```json\n{"emotion": "HAPPINESS", "intensity": 3}\n```'
    )
    result = classify_emotion("Q", "A")
    assert result == {"emotion": "HAPPINESS", "intensity": 3}


def test_classify_emotion_falls_back_on_non_json(monkeypatch):
    monkeypatch.setattr(emotion_classifier.llm_client, "call_llm", lambda **k: "not json at all")
    result = classify_emotion("Q", "A")
    assert result == {"emotion": "SURPRISE", "intensity": 2}


def test_classify_emotion_falls_back_on_unknown_emotion(monkeypatch):
    monkeypatch.setattr(
        emotion_classifier.llm_client, "call_llm",
        lambda **k: '{"emotion": "LOVE", "intensity": 2}'
    )
    result = classify_emotion("Q", "A")
    assert result == {"emotion": "SURPRISE", "intensity": 2}


def test_classify_emotion_falls_back_on_out_of_range_intensity(monkeypatch):
    monkeypatch.setattr(
        emotion_classifier.llm_client, "call_llm",
        lambda **k: '{"emotion": "SADNESS", "intensity": 7}'
    )
    result = classify_emotion("Q", "A")
    assert result == {"emotion": "SURPRISE", "intensity": 2}


def test_classify_emotion_falls_back_on_missing_keys(monkeypatch):
    monkeypatch.setattr(
        emotion_classifier.llm_client, "call_llm",
        lambda **k: '{"emotion": "SADNESS"}'
    )
    result = classify_emotion("Q", "A")
    assert result == {"emotion": "SURPRISE", "intensity": 2}


def test_every_core_emotion_maps_to_a_valid_valence():
    for emotion in CORE_EMOTIONS:
        assert derive_valence(emotion) in config.VALENCE_LEVELS


def test_derive_arousal_covers_all_three_intensities():
    assert derive_arousal(1) == "low"
    assert derive_arousal(2) == "medium"
    assert derive_arousal(3) == "high"


def test_happiness_maps_to_high_valence():
    assert derive_valence("HAPPINESS") == "high"


def test_surprise_maps_to_medium_valence():
    assert derive_valence("SURPRISE") == "medium"


def test_negative_emotions_map_to_low_valence():
    for emotion in ("ANGER", "CONTEMPT", "DISGUST", "FEAR", "SADNESS"):
        assert derive_valence(emotion) == "low"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_emotion_classifier.py -v`
Expected: FAIL / collection error — `emotion_classifier` module does not exist yet.

- [ ] **Step 3: Write the implementation**

Create `emotion_classifier.py`:

```python
"""
Emotion Classifier — direct Ekman-emotion classification for the Furhat
face+voice reaction, independent of evaluator.py.

One LLM call, sees only (question, answer_text) -- not the evaluator's
rationale or category -- so this stays a genuinely separate read on the
answer's emotional content rather than a restatement of the evaluator's
own judgment. Picks freely among all 7 of Ekman's core emotions, no
register restriction (unlike the earlier VA-keyed emotion_bank.py, which
excluded ANGER/CONTEMPT/DISGUST as "too hostile" -- that restriction was
a property of the old mechanism, deliberately dropped here). See
docs/superpowers/specs/2026-08-16-emotion-first-classification-design.md.

response_bank.py still needs a (valence, arousal) pair to pick spoken
text, so this module also derives one from the classification result --
valence from a fixed emotion lookup, arousal from intensity -- rather
than reusing evaluator.py's own valence/arousal. Face (the classified
emotion) and text (the derived-VA response) both trace back to this one
classify_emotion() call, preserving the "one source of truth" coherence
guarantee from the original VA-first design.
"""

import json
import re
import config
import llm_client

CORE_EMOTIONS = ["ANGER", "CONTEMPT", "DISGUST", "FEAR", "HAPPINESS", "SADNESS", "SURPRISE"]

# Grounded in Schneider et al. (2025)'s circumplex quadrants: HAPPINESS in
# the positive/high-arousal quadrant, the rest in the negative quadrants,
# SURPRISE conventionally placed near-neutral valence at high arousal.
EMOTION_TO_VALENCE = {
    "HAPPINESS": "high",
    "SURPRISE": "medium",
    "ANGER": "low",
    "CONTEMPT": "low",
    "DISGUST": "low",
    "FEAR": "low",
    "SADNESS": "low",
}

# Arousal is derived from intensity, NOT fixed per emotion -- fixing both
# per emotion would make most of response_bank.py's 9 VA cells permanently
# unreachable (e.g. HAPPINESS always landing on high/high). This keeps all
# 9 cells reachable via at least one emotion at some intensity.
INTENSITY_TO_AROUSAL = {1: "low", 2: "medium", 3: "high"}

# Fail-closed default when the LLM returns something unparseable/invalid --
# same "fail closed" philosophy as emotion_bank.pick_emotion_llm()'s
# candidates[0] fallback. SURPRISE/2 is the mid-valence, mid-intensity
# cell: a parsing failure implies neither a positive nor a negative read.
_FALLBACK = {"emotion": "SURPRISE", "intensity": 2}

_SYSTEM_PROMPT = (
    "You are classifying the emotional content of a job interview answer, "
    "independent of how good or bad the answer is. Pick exactly one of "
    "Ekman's core emotions that best fits the answer's content: "
    "ANGER, CONTEMPT, DISGUST, FEAR, HAPPINESS, SADNESS, SURPRISE. "
    "Also rate its intensity from 1 (mild) to 3 (strong).\n\n"
    "Respond with ONLY a JSON object of the exact shape: "
    '{"emotion": "<ONE_OF_THE_7_WORDS_ABOVE>", "intensity": <1, 2, or 3>}'
)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def classify_emotion(question: str, answer_text: str) -> dict:
    user_message = f"Interview question: {question}\n\nCandidate answer: {answer_text}"

    raw = llm_client.call_llm(
        system=_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=50,
        temperature=0.3,  # judgment task, not creative
    )
    raw = _strip_fences(raw)

    try:
        data = json.loads(raw)
        emotion = data["emotion"]
        intensity = int(data["intensity"])
        if emotion not in EMOTION_TO_VALENCE or intensity not in INTENSITY_TO_AROUSAL:
            raise ValueError(f"Unexpected emotion/intensity: {data!r}")
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return dict(_FALLBACK)

    return {"emotion": emotion, "intensity": intensity}


def derive_valence(emotion: str) -> str:
    return EMOTION_TO_VALENCE[emotion]


def derive_arousal(intensity: int) -> str:
    return INTENSITY_TO_AROUSAL[intensity]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_emotion_classifier.py -v`
Expected: PASS (all 12 tests)

- [ ] **Step 5: Commit**

```bash
git add emotion_classifier.py tests/test_emotion_classifier.py
git commit -m "Add emotion_classifier.py: direct Ekman-emotion classification, independent of evaluator.py"
```

---

### Task 2: Wire `emotion_classifier` into `graph.py`'s `select_response()`

**Files:**
- Modify: `graph.py` (imports at top, `ConversationState` comment at line 42, `select_response()` at lines 154-170, remove `_emotion_bank = EmotionBank()` at line 48, module docstring line 9)
- Modify: `tests/test_graph_robot_reaction.py`

**Interfaces:**
- Consumes: `emotion_classifier.classify_emotion(question, answer_text) -> dict` (Task 1), `emotion_classifier.derive_valence(emotion) -> str` (Task 1), `emotion_classifier.derive_arousal(intensity) -> str` (Task 1), `_response_bank.get(valence, arousal) -> str` (existing, `response_bank.py`), `robot_bridge.send_reaction(emotion, intensity, text=None) -> dict` (existing, unchanged).
- Produces: `select_response(state) -> dict` still returns the same shape (`final_response`, `emotion_reaction`, `robot_reaction`, `routed_to`) — only how `emotion_reaction` and the VA pair fed to `response_bank.get()` are computed changes.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/test_graph_robot_reaction.py`:

```python
import json

import graph


def test_select_response_includes_disabled_robot_reaction_by_default(monkeypatch):
    monkeypatch.setattr(graph.config, "ROBOT_REACTION_ENABLED", False)
    monkeypatch.setattr(
        graph.emotion_classifier, "classify_emotion",
        lambda **k: {"emotion": "SURPRISE", "intensity": 2}
    )

    state = {
        "question": "Q",
        "answer_text": "A",
        "evaluation": {"category": "GOOD", "valence": "medium", "arousal": "medium", "confidence": 0.9},
    }
    result = graph.select_response(state)

    assert result["robot_reaction"] == {"sent": False, "reason": "disabled"}
    assert result["routed_to"] == "finalized"
    assert result["final_response"]  # still picks a real text reply

    # emotion_reaction is exactly what classify_emotion returned -- no VA
    # lookup involved on this side anymore.
    assert result["emotion_reaction"] == {"emotion": "SURPRISE", "intensity": 2}


def test_select_response_sends_reaction_when_enabled(monkeypatch):
    monkeypatch.setattr(graph.config, "ROBOT_REACTION_ENABLED", True)
    monkeypatch.setattr(
        graph.emotion_classifier, "classify_emotion",
        lambda **k: {"emotion": "HAPPINESS", "intensity": 3}
    )

    captured = {}

    def fake_send_reaction(emotion, intensity, text=None):
        captured["emotion"] = emotion
        captured["intensity"] = intensity
        captured["text"] = text
        return {"sent": True, "reason": None}

    monkeypatch.setattr(graph.robot_bridge, "send_reaction", fake_send_reaction)

    state = {
        "question": "Q",
        "answer_text": "A",
        "evaluation": {"category": "GOOD", "valence": "high", "arousal": "high", "confidence": 0.9},
    }
    result = graph.select_response(state)

    assert captured["emotion"] == "HAPPINESS"
    assert captured["intensity"] == 3
    assert captured["text"] == result["final_response"]  # same text response_bank picked
    assert result["robot_reaction"] == {"sent": True, "reason": None}
    assert result["emotion_reaction"] == {"emotion": "HAPPINESS", "intensity": 3}


def test_select_response_derives_va_from_classified_emotion_not_evaluator(monkeypatch):
    """The spoken reply must come from the classified emotion's derived
    (valence, arousal), not from evaluator's own valence/arousal -- the two
    signals are allowed to diverge by design (see spec section 4)."""
    monkeypatch.setattr(graph.config, "ROBOT_REACTION_ENABLED", False)
    monkeypatch.setattr(
        graph.emotion_classifier, "classify_emotion",
        lambda **k: {"emotion": "SADNESS", "intensity": 1}  # derives to low/low
    )

    captured = {}
    monkeypatch.setattr(
        graph._response_bank, "get",
        lambda valence, arousal: captured.setdefault("va", (valence, arousal)) or "some reply"
    )

    # Evaluator's own valence/arousal is deliberately the OPPOSITE of what
    # SADNESS/1 derives to, to prove select_response() ignores it.
    state = {
        "question": "Q",
        "answer_text": "A",
        "evaluation": {"category": "GOOD", "valence": "high", "arousal": "high", "confidence": 0.9},
    }
    result = graph.select_response(state)

    assert captured["va"] == ("low", "low")
    assert result["final_response"] == "some reply"


def test_select_response_does_not_mutate_evaluators_own_valence_arousal(monkeypatch):
    monkeypatch.setattr(graph.config, "ROBOT_REACTION_ENABLED", False)
    monkeypatch.setattr(
        graph.emotion_classifier, "classify_emotion",
        lambda **k: {"emotion": "FEAR", "intensity": 3}
    )

    evaluation = {"category": "GOOD", "valence": "high", "arousal": "high", "confidence": 0.9}
    state = {"question": "Q", "answer_text": "A", "evaluation": dict(evaluation)}
    graph.select_response(state)

    # select_response() derives its own VA pair from the classified emotion
    # for response_bank/robot_bridge -- it must never touch the evaluator's
    # own valence/arousal, which guardrail.check_consistency() and
    # run_log.jsonl still depend on independently.
    assert state["evaluation"] == evaluation


def test_finalize_logs_robot_reaction_field(monkeypatch, tmp_path):
    log_path = tmp_path / "run_log.jsonl"
    monkeypatch.setattr(graph.config, "RUN_LOG_PATH", str(log_path))
    monkeypatch.setattr(graph.config, "DATA_DIR", str(tmp_path))

    state = {
        "question": "Q",
        "persona": "concise_confident",
        "answer_text": "A",
        "evaluation": {"category": "GOOD", "valence": "medium", "arousal": "medium", "confidence": 0.9},
        "guardrail_result": {"passed": True, "matched_patterns": [], "style_leakage_score": 0},
        "consistency": {"consistent": True, "note": None},
        "final_response": "some reply",
        "routed_to": "finalized",
        "robot_reaction": {"sent": False, "reason": "disabled"},
        "emotion_reaction": {"emotion": "SURPRISE", "intensity": 2},
    }
    graph.finalize(state)

    with open(log_path) as f:
        record = json.loads(f.readline())
    assert record["robot_reaction"] == {"sent": False, "reason": "disabled"}
    assert record["emotion_reaction"] == {"emotion": "SURPRISE", "intensity": 2}


def test_finalize_logs_null_robot_reaction_on_review_queue_path(monkeypatch, tmp_path):
    log_path = tmp_path / "run_log.jsonl"
    monkeypatch.setattr(graph.config, "RUN_LOG_PATH", str(log_path))
    monkeypatch.setattr(graph.config, "DATA_DIR", str(tmp_path))

    # route_to_review never calls select_response, so robot_reaction is
    # never set on this path -- same absent-key pattern as guardrail_result
    # on the schema_invalid path.
    state = {
        "question": "Q",
        "persona": "concise_confident",
        "answer_text": "A",
        "evaluation": {"category": "NEUTRAL", "valence": "medium", "arousal": "medium", "confidence": 0.5},
        "guardrail_result": {"passed": True, "matched_patterns": [], "style_leakage_score": 0},
        "consistency": {"consistent": True, "note": None},
        "final_response": None,
        "routed_to": "review_queue",
    }
    graph.finalize(state)

    with open(log_path) as f:
        record = json.loads(f.readline())
    assert record["robot_reaction"] is None
    assert record["emotion_reaction"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_graph_robot_reaction.py -v`
Expected: FAIL — `graph` has no attribute `emotion_classifier`, and `select_response()` still uses the old `_emotion_bank`/VA-based flow so the derived-VA test fails.

- [ ] **Step 3: Update `graph.py`**

In the module docstring (around line 9), change:

```python
Wires together personas.py, evaluator.py, guardrail.py, response_bank.py,
emotion_bank.py, robot_bridge.py, and review_queue.py without modifying
their internals.
```

to:

```python
Wires together personas.py, evaluator.py, guardrail.py, response_bank.py,
emotion_classifier.py, robot_bridge.py, and review_queue.py without
modifying their internals.
```

Change the imports block (around line 29):

```python
from response_bank import ResponseBank
from emotion_bank import EmotionBank
from schemas import EvaluatorOutputSchema
```

to:

```python
from response_bank import ResponseBank
import emotion_classifier
from schemas import EvaluatorOutputSchema
```

Change the `ConversationState` comment (line 42):

```python
    emotion_reaction: dict    # emotion, intensity — from emotion_bank.get(), always computed
```

to:

```python
    emotion_reaction: dict    # emotion, intensity — from emotion_classifier.classify_emotion(), always computed
```

Change the bank instantiation (lines 47-48):

```python
_response_bank = ResponseBank()
_emotion_bank = EmotionBank()
```

to:

```python
_response_bank = ResponseBank()
```

Replace `select_response()` (lines 154-170):

```python
def select_response(state: ConversationState) -> dict:
    ev = state["evaluation"]
    response = _response_bank.get(ev["valence"], ev["arousal"])

    reaction = _emotion_bank.get(
        ev["valence"], ev["arousal"],
        question=state.get("question"), answer_text=state.get("answer_text"),
        rationale=ev.get("rationale"),
    )
    robot_reaction = robot_bridge.send_reaction(reaction["emotion"], reaction["intensity"], text=response)

    return {
        "final_response": response,
        "emotion_reaction": reaction,
        "robot_reaction": robot_reaction,
        "routed_to": "finalized",
    }
```

with:

```python
def select_response(state: ConversationState) -> dict:
    reaction = emotion_classifier.classify_emotion(
        question=state.get("question"), answer_text=state.get("answer_text")
    )
    derived_valence = emotion_classifier.derive_valence(reaction["emotion"])
    derived_arousal = emotion_classifier.derive_arousal(reaction["intensity"])
    response = _response_bank.get(derived_valence, derived_arousal)

    robot_reaction = robot_bridge.send_reaction(reaction["emotion"], reaction["intensity"], text=response)

    return {
        "final_response": response,
        "emotion_reaction": reaction,
        "robot_reaction": robot_reaction,
        "routed_to": "finalized",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_graph_robot_reaction.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `pytest tests/ -v`
Expected: All tests pass except `tests/test_emotion_bank.py`, which will fail/error because `select_response()` no longer references `_emotion_bank` — this is expected here and gets deleted in Task 4. If anything else fails, stop and investigate before continuing.

- [ ] **Step 6: Commit**

```bash
git add graph.py tests/test_graph_robot_reaction.py
git commit -m "Wire emotion_classifier into select_response(), replacing VA-first emotion_bank lookup"
```

---

### Task 3: Update `demo_app.py` to show the classified emotion and its derived VA

**Files:**
- Modify: `demo_app.py` (imports around line 13-18, reaction display block at lines 105-113)

**Interfaces:**
- Consumes: `emotion_classifier.derive_valence(emotion) -> str`, `emotion_classifier.derive_arousal(intensity) -> str` (Task 1). `state["emotion_reaction"]` shape is unchanged (`{"emotion": str, "intensity": int}`), still set by `graph.select_response()` (Task 2).

No test file — this is a Streamlit UI script with no unit tests elsewhere in the repo; verify with a manual run per Step 3.

- [ ] **Step 1: Add the `emotion_classifier` import**

In `demo_app.py`, change:

```python
import config
import graph
from question_bank import QuestionBank
from prompts.persona_prompts import PERSONAS
```

to:

```python
import config
import graph
import emotion_classifier
from question_bank import QuestionBank
from prompts.persona_prompts import PERSONAS
```

- [ ] **Step 2: Replace the reaction display block**

The old block (lines 105-113) read the VA cell straight off `graph._emotion_bank`, which no longer exists after Task 2. Replace:

```python
            reaction = state["emotion_reaction"]
            cell_key = config.va_cell_key(ev["valence"], ev["arousal"])
            candidates = graph._emotion_bank._data[cell_key]["candidates"]
            selection_mode = "LLM-picked" if config.EMOTION_LLM_SELECTION_ENABLED else "default"
            st.write(
                f"**Robot's facial reaction:** {reaction['emotion']} "
                f"(intensity {reaction['intensity']}/3) — {selection_mode} from "
                f"{candidates} for {ev['valence']} valence, always computed, sent or not."
            )
```

with:

```python
            reaction = state["emotion_reaction"]
            derived_valence = emotion_classifier.derive_valence(reaction["emotion"])
            derived_arousal = emotion_classifier.derive_arousal(reaction["intensity"])
            st.write(
                f"**Robot's facial reaction:** {reaction['emotion']} "
                f"(intensity {reaction['intensity']}/3) → derived valence/arousal: "
                f"{derived_valence}/{derived_arousal}, always computed, sent or not."
            )
            if derived_valence != ev["valence"] or derived_arousal != ev["arousal"]:
                st.caption(
                    f"Note: evaluator's own interpretive stance ({ev['valence']}/{ev['arousal']}) "
                    f"differs from the classified-emotion-derived pair used for the spoken reply "
                    f"({derived_valence}/{derived_arousal}). Both are logged; this divergence is "
                    "expected, not a bug — see docs/superpowers/specs/"
                    "2026-08-16-emotion-first-classification-design.md."
                )
```

- [ ] **Step 3: Manually verify**

Run: `streamlit run demo_app.py`

In the browser: pick any session/question/persona, click "Run conversation", and confirm stage 4 shows "Robot's facial reaction: ... → derived valence/arousal: .../..." with no `AttributeError` (confirms `graph._emotion_bank` is fully gone from this file) and no `KeyError`. Stop the Streamlit process after confirming.

- [ ] **Step 4: Commit**

```bash
git add demo_app.py
git commit -m "Update demo_app.py to show classify_emotion's derived valence/arousal"
```

---

### Task 4: Delete the superseded `emotion_bank.py` mechanism

**Files:**
- Delete: `emotion_bank.py`, `data/emotion_bank_seed.json`, `tests/test_emotion_bank.py`
- Modify: `config.py` (remove `EMOTION_BANK_PATH`, remove the `EMOTION_LLM_SELECTION_ENABLED` block)
- Modify: `robot_bridge.py` (docstring line 2)

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — this is a pure removal task. Confirmed with the user this session: delete, don't leave dormant (the old candidate-list mechanism shipped and was superseded same-day; keeping two parallel emotion-selection systems adds complexity with no benefit).

- [ ] **Step 1: Delete the dead files**

```bash
git rm emotion_bank.py data/emotion_bank_seed.json tests/test_emotion_bank.py
```

- [ ] **Step 2: Remove the now-unused config entries**

In `config.py`, remove this line from the "File locations" section:

```python
EMOTION_BANK_PATH = os.path.join(DATA_DIR, "emotion_bank_seed.json")
```

Remove this entire block at the end of the file (the comment plus the assignment):

```python
# Off by default — when False, EmotionBank.get() deterministically picks
# candidates[0] for each cell, no LLM call, free. When True, an LLM picks
# among that cell's pre-approved (valence-consistent) candidates based on
# the actual answer content, for variety without risking a face that
# contradicts the spoken reply's tone. Independent of ROBOT_REACTION_ENABLED
# so the variety is visible in demo_app.py even without a robot connected.
EMOTION_LLM_SELECTION_ENABLED = os.environ.get("EMOTION_LLM_SELECTION_ENABLED", "false").lower() == "true"
```

- [ ] **Step 3: Fix the stale docstring reference in `robot_bridge.py`**

In `robot_bridge.py`, change:

```python
Robot Reaction Bridge — sends emotion_bank's (emotion, intensity) pick,
plus response_bank's spoken reply text, to furhat-emotion-study's
```

to:

```python
Robot Reaction Bridge — sends emotion_classifier's (emotion, intensity) pick,
plus response_bank's spoken reply text, to furhat-emotion-study's
```

- [ ] **Step 4: Run the full suite**

Run: `pytest tests/ -v`
Expected: All tests pass, with no references to `emotion_bank` or `EMOTION_LLM_SELECTION_ENABLED` remaining anywhere. Confirm with:

```bash
grep -rn "emotion_bank\|EmotionBank\|EMOTION_LLM_SELECTION_ENABLED\|EMOTION_BANK_PATH" . --include="*.py"
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add config.py robot_bridge.py
git commit -m "Remove superseded emotion_bank.py mechanism (replaced by emotion_classifier.py)"
```

---

### Task 5: Update `CLAUDE.md` architecture documentation

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing — documentation only.
- Produces: nothing consumed by later tasks — this is the last task.

- [ ] **Step 1: Replace the `emotion_bank.py` bullet with `emotion_classifier.py`**

In the `## Architecture` section, change:

```markdown
- **`emotion_bank.py`** — companion to `response_bank.py`: same
  `(valence, arousal)` input, same 3×3-grid pattern, but returns a Furhat
  facial emotion + intensity (`data/emotion_bank_seed.json`) instead of
  reply text. Deliberately reads the *same* VA pair as the text reply
  rather than a second, independent judgment, so the robot's face and
  spoken reply can never contradict each other.
```

to:

```markdown
- **`emotion_classifier.py`** — `classify_emotion(question, answer_text)`,
  one LLM call, independent of `evaluator.py` (no shared prompt, no shared
  code — sees only the question and answer text). Picks freely among all
  7 of Ekman's core emotions (Anger, Contempt, Disgust, Fear, Happiness,
  Sadness, Surprise) plus an intensity 1-3. `derive_valence()` and
  `derive_arousal()` then turn that pick into a `(valence, arousal)` pair
  for `response_bank.py`'s spoken reply — valence from a fixed
  emotion→valence table, arousal from intensity — so the robot's face
  (the classified emotion) and spoken reply (the derived-VA text) both
  trace back to the same classification call and can never contradict
  each other. This is "emotion-first": the reverse of the earlier
  VA-first `emotion_bank.py` mechanism it replaces. See
  `docs/superpowers/specs/2026-08-16-emotion-first-classification-design.md`.
```

- [ ] **Step 2: Clarify what `evaluator.py`'s valence/arousal still drive**

Find the `evaluator.py` bullet in the same section (starts with `- **\`evaluator.py\`** (#2) — \`evaluate()\` makes one LLM call...`). At the end of that bullet's paragraph, append this sentence:

```markdown
  Its `valence`/`arousal` still feed `EvaluatorOutputSchema` validation,
  `guardrail.check_consistency()`, and `run_log.jsonl` — since
  `emotion_classifier.py` was introduced, they no longer determine the
  robot's spoken reply or facial reaction, which are driven by an
  independently classified emotion instead. The two valence signals can
  diverge; both are logged, and that divergence is intentional, not a bug.
```

- [ ] **Step 3: Verify the edit renders correctly**

Run: `grep -n "emotion_classifier\|emotion_bank" CLAUDE.md`
Expected: only the new `emotion_classifier.py` references remain — no `emotion_bank.py` mentions left.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "Update CLAUDE.md: document emotion_classifier.py replacing emotion_bank.py"
```
