import anvil.secrets
"""Body composition coach — persistence + craftify_library.BodyCoach rules."""

import json
from datetime import date
from types import SimpleNamespace

import anvil.server
import anvil.users
from anvil.tables import app_tables

from craftify_library.BodyCoach.adapt import adapt_calories, trend_rate_kg
from craftify_library.BodyCoach.dexa import navy_dexa_offset
from craftify_library.BodyCoach.plan import macro_targets, navy_bf, propose_plan
from craftify_library.BodyCoach.plan_kwargs import plan_kwargs_from_profile
from craftify_library.BodyCoach.schedule import average_weight_in_week, build_schedule, week_index_for
from craftify_library.CraftifyAuth import AuthError, craftify_require_user
from DexaExtract import extract_from_bytes
from plan_history import dexa_weeks, merge_issued_calories


def _user():
    return craftify_require_user()


def _table_rows(table):
    try:
        return list(table.search())
    except IndexError:
        return list(table)


def _same_user(link, user) -> bool:
    if link is None or user is None:
        return False
    if link == user:
        return True
    try:
        return link.get_id() == user.get_id()
    except Exception:
        return False


def _cell(row, key, default=None):
    try:
        return row[key]
    except Exception:
        return default


def _rows_for_user(table, user, **filters):
    rows = []
    for row in _table_rows(table):
        if not _same_user(_cell(row, "user"), user):
            continue
        if all(_cell(row, key) == value for key, value in filters.items()):
            rows.append(row)
    return rows


def _coach_state(profile) -> dict:
    try:
        return json.loads(profile["coach_state_json"] or "{}")
    except json.JSONDecodeError:
        return {}


def _save_coach_state(profile, state: dict) -> None:
    profile["coach_state_json"] = json.dumps(state)
    profile.update()


def _row_as_profile(row) -> SimpleNamespace:
    return SimpleNamespace(
        sex=row["sex"],
        date_of_birth=row["date_of_birth"],
        height_cm=row["height_cm"],
        start_weight_kg=row["start_weight_kg"],
        waist_cm=row["waist_cm"],
        neck_cm=row["neck_cm"],
        hip_cm=row.get("hip_cm"),
        training_days=row["training_days"],
        daily_steps=row["daily_steps"],
        start_date=row["start_date"],
        outcome=row["outcome"],
        chain_gain=row["chain_gain"],
        phases_json=row["phases_json"],
        forecast_end=row.get("forecast_end"),
        coach_state_json=row.get("coach_state_json"),
        dexa_bf_percent=_cell(row, "dexa_bf_percent"),
        dexa_ffm_kg=_cell(row, "dexa_ffm_kg"),
        dexa_rmr_kcal=_cell(row, "dexa_rmr_kcal"),
    )


def _weight_view(row):
    return SimpleNamespace(logged_on=row["logged_on"], weight_kg=row["weight_kg"])


def _log_view(row):
    return SimpleNamespace(
        week_index=row["week_index"],
        check_in_date=row.get("check_in_date"),
        avg_weight_kg=row.get("avg_weight_kg"),
        waist_cm=row.get("waist_cm"),
        neck_cm=row.get("neck_cm"),
        bf_percent=row.get("bf_percent"),
        training_sessions=row.get("training_sessions"),
        daily_steps=row.get("daily_steps"),
        training_feel=row.get("training_feel"),
        adherence=row.get("adherence"),
        trend_rate_kg=row.get("trend_rate_kg"),
        status=row.get("status") or "logged",
        notes=row.get("notes"),
        next_calories=row.get("next_calories"),
        adjustment_reason=row.get("adjustment_reason"),
    )


def _load_bundle(user):
    rows = _rows_for_user(app_tables.profiles, user)
    profile = rows[0] if rows else None
    if profile is None:
        return None, [], []
    weight_rows = sorted(_rows_for_user(app_tables.weight_logs, user), key=lambda r: r["logged_on"])
    log_rows = sorted(_rows_for_user(app_tables.week_logs, user), key=lambda r: r["week_index"])
    return profile, [_weight_view(r) for r in weight_rows], [_log_view(r) for r in log_rows]


def _backfill_coach_state(profile) -> None:
    state = _coach_state(profile)
    if state.get("bmr"):
        return
    proposal = propose_plan(**plan_kwargs_from_profile(_row_as_profile(profile)))
    _save_coach_state(
        profile,
        {
            "bmr": proposal.bmr,
            "tdee": proposal.tdee,
            "multiplier": proposal.multiplier,
            "weekly_rate_kg": proposal.weekly_rate_kg,
            "issued_calories": {"1": profile["calories"]},
            "navy_bf_percent": proposal.navy_bf_percent,
            "navy_dexa_offset": _offset_from_proposal(proposal, _cell(profile, "dexa_bf_percent")),
            "bmr_source": proposal.bmr_source,
            "bmr_mifflin": proposal.bmr_mifflin,
            "bf_milestones": proposal.bf_milestones,
        },
    )


def _adjustment_reason(last_log, profile_reason: str) -> str:
    """Week logs are SimpleNamespace views — not dicts."""
    if last_log is None:
        return profile_reason
    reason = getattr(last_log, "adjustment_reason", None)
    return reason if reason else profile_reason


def _iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value)
    return text[:10] if text else None


def _as_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _offset_from_proposal(proposal, dexa_bf):
    if dexa_bf is None or proposal.bf_percent is None or proposal.navy_bf_percent is None:
        return None
    return navy_dexa_offset(dexa_bf_percent=proposal.bf_percent, navy_bf_percent=proposal.navy_bf_percent)


def _dexa_table():
    return getattr(app_tables, "dexa_scans", None)


def _dexa_rows(user):
    table = _dexa_table()
    if table is None:
        return []
    return _rows_for_user(table, user)


def _dump_scans(user):
    rows = []
    for scan in _dexa_rows(user):
        media = _cell(scan, "file")
        rows.append(
            {
                "measured_on": _iso(_cell(scan, "measured_on")),
                "week_index": _cell(scan, "week_index"),
                "bf_percent": _cell(scan, "bf_percent"),
                "ffm_kg": _cell(scan, "ffm_kg"),
                "rmr_kcal": _cell(scan, "rmr_kcal"),
                "filename": getattr(media, "name", None) if media is not None else None,
            }
        )
    return rows


def _write_dexa(profile, payload):
    measured = _as_date(payload.get("dexa_measured_on"))
    profile["dexa_measured_on"] = measured
    profile["dexa_bf_percent"] = payload.get("dexa_bf_percent")
    profile["dexa_ffm_kg"] = payload.get("dexa_ffm_kg")
    rmr = payload.get("dexa_rmr_kcal")
    profile["dexa_rmr_kcal"] = int(rmr) if rmr not in (None, "") else None


def _coach_state_from_proposal(profile, proposal):
    old = _coach_state(profile)
    return {
        "bmr": proposal.bmr,
        "tdee": proposal.tdee,
        "multiplier": proposal.multiplier,
        "weekly_rate_kg": proposal.weekly_rate_kg,
        "issued_calories": merge_issued_calories(old.get("issued_calories"), proposal.calories),
        "navy_bf_percent": proposal.navy_bf_percent,
        "navy_dexa_offset": _offset_from_proposal(proposal, _cell(profile, "dexa_bf_percent")),
        "bmr_source": proposal.bmr_source,
        "bmr_mifflin": proposal.bmr_mifflin,
        "bf_milestones": proposal.bf_milestones,
        "slow_streak": old.get("slow_streak") or 0,
    }


def _dump(profile, weights, logs) -> dict:
    phases = json.loads(profile["phases_json"])
    series = json.loads(profile["series_json"])
    actual = [{"date": _iso(getattr(row, "logged_on", None) or row["logged_on"]), "kg": getattr(row, "weight_kg", None) if hasattr(row, "weight_kg") else row["weight_kg"]} for row in weights]
    latest = actual[-1]["kg"] if actual else None
    state = _coach_state(profile)
    schedule = build_schedule(profile=_row_as_profile(profile), weights=weights, logs=logs)
    current_week = week_index_for(date.today(), profile["start_date"])
    current_row = next((row for row in schedule if row["week"] == current_week), schedule[0] if schedule else None)
    last_log = logs[-1] if logs else None
    return {
        "has_plan": True,
        "phase": profile["phase"],
        "calories": current_row["target_calories"] if current_row else profile["calories"],
        "protein_g": current_row["protein_g"] if current_row else profile["protein_g"],
        "fat_g": current_row["fat_g"] if current_row else profile["fat_g"],
        "carbs_g": current_row["carbs_g"] if current_row else profile["carbs_g"],
        "reason": _adjustment_reason(last_log, profile["reason"]),
        "bf_percent": profile.get("bf_percent"),
        "target_bf_percent": profile.get("target_bf_percent"),
        "target_weight_kg": profile.get("target_weight_kg"),
        "start_weight_kg": profile["start_weight_kg"],
        "forecast_end": profile["forecast_end"].isoformat() if profile.get("forecast_end") else None,
        "start_date": profile["start_date"].isoformat(),
        "phases": phases,
        "weight_series": series,
        "weights": actual,
        "latest_weight_kg": latest,
        "chain_gain": profile["chain_gain"],
        "outcome": profile["outcome"],
        "training_days": profile["training_days"],
        "daily_steps": profile["daily_steps"],
        "waist_cm": profile["waist_cm"],
        "neck_cm": profile["neck_cm"],
        "hip_cm": profile.get("hip_cm"),
        "sex": profile["sex"],
        "date_of_birth": profile["date_of_birth"],
        "height_cm": profile["height_cm"],
        "bmr_source": state.get("bmr_source"),
        "bf_milestones": state.get("bf_milestones") or [],
        "current_week": current_week,
        "tdee": state.get("tdee"),
        "bmr": state.get("bmr"),
        "weekly_rate_kg": state.get("weekly_rate_kg"),
        "navy_dexa_offset": state.get("navy_dexa_offset"),
        "dexa_bf_percent": _cell(profile, "dexa_bf_percent"),
        "dexa_ffm_kg": _cell(profile, "dexa_ffm_kg"),
        "dexa_rmr_kcal": _cell(profile, "dexa_rmr_kcal"),
        "dexa_measured_on": _iso(_cell(profile, "dexa_measured_on")),
        "dexa_weeks": sorted({
            int(week)
            for week in dexa_weeks(_cell(profile, "dexa_measured_on"), profile["start_date"], week_index_for)
            + [_cell(scan, "week_index") for scan in _dexa_rows(_user())]
            if week
        }),
        "dexa_scans": _dump_scans(_user()),
        "schedule": schedule,
        "email": _user()["email"],
    }


@anvil.server.callable
def bodycomp_get_plan():
    user = _user()
    profile, weights, logs = _load_bundle(user)
    if profile is None:
        return {"has_plan": False, "email": user["email"]}
    _backfill_coach_state(profile)
    return _dump(profile, weights, logs)


@anvil.server.callable
def bodycomp_save_plan(payload: dict):
    user = _user()
    proposal = propose_plan(
        sex=payload["sex"],
        born=payload["date_of_birth"],
        height_cm=float(payload["height_cm"]),
        weight_kg=float(payload["weight_kg"]),
        waist_cm=float(payload["waist_cm"]),
        neck_cm=float(payload["neck_cm"]),
        hip_cm=float(payload["hip_cm"]) if payload.get("hip_cm") else None,
        training_days=int(payload["training_days"]),
        daily_steps=int(payload["daily_steps"]),
        start=payload["start_date"],
        outcome=payload["outcome"],
        chain_gain=bool(payload.get("chain_gain")),
        dexa_bf_percent=payload.get("dexa_bf_percent"),
        dexa_ffm_kg=payload.get("dexa_ffm_kg"),
        dexa_rmr_kcal=int(payload["dexa_rmr_kcal"]) if payload.get("dexa_rmr_kcal") not in (None, "") else None,
    )
    rows = _rows_for_user(app_tables.profiles, user)
    if rows:
        profile = rows[0]
    else:
        profile = app_tables.profiles.add_row(user=user, coach_state_json="{}")
    profile["sex"] = payload["sex"]
    profile["date_of_birth"] = payload["date_of_birth"]
    profile["height_cm"] = float(payload["height_cm"])
    profile["start_weight_kg"] = float(payload["weight_kg"])
    profile["waist_cm"] = float(payload["waist_cm"])
    profile["neck_cm"] = float(payload["neck_cm"])
    profile["hip_cm"] = float(payload["hip_cm"]) if payload.get("hip_cm") else None
    profile["training_days"] = int(payload["training_days"])
    profile["daily_steps"] = int(payload["daily_steps"])
    profile["start_date"] = payload["start_date"]
    profile["outcome"] = payload["outcome"]
    profile["chain_gain"] = bool(payload.get("chain_gain")) or (
        proposal.phase == "cut" and any(p.name == "bulk" for p in proposal.phases)
    )
    _write_dexa(profile, payload)
    profile["phase"] = proposal.phase
    profile["calories"] = proposal.calories
    protein_g, fat_g, carbs_g = macro_targets(proposal.calories, float(payload["weight_kg"]), proposal.phase)
    profile["protein_g"] = protein_g
    profile["fat_g"] = fat_g
    profile["carbs_g"] = carbs_g
    profile["reason"] = proposal.reason
    profile["bf_percent"] = proposal.bf_percent
    profile["target_bf_percent"] = proposal.target_bf_percent
    profile["target_weight_kg"] = proposal.target_weight_kg
    profile["forecast_end"] = proposal.forecast_end
    profile["phases_json"] = json.dumps(
        [
            {
                "name": phase.name,
                "start": phase.start.isoformat(),
                "end": phase.end.isoformat() if phase.end else None,
                "calories": phase.calories,
                "summary": phase.summary,
            }
            for phase in proposal.phases
        ]
    )
    profile["series_json"] = json.dumps([{"label": label, "kg": kg} for label, kg in proposal.weight_series])
    _save_coach_state(profile, _coach_state_from_proposal(profile, proposal))
    profile.update()
    profile, weights, logs = _load_bundle(user)
    return _dump(profile, weights, logs)


@anvil.server.callable
def bodycomp_log_weight(weight_kg: float, logged_on=None):
    user = _user()
    logged_on = logged_on or date.today()
    rows = _rows_for_user(app_tables.weight_logs, user, logged_on=logged_on)
    if rows:
        row = rows[0]
        row["weight_kg"] = float(weight_kg)
        row.update()
    else:
        app_tables.weight_logs.add_row(user=user, logged_on=logged_on, weight_kg=float(weight_kg))
    profile, weights, logs = _load_bundle(user)
    if profile is None:
        return {"has_plan": False}
    return _dump(profile, weights, logs)


@anvil.server.callable
def bodycomp_check_in(week_index: int, payload: dict | None = None):
    user = _user()
    payload = payload or {}
    profile, weights, logs = _load_bundle(user)
    if profile is None:
        raise AuthError("Create a plan before checking in.")
    check_in_date = payload.get("check_in_date") or date.today()
    schedule = build_schedule(profile=_row_as_profile(profile), weights=weights, logs=logs)
    row = next((item for item in schedule if item["week"] == week_index), None)
    if row is None:
        raise AuthError("Unknown week.")
    week_start = date.fromisoformat(row["week_start"])
    avg_weight = payload.get("avg_weight_kg")
    if avg_weight is None:
        avg_weight = average_weight_in_week([(w["logged_on"], w["weight_kg"]) for w in weights], week_start)
    existing = _rows_for_user(app_tables.week_logs, user, week_index=week_index)
    log = existing[0] if existing else app_tables.week_logs.add_row(user=user, week_index=week_index)
    if existing and _cell(log, "check_in_date"):
        check_in_date = log["check_in_date"]
    log["check_in_date"] = check_in_date
    log["avg_weight_kg"] = avg_weight
    log["waist_cm"] = payload.get("waist_cm")
    log["neck_cm"] = payload.get("neck_cm")
    log["training_sessions"] = payload.get("training_sessions")
    log["daily_steps"] = payload.get("daily_steps")
    log["training_feel"] = payload.get("training_feel")
    log["adherence"] = payload.get("adherence")
    log["notes"] = payload.get("notes")
    log["status"] = "logged" if payload.get("adherence") not in {"off", "roughly"} else "excluded"
    if payload.get("waist_cm") and payload.get("neck_cm"):
        bf = navy_bf(profile["sex"], profile["height_cm"], payload["waist_cm"], payload["neck_cm"], profile.get("hip_cm"))
        log["bf_percent"] = round(bf, 1) if bf is not None else None
    log.update()
    log_rows = sorted(_rows_for_user(app_tables.week_logs, user), key=lambda r: r["week_index"])
    logs = [_log_view(r) for r in log_rows]
    schedule = build_schedule(profile=_row_as_profile(profile), weights=weights, logs=logs)
    avgs = [item["actual_weight_kg"] for item in schedule if item["week"] <= week_index]
    rate = trend_rate_kg(avgs)
    log["trend_rate_kg"] = rate
    state = _coach_state(profile)
    slow_streak = int(state.get("slow_streak", 0))
    if rate is not None and rate > -(state.get("weekly_rate_kg") or 0.4) * 0.6:
        slow_streak += 1
    else:
        slow_streak = 0
    state["slow_streak"] = slow_streak
    current_calories = row["target_calories"]
    adaptation = adapt_calories(
        phase=row["phase"],
        current_calories=current_calories,
        chosen_rate_kg=state.get("weekly_rate_kg") or 0.4,
        trend_rate_kg=rate,
        slow_streak=slow_streak,
        bmr=int(state.get("bmr") or 1500),
        maintenance=int(state.get("tdee") or current_calories),
    )
    next_week = week_index + 1
    issued = state.setdefault("issued_calories", {})
    next_key = str(next_week)
    if next_key not in issued:
        issued[next_key] = adaptation.next_calories
        log["next_calories"] = adaptation.next_calories
        log["adjustment_reason"] = adaptation.reason
        if next_week == week_index_for(date.today(), profile["start_date"]) + 1:
            profile["calories"] = adaptation.next_calories
            profile["reason"] = adaptation.reason
            profile.update()
    _save_coach_state(profile, state)
    log.update()
    profile, weights, logs = _load_bundle(user)
    return _dump(profile, weights, logs)


@anvil.server.callable
def bodycomp_delete_week_log(week_index: int):
    user = _user()
    for log in _rows_for_user(app_tables.week_logs, user, week_index=int(week_index)):
        log.delete()
    profile, weights, logs = _load_bundle(user)
    if profile is None:
        return {"has_plan": False}
    return _dump(profile, weights, logs)


@anvil.server.callable
def bodycomp_delete_weight(logged_on):
    user = _user()
    day = _as_date(logged_on)
    for row in _rows_for_user(app_tables.weight_logs, user, logged_on=day):
        row.delete()
    profile, weights, logs = _load_bundle(user)
    if profile is None:
        return {"has_plan": False}
    return _dump(profile, weights, logs)


@anvil.server.callable
def bodycomp_reissue_next_week(week_index: int):
    """Recalculate and overwrite the next week's issued calories from this week's log."""
    user = _user()
    profile, weights, logs = _load_bundle(user)
    if profile is None:
        raise AuthError("Create a plan first.")
    week_index = int(week_index)
    schedule = build_schedule(profile=_row_as_profile(profile), weights=weights, logs=logs)
    row = next((item for item in schedule if item["week"] == week_index), None)
    if row is None:
        raise AuthError("Unknown week.")
    avgs = [item["actual_weight_kg"] for item in schedule if item["week"] <= week_index]
    rate = trend_rate_kg(avgs)
    state = _coach_state(profile)
    adaptation = adapt_calories(
        phase=row["phase"],
        current_calories=row["target_calories"],
        chosen_rate_kg=state.get("weekly_rate_kg") or 0.4,
        trend_rate_kg=rate,
        slow_streak=int(state.get("slow_streak") or 0),
        bmr=int(state.get("bmr") or 1500),
        maintenance=int(state.get("tdee") or row["target_calories"]),
    )
    issued = state.setdefault("issued_calories", {})
    issued[str(week_index + 1)] = adaptation.next_calories
    existing = _rows_for_user(app_tables.week_logs, user, week_index=week_index)
    if existing:
        existing[0]["next_calories"] = adaptation.next_calories
        existing[0]["adjustment_reason"] = adaptation.reason
        existing[0].update()
    if week_index + 1 == week_index_for(date.today(), profile["start_date"]):
        profile["calories"] = adaptation.next_calories
        profile["reason"] = adaptation.reason
        profile.update()
    _save_coach_state(profile, state)
    profile, weights, logs = _load_bundle(user)
    return _dump(profile, weights, logs)


@anvil.server.callable
def bodycomp_read_dexa(media):
    if media is None:
        raise AuthError("Choose a DEXA file first.")
    data = media.get_bytes()
    parsed = extract_from_bytes(data, getattr(media, "content_type", "") or "", getattr(media, "name", "") or "")
    parsed.pop("extracted_text", None)
    return parsed


@anvil.server.callable
def bodycomp_store_dexa(media, payload=None):
    user = _user()
    payload = payload or {}
    if media is None:
        raise AuthError("Choose a DEXA file first.")
    parsed = extract_from_bytes(
        media.get_bytes(),
        getattr(media, "content_type", "") or "",
        getattr(media, "name", "") or "",
    )
    measured = _as_date(payload.get("dexa_measured_on") or parsed.get("dexa_measured_on"))
    bf = payload.get("dexa_bf_percent") if payload.get("dexa_bf_percent") not in (None, "") else parsed.get("dexa_bf_percent")
    ffm = payload.get("dexa_ffm_kg") if payload.get("dexa_ffm_kg") not in (None, "") else parsed.get("dexa_ffm_kg")
    rmr = payload.get("dexa_rmr_kcal") if payload.get("dexa_rmr_kcal") not in (None, "") else parsed.get("dexa_rmr_kcal")
    profile_rows = _rows_for_user(app_tables.profiles, user)
    start = profile_rows[0]["start_date"] if profile_rows else date.today()
    week = week_index_for(measured or date.today(), start)
    table = _dexa_table()
    if table is None:
        raise AuthError("DEXA storage is not available yet. Restart the app after the schema update.")
    table.add_row(
        user=user,
        measured_on=measured,
        week_index=week,
        bf_percent=bf,
        ffm_kg=ffm,
        rmr_kcal=int(rmr) if rmr not in (None, "") else None,
        file=media,
        extracted_json=json.dumps({k: v for k, v in parsed.items() if k != "extracted_text"}),
        notes=payload.get("notes") or "",
    )
    if profile_rows:
        profile = profile_rows[0]
        _write_dexa(
            profile,
            {
                "dexa_measured_on": measured,
                "dexa_bf_percent": bf,
                "dexa_ffm_kg": ffm,
                "dexa_rmr_kcal": rmr,
            },
        )
        proposal = propose_plan(**plan_kwargs_from_profile(_row_as_profile(profile)))
        profile["bf_percent"] = proposal.bf_percent
        profile["target_bf_percent"] = proposal.target_bf_percent
        profile["target_weight_kg"] = proposal.target_weight_kg
        profile["reason"] = proposal.reason
        profile["calories"] = proposal.calories
        _save_coach_state(profile, _coach_state_from_proposal(profile, proposal))
        profile.update()
    profile, weights, logs = _load_bundle(user)
    if profile is None:
        return {"has_plan": False, "extract": parsed}
    dumped = _dump(profile, weights, logs)
    dumped["extract"] = parsed
    return dumped


def _ensure_local_password():
    """Give the original local account a known password so the login page works."""
    email = "local@bodycomp.app"
    password = "local-dev-session"
    row = None
    for item in _table_rows(app_tables.users):
        if (item["email"] or "").strip().lower() == email:
            row = item
            break
    if row is None:
        return
    row["enabled"] = True
    row["confirmed_email"] = True
    if "n_password_failures" in row:
        row["n_password_failures"] = 0
    try:
        import bcrypt
        row["password_hash"] = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()
    except Exception:
        return
    row.update()


@anvil.server.callable
def bodycomp_startup():
    """Return plan state for the signed-in user. Does not create a session."""
    try:
        _ensure_local_password()
    except Exception:
        pass
    user = anvil.users.get_user()
    if user is None:
        return {"logged_in": False}
    profile, weights, logs = _load_bundle(user)
    if profile is None:
        return {"has_plan": False, "email": user["email"]}
    _backfill_coach_state(profile)
    return _dump(profile, weights, logs)


@anvil.server.callable
def bodycomp_sign_out():
    anvil.users.logout()
    return True
