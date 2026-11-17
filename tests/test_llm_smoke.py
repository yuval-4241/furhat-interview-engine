"""Real-LLM smoke checks for the new prompts (spec "Testing"). Skipped by
default; run with: RUN_LLM_SMOKE=1 pytest tests/test_llm_smoke.py -v"""

import os

import pytest

from engine import acknowledgement
import config
from connectors import llm_client
from engine import pe_check
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
