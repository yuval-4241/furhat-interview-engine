"""
listening_gestures.py -- builds the robot's bank of listening gestures:
an LLM proposes many candidates, validate() keeps only the allowed
"listening muscles" within their ranges, dedupe() drops near-copies, and the
researcher approves the final set on the robot. The skill (interview-skill)
then plays the approved gestures at random while the participant speaks.

    python listening_gestures.py generate --n 40   # -> data/listening_gestures_candidates.json
    python listening_gestures.py review            # play each on the robot, keep y/n (terminal)
    streamlit run gesture_review_app.py            # the same review, with buttons and notes

Offline on purpose: a gesture generated from what the participant is saying
would be a hidden evaluation (No-Masking) and differ between participants.
"""

import argparse
import json
import os
import re

import numpy as np

import config
import furhat_client
import llm_client
from prompts.listening_gestures_prompt import LISTENING_GESTURES_SYSTEM_PROMPT

# The "listening muscles" and their limits. Neck values are degrees, face
# values 0-1. Small nods signal "go on", large ones agreement (Mori et al.
# 2021), so nods stay shallow; the smile stays below HAPPINESS level 1
# (MOUTH_SMILE 0.35) and without AU6, per the researcher's decision to include
# a slight smile. Anything else (EXPR_*, AU4 frown, jaw) is not allowed.
# Limits raised after the first robot review (2026-11-14): smiles of 0.08-0.1
# and brow raises of ~0.2 were not visible on the robot's face.
ALLOWED_PARAMS = {
    "NECK_TILT": (-2.0, 5.0),            # nod / lean in
    "NECK_ROLL": (-8.0, 8.0),            # head tilt to the side
    "NECK_PAN": (-4.0, 4.0),             # small turn
    "BROW_INNER_UP": (0.0, 0.5),         # AU1
    "BROW_OUTER_UP_LEFT": (0.0, 0.5),    # AU2
    "BROW_OUTER_UP_RIGHT": (0.0, 0.5),   # AU2
    "MOUTH_SMILE_LEFT": (0.0, 0.25),     # AU12, slight
    "MOUTH_SMILE_RIGHT": (0.0, 0.25),
    # AU4, slight, for "focused listening" (researcher request 2026-11-14). Kept
    # below the weakest AU4 any reaction uses at intensity 2-3 (FEAR/CONTEMPT
    # level 2: 0.32; ANGER starts at 0.60) and never combined with other anger
    # AUs; whether it reads as concentration or disapproval is checked on the robot.
    "BROW_DOWN_LEFT": (0.0, 0.28),
    "BROW_DOWN_RIGHT": (0.0, 0.28),
    "BLINK_LEFT": (0.0, 1.0),
    "BLINK_RIGHT": (0.0, 1.0),
}
CATEGORIES = ("go_on", "attention", "interest", "warmth", "focus")
MIN_SECONDS, MAX_SECONDS = 0.5, 3.5
DEDUPE_DISTANCE = 0.1  # in the normalised feature space of _features()

CANDIDATES_PATH = os.path.join(config.DATA_DIR, "listening_gestures_candidates.json")
REVIEW_PATH = os.path.join(config.DATA_DIR, "listening_gestures_review.json")  # decision + note per gesture

# The hand-made gestures the robot used before this pipeline; few-shot examples.
EXAMPLES = [
    {"name": "SmallNod", "category": "go_on", "description": "One shallow nod.",
     "frames": [{"time": [0.25], "params": {"NECK_TILT": 4.0}}], "reset": 0.6},
    {"name": "DoubleNod", "category": "attention", "description": "Two quick, shallow nods.",
     "frames": [{"time": [0.15], "params": {"NECK_TILT": 3.0}}, {"time": [0.3], "params": {"NECK_TILT": 0.0}},
                {"time": [0.45], "params": {"NECK_TILT": 3.0}}], "reset": 0.75},
    {"name": "HeadTiltLeft", "category": "interest", "description": "Slight head tilt to one side, held.",
     "frames": [{"time": [0.5, 2.0], "params": {"NECK_ROLL": 6.0}}], "reset": 2.6},
    {"name": "SoftSmileTilt", "category": "warmth", "description": "A slight smile with a small head tilt.",
     "frames": [{"time": [0.6, 2.2], "params": {"MOUTH_SMILE_LEFT": 0.12, "MOUTH_SMILE_RIGHT": 0.12,
                                                "NECK_ROLL": -3.0}}], "reset": 3.0},
]


# Requested by the researcher after the first review (2026-11-14).
NEW_GESTURES = [
    {"name": "BrowRaiseBoth", "category": "attention", "description": "Both brows raised together, briefly.",
     "frames": [{"time": [0.2, 0.6], "params": {"BROW_INNER_UP": 0.4, "BROW_OUTER_UP_LEFT": 0.4,
                                                "BROW_OUTER_UP_RIGHT": 0.4}}], "reset": 0.9},
    {"name": "FocusedBrowFurrow", "category": "focus", "description": "A slight, brief brow lowering: concentrating.",
     "frames": [{"time": [0.3, 1.1], "params": {"BROW_DOWN_LEFT": 0.18, "BROW_DOWN_RIGHT": 0.18}}], "reset": 1.5},
    {"name": "FocusedFurrowNod", "category": "focus", "description": "A slight brow lowering with a shallow nod.",
     "frames": [{"time": [0.3, 1.0], "params": {"BROW_DOWN_LEFT": 0.15, "BROW_DOWN_RIGHT": 0.15, "NECK_TILT": 2.0}}],
     "reset": 1.4},
]


def validate(g: dict):
    """(clean gesture, problems). clean is None when the gesture can't be used;
    out-of-range values are clamped and reported."""
    problems = []
    try:
        if g.get("category") not in CATEGORIES:
            return None, [f"unknown category {g.get('category')!r}"]
        frames, reset = g["frames"], float(g["reset"])
        clean_frames, last = [], 0.0
        for f in frames:
            times = [float(t) for t in f["time"]]
            if not times or times != sorted(times) or times[0] < last:
                return None, [f"frame times must increase: {f['time']}"]
            last = times[-1]
            params = {}
            for name, value in f["params"].items():
                if name not in ALLOWED_PARAMS:
                    return None, [f"parameter {name} is not a listening parameter"]
                lo, hi = ALLOWED_PARAMS[name]
                clamped = min(max(float(value), lo), hi)
                if clamped != value:
                    problems.append(f"{name} {value} clamped to {clamped}")
                params[name] = clamped
            clean_frames.append({"time": f["time"], "params": params})
        if not last < reset <= MAX_SECONDS or reset < MIN_SECONDS:
            return None, [f"reset {reset}s must come after the last frame and within {MIN_SECONDS}-{MAX_SECONDS}s"]
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return None, [f"malformed gesture: {e}"]
    return {**g, "frames": clean_frames}, problems


def _features(g: dict) -> np.ndarray:
    """Peak |value| of every allowed parameter (scaled to 0-1 by its range) plus the duration."""
    names = list(ALLOWED_PARAMS)
    peaks = np.zeros(len(names))
    for f in g["frames"]:
        for name, value in f["params"].items():
            lo, hi = ALLOWED_PARAMS[name]
            i = names.index(name)
            peaks[i] = max(peaks[i], abs(value) / max(abs(lo), abs(hi)))
    return np.append(peaks, g["reset"] / MAX_SECONDS)


def dedupe(gestures: list, min_distance: float = DEDUPE_DISTANCE) -> list:
    """Greedy: keep a gesture only if it is at least min_distance away from every kept one."""
    kept, kept_vectors = [], []
    for g in gestures:
        v = _features(g)
        if all(np.linalg.norm(v - k) >= min_distance for k in kept_vectors):
            kept.append(g)
            kept_vectors.append(v)
    return kept


def parse_reply(raw: str) -> list:
    text = re.sub(r"^```(json)?|```$", "", raw.strip()).strip()
    try:
        gestures = json.loads(text).get("gestures", [])
    except (json.JSONDecodeError, AttributeError):
        return []
    return gestures if isinstance(gestures, list) else []


def generate(n: int = 40) -> list:
    system = LISTENING_GESTURES_SYSTEM_PROMPT.format(
        n=n, min_s=MIN_SECONDS, max_s=MAX_SECONDS,
        allowed="\n".join(f"- {k}: {lo} to {hi}" for k, (lo, hi) in ALLOWED_PARAMS.items()),
        examples="\n".join(json.dumps(e) for e in EXAMPLES))
    raw = llm_client.call_llm(system, f"Design {n} listening gestures.", max_tokens=12000, role="lines")
    candidates, rejected = [], 0
    for g in parse_reply(raw):
        clean, problems = validate(g)
        if clean is None:
            rejected += 1
            print(f"rejected {g.get('name')}: {problems}")
        else:
            candidates.append(clean)
    kept = dedupe(candidates)
    print(f"{len(candidates) + rejected} generated, {rejected} rejected, "
          f"{len(candidates) - len(kept)} near-copies dropped, {len(kept)} kept")
    return kept


def review(candidates: list) -> list:
    """Play each candidate on the robot; the researcher keeps it (y), drops it (n) or replays it (r)."""
    approved = []
    for i, g in enumerate(candidates, start=1):
        while True:
            furhat_client.play_gesture(g)
            answer = input(f"[{i}/{len(candidates)}] {g['name']} ({g['category']}): {g['description']}  keep? [y/n/r] ")
            if answer.strip().lower() in ("y", "n"):
                break
        if answer.strip().lower() == "y":
            approved.append(g)
    return approved


def strengthen(g: dict, prefix: str, factor: float) -> dict:
    """The gesture with every parameter starting with prefix scaled by factor (within its limit)."""
    frames = []
    for f in g["frames"]:
        params = {k: (round(min(v * factor, ALLOWED_PARAMS[k][1]), 2) if k.startswith(prefix) else v)
                  for k, v in f["params"].items()}
        frames.append({**f, "params": params})
    return {**g, "frames": frames}


def _swap_side(text: str) -> str:
    return text.replace("LEFT", "\0").replace("RIGHT", "LEFT").replace("\0", "RIGHT") \
               .replace("Left", "\0").replace("Right", "Left").replace("\0", "Right")


def mirror(g: dict):
    """The same gesture on the other side, or None when it is symmetric."""
    frames = []
    for f in g["frames"]:
        params = {}
        for k, v in f["params"].items():
            params[_swap_side(k)] = -v if k in ("NECK_ROLL", "NECK_PAN") else v
        frames.append({**f, "params": params})
    if frames == g["frames"]:
        return None
    name = _swap_side(g["name"])
    return {**g, "name": name if name != g["name"] else g["name"] + "Mirrored",
            "description": g["description"] + " (mirrored)", "frames": frames}


def revise(candidates: list, review: dict, extra=()):
    """Applies the researcher's first review: stronger brows and smiles (they weren't visible),
    and a mirrored version of every kept one-sided gesture. Changed and new gestures go back
    to undecided, with a note saying what changed. Returns (candidates, decisions)."""
    out, decisions = [], {}
    for g in candidates:
        d = dict(review.get(g["name"], {"decision": "", "note": ""}))
        if d.get("decision") != "drop":
            changed, notes = g, []
            for prefix, factor, what in (("BROW_", 1.7, "brows x1.7"), ("MOUTH_SMILE", 2.0, "smile x2")):
                stronger = strengthen(changed, prefix, factor)
                if stronger != changed:
                    changed, notes = stronger, notes + [what]
            if notes:
                old = f" (was: {d['note']})" if d.get("note") else ""
                d = {"decision": "", "note": f"revised: {', '.join(notes)}{old}"}
                g = changed
        out.append(g)
        decisions[g["name"]] = d
    names = {g["name"] for g in out}
    for g in list(out):
        if review.get(g["name"], {}).get("decision") == "keep":
            m = mirror(g)
            if m and m["name"] not in names:
                out.append(m)
                names.add(m["name"])
                decisions[m["name"]] = {"decision": "", "note": f"new: mirror of {g['name']}"}
    for g in extra:
        if g["name"] not in names:
            out.append(g)
            names.add(g["name"])
            decisions[g["name"]] = {"decision": "", "note": "new: researcher request"}
    return out, decisions


def load_review() -> dict:
    """{gesture name: {"decision": "keep"|"drop"|"", "note": str}} saved so far, or {}."""
    try:
        with open(REVIEW_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_review(candidates: list, decisions: dict) -> list:
    """Saves every decision and note, and writes the kept gestures for the skill. Returns the kept ones."""
    with open(REVIEW_PATH, "w", encoding="utf-8") as f:
        json.dump(decisions, f, ensure_ascii=False, indent=2)
    approved = [g for g in candidates if decisions.get(g["name"], {}).get("decision") == "keep"]
    os.makedirs(os.path.dirname(config.LISTENING_GESTURES_APPROVED_PATH), exist_ok=True)
    with open(config.LISTENING_GESTURES_APPROVED_PATH, "w", encoding="utf-8") as f:
        json.dump(approved, f, ensure_ascii=False, indent=2)
    return approved


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate").add_argument("--n", type=int, default=40)
    sub.add_parser("review")
    sub.add_parser("revise", help="apply the saved review: stronger brows/smiles + mirrored versions")
    args = parser.parse_args()
    if args.cmd == "revise":
        with open(CANDIDATES_PATH, encoding="utf-8") as f:
            candidates, decisions = revise(json.load(f), load_review(), extra=NEW_GESTURES)
        with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
            json.dump(candidates, f, ensure_ascii=False, indent=2)
        approved = save_review(candidates, decisions)
        print(f"{len(candidates)} candidates, {sum(1 for d in decisions.values() if not d['decision'])} "
              f"to review, {len(approved)} approved")
        return
    if args.cmd == "generate":
        kept = generate(args.n)
        with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
            json.dump(kept, f, ensure_ascii=False, indent=2)
        print(f"wrote {CANDIDATES_PATH}")
    else:
        with open(CANDIDATES_PATH, encoding="utf-8") as f:
            approved = review(json.load(f))
        with open(config.LISTENING_GESTURES_APPROVED_PATH, "w", encoding="utf-8") as f:
            json.dump(approved, f, ensure_ascii=False, indent=2)
        print(f"{len(approved)} approved -> {config.LISTENING_GESTURES_APPROVED_PATH} (rebuild the skill to use them)")


if __name__ == "__main__":
    main()
