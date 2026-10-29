import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client_code"))

from ProgressCharts import fade_after, journey_points, macro_stack, score_week, week_chip


def _row(**overrides):
    row = {
        "week": 1,
        "status": "logged",
        "actual_weight_kg": 81.5,
        "target_weight_kg": 81.3,
        "weight_delta_kg": 0.2,
        "bf_percent": 18.0,
        "target_bf_percent": 18.2,
        "bf_delta": -0.2,
        "target_calories": 2100,
        "protein_g": 180,
        "fat_g": 60,
        "carbs_g": 200,
    }
    row.update(overrides)
    return row


def test_score_week_weight_lane():
    assert score_week(_row(weight_delta_kg=0.2))["weight_hit"] is True
    assert score_week(_row(weight_delta_kg=0.5))["weight_hit"] is False


def test_score_week_bf_lane():
    assert score_week(_row(bf_delta=0.6))["bf_hit"] is True
    assert score_week(_row(bf_delta=0.7))["bf_hit"] is False


def test_planned_week_without_actual_is_unscored():
    scored = score_week(_row(status="planned", actual_weight_kg=None, weight_delta_kg=None, bf_percent=None, bf_delta=None))
    assert scored["weight_hit"] is None
    assert scored["bf_hit"] is None


def test_week_chip_counts_weight_hits_among_logged():
    rows = [
        _row(week=1, weight_delta_kg=0.1),
        _row(week=2, weight_delta_kg=0.2),
        _row(week=3, weight_delta_kg=0.3),
        _row(week=4, weight_delta_kg=0.8),
    ]
    assert week_chip(rows, current_week=4) == "3 hit · 1 miss"


def test_macro_stack_kcal_and_gap():
    assert macro_stack(_row(protein_g=180, fat_g=60, carbs_g=200)) == {
        "protein_g": 180,
        "fat_g": 60,
        "carbs_g": 200,
        "protein_kcal": 720,
        "fat_kcal": 540,
        "carbs_kcal": 800,
        "kcal": 2060,
    }
    assert macro_stack(_row(target_calories=None)) is None
    assert macro_stack(_row(target_calories=0)) is None


def test_journey_skips_incomplete_and_flags_dexa():
    points = journey_points(
        [
            _row(week=1, actual_weight_kg=81.5, bf_percent=18.0),
            _row(week=2, actual_weight_kg=81.2, bf_percent=None),
            _row(week=9, actual_weight_kg=79.0, bf_percent=16.4),
        ],
        dexa_weeks=[9],
    )
    assert [point["week"] for point in points] == [1, 9]
    assert points[0]["dexa"] is False
    assert points[1]["dexa"] is True
    assert points[1]["weight"] == 79.0
    assert points[1]["bf"] == 16.4


def test_fade_after_marks_weeks_past_current():
    faded = fade_after([10, 20, 30, 40], current_week=2)
    assert [item["faded"] for item in faded] == [False, False, True, True]
    assert [item["value"] for item in faded] == [10, 20, 30, 40]
