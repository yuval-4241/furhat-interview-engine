# tests/ — the test suite

Run: `pytest tests/ -q`. `fakes.py` has the fake website and fake robot, so no test touches the network or the robot. One test file per module: `test_<module>.py`; `test_graph_*` and `test_consistency.py` cover evaluation/graph.py and the guardrail; `test_llm_smoke.py` runs only with RUN_LLM_SMOKE=1.

