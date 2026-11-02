from datetime import date

import Roadmap

BODY = dict(sex="male", height_cm=175, weight_kg=79.8, ffm_kg=57.7, goal_bf=14.5, goal_ffmi=22, training_years=1,
            start=date(2026, 11, 2))


def _by_key(**overrides):
    return {plan["key"]: plan for plan in Roadmap.roadmaps(**dict(BODY, **overrides))}


def test_cycles_cut_first_then_bulk_and_reach_the_goal():
    plan = _by_key()["cycles"]
    kinds = [phase["kind"] for phase in plan["phases"]]
    assert kinds[:3] == ["cut", "maintain", "bulk"]
    assert plan["phases"][0]["end"]["bf_percent"] == 12.0
    assert plan["reaches_goal"]
    assert plan["end"]["ffmi"] >= 21.95
    assert max(phase["end"]["bf_percent"] for phase in plan["phases"]) <= 16.2
    assert 2.5 < plan["weeks"] / 52 < 5


def test_cycles_is_fastest_and_recomp_slowest_for_a_high_body_fat_start():
    plans = _by_key()
    assert plans["cycles"]["weeks"] < plans["slow_gain"]["weeks"] < plans["recomp"]["weeks"]


def test_phase_numbers_are_consistent():
    plan = _by_key()["cycles"]
    for before, after in zip(plan["phases"], plan["phases"][1:]):
        assert before["end"] == after["start"]
    cut = plan["phases"][0]
    assert cut["kcal_per_day"] < 0 and cut["kg_per_week"] < 0
    bulk = plan["phases"][2]
    assert bulk["kcal_per_day"] > 0 and bulk["kg_per_week"] > 0
    assert len(plan["path"]) == len(plan["phases"]) + 1


def test_fat_only_goal_is_a_single_cut():
    plan = _by_key(goal_ffmi=18.0, goal_bf=15)["cycles"]
    assert [phase["kind"] for phase in plan["phases"]] == ["cut", "maintain"]
    assert plan["end"]["bf_percent"] == 15.0


def test_muscle_gain_slows_near_the_ceiling():
    assert Roadmap.lean_gain_per_week("male", 1, 19) > Roadmap.lean_gain_per_week("male", 1, 22) > 0
    assert Roadmap.goal_check("male", 22) is None
    assert "ceiling" in Roadmap.goal_check("male", 24)
