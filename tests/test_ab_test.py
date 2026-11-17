from scripts import ab_test
from evaluation import personas
from evaluation.question_bank import QuestionBank


def _fake_call_llm(system, user_message, max_tokens=500, temperature=0.7, model=None):
    return "fake synthetic answer"


def test_build_answer_pool_uses_requested_session(monkeypatch):
    monkeypatch.setattr(personas.llm_client, "call_llm", _fake_call_llm)

    pool = ab_test._build_answer_pool(n=6, session_number=5)

    session_5_texts = {q["text"] for q in QuestionBank().session(5)}
    assert all(item["question"] in session_5_texts for item in pool)


def test_build_answer_pool_defaults_to_session_1(monkeypatch):
    monkeypatch.setattr(personas.llm_client, "call_llm", _fake_call_llm)

    pool = ab_test._build_answer_pool(n=6)

    session_1_texts = {q["text"] for q in QuestionBank().session(1)}
    assert all(item["question"] in session_1_texts for item in pool)
