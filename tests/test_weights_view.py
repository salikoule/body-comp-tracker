import sys
import types
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if "body_comp_tracker" not in sys.modules:
    package = types.ModuleType("body_comp_tracker")
    package.__path__ = [str(ROOT / "client_code")]
    sys.modules["body_comp_tracker"] = package

from body_comp_tracker import WeightsView as View  # noqa: E402

TODAY = date(2026, 11, 14)
WEIGHTS = [
    {"date": "2026-11-10", "kg": 80.0},
    {"date": "2026-11-12", "kg": 79.4},
    {"date": "2026-11-13", "kg": 79.2},
    {"date": "2026-11-14", "kg": 79.6},
    {"date": "2026-10-01", "kg": 82.0},
]


def test_entries_are_newest_first_with_the_change_from_the_previous_logged_day():
    rows = View.entries(WEIGHTS, start="2026-10-20")
    assert [row["date"] for row in rows] == ["2026-11-14", "2026-11-13", "2026-11-12", "2026-11-10", "2026-10-01"]
    assert rows[0]["delta"] == 0.4
    assert rows[1]["delta"] == -0.2
    assert rows[-1]["delta"] is None
    assert rows[0]["label"].startswith("Sat ")
    assert rows[-1]["week"] is None
    assert rows[0]["week"] == 4


def test_a_later_duplicate_date_replaces_the_earlier_one():
    rows = View.entries([{"date": "2026-11-14", "kg": 80}, {"date": "2026-11-14", "kg": 79.5}])
    assert rows == [{
        "date": "2026-11-14", "label": "Sat 14 Nov 2026", "kg": 79.5, "delta": None, "week": None,
    }]


def test_summary_uses_the_last_seven_days_and_breaks_the_streak_on_a_gap():
    stats = View.summary(WEIGHTS, TODAY)
    assert stats["count"] == 5
    assert stats["latest_kg"] == 79.6
    assert stats["since_first"] == -2.4
    assert stats["week_count"] == 4
    assert stats["week_avg"] == 79.6
    assert stats["streak"] == 3
    assert stats["streak_current"] is True
    assert stats["delta"] == 0.4
    assert View.summary([], TODAY) is None


def test_an_old_streak_is_not_current():
    stats = View.summary([{"date": "2026-11-01", "kg": 81}, {"date": "2026-11-02", "kg": 80.8}], TODAY)
    assert stats["streak"] == 2
    assert stats["streak_current"] is False
    assert stats["week_avg"] is None


def test_a_drop_is_green_and_a_missing_change_is_blank():
    assert "bc-delta-good" in View.delta_html(-1.3)
    assert "+0.4" in View.delta_html(0.4)
    assert "bc-empty" in View.delta_html(None)
