import pytest

import CoachAI

CONTEXT = {"roadmaps": [{"key": "cycles", "phases": [{}, {}, {}]}, {"key": "recomp", "phases": [{}]}]}


def test_clean_keeps_valid_fields_and_drops_junk():
    raw = {
        "headline": "  Cut first, then build.  ",
        "verdict": "ambitious",
        "recommended": "cycles",
        "why": ["Fastest", "", 3, "Keeps fat in check"],
        "phase_notes": [{"phase": 0, "note": "Hold protein high."}, {"phase": 9, "note": "out of range"}, "bad"],
        "this_month": ["a", "b", "c", "d"],
        "watch_outs": "not a list",
        "plan_fit": "Your current cut is phase 1.",
        "goal_tweak": {"bf_percent": 15, "ffmi": 21, "reason": "Closer milestone."},
    }
    review = CoachAI.clean(raw, CONTEXT)
    assert review["headline"] == "Cut first, then build."
    assert review["why"] == ["Fastest", "Keeps fat in check"]
    assert review["phase_notes"] == [{"phase": 0, "note": "Hold protein high."}]
    assert review["this_month"] == ["a", "b", "c"]
    assert review["watch_outs"] == []
    assert review["goal_tweak"] == {"bf_percent": 15.0, "ffmi": 21.0, "reason": "Closer milestone."}


def test_clean_falls_back_on_unknown_strategy_and_verdict():
    review = CoachAI.clean({"recommended": "bulk_forever", "verdict": "amazing", "goal_tweak": {"bf_percent": "x"}}, CONTEXT)
    assert review["recommended"] == "cycles"
    assert review["verdict"] == "ambitious"
    assert review["goal_tweak"] is None


def test_review_needs_a_key():
    with pytest.raises(CoachAI.CoachError):
        CoachAI.review(CONTEXT, "")
