import pandas as pd

import bias_check
import personas
import evaluator
from question_bank import QuestionBank


def _fake_call_llm(system, user_message, max_tokens=500, temperature=0.7, model=None):
    return "fake synthetic answer"


def _fake_evaluate(question, answer_text, prompt_variant="A", retry_hint=None):
    return evaluator.Evaluation(
        category="GOOD",
        valence="medium",
        arousal="medium",
        confidence=0.9,
        rationale="Specific and relevant.",
    )


def test_build_matched_question_pool_uses_requested_session():
    pool = bias_check._build_matched_question_pool(n=6, session_number=5)

    session_5_texts = {q["text"] for q in QuestionBank().session(5)}
    assert all(q["text"] in session_5_texts for q in pool)


def test_build_matched_question_pool_cycles_past_session_size():
    pool = bias_check._build_matched_question_pool(n=8, session_number=1)

    assert len(pool) == 8
    assert pool[0] == pool[6]  # session 1 has 6 questions, so index 6 wraps to index 0


def test_run_bias_check_generates_both_personas_per_question(monkeypatch):
    monkeypatch.setattr(personas.llm_client, "call_llm", _fake_call_llm)
    monkeypatch.setattr(bias_check.evaluator, "evaluate", _fake_evaluate)

    df = bias_check.run_bias_check(n=3, session_number=1)

    assert len(df) == 6  # 3 questions x 2 personas
    for question_id in range(3):
        rows = df[df["question_id"] == question_id]
        assert set(rows["persona"]) == {bias_check.PERSONA_A, bias_check.PERSONA_B}


def test_chi_square_report_no_difference_is_not_significant():
    df = pd.DataFrame(
        {
            "persona": ["A"] * 20 + ["B"] * 20,
            "category": ["GOOD"] * 40,
        }
    )

    result = bias_check._chi_square_report(df, "category")

    assert result["dof"] == 0
    assert result["significant"] is False

def test_chi_square_report_detects_a_real_difference():
    df = pd.DataFrame(
        {
            "persona": ["A"] * 20 + ["B"] * 20,
            "valence": (["high"] * 16 + ["medium"] * 4) + (["high"] * 7 + ["medium"] * 13),
        }
    )

    result = bias_check._chi_square_report(df, "valence")

    assert result["significant"] is True
    assert result["p"] < 0.05
