import sys
import types
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client_code"))
if "body_comp_tracker" not in sys.modules:
    package = types.ModuleType("body_comp_tracker")
    package.__path__ = [str(ROOT / "client_code")]
    sys.modules["body_comp_tracker"] = package

from body_comp_tracker import DexaMap  # noqa: E402
from body_comp_tracker.DexaRatings import person_from_state  # noqa: E402

SCAN = {
    "measured_on": "2026-10-22",
    "bf_percent": 28.8,
    "ffm_kg": 57.698,
    "fat_mass_kg": 22.055,
    "lean_mass_kg": 54.568,
    "bmc_kg": 3.129,
}
STATE = {"sex": "male", "date_of_birth": "1994-12-07", "height_cm": 175, "target_bf_percent": 12, "target_weight_kg": 65.6}


def _model(scans=(SCAN,)):
    return DexaMap.map_model(list(scans), person_from_state(STATE, date(2026, 10, 22)))


def _zone_at(model, x, y):
    for zone in model["zones"]:
        polygon = zone["polygon"]
        inside = False
        for i, (x1, y1) in enumerate(polygon):
            x2, y2 = polygon[i - 1]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
        if inside:
            return zone["band"]["label"]
    return None


def test_point_and_goal_land_in_the_same_bands_as_the_cards():
    model = _model()
    latest, goal = model["latest"], model["goal"]
    assert round(latest["fmi"], 1) == 7.2 and round(latest["ffmi"], 1) == 18.8
    assert round(goal["fmi"], 1) == 2.6 and round(goal["ffmi"], 1) == 18.8
    assert _zone_at(model, latest["fmi"], latest["ffmi"]) == "High"
    assert _zone_at(model, goal["fmi"], goal["ffmi"]) == "Fit"


def test_zones_tile_the_view_and_fit_the_slots():
    model = _model()
    assert [zone["band"]["label"] for zone in model["zones"]] == ["Athletic", "Fit", "Average", "High", "Very high"]
    for zone in model["zones"]:
        assert 3 <= len(zone["polygon"]) <= DexaMap.POLYGON_SLOTS
        assert len(DexaMap._pad(zone["polygon"])) == DexaMap.POLYGON_SLOTS * 2


def test_reading_explains_the_plan_and_progress():
    later = dict(SCAN, measured_on="2027-01-10", fat_mass_kg=18.0, ffm_kg=58.2)
    notes = {note["title"]: note["text"] for note in DexaMap.reading(_model([SCAN, later]))}
    assert "high body fat (28.8%) with average muscle" in notes["Where you are"]
    assert "65.6 kg at 12.0% body fat" in notes["Where the plan takes you"]
    assert "−4.1 kg fat and +0.5 kg lean mass since 22 Oct 2026" in notes["Since your first scan"]


def test_no_height_means_no_map():
    assert DexaMap.map_model([SCAN], {"sex": "male", "height_cm": None}) is None
