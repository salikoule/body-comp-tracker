import sys
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client_code"))

import ProgressCharts

package = sys.modules.setdefault("body_comp_tracker", ModuleType("body_comp_tracker"))
package.__path__ = [str(ROOT / "client_code")]
sys.modules["body_comp_tracker.ProgressCharts"] = ProgressCharts

import ProgressView
from ProgressCharts import (
    calorie_plan_options,
    composition_options,
    forecast_cone,
    fuel_ring_options,
    hero_options,
    macro_stack,
    phase_ranges,
    plan_weight_on,
    progress_model,
    score_week,
    trend_points,
    trend_rate,
)

START = date(2026, 10, 19)


def _schedule(weeks=10, logged=()):
    rows = []
    for index in range(weeks):
        week = index + 1
        phase = "cut" if week <= 6 else ("reverse" if week <= 7 else "bulk")
        row = {
            "week": week,
            "week_start": START + timedelta(days=7 * index),
            "phase": phase,
            "status": "planned",
            "target_weight_kg": round(80 - 0.4 * index, 1),
            "target_bf_percent": round(22 - 0.5 * index, 1),
            "target_calories": 2000 if phase == "cut" else 2400,
            "protein_g": 176,
            "fat_g": 56,
            "carbs_g": 198,
            "actual_weight_kg": None,
            "bf_percent": None,
        }
        rows.append(row)
    for week, kg, bf in logged:
        rows[week - 1].update({"status": "logged", "actual_weight_kg": kg, "bf_percent": bf})
    return rows


def _state(rows, current_week, weights=(), scans=()):
    return {"schedule": rows, "current_week": current_week, "weights": list(weights), "dexa_scans": list(scans)}


def _daily(days, start_kg=80.0, per_day=-0.06):
    return [{"date": (START + timedelta(days=i)).isoformat(), "kg": round(start_kg + per_day * i, 2)} for i in range(days)]


def test_score_week_lane_includes_the_edge():
    row = {"status": "logged", "actual_weight_kg": 79.9, "target_weight_kg": 79.5, "bf_percent": 21.7, "target_bf_percent": 22.1}
    assert score_week(row) == {"week": None, "weight_hit": True, "bf_hit": True}
    assert score_week(dict(row, actual_weight_kg=80.0))["weight_hit"] is False


def test_planned_week_is_unscored():
    assert score_week({"status": "planned", "actual_weight_kg": 80})["weight_hit"] is None


def test_macro_stack_kcal_and_gap():
    assert macro_stack({"target_calories": 2000, "protein_g": 176, "fat_g": 56, "carbs_g": 198})["kcal"] == 2000
    assert macro_stack({"target_calories": 0}) is None


def test_trend_needs_three_weigh_ins_and_tracks_a_steady_cut():
    assert trend_points([(START, 80.0), (START + timedelta(days=1), 79.9)]) == []
    points = [(START + timedelta(days=i), 80 - 0.05 * i) for i in range(21)]
    trend = trend_points(points)
    assert abs(trend[-1][1] - points[-1][1]) < 1e-6
    assert abs(trend_rate(trend) - (-0.35)) < 1e-6


def test_trend_rate_needs_a_week_of_span():
    trend = [(START + timedelta(days=i), 80.0) for i in range(4)]
    assert trend_rate(trend) is None


def test_plan_weight_interpolates_between_week_midpoints():
    rows = _schedule()
    midway = START + timedelta(days=7)
    assert abs(plan_weight_on(rows, midway) - 79.8) < 0.05


def test_phase_ranges_group_consecutive_weeks():
    ranges = phase_ranges(_schedule())
    assert [(item["phase"], item["start"], item["end"]) for item in ranges] == [("cut", 1, 6), ("reverse", 7, 7), ("bulk", 8, 10)]


def test_forecast_cone_widens_and_ends_on_the_phase_end():
    trend = [(START, 80.0)]
    cone = forecast_cone(trend, -0.4, START + timedelta(days=28))
    assert cone[-1]["date"] == START + timedelta(days=28)
    assert abs(cone[-1]["mid"] - 78.4) < 1e-6
    assert (cone[-1]["hi"] - cone[-1]["lo"]) > (cone[0]["hi"] - cone[0]["lo"])


def test_model_counts_hits_and_streak():
    rows = _schedule(logged=((1, 80.1, 22.0), (2, 80.5, 21.6), (3, 79.3, 21.0), (4, 78.8, 20.4)))
    model = progress_model(_state(rows, 5), START + timedelta(days=30))
    assert (model["hits"], model["misses"], model["streak"]) == (3, 1, 2)
    assert model["rate"] is not None


def test_model_early_plan_has_no_trend_and_says_so():
    rows = _schedule(logged=((1, 79.9, 21.7),))
    model = progress_model(_state(rows, 2), START + timedelta(days=10))
    assert model["trend"] == [] and model["cone"] == []
    tone, text = ProgressView.verdict(model)
    assert tone == "ok" and "inside the lane" in text
    options = hero_options(model, "weight", "12w")
    names = [series.get("name") for series in options["series"]]
    assert "Measured" in names and "Trend" not in names


def test_hero_with_weigh_ins_draws_trend_forecast_and_lane():
    rows = _schedule(logged=((1, 79.9, 21.7), (2, 79.5, 21.4)))
    model = progress_model(_state(rows, 3, weights=_daily(17)), START + timedelta(days=17))
    options = hero_options(model, "weight", "4w")
    names = [series.get("name") for series in options["series"]]
    for name in ("Plan lane", "Plan", "Weigh-in", "Forecast range", "Forecast", "Trend"):
        assert name in names
    lane = options["series"][0]
    assert lane["type"] == "custom" and len(lane["data"][0]) == 6
    assert options["xAxis"]["min"] < options["xAxis"]["max"]
    assert options["yAxis"]["min"] < options["yAxis"]["max"]
    assert ProgressView.verdict(model)[1].startswith("<b>")


def test_hero_body_fat_shows_dexa():
    rows = _schedule(logged=((1, 79.9, 21.7),))
    scans = [{"week_index": 1, "bf_percent": 21.9, "ffm_kg": 62.0}]
    model = progress_model(_state(rows, 2, scans=scans), START + timedelta(days=10))
    options = hero_options(model, "bf", "plan")
    dexa = [series for series in options["series"] if series.get("name") == "DEXA"][0]
    assert dexa["data"][0][1] == 21.9


def test_fuel_and_calorie_plan_options():
    rows = _schedule()
    model = progress_model(_state(rows, 2), START + timedelta(days=10))
    ring = fuel_ring_options(rows[1])
    assert "2000" in ring["series"][0]["label"]["formatter"]
    kcal = calorie_plan_options(model)
    assert [series["name"] for series in kcal["series"][:3]] == ["Cut", "Reverse", "Bulk"]
    assert kcal["series"][0]["data"][6] == 2000


def test_composition_uses_weight_times_body_fat():
    rows = _schedule(logged=((1, 80.0, 20.0),))
    model = progress_model(_state(rows, 2), START + timedelta(days=10))
    fat = composition_options(model, "fat")
    lean = composition_options(model, "lean")
    assert fat["series"][1]["data"][0] == 16.0
    assert lean["series"][1]["data"][0] == 64.0


def test_scorecard_marks_states_and_tooltips():
    rows = _schedule(logged=((1, 80.1, 22.0), (2, 81.5, 21.6)))
    model = progress_model(_state(rows, 3), START + timedelta(days=16))
    markup = ProgressView.scorecard_html(model)
    assert markup.count('data-week="1"') == 2
    assert "is-hit" in markup and "is-miss" in markup and "is-now" in markup
    assert "Week 2 · 26 Oct–1 Nov" in markup


def test_tiles_and_timeline_render_early_state():
    rows = _schedule(logged=((1, 79.9, 21.7),))
    model = progress_model(_state(rows, 2), START + timedelta(days=10))
    tiles = ProgressView.tiles_html(model)
    assert "Weight · week 1" in tiles and "Trend starts after 3 daily weigh-ins" in tiles
    assert "Needs two logged weeks" in tiles
    timeline = ProgressView.timeline_html(model)
    assert "You · W2" in timeline and "2000 kcal" in timeline


def test_signed_formats_sign_and_zero():
    assert ProgressView.signed(0.4) == "+0.4"
    assert ProgressView.signed(-0.42, 2) == "−0.42"
    assert ProgressView.signed(0.01) == "±0.0"
