"""
session_flow.py -- decides which questions get the full robot-reaction +
perspective-taking cycle, vs. a plain evaluated acknowledgement.

Per the 2026-10-28 design spec: only "central/significant" questions
(behavioral_pbdi, self_reflection) trigger a reaction + PE question --
not every turn. Decided from question_bank_seed.json's existing
`category` field, no new data needed.
"""

PE_CATEGORIES = {"behavioral_pbdi", "self_reflection"}


def triggers_pe(category: str) -> bool:
    return category in PE_CATEGORIES
