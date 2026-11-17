# scripts/ — things you run

Run from the repo root with `python -m scripts.<name>`.

| File | What it does |
|---|---|
| `run_demo.py` | Batch run: every persona x every session-1 question -> results/ |
| `ab_test.py` | A/B test of the two evaluator prompts (chi-square, SciPy) -> results/ab_test_results* |
| `bias_check.py` | No-Masking bias check between two personas -> results/bias_check_results* |
| `listening_gestures.py` | Generate and review the robot's listening gestures (`generate`, `review`) |
| `run.sh` | Starts the earlier live demo: builds the skill, waits for the robot, opens apps/interaction_app.py |
