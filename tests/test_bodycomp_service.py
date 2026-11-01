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


def test_plan_save_keeps_issued_calories():
    sys.path.insert(0, str(ROOT / "server_code"))
    from plan_history import merge_issued_calories, dexa_weeks
    from BodyCoach.schedule import week_index_for

    issued = merge_issued_calories({"1": 2000, "2": 1900}, 1800)
    assert issued == {"1": 2000, "2": 1900}
    assert merge_issued_calories({}, 2100) == {"1": 2100}
    assert dexa_weeks(date(2026, 10, 22), date(2026, 10, 19), week_index_for) == [1]


def test_dexa_text_extracts_core_metrics():
    sys.path.insert(0, str(ROOT / "server_code"))
    from DexaExtract import extract_from_text

    parsed = extract_from_text("DEXA 2026-10-20 Body fat 28.8% Fat-free mass 57.7 kg RMR 1550 kcal")
    assert parsed["dexa_bf_percent"] == 28.8
    assert parsed["dexa_ffm_kg"] == 57.7
    assert parsed["dexa_rmr_kcal"] == 1550
    assert parsed["dexa_measured_on"] == "2026-10-20"


def test_dexa_normalize_corrects_misread_core_metrics_from_masses():
    sys.path.insert(0, str(ROOT / "server_code"))
    from DexaExtract import missing_required, normalize

    misread = {
        "dexa_measured_on": "2026-10-22",
        "dexa_bf_percent": 22,
        "dexa_ffm_kg": 62.4,
        "dexa_rmr_kcal": 1550,
        "total_mass_kg": 79.8,
        "fat_mass_kg": 22.055,
        "lean_mass_kg": 54.568,
        "bmc_kg": 3.129,
        "vat_g": 636,
    }
    fixed = normalize(misread)
    assert fixed["dexa_bf_percent"] == 28.8
    assert fixed["dexa_ffm_kg"] == 57.7
    assert missing_required(fixed) == []


def test_dexa_normalize_keeps_reported_values_that_agree():
    sys.path.insert(0, str(ROOT / "server_code"))
    from DexaExtract import missing_required, normalize

    read = normalize({"dexa_measured_on": "22/10/2026", "dexa_bf_percent": 28.8, "dexa_ffm_kg": 57.698,
                      "total_mass_kg": 79.8, "fat_mass_kg": 22.055, "lean_mass_kg": 54.568, "bmc_kg": 3.129})
    assert read["dexa_bf_percent"] == 28.8
    assert read["dexa_ffm_kg"] == 57.698
    assert read["dexa_measured_on"] == "2026-10-22"
    assert missing_required(read) == ["dexa_rmr_kcal"]


def test_tracker_icons_are_lucide_from_body_comp():
    for name in ("flame", "protein", "fat", "carbs", "down", "up", "reverse"):
        assert ICON[name].startswith("<svg")
    assert 'cx="12.5"' in ICON["protein"]
    assert "M7 16.3" in ICON["fat"]
    assert "M2 22 16 8" in ICON["carbs"]
    assert ICON["fat"] != ICON["carbs"]
    assert PHASE_ICON["cut"] == "down"
    assert PHASE_ICON["bulk"] == "up"
