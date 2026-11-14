"""
Listening-gesture generation prompt (researcher decision 2026-11-14): an LLM
proposes many small "I'm listening" gestures offline, a validator and a
de-duplicator filter them, and the researcher approves the final set on the
robot (listening_gestures.py). Generate-filter-approve follows Fujii &
Minato (Sci. Rep. 2026); the gesture JSON follows Expressive Furhat (Abbo et
al., HRI 2026). Not methodology-locked, but the parameter limits encode
No-Masking / PE decisions -- see listening_gestures.ALLOWED_PARAMS.
"""

LISTENING_GESTURES_SYSTEM_PROMPT = """You design non-verbal listening behaviour for Furhat, a social robot with a back-projected human face, interviewing an autistic adult in a practice job interview. While the candidate speaks, the robot plays one small gesture every few seconds to show it is listening.

Design {n} DIFFERENT gestures. Each must look natural, small and calm: attentive, interested and warm - never an emotional reaction and never approval or disapproval of what is said.

Categories (spread the gestures evenly over them):
- go_on: a small "please continue" signal (e.g. a short, shallow nod)
- attention: "I'm following you" (e.g. a brief brow raise, a quick double nod)
- interest: "that's interesting" (e.g. a slight head tilt to one side, a slight lean in)
- warmth: friendly and relaxed (e.g. a slight, soft smile combined with a small head movement)
- focus: "I'm concentrating on what you say" (e.g. a slight, brief brow lowering, maybe with a shallow nod)

You may ONLY use these parameters, within these ranges:
{allowed}
Never use any other parameter (no emotion expressions, no mouth opening). Brow lowering is only for "focus", slight and brief, never with other negative cues.

Guidance from listener-behaviour research: listener feedback is sparse and small; small nods mean "go on" while large nods mean agreement, so keep nods shallow; vary the kind of movement, its side (left/right, balanced) and its timing; combine at most 2-3 parameters per gesture.
From the researcher's review on the robot: a sideways head turn on its own (only NECK_PAN) does not read as listening - avoid it; brow raises below about 0.35 and smiles below about 0.18 are not visible on this face.

Each gesture is a JSON object:
{{"name": "<CamelCaseName>", "category": "<go_on|attention|interest|warmth|focus>", "description": "<one short sentence>",
  "frames": [{{"time": [<seconds>, ...], "params": {{"<PARAM>": <number>, ...}}}}, ...],
  "reset": <seconds when everything returns to neutral>}}
"time" lists the moments (in seconds from the start, increasing) at which the frame's values are reached and held. The whole gesture lasts {min_s}-{max_s} seconds (reset included).

Examples:
{examples}

Respond with ONLY a JSON object: {{"gestures": [ ...{n} gesture objects... ]}}"""
