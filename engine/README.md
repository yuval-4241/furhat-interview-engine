# engine/ — the Live session

Everything the robot does in a Live session, from the polling loop to the friend debrief.
Run the Engine: `python -m engine.engine_worker` (or the `engine` alias).

| File | What it does |
|---|---|
| `engine_worker.py` | The main loop: polls the website, runs each Live session, heartbeat, applies the robot persona (and keeps the friend's face once the debrief started) |
| `conversation_flow.py` | The turn state machine: speak, listen, react, PE question, grade, feedback, friend debrief |
| `small_talk.py` | Opening/closing small talk, the short reaction before each scripted opening line, follow-up questions |
| `acknowledgement.py` | The 2-3 sentence reply after a non-PBDI main answer (content only, no praise) |
| `emotion_classifier.py` | Picks the robot's emotion + intensity from the answer, and records what triggered it |
| `reaction_line.py` | What the robot says with its emotional reaction (never names the emotion) |
| `pe_check.py` | Grades the PE answer: emotion (Correct/Partial/Wrong) and reason (Matches/Partly/No/Missing) |
| `pe_feedback.py` | The robot's line revealing what it felt and why |
| `debrief.py` | The friend debrief: open questions, goodbye, extracting and grading the moments the participant told |
| `hebrew_gender.py` | Says Hebrew slash forms ("ספר/י") in the participant's gender |
| `llm_line.py` | Shared helper: one spoken line from the LLM, cleaned, with a fixed fallback |
| `worker_common.py` | Shared worker id, timestamps and log lines |
