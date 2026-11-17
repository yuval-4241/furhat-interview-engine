# connectors/ — connections to the outside world

The only files that talk to external services. Everything else calls these.

| File | What it does |
|---|---|
| `llm_client.py` | The only file that calls an LLM provider (OpenAI / OpenRouter / the lab server); models per task |
| `lab_db.py` | Picks the website client by LAB_BACKEND in .env |
| `supabase_client.py` | The lab website's database (Supabase) — current |
| `base44_client.py` | The old Base44 website — still reachable |
| `furhat_client.py` | The robot's skill bridge: say, react, listen, persona, health |
| `robot_bridge.py` | Sends a reaction to the robot from the research pipeline (off by default) |
| `model_registry.py` | Keeps the website's model list in sync with config.LLM_MODELS |
| `stt.py` | Google speech-to-text, for the earlier live demo |
