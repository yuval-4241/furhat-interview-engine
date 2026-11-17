"""
lab_db.py — picks the lab-website client the Engine uses, by config.LAB_BACKEND:
"supabase" -> supabase_client (the new website), anything else -> base44_client.
Both expose list_records / get_record / create_record / update_record / claim
and raise Base44Error / RateLimited.
"""

import config

if config.LAB_BACKEND == "supabase":
    from connectors import supabase_client as client
else:
    from connectors import base44_client as client
# The new website owns the LLMModel list and creates all Turns itself; the
# Engine account is not allowed to write either.
ENGINE_MANAGES_MODELS_AND_TURNS = config.LAB_BACKEND != "supabase"
