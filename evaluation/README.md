# evaluation/ — evaluation and the research pipeline

Content-only evaluation of answers, the No-Masking guardrail, and the synthetic-candidate pipeline used to test them.
Run one conversation: `python -m evaluation.graph`.

| File | What it does |
|---|---|
| `evaluator.py` | Content-only evaluation of an answer (GOOD/NEUTRAL/BAD + valence/arousal stance) |
| `guardrail.py` | No-Masking guardrail: flags style-bias language; category/VA consistency check |
| `schemas.py` | Validates the evaluator's JSON before it is trusted |
| `personas.py` | Synthetic candidates in different communication styles (bias probe) |
| `graph.py` | The evaluation pipeline as a LangGraph state machine |
| `review_queue.py` | Low-confidence or flagged items for human review |
| `question_bank.py` | Loads the interview question set (data/seeds/) |
| `response_bank.py` | The older valence/arousal reply bank (data/seeds/) |
