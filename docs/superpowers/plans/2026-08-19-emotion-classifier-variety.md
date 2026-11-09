# Emotion Classifier Variety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `emotion_classifier.py`'s observed HAPPINESS-default skew on bland/factual answers by adding a chain-of-thought cue step and an explicit anti-default instruction to its prompt, plus raising `temperature` for mechanical variety — without changing `classify_emotion()`'s return shape or any downstream caller.

**Architecture:** Single-file change to `emotion_classifier.py`'s `_SYSTEM_PROMPT` and the `llm_client.call_llm()` call inside `classify_emotion()`. The LLM's raw JSON response gains an optional `"cue"` field (the specific word/phrase driving its judgment), read via `.get()` and discarded after parsing — `emotion`/`intensity` remain the only fields that matter for the return value and the fail-closed fallback. No other file changes.

**Tech Stack:** Python 3.10+, `llm_client.call_llm()`, pytest with `monkeypatch`.

## Global Constraints

- `classify_emotion(question, answer_text) -> dict` must keep returning exactly `{"emotion": str, "intensity": int}` — no `"cue"` key in the return value, ever.
- `"cue"` is read with `.get("cue")`, never `["cue"]` — a response missing it must not trigger the fail-closed fallback on its own.
- `derive_valence()`, `derive_arousal()`, `EMOTION_TO_VALENCE`, `INTENSITY_TO_AROUSAL`, `CORE_EMOTIONS`, `_FALLBACK` stay unchanged.
- `graph.py`, `robot_bridge.py`, `demo_app.py` are not touched — none of them reference the prompt or temperature directly.
- Every existing test in `tests/test_emotion_classifier.py` must keep passing unchanged (they mock two-key JSON responses with no `"cue"`).

---

### Task 1: Add chain-of-thought cue + anti-default prompt + temperature bump

**Files:**
- Modify: `emotion_classifier.py` (`_SYSTEM_PROMPT`, `classify_emotion()`)
- Test: `tests/test_emotion_classifier.py`

**Interfaces:**
- Consumes: `llm_client.call_llm(system, user_message, model=None, temperature=0.7, max_tokens=500) -> str` (existing, unchanged).
- Produces: `classify_emotion(question, answer_text) -> dict` — same signature and return shape as before (`{"emotion": str, "intensity": int}`), used unchanged by `graph.py`'s `select_response()`.

- [ ] **Step 1: Write the failing test for the new `"cue"` handling**

Add to `tests/test_emotion_classifier.py` (after the existing `test_classify_emotion_strips_code_fences` test):

```python
def test_classify_emotion_discards_cue_field_from_return_value(monkeypatch):
    """The chain-of-thought "cue" field is a reasoning scratchpad the model
    fills in before naming the emotion -- it must never appear in
    classify_emotion()'s return value, only emotion/intensity do."""
    monkeypatch.setattr(
        emotion_classifier.llm_client, "call_llm",
        lambda **k: '{"cue": "no complaints, flat factual tone", "emotion": "SURPRISE", "intensity": 1}'
    )
    result = classify_emotion("Tell me about yourself", "I have 5 years of experience in QA.")
    assert result == {"emotion": "SURPRISE", "intensity": 1}
    assert "cue" not in result


def test_classify_emotion_uses_higher_temperature_for_variety(monkeypatch):
    captured = {}

    def fake_call_llm(**kwargs):
        captured.update(kwargs)
        return '{"cue": "none", "emotion": "HAPPINESS", "intensity": 2}'

    monkeypatch.setattr(emotion_classifier.llm_client, "call_llm", fake_call_llm)
    classify_emotion("Q", "A")

    assert captured["temperature"] == 0.8
```

Note: `test_classify_emotion_parses_valid_llm_response` (already in the file, mocks a two-key JSON response with no `"cue"`) already covers the backward-compatibility requirement from the spec — a response without `"cue"` must still parse successfully. No new test needed for that; it will simply keep passing once Step 3 lands, since `"cue"` is read with `.get()`.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `pytest tests/test_emotion_classifier.py -v`
Expected: `test_classify_emotion_discards_cue_field_from_return_value` FAILS (current code doesn't reject unknown JSON keys, so it likely already passes — check the actual output; if it already passes, that's fine, it's still a valid regression guard going forward). `test_classify_emotion_uses_higher_temperature_for_variety` FAILS — current `temperature` is `0.3`, not `0.8`.

- [ ] **Step 3: Update `emotion_classifier.py`**

Replace `_SYSTEM_PROMPT`:

```python
_SYSTEM_PROMPT = (
    "You are classifying the emotional content of a job interview answer, "
    "independent of how good or bad the answer is.\n\n"
    "First, find the specific word or phrase in the answer that most "
    "signals an emotion -- not the overall tone of a confident or "
    "professional-sounding answer, just what's actually there. Generic "
    "confident or professional phrasing on its own is not a signal of "
    "happiness -- if an answer is simply factual with no real emotional "
    "language, prefer SURPRISE (noteworthy, not positive or negative) "
    "over defaulting to HAPPINESS.\n\n"
    "Then pick exactly one of Ekman's core emotions that best fits: "
    "ANGER, CONTEMPT, DISGUST, FEAR, HAPPINESS, SADNESS, SURPRISE. "
    "Also rate its intensity from 1 (mild) to 3 (strong).\n\n"
    "Respond with ONLY a JSON object of the exact shape: "
    '{"cue": "<the word or phrase, or \\"none\\" if truly nothing '
    'stands out>", "emotion": "<ONE_OF_THE_7_WORDS_ABOVE>", '
    '"intensity": <1, 2, or 3>}'
)
```

Replace the body of `classify_emotion()`:

```python
def classify_emotion(question: str, answer_text: str) -> dict:
    user_message = f"Interview question: {question}\n\nCandidate answer: {answer_text}"

    raw = llm_client.call_llm(
        system=_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=80,
        temperature=0.8,  # variety over reproducibility -- see spec
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
```

(This is unchanged from the current implementation except `max_tokens=50` → `80` and `temperature=0.3` → `0.8` — the `"cue"` field is present in the model's JSON response but was never read into `data["emotion"]`/`data["intensity"]` in the first place, so no parsing change is needed for it to be silently ignored. Only `emotion`/`intensity` are ever pulled out of `data`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_emotion_classifier.py -v`
Expected: PASS (all tests, including the 2 new ones).

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `pytest tests/ -v`
Expected: All tests pass (67 + 2 new = 69).

- [ ] **Step 6: Manual live sanity check**

Run:

```bash
source venv/bin/activate
LLM_PROVIDER=openai python3 -c "
import emotion_classifier as ec

cases = [
    ('Tell me about your strengths', 'I am very organized and detail-oriented.'),
    ('Tell me about yourself', 'I have 5 years of experience in QA testing.'),
]
for q, a in cases:
    print(ec.classify_emotion(q, a), '<-', a)
"
```

This is not a pytest assertion (LLM output at `temperature=0.8` isn't
deterministic) — just confirm the two previously-always-HAPPINESS bland
answers now sometimes classify as something other than HAPPINESS (e.g.
SURPRISE), and that no exception is raised.

- [ ] **Step 7: Commit**

```bash
git add emotion_classifier.py tests/test_emotion_classifier.py
git commit -m "Add CoT cue + anti-default prompt and raise temperature in emotion_classifier.py"
```
