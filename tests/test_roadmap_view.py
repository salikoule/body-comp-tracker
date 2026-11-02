import sys
import types
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if "body_comp_tracker" not in sys.modules:
    package = types.ModuleType("body_comp_tracker")
    package.__path__ = [str(ROOT / "client_code")]
    sys.modules["body_comp_tracker"] = package

import Roadmap  # noqa: E402
from body_comp_tracker import RoadmapView as View  # noqa: E402

PLANS = Roadmap.roadmaps(sex="male", height_cm=175, weight_kg=79.8, ffm_kg=57.7, goal_bf=14.5, goal_ffmi=22,
                         training_years=1, start=date(2026, 11, 2))
for plan, (key, name, pitch) in zip(PLANS, Roadmap.STRATEGIES):
    plan.update({"name": name, "pitch": pitch})


def test_goal_preview_describes_the_body_in_kilos():
    text = View.goal_preview(14.5, 22.0, 175, 57.7)
    assert "78.8 kg" in text and "67.4 kg fat-free" in text and "9.7 kg more lean mass" in text


def test_tiles_mark_selection_and_coach_pick():
    html = View.tiles_html(PLANS, "slow_gain", recommended="cycles")
    assert html.count("bc-rm-tile") >= 3
    assert 'is-selected" data-key="slow_gain"' in html
    assert html.index("Coach pick") < html.index('data-key="slow_gain"')


def test_timeline_lists_every_phase_with_notes():
    plan = PLANS[0]
    html = View.timeline_html(plan, {0: "Keep protein at 2.2 g/kg."})
    assert html.count('class="bc-rm-row"') == len(plan["phases"])
    assert "Keep protein at 2.2 g/kg." in html
    assert "kcal a day below maintenance" in html and "kcal a day above maintenance" in html


def test_stale_review_when_goal_or_scan_changes():
    entry = {"goal": {"bf_percent": 14.5, "ffmi": 22.0, "training_years": 1.0}, "scan": "2026-10-22"}
    assert not View.review_is_stale(entry, dict(entry["goal"]), "2026-10-22")
    assert View.review_is_stale(entry, dict(entry["goal"], ffmi=20.5), "2026-10-22")
    assert View.review_is_stale(entry, entry["goal"], "2027-01-10")
