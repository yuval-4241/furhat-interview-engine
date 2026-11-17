"""
hebrew_gender.py -- resolves the question bank's slash forms ("ספר/י",
"מתמודד/ת", "אתה/את") into one spoken form for the participant's gender
(plan decision P2), so the robot never reads a slash aloud.

Rule-based: in "<base>/<alt>", an alt in _SUFFIXES is a feminine suffix
(base + suffix; a base ending in ה drops it before a י suffix: תעשה/י ->
תעשי; a final letter turns regular: מוכן/ה -> מוכנה). Any other alt is a
whole alternative word (אתה/את). The feminine-first "את/ה" is special-cased:
male "אתה", female "את". "ו/או" (and/or) is left alone.
Unknown gender -> the first form, as written.
"""

import re

_SLASH_FORM = re.compile(r"([א-ת]+)/([א-ת]+)")
_FINAL_TO_REGULAR = str.maketrans("ךםןףץ", "כמנפצ")
_SUFFIXES = ("י", "ת", "ה", "ית")


def _feminine(base: str, alt: str) -> str:
    if alt not in _SUFFIXES:
        return alt
    if alt == "י" and base.endswith("ה"):
        return base[:-1] + "י"
    return base[:-1] + base[-1].translate(_FINAL_TO_REGULAR) + alt


def render(text: str, gender=None) -> str:
    def pick(match):
        base, alt = match.group(1), match.group(2)
        if alt == "או":
            return match.group(0)
        if (base, alt) == ("את", "ה"):  # feminine-first: the suffix rule would invert it
            return "את" if gender == "female" else "אתה"
        return _feminine(base, alt) if gender == "female" else base

    return _SLASH_FORM.sub(pick, text)
