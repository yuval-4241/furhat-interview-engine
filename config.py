"""
Central config for the Conversation Engine v1.
Combines pieces #8 (synthetic personas), #2 (evaluator), #5 (no-masking guardrail),
#6 (response bank), #7 (human review queue) into one runnable loop.
"""

import os

# ── LLM settings ────────────────────────────────────────────────────────────
# LLM_PROVIDER selects which backend llm_client.get_client() talks to.
# "lab" (default) = lab GPU server. "openai" = OpenAI's API directly —
# used when the lab server is unreachable/busy.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "lab")

LAB_LLM_BASE_URL = "http://100.110.96.82:8000/v1"
LAB_LLM_TOKEN = os.environ.get("LAB_LLM_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_SPEECH_API_KEY = os.environ.get("GOOGLE_SPEECH_API_KEY", "")

# Model choice: start fast/cheap while building, move up once quality matters.
# For Hebrew response generation later, consider dictalm3-12b / dictalm3-24b.
if LLM_PROVIDER == "openai":
    MODEL_FAST = "gpt-4o-mini"
    MODEL_DEFAULT = "gpt-4o-mini"
    MODEL_HEBREW = "gpt-4o-mini"
else:
    MODEL_FAST = "llama3.1-8b"      # quick loop while building/debugging
    MODEL_DEFAULT = "gpt-oss-20b"   # good speed/quality tradeoff — use this by default
    MODEL_HEBREW = "dictalm3-12b"   # for Hebrew-heavy tasks later (response bank, personas)

MODEL = MODEL_DEFAULT

# ════════════════════════════════════════════════════════════════════════════
# ▶▶ ADD NEW LLM MODELS HERE ◀◀
#
# 1. If the model's provider isn't in LLM_PROVIDERS yet, add it (any
#    OpenAI-compatible API: base_url + the env var holding its key).
# 2. Put the key in .env under that env var name (never in this file).
# 3. Add the model to LLM_MODELS: engine_key -> provider + display name.
#    The engine_key is the exact model id the provider expects.
# 4. Restart engine_worker.py: it syncs this list to the website's LLMModel
#    entity, so the model shows up in the New Session dropdown automatically
#    (models whose key is missing are shown as inactive).
# Never add 70B+ models (CLAUDE.md).
# ════════════════════════════════════════════════════════════════════════════
LLM_PROVIDERS = {
    "lab":    {"base_url": LAB_LLM_BASE_URL, "api_key_env": "LAB_LLM_TOKEN"},
    "openai": {"base_url": None,             "api_key_env": "OPENAI_API_KEY"},
    # e.g. "groq": {"base_url": "https://api.groq.com/openai/v1", "api_key_env": "GROQ_API_KEY"},
}

LLM_MODELS = {
    "llama3.1-8b":  {"provider": "lab",    "display_name": "Llama 3.1 8B (fast)"},
    "gpt-oss-20b":  {"provider": "lab",    "display_name": "GPT-OSS 20B (default)"},
    "dictalm3-12b": {"provider": "lab",    "display_name": "DictaLM 3 12B (Hebrew)"},
    "gpt-4o-mini":  {"provider": "openai", "display_name": "GPT-4o mini"},
}

# ── VA Matrix (3x3) — must match your thesis's response bank structure ────
VALENCE_LEVELS = ["low", "medium", "high"]
AROUSAL_LEVELS = ["low", "medium", "high"]

def va_cells():
    """All 9 (valence, arousal) combinations, e.g. ('high','medium')."""
    return [(v, a) for v in VALENCE_LEVELS for a in AROUSAL_LEVELS]

def va_cell_key(valence: str, arousal: str) -> str:
    return f"{valence}_{arousal}"

# ── Evaluator categories ───────────────────────────────────────────────────
QUALITY_CATEGORIES = ["GOOD", "NEUTRAL", "BAD"]

# ── Confidence routing threshold ───────────────────────────────────────────
# Below this, item goes to the human review queue (#7) regardless of guardrail.
CONFIDENCE_ROUTE_THRESHOLD = 0.70

# ── No-Masking guardrail (#5) ──────────────────────────────────────────────
# Phrase/pattern families the guardrail scans the evaluator's OWN rationale for.
# These represent the evaluator smuggling in neurotypical-norm judgments
# (posture, eye contact, STAR conformity, tone-policing) instead of judging
# content/informational presence only. Kept at pattern level, not exhaustive —
# extend this list as you observe real evaluator drift.
NO_MASKING_FLAG_PATTERNS = [
    "eye contact",
    "didn't smile",
    "flat affect",
    "monotone",
    "awkward",
    "lacked enthusiasm",
    "should have structured",
    "not in STAR format",
    "too blunt",
    "too direct",
    "poor body language",
    "didn't elaborate enough",  # borderline — content-length is ok to flag,
                                  # but phrase it around content, not style
    "sounded robotic",
    "seemed nervous",
    "fidget",
    # Hebrew equivalents, approved by the researcher on 2026-11-08 (Plan 2,
    # decision P3). Whole phrases, because matching is literal-substring:
    # a robot line that repeats the participant's own content ("היית לחוץ
    # בעבודה") must not be flagged. Both gender forms where they differ.
    "קשר עין",
    "שפת גוף",
    "טון הדיבור",
    "מונוטוני",
    "נשמעת לחוץ", "נשמעת לחוצה",
    "נראית לחוץ", "נראית לחוצה",
    "נשמעת בטוח", "נשמעת בטוחה",
    "חוסר התלהבות",
    "ישיר מדי", "ישירה מדי",
    "בוטה מדי",
    "מבנה התשובה",
    "לא בפורמט STAR",
    "ארוכה מדי", "קצרה מדי",
    "לא הרחבת מספיק",
    "נשמעת רובוטי",
    "גמגום",
    "תשובה מצוינת", "תשובה טובה", "תשובה מעולה", "כל הכבוד",
]

# ── File locations ──────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESPONSE_BANK_PATH = os.path.join(DATA_DIR, "response_bank_seed.json")
REVIEW_QUEUE_PATH = os.path.join(DATA_DIR, "review_queue.jsonl")
RUN_LOG_PATH = os.path.join(DATA_DIR, "run_log.jsonl")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
TECHNICAL_LOG_PATH = os.path.join(DATA_DIR, "technical_log.jsonl")

# Batch-run outputs (e.g. run_demo.py) — separate from the cumulative
# data/run_log.jsonl, so each batch's records/summary are easy to inspect
# on their own.
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# ── Robot reaction bridge (furhat-emotion-study, opt-in) ───────────────────
# Off by default — most runs (pytest, run_demo.py, ab_test.py) never attempt
# this call. Only set ROBOT_REACTION_ENABLED=true when the Furhat skill is
# actually running and you want a live/simulated robot reaction alongside
# the spoken reply. See docs/superpowers/specs/2026-08-11-robot-reaction-bridge-design.md.
ROBOT_REACTION_ENABLED = os.environ.get("ROBOT_REACTION_ENABLED", "false").lower() == "true"
ROBOT_BRIDGE_URL = "http://localhost:8765/react"
ROBOT_BRIDGE_TIMEOUT = 2.0  # seconds — never let a dead robot connection stall the pipeline
ROBOT_BRIDGE_BASE_URL = "http://localhost:8765"
LISTEN_TIMEOUT_MS = 10000
LISTEN_END_SIL_MS = 3000
LISTEN_MAX_SPEECH_MS = 120000

# ── Base44 lab app (frontend + DB the Engine polls) ─────────────────────────
# The app never calls the Engine; the Engine polls entities through the REST
# API and writes back. Token is a Base44 personal access token — env only.
BASE44_BASE_URL = "https://app.base44.com/api/apps"
BASE44_APP_ID = os.environ.get("BASE44_APP_ID", "")
BASE44_API_TOKEN = os.environ.get("BASE44_API_TOKEN", "")
BASE44_TIMEOUT = 10.0  # seconds

# engine_worker.py polling — light on purpose: runs on the researcher's laptop
ENGINE_VERSION = "0.1-mvp"
# Base44 allows 70 list requests/min per caller, and the worker's personal
# token shares that budget with the researcher's open browser tab. One poll
# costs ~3 list requests, so 6s keeps the worker near 30/min.
WORKER_POLL_ACTIVE = 6.0       # seconds between polls while a Session is Running
WORKER_POLL_IDLE = 20.0        # seconds between polls otherwise
WORKER_HEARTBEAT_EVERY = 20.0  # app shows "Engine unavailable" after 60s without one
WORKER_BACKOFF_START = 15.0    # first wait after a Base44 429, doubled each time in a row
WORKER_BACKOFF_MAX = 120.0
ROBOT_WAIT_SECONDS = 60.0      # how long a pending RobotCommand waits for the robot before error
