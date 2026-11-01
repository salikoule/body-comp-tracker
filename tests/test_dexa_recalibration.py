import json
from datetime import date
from types import SimpleNamespace

from BodyCoach.plan import propose_plan
from BodyCoach.plan_kwargs import plan_kwargs_from_profile
from BodyCoach.schedule import build_schedule


def _phases_json(proposal):
    return json.dumps([
        {"name": p.name, "start": p.start.isoformat(), "end": p.end.isoformat() if p.end else None,
         "calories": p.calories, "summary": p.summary}
        for p in proposal.phases
    ])


def _profile(**overrides):
    base = dict(
        sex="male", date_of_birth=date(1994, 12, 7), height_cm=175.0, start_weight_kg=79.5,
        waist_cm=94.0, neck_cm=40.0, hip_cm=None, training_days=4, daily_steps=10000,
        start_date=date(2026, 10, 23), outcome="lose_fat", chain_gain=True,
        dexa_bf_percent=None, dexa_ffm_kg=None, dexa_rmr_kcal=None,
        coach_state_json='{"issued_calories":{"1":2000},"weekly_rate_kg":0.398}',
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _largest_jumps(rows):
    weight = max(abs(b["target_weight_kg"] - a["target_weight_kg"]) for a, b in zip(rows, rows[1:]))
    bf = max(abs(b["target_bf_percent"] - a["target_bf_percent"]) for a, b in zip(rows, rows[1:]))
    return weight, bf


def _schedule(profile, proposal):
    profile.phases_json = _phases_json(proposal)
    profile.forecast_end = proposal.forecast_end
    return build_schedule(profile=profile, weights=[], logs=[], today=date(2026, 11, 1))


def test_dexa_anchor_without_new_phases_leaps_at_the_end_of_the_cut():
    before = _profile()
    stale = propose_plan(**plan_kwargs_from_profile(before))
    after = _profile(dexa_bf_percent=25.3, dexa_ffm_kg=57.7, dexa_rmr_kcal=1650)
    after.phases_json = _phases_json(stale)
    after.forecast_end = stale.forecast_end
    rows = build_schedule(profile=after, weights=[], logs=[], today=date(2026, 11, 1))
    weight_jump, bf_jump = _largest_jumps(rows)
    assert weight_jump > 2 or bf_jump > 2


def test_dexa_anchor_with_rebuilt_phases_moves_smoothly():
    after = _profile(dexa_bf_percent=25.3, dexa_ffm_kg=57.7, dexa_rmr_kcal=1650)
    rows = _schedule(after, propose_plan(**plan_kwargs_from_profile(after)))
    weight_jump, bf_jump = _largest_jumps(rows)
    assert weight_jump <= 0.6
    assert bf_jump <= 1.0
