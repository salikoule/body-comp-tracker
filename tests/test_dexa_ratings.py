import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client_code"))

from DexaRatings import age_on, bf_cuts, person_from_state, rate_scan, rating  # noqa: E402

SCAN = {
    "measured_on": "2026-10-22",
    "bf_percent": 28.8,
    "ffm_kg": 57.698,
    "rmr_kcal": 1550,
    "total_mass_kg": 79.8,
    "fat_mass_kg": 22.055,
    "lean_mass_kg": 54.568,
    "bmc_kg": 3.129,
    "vat_g": 636,
}
STATE = {"sex": "male", "date_of_birth": "1994-12-07", "height_cm": 174, "target_bf_percent": 12, "target_weight_kg": 65.6}


def _cards():
    person = person_from_state(STATE, date(2026, 10, 22))
    return person, {card["key"]: card for card in rate_scan(SCAN, person)}


def test_age_and_bands_follow_the_person():
    assert age_on("1994-12-07", date(2026, 10, 22)) == 31
    assert bf_cuts("male", 31) == (12, 18, 24, 30)
    assert bf_cuts("male", 45) == (14, 20, 26, 32)
    assert bf_cuts("female", 31) == (20, 27, 33, 39)


def test_real_scan_is_rated_and_explained():
    person, cards = _cards()
    bf = cards["bf_percent"]
    assert (bf["tone"], bf["verdict"]) == ("high", "High")
    assert "a man aged 31" in bf["summary"]
    assert "70.4 kg" in bf["detail"] and "9.4 kg less fat" in bf["detail"]
    assert "Your plan aims for 12.0% (65.6 kg)" in bf["detail"]
    assert (cards["vat_g"]["tone"], cards["vat_g"]["verdict"]) == ("fair", "Moderate")
    assert "186 g above ideal" in cards["vat_g"]["detail"]
    assert (cards["ffmi"]["display"], cards["ffmi"]["verdict"]) == ("19.1", "Average")
    assert "2.9 kg more lean mass" in cards["ffmi"]["detail"]
    assert cards["rmr_kcal"]["tone"] == "info" and "1,616 kcal" in cards["rmr_kcal"]["detail"]
    assert 0 <= bf["marker"] <= 100


def test_deltas_reward_fat_loss_and_lean_gain():
    person, _cards_now = _cards()
    later = dict(SCAN, bf_percent=26.0, ffm_kg=58.6, vat_g=560)
    cards = {card["key"]: card for card in rate_scan(later, person, previous=SCAN)}
    assert cards["bf_percent"]["delta"] == {"text": "−2.8 pp since last scan", "tone": "good"}
    assert cards["vat_g"]["delta"]["tone"] == "good"
    assert cards["ffmi"]["delta"]["tone"] == "good"


def test_table_cell_rating_has_hover_text():
    person, _ = _cards()
    tone, text = rating(SCAN, person, "bf_percent")
    assert tone == "high" and text.startswith("High: 28.8%")
    assert rating(SCAN, person, "rmr_kcal") == (None, "")
