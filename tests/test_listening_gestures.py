import json

import listening_gestures as lg


def gesture(**over):
    g = {"name": "SmallNod", "category": "go_on", "description": "a small nod",
         "frames": [{"time": [0.25], "params": {"NECK_TILT": 4.0}}], "reset": 0.6}
    g.update(over)
    return g


def test_valid_gesture_passes_unchanged():
    clean, problems = lg.validate(gesture())
    assert problems == []
    assert clean == gesture()


def test_forbidden_param_is_rejected():
    g = gesture(frames=[{"time": [0.3], "params": {"EXPR_SAD": 0.5}}])
    clean, problems = lg.validate(g)
    assert clean is None and "EXPR_SAD" in problems[0]


def test_out_of_range_values_are_clamped():
    g = gesture(frames=[{"time": [0.3], "params": {"NECK_TILT": 20.0, "MOUTH_SMILE_LEFT": 0.9}}])
    clean, problems = lg.validate(g)
    assert clean["frames"][0]["params"] == {"NECK_TILT": 5.0,
                                            "MOUTH_SMILE_LEFT": lg.ALLOWED_PARAMS["MOUTH_SMILE_LEFT"][1]}
    assert len(problems) == 2


def test_unknown_category_and_bad_timing_are_rejected():
    assert lg.validate(gesture(category="anger"))[0] is None
    assert lg.validate(gesture(frames=[{"time": [0.5, 0.2], "params": {"NECK_ROLL": 3}}]))[0] is None
    assert lg.validate(gesture(reset=0.1))[0] is None  # reset before the last frame
    assert lg.validate(gesture(reset=9.0))[0] is None  # too long


def test_dedupe_drops_near_copies_and_keeps_different_ones():
    a = gesture(name="A")
    a_copy = gesture(name="A2", frames=[{"time": [0.25], "params": {"NECK_TILT": 4.2}}])
    tilt = gesture(name="Tilt", category="interest",
                   frames=[{"time": [0.5, 2.0], "params": {"NECK_ROLL": 6.0}}], reset=2.6)
    kept = lg.dedupe([a, a_copy, tilt])
    assert [g["name"] for g in kept] == ["A", "Tilt"]


def test_parse_reply_reads_the_gesture_list():
    raw = '```json\n{"gestures": [' + json.dumps(gesture()) + ']}\n```'
    assert lg.parse_reply(raw) == [gesture()]
    assert lg.parse_reply("not json") == []


def test_examples_in_the_prompt_are_valid():
    for g in lg.EXAMPLES:
        assert lg.validate(g)[1] == [], g["name"]


def test_save_review_writes_decisions_and_only_kept_gestures(tmp_path, monkeypatch):
    monkeypatch.setattr(lg, "REVIEW_PATH", str(tmp_path / "review.json"))
    approved_path = tmp_path / "approved.json"
    monkeypatch.setattr(lg.config, "LISTENING_GESTURES_APPROVED_PATH", str(approved_path))
    a, b = gesture(name="A"), gesture(name="B")
    decisions = {"A": {"decision": "keep", "note": "natural"}, "B": {"decision": "drop", "note": "too big"}}

    approved = lg.save_review([a, b], decisions)

    assert [g["name"] for g in approved] == ["A"]
    assert json.loads(approved_path.read_text()) == [a]
    assert lg.load_review() == decisions


def test_mirror_swaps_sides():
    g = gesture(name="TiltLeftBrow", category="interest",
                frames=[{"time": [0.5, 2.0], "params": {"NECK_ROLL": -2.8, "NECK_PAN": -1.0,
                                                         "BROW_OUTER_UP_LEFT": 0.18}}], reset=2.6)
    m = lg.mirror(g)
    assert m["name"] == "TiltRightBrow"
    assert m["frames"][0]["params"] == {"NECK_ROLL": 2.8, "NECK_PAN": 1.0, "BROW_OUTER_UP_RIGHT": 0.18}
    assert lg.mirror(gesture()) is None  # a symmetric gesture has no mirror


def test_strengthen_scales_matching_params_within_limits():
    g = gesture(frames=[{"time": [0.3], "params": {"BROW_INNER_UP": 0.22, "NECK_TILT": 2.0}}])
    s = lg.strengthen(g, "BROW_", 1.7)
    assert s["frames"][0]["params"] == {"BROW_INNER_UP": 0.37, "NECK_TILT": 2.0}
    big = lg.strengthen(gesture(frames=[{"time": [0.3], "params": {"MOUTH_SMILE_LEFT": 0.2}}]), "MOUTH_SMILE", 5)
    assert big["frames"][0]["params"]["MOUTH_SMILE_LEFT"] == lg.ALLOWED_PARAMS["MOUTH_SMILE_LEFT"][1]


def test_revise_applies_the_review_and_resets_changed_gestures():
    brow = gesture(name="BriefBrowRise", category="attention",
                   frames=[{"time": [0.2, 0.5], "params": {"BROW_INNER_UP": 0.22}}], reset=0.8)
    tilt = gesture(name="GentleTiltLeftHold", category="interest",
                   frames=[{"time": [0.5, 2.0], "params": {"NECK_ROLL": -3.6}}], reset=2.6)
    pan = gesture(name="SoftPanLeft", category="interest",
                  frames=[{"time": [0.4], "params": {"NECK_PAN": -2.0}}], reset=1.0)
    review = {"BriefBrowRise": {"decision": "keep", "note": "make the brow upper"},
              "GentleTiltLeftHold": {"decision": "keep", "note": ""},
              "SoftPanLeft": {"decision": "drop", "note": ""}}

    candidates, decisions = lg.revise([brow, tilt, pan], review)

    names = [g["name"] for g in candidates]
    assert names == ["BriefBrowRise", "GentleTiltLeftHold", "SoftPanLeft", "GentleTiltRightHold"]
    assert candidates[0]["frames"][0]["params"]["BROW_INNER_UP"] == 0.37
    assert decisions["BriefBrowRise"]["decision"] == "" and "brow" in decisions["BriefBrowRise"]["note"]
    assert decisions["GentleTiltLeftHold"]["decision"] == "keep"  # unchanged: decision kept
    assert decisions["SoftPanLeft"]["decision"] == "drop"
    assert decisions["GentleTiltRightHold"]["decision"] == ""  # new mirror: to review


def test_revise_adds_extra_gestures_for_review():
    extra = gesture(name="BrowRaiseBoth", category="attention",
                    frames=[{"time": [0.2, 0.6], "params": {"BROW_INNER_UP": 0.4}}], reset=0.9)
    candidates, decisions = lg.revise([gesture()], {}, extra=[extra])
    assert [g["name"] for g in candidates] == ["SmallNod", "BrowRaiseBoth"]
    assert decisions["BrowRaiseBoth"] == {"decision": "", "note": "new: researcher request"}


def test_new_gestures_are_valid():
    for g in lg.NEW_GESTURES:
        assert lg.validate(g)[1] == [], g["name"]
