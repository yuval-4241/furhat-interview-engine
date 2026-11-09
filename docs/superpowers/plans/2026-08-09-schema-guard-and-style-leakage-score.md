# Schema Guard + Style-Leakage Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two real gaps identified in `docs/unified_architecture.md` (Task 1): the evaluator's structured output isn't validated before it's trusted, and the No-Masking guardrail only returns yes/no, not a severity number.

**Architecture:** Add a small, additive Pydantic validation layer (`schemas.py`) that checks `evaluator.py`'s output against `config.py`'s existing category/valence/arousal enums, with a one-shot LLM retry on failure and a new `review_queue` reason (`"schema_invalid"`) as the last resort. Separately, extend `guardrail.py`'s existing `GuardrailResult` with a derived `style_leakage_score` (count of matched patterns) — nothing existing changes shape, only gains new fields.

**Tech Stack:** Python 3.10+, Pydantic (new dependency), pytest (new dependency — this project currently has zero automated tests), LangGraph (existing).

## Global Constraints

- Don't modify `config.py`'s `NO_MASKING_FLAG_PATTERNS` or `PERSONAS` without flagging — this plan does not touch either, only reads `config.QUALITY_CATEGORIES`/`VALENCE_LEVELS`/`AROUSAL_LEVELS`.
- `guardrail.py`'s existing `passed`/`matched_patterns` fields and `.as_dict()` keys must stay backward compatible — only additive changes.
- Never commit `.env` or hardcode API tokens.
- This project has no `tests/` directory or pytest config yet — this plan creates both.

---

### Task 1: Schema Guard — `schemas.py`

**Files:**
- Create: `schemas.py`
- Modify: `requirements.txt`
- Test: `tests/test_schemas.py`

**Interfaces:**
- Produces: `schemas.EvaluatorOutputSchema` (Pydantic `BaseModel`) — a class with fields `category: Literal["GOOD","NEUTRAL","BAD"]`, `valence: Literal["low","medium","high"]`, `arousal: Literal["low","medium","high"]`, `confidence: float` (bounded 0.0-1.0), `rationale: str` (min length 1). Raises `pydantic.ValidationError` on invalid input. Consumed by Task 4.

- [ ] **Step 1: Add pydantic and pytest to requirements.txt**

Edit `requirements.txt` to add two lines at the end:

```
openai>=1.0
langgraph
streamlit
pandas
scipy
pydantic
pytest
```

- [ ] **Step 2: Install the new dependencies**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pip install -r requirements.txt`
Expected: pydantic and pytest install without errors.

- [ ] **Step 3: Create the tests directory and write the failing tests**

Create `tests/__init__.py` (empty file — makes `tests` an importable package so `import config`/`import schemas` resolve the same way from inside test files as from the project root).

Create `tests/test_schemas.py`:

```python
import typing

import pytest
from pydantic import ValidationError

import config
from schemas import EvaluatorOutputSchema


def test_valid_evaluation_passes():
    data = {
        "category": "GOOD",
        "valence": "medium",
        "arousal": "medium",
        "confidence": 0.9,
        "rationale": "Answer is specific and on-topic.",
    }
    result = EvaluatorOutputSchema(**data)
    assert result.category == "GOOD"
    assert result.confidence == 0.9


def test_invalid_category_rejected():
    data = {
        "category": "good",  # lowercase — not one of GOOD/NEUTRAL/BAD
        "valence": "medium",
        "arousal": "medium",
        "confidence": 0.9,
        "rationale": "Answer is specific and on-topic.",
    }
    with pytest.raises(ValidationError):
        EvaluatorOutputSchema(**data)


def test_confidence_above_one_rejected():
    data = {
        "category": "GOOD",
        "valence": "medium",
        "arousal": "medium",
        "confidence": 1.5,  # out of [0.0, 1.0]
        "rationale": "Answer is specific and on-topic.",
    }
    with pytest.raises(ValidationError):
        EvaluatorOutputSchema(**data)


def test_confidence_below_zero_rejected():
    data = {
        "category": "GOOD",
        "valence": "medium",
        "arousal": "medium",
        "confidence": -0.1,
        "rationale": "Answer is specific and on-topic.",
    }
    with pytest.raises(ValidationError):
        EvaluatorOutputSchema(**data)


def test_empty_rationale_rejected():
    data = {
        "category": "GOOD",
        "valence": "medium",
        "arousal": "medium",
        "confidence": 0.9,
        "rationale": "",
    }
    with pytest.raises(ValidationError):
        EvaluatorOutputSchema(**data)


def test_invalid_valence_rejected():
    data = {
        "category": "GOOD",
        "valence": "extreme",  # not one of low/medium/high
        "arousal": "medium",
        "confidence": 0.9,
        "rationale": "Answer is specific and on-topic.",
    }
    with pytest.raises(ValidationError):
        EvaluatorOutputSchema(**data)


def test_category_choices_match_config():
    """Drift guard: schemas.py hardcodes the same values as config.py's
    QUALITY_CATEGORIES (Pydantic Literal types need static values). If
    someone updates config.py without updating schemas.py, this test
    catches the mismatch instead of it silently going stale."""
    args = typing.get_args(EvaluatorOutputSchema.model_fields["category"].annotation)
    assert set(args) == set(config.QUALITY_CATEGORIES)


def test_valence_choices_match_config():
    args = typing.get_args(EvaluatorOutputSchema.model_fields["valence"].annotation)
    assert set(args) == set(config.VALENCE_LEVELS)


def test_arousal_choices_match_config():
    args = typing.get_args(EvaluatorOutputSchema.model_fields["arousal"].annotation)
    assert set(args) == set(config.AROUSAL_LEVELS)
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schemas'` (the file doesn't exist yet).

- [ ] **Step 5: Create schemas.py**

```python
"""
Pydantic schemas that validate structured LLM output before it's trusted
downstream. See docs/unified_architecture.md (Task 4) for the design this
implements — this file is the "Schema Guard" that closes the gap where a
malformed-but-parseable evaluator response (e.g. "category": "good"
lowercase, or confidence > 1.0) could previously propagate silently.

Category/VALevel are hardcoded to match config.py's QUALITY_CATEGORIES /
VALENCE_LEVELS / AROUSAL_LEVELS exactly — Pydantic Literal types need
static values, so these can't just read the config lists at runtime.
tests/test_schemas.py checks the two stay in sync.
"""

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["GOOD", "NEUTRAL", "BAD"]
VALevel = Literal["low", "medium", "high"]


class EvaluatorOutputSchema(BaseModel):
    category: Category
    valence: VALevel
    arousal: VALevel
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/test_schemas.py -v`
Expected: PASS — all 9 tests green.

- [ ] **Step 7: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add requirements.txt schemas.py tests/__init__.py tests/test_schemas.py
git commit -m "Add EvaluatorOutputSchema (Pydantic schema guard for evaluator output)"
```

---

### Task 2: Style-leakage score — `guardrail.py`

**Files:**
- Modify: `guardrail.py:19-25` (the `GuardrailResult` dataclass)
- Test: `tests/test_guardrail.py`

**Interfaces:**
- Consumes: nothing new (uses existing `config.NO_MASKING_FLAG_PATTERNS`).
- Produces: `guardrail.GuardrailResult` gains a third field, `style_leakage_score: int` — always equal to `len(matched_patterns)`, computed automatically even if the dataclass is constructed directly. `.as_dict()` gains a `"style_leakage_score"` key alongside the two existing keys (`"passed"`, `"matched_patterns"` are unchanged).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_guardrail.py`:

```python
from guardrail import GuardrailResult, check_rationale


def test_no_matches_passes_with_zero_score():
    result = check_rationale("The candidate described a specific project and its outcome.")
    assert result.passed is True
    assert result.matched_patterns == []
    assert result.style_leakage_score == 0


def test_matches_fail_with_positive_score():
    result = check_rationale("The candidate lacked eye contact and seemed nervous.")
    assert result.passed is False
    assert result.style_leakage_score == len(result.matched_patterns)
    assert result.style_leakage_score >= 1


def test_as_dict_keeps_existing_keys_unchanged():
    result = check_rationale("Specific and relevant content only.")
    d = result.as_dict()
    assert d["passed"] is True
    assert d["matched_patterns"] == []


def test_as_dict_includes_new_style_leakage_score_key():
    result = check_rationale("The candidate sounded robotic and was too blunt.")
    d = result.as_dict()
    assert "style_leakage_score" in d
    assert d["style_leakage_score"] == len(d["matched_patterns"])


def test_style_leakage_score_always_derived_even_when_constructed_directly():
    """style_leakage_score can't be set independently of matched_patterns —
    it's always recomputed, so the two can never drift out of sync."""
    result = GuardrailResult(passed=False, matched_patterns=["eye contact", "monotone"])
    assert result.style_leakage_score == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/test_guardrail.py -v`
Expected: FAIL — `TypeError` or `AttributeError` on `style_leakage_score` (field doesn't exist yet).

- [ ] **Step 3: Modify guardrail.py**

Replace the `GuardrailResult` class (lines 19-25) with:

```python
@dataclass
class GuardrailResult:
    passed: bool
    matched_patterns: list = field(default_factory=list)
    style_leakage_score: int = 0

    def __post_init__(self):
        # Always derived from matched_patterns — never independently settable,
        # so the two fields can't drift out of sync with each other.
        self.style_leakage_score = len(self.matched_patterns)

    def as_dict(self):
        return {
            "passed": self.passed,
            "matched_patterns": self.matched_patterns,
            "style_leakage_score": self.style_leakage_score,
        }
```

`check_rationale()` (lines 28-31) does not need to change — it already constructs `GuardrailResult(passed=..., matched_patterns=matches)`, and `__post_init__` now fills in `style_leakage_score` automatically.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/test_guardrail.py -v`
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add guardrail.py tests/test_guardrail.py
git commit -m "Add derived style_leakage_score to GuardrailResult"
```

---

### Task 3: Retry hint — `evaluator.py`

**Files:**
- Modify: `evaluator.py:40-63` (the `evaluate()` function)
- Test: `tests/test_evaluator_retry_hint.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `evaluator.evaluate(question: str, answer_text: str, prompt_variant: str = "A", retry_hint: str = None) -> Evaluation` — one new optional parameter. When `retry_hint` is given, it's appended to the user message sent to the LLM. When omitted (the default), behavior is byte-for-byte identical to today — every existing caller (`graph.py`, `ab_test.py`) keeps working unchanged. Consumed by Task 4.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_evaluator_retry_hint.py`:

```python
import json

import evaluator


def _fake_valid_json():
    return json.dumps(
        {
            "category": "GOOD",
            "valence": "medium",
            "arousal": "medium",
            "confidence": 0.9,
            "rationale": "Specific and relevant.",
        }
    )


def test_retry_hint_appended_to_user_message_when_given(monkeypatch):
    captured = {}

    def fake_call_llm(system, user_message, max_tokens=500, temperature=0.7, model=None):
        captured["user_message"] = user_message
        return _fake_valid_json()

    monkeypatch.setattr(evaluator.llm_client, "call_llm", fake_call_llm)

    evaluator.evaluate(
        "Tell me about yourself.",
        "I have five years of experience.",
        retry_hint="confidence must be <= 1.0",
    )

    assert "confidence must be <= 1.0" in captured["user_message"]


def test_no_retry_hint_by_default_leaves_message_unchanged(monkeypatch):
    captured = {}

    def fake_call_llm(system, user_message, max_tokens=500, temperature=0.7, model=None):
        captured["user_message"] = user_message
        return _fake_valid_json()

    monkeypatch.setattr(evaluator.llm_client, "call_llm", fake_call_llm)

    evaluator.evaluate("Tell me about yourself.", "I have five years of experience.")

    assert captured["user_message"] == (
        "Interview question: Tell me about yourself.\n\n"
        "Candidate answer: I have five years of experience."
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/test_evaluator_retry_hint.py -v`
Expected: FAIL — `TypeError: evaluate() got an unexpected keyword argument 'retry_hint'`.

- [ ] **Step 3: Modify evaluator.py**

Replace the `evaluate()` function (lines 40-63) with:

```python
def evaluate(
    question: str,
    answer_text: str,
    prompt_variant: str = "A",
    retry_hint: str = None,
) -> Evaluation:
    if prompt_variant not in _PROMPT_VARIANTS:
        raise ValueError(f"Unknown prompt_variant: {prompt_variant!r} (expected 'A' or 'B')")

    user_message = f"Interview question: {question}\n\nCandidate answer: {answer_text}"
    if retry_hint:
        user_message += (
            f"\n\nYour previous response was invalid: {retry_hint}\n"
            "Return ONLY valid JSON matching the required shape exactly."
        )

    raw = llm_client.call_llm(
        system=_PROMPT_VARIANTS[prompt_variant],
        user_message=user_message,
        max_tokens=400,
        temperature=0.3,  # lower temp — this is a judgment task, not creative
    )
    raw = _strip_fences(raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Evaluator returned non-JSON output: {raw!r}") from e

    return Evaluation(
        category=data["category"],
        valence=data["valence"],
        arousal=data["arousal"],
        confidence=float(data["confidence"]),
        rationale=data["rationale"],
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/test_evaluator_retry_hint.py -v`
Expected: PASS — both tests green.

- [ ] **Step 5: Run the full test suite so far to check nothing else broke**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/ -v`
Expected: PASS — all tests from Task 1, 2, and 3 green (14 tests total).

- [ ] **Step 6: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add evaluator.py tests/test_evaluator_retry_hint.py
git commit -m "Add optional retry_hint parameter to evaluator.evaluate()"
```

---

### Task 4: Wire the schema guard into graph.py

**Files:**
- Modify: `graph.py:28-35` (the `ConversationState` TypedDict)
- Modify: `graph.py:46-56` (the `evaluate_node` function)
- Modify: `graph.py:78-98` (the `route_to_review` function)
- Modify: `graph.py:124-148` (the `_build_graph` function)
- Test: `tests/test_graph_schema_guard.py`

**Interfaces:**
- Consumes: `schemas.EvaluatorOutputSchema` (Task 1), `evaluator.evaluate(..., retry_hint=...)` (Task 3).
- Produces: `graph.ConversationState` gains an optional `schema_invalid: bool` key. `graph._route_after_evaluate(state) -> str` — new routing function, returns `"route_to_review"` or `"guardrail_check"`. `review_queue.enqueue()` can now be called with `reason="schema_invalid"` (a fourth value alongside the three existing ones).

This is the biggest task — read all 4 steps before starting, since the graph wiring changes together.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_graph_schema_guard.py`:

```python
import graph
from evaluator import Evaluation


def _good_evaluation():
    return Evaluation(
        category="GOOD",
        valence="medium",
        arousal="medium",
        confidence=0.9,
        rationale="Specific and relevant content.",
    )


def _bad_schema_evaluation():
    return Evaluation(
        category="good",  # invalid: not one of GOOD/NEUTRAL/BAD
        valence="medium",
        arousal="medium",
        confidence=0.9,
        rationale="Specific and relevant content.",
    )


def test_evaluate_node_passes_through_when_schema_valid(monkeypatch):
    monkeypatch.setattr(graph.evaluator, "evaluate", lambda *a, **k: _good_evaluation())

    state = {"question": "Q", "answer_text": "A"}
    result = graph.evaluate_node(state)

    assert result["schema_invalid"] is False
    assert result["evaluation"]["category"] == "GOOD"


def test_evaluate_node_retries_once_then_succeeds(monkeypatch):
    calls = []

    def fake_evaluate(question, answer_text, prompt_variant="A", retry_hint=None):
        calls.append(retry_hint)
        if retry_hint is None:
            return _bad_schema_evaluation()
        return _good_evaluation()

    monkeypatch.setattr(graph.evaluator, "evaluate", fake_evaluate)

    state = {"question": "Q", "answer_text": "A"}
    result = graph.evaluate_node(state)

    assert len(calls) == 2
    assert calls[0] is None
    assert calls[1] is not None
    assert result["schema_invalid"] is False
    assert result["evaluation"]["category"] == "GOOD"


def test_evaluate_node_flags_schema_invalid_after_two_failures(monkeypatch):
    monkeypatch.setattr(graph.evaluator, "evaluate", lambda *a, **k: _bad_schema_evaluation())

    state = {"question": "Q", "answer_text": "A"}
    result = graph.evaluate_node(state)

    assert result["schema_invalid"] is True


def test_route_after_evaluate_skips_guardrail_when_schema_invalid():
    assert graph._route_after_evaluate({"schema_invalid": True}) == "route_to_review"


def test_route_after_evaluate_goes_to_guardrail_when_schema_valid():
    assert graph._route_after_evaluate({"schema_invalid": False}) == "guardrail_check"


def test_route_to_review_uses_schema_invalid_reason(monkeypatch):
    enqueued = {}

    def fake_enqueue(item, reason):
        enqueued["item"] = item
        enqueued["reason"] = reason

    monkeypatch.setattr(graph.review_queue, "enqueue", fake_enqueue)

    state = {
        "schema_invalid": True,
        "question": "Q",
        "persona": "concise_confident",
        "answer_text": "A",
        "evaluation": {"category": "good"},
    }
    result = graph.route_to_review(state)

    assert enqueued["reason"] == "schema_invalid"
    assert result["routed_to"] == "review_queue"


def test_route_to_review_backward_compatible_without_schema_invalid_key(monkeypatch):
    """Existing low_confidence/guardrail_flag paths never set schema_invalid
    at all — state.get() must default to falsy without raising KeyError."""
    enqueued = {}

    def fake_enqueue(item, reason):
        enqueued["reason"] = reason

    monkeypatch.setattr(graph.review_queue, "enqueue", fake_enqueue)

    state = {
        "question": "Q",
        "persona": "vague_low_effort",
        "answer_text": "A",
        "evaluation": {"category": "NEUTRAL", "confidence": 0.5},
        "guardrail_result": {"passed": True, "matched_patterns": [], "style_leakage_score": 0},
    }
    result = graph.route_to_review(state)

    assert enqueued["reason"] == "low_confidence"
    assert result["routed_to"] == "review_queue"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/test_graph_schema_guard.py -v`
Expected: FAIL — `AttributeError: module 'graph' has no attribute '_route_after_evaluate'`, and `evaluate_node` won't return a `schema_invalid` key yet.

- [ ] **Step 3: Add the schemas import**

In `graph.py`, add to the imports (after the existing `import review_queue` on line 24):

```python
from pydantic import ValidationError
from schemas import EvaluatorOutputSchema
```

- [ ] **Step 4: Update ConversationState**

Replace lines 28-35 with:

```python
class ConversationState(TypedDict, total=False):
    question: str
    persona: str
    answer_text: str
    evaluation: dict          # category, valence, arousal, confidence, rationale
    schema_invalid: bool      # True if evaluation failed EvaluatorOutputSchema twice
    guardrail_result: dict    # passed, matched_patterns, style_leakage_score
    final_response: Optional[str]
    routed_to: str            # "review_queue" or "finalized"
```

- [ ] **Step 5: Replace evaluate_node**

Replace lines 46-56 (the `evaluate_node` function) with:

```python
def _evaluation_to_dict(ev) -> dict:
    return {
        "category": ev.category,
        "valence": ev.valence,
        "arousal": ev.arousal,
        "confidence": ev.confidence,
        "rationale": ev.rationale,
    }


def evaluate_node(state: ConversationState) -> dict:
    ev = evaluator.evaluate(state["question"], state["answer_text"])
    evaluation_dict = _evaluation_to_dict(ev)

    try:
        EvaluatorOutputSchema(**evaluation_dict)
        return {"evaluation": evaluation_dict, "schema_invalid": False}
    except ValidationError as e:
        retry_ev = evaluator.evaluate(
            state["question"], state["answer_text"], retry_hint=str(e)
        )
        retry_dict = _evaluation_to_dict(retry_ev)
        try:
            EvaluatorOutputSchema(**retry_dict)
            return {"evaluation": retry_dict, "schema_invalid": False}
        except ValidationError:
            return {"evaluation": retry_dict, "schema_invalid": True}
```

- [ ] **Step 6: Add the routing function**

Add this new function right after `_is_low_confidence` (after line 69, before `route_decision`):

```python
def _is_schema_invalid(state: ConversationState) -> bool:
    return state.get("schema_invalid", False)


def _route_after_evaluate(state: ConversationState) -> str:
    if _is_schema_invalid(state):
        return "route_to_review"
    return "guardrail_check"
```

- [ ] **Step 7: Update route_to_review**

Replace lines 78-98 (the `route_to_review` function) with:

```python
def route_to_review(state: ConversationState) -> dict:
    if state.get("schema_invalid"):
        reason = "schema_invalid"
    else:
        flagged = _is_flagged(state)
        low_confidence = _is_low_confidence(state)
        if flagged and low_confidence:
            reason = "low_confidence+guardrail_flag"
        elif flagged:
            reason = "guardrail_flag"
        else:
            reason = "low_confidence"

    review_queue.enqueue(
        {
            "question": state["question"],
            "persona": state["persona"],
            "answer_text": state["answer_text"],
            "evaluation": state["evaluation"],
            "guardrail_result": state.get("guardrail_result"),
        },
        reason,
    )
    return {"final_response": None, "routed_to": "review_queue"}
```

Note the change from `state["guardrail_result"]` to `state.get("guardrail_result")` — in the new `schema_invalid` path, `guardrail_check` never runs, so `guardrail_result` isn't in state at all. `.get()` returns `None` instead of raising `KeyError`.

- [ ] **Step 8: Update _build_graph to add the new conditional edge**

Replace lines 124-148 (the `_build_graph` function) with:

```python
def _build_graph():
    graph = StateGraph(ConversationState)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("guardrail_check", guardrail_node)
    graph.add_node("route_to_review", route_to_review)
    graph.add_node("select_response", select_response)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("generate_answer")
    graph.add_edge("generate_answer", "evaluate")
    graph.add_conditional_edges(
        "evaluate",
        _route_after_evaluate,
        {
            "route_to_review": "route_to_review",
            "guardrail_check": "guardrail_check",
        },
    )
    graph.add_conditional_edges(
        "guardrail_check",
        route_decision,
        {
            "route_to_review": "route_to_review",
            "select_response": "select_response",
        },
    )
    graph.add_edge("route_to_review", "finalize")
    graph.add_edge("select_response", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()
```

(This replaces the old single `graph.add_edge("evaluate", "guardrail_check")` line with a conditional branch — schema-invalid answers now skip `guardrail_check` entirely, since there's no trustworthy `rationale` to audit.)

- [ ] **Step 9: Run the tests to verify they pass**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/test_graph_schema_guard.py -v`
Expected: PASS — all 7 tests green.

- [ ] **Step 10: Run the entire test suite**

Run: `cd /Users/yuvalzohar/Documents/GitHub/conversation_engine && source venv/bin/activate && python3 -m pytest tests/ -v`
Expected: PASS — all 23 tests green (9 from Task 1 + 5 from Task 2 + 2 from Task 3 + 7 from Task 4).

- [ ] **Step 11: One manual full-pipeline smoke test with a real LLM call**

This mirrors the existing project convention (`CLAUDE.md` Day 1 step 5 — "Run ONE full manual pass"). The automated tests above all mock the LLM; this step confirms the real, wired pipeline still runs end-to-end.

Run:
```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
source venv/bin/activate
set -a && source .env && set +a
python3 graph.py
```
Expected: prints a JSON `final_state` with `"schema_invalid": false` (a real evaluator response should validate cleanly) and `"routed_to"` either `"finalized"` or `"review_queue"` as before.

- [ ] **Step 12: Commit**

```bash
cd /Users/yuvalzohar/Documents/GitHub/conversation_engine
git add graph.py tests/test_graph_schema_guard.py
git commit -m "Wire Pydantic schema guard into graph.py with schema_invalid routing"
```

---

## Self-Review Notes

- **Spec coverage:** Gap 1 (no schema validation) closed by Tasks 1+3+4. Gap 2 (no numeric divergence score) closed by Task 2. Both gaps from the simple-English table are covered.
- **Type consistency check:** `EvaluatorOutputSchema` (Task 1) is imported and used identically in Task 4. `retry_hint` parameter name (Task 3) matches its usage in Task 4's `evaluate_node`. `GuardrailResult.style_leakage_score` (Task 2) is referenced in `ConversationState`'s comment (Task 4, Step 4) for documentation accuracy, though Task 4 doesn't otherwise consume it — that's intentional, per the design doc: routing on `style_leakage_score` is "a config decision, not an architecture one," left for later.
- **Out of scope, by design:** the `ConsistencyCheckResult` and `ReviewQueueItemSchema` models from `docs/unified_architecture.md` Task 4 are NOT part of this plan — the user asked specifically for the two gaps (schema validation, numeric score), not the full unified-architecture doc. Building those would be a separate future plan.
