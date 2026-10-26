"""Keep in sync with BodyCompService._adjustment_reason (SimpleNamespace week logs)."""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client_code"))
from Icons import ICON, PHASE_ICON
from types import SimpleNamespace

from BodyCoach.schedule import build_schedule


def adjustment_reason(last_log, profile_reason: str) -> str:
    if last_log is None:
        return profile_reason
    reason = getattr(last_log, "adjustment_reason", None)
    return reason if reason else profile_reason


def test_adjustment_reason_from_log_view():
    log = SimpleNamespace(adjustment_reason="Slow loss — minus 100 kcal")
    assert adjustment_reason(log, "Initial plan") == "Slow loss — minus 100 kcal"


def test_adjustment_reason_falls_back_to_profile():
    log = SimpleNamespace(adjustment_reason=None)
    assert adjustment_reason(log, "Initial plan") == "Initial plan"
    assert adjustment_reason(None, "Initial plan") == "Initial plan"


def test_build_schedule_with_namespace_logs():
    profile = SimpleNamespace(
        sex="male",
        date_of_birth=date(1990, 5, 15),
        height_cm=178.0,
        start_weight_kg=82.0,
        waist_cm=86.0,
        neck_cm=38.0,
        hip_cm=None,
        training_days=4,
        daily_steps=10000,
        start_date=date(2026, 1, 6),
        outcome="lose_fat",
        chain_gain=False,
        phases_json='[{"name":"cut","start":"2026-01-06","end":null,"calories":2100,"summary":"Cut"}]',
        forecast_end=date(2026, 6, 1),
        coach_state_json='{"issued_calories":{"1":2100},"weekly_rate_kg":0.4,"bmr":1700,"tdee":2400}',
        dexa_bf_percent=None,
        dexa_ffm_kg=None,
        dexa_rmr_kcal=None,
    )
    logs = [
        SimpleNamespace(
            week_index=1,
            check_in_date=date(2026, 1, 12),
            avg_weight_kg=81.5,
            waist_cm=85.0,
            neck_cm=38.0,
            bf_percent=18.0,
            training_sessions=4,
            daily_steps=10000,
            training_feel="normal",
            adherence="on_target",
            trend_rate_kg=-0.5,
            status="logged",
            notes=None,
            adjustment_reason="Trend slow",
        )
    ]
    rows = build_schedule(profile=profile, weights=[], logs=logs, today=date(2026, 1, 15))
    assert rows[0]["week"] == 1
    assert rows[0]["actual_weight_kg"] == 81.5
    assert adjustment_reason(logs[-1], "fallback") == "Trend slow"


def test_tracker_icons_are_lucide_from_body_comp():
    for name in ("flame", "protein", "fat", "carbs", "down", "up", "reverse"):
        assert ICON[name].startswith("<svg")
    assert 'cx="12.5"' in ICON["protein"]
    assert "M7 16.3" in ICON["fat"]
    assert "M2 22 16 8" in ICON["carbs"]
    assert ICON["fat"] != ICON["carbs"]
    assert PHASE_ICON["cut"] == "down"
    assert PHASE_ICON["bulk"] == "up"
