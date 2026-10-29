"""Pure Progress scoring helpers. No Anvil imports so pytest can run them."""

SCORED_STATUSES = ("logged", "excluded", "partial")
WEIGHT_LANE_KG = 0.4
BF_LANE_PP = 0.6
CHIP_WINDOW = 8


def _to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(actual_key, target_key, delta_key, row):
    delta = _to_float(row.get(delta_key))
    if delta is not None:
        return delta
    actual = _to_float(row.get(actual_key))
    target = _to_float(row.get(target_key))
    if actual is None or target is None:
        return None
    return actual - target


def _in_lane(delta, lane):
    if delta is None:
        return None
    return abs(delta) <= lane


def score_week(row):
    row = row or {}
    week = row.get("week")
    status = row.get("status") or ""
    if status not in SCORED_STATUSES:
        return {"week": week, "weight_hit": None, "bf_hit": None}

    weight_hit = None
    if _to_float(row.get("actual_weight_kg")) is not None:
        weight_hit = _in_lane(
            _delta("actual_weight_kg", "target_weight_kg", "weight_delta_kg", row),
            WEIGHT_LANE_KG,
        )

    bf_hit = None
    if _to_float(row.get("bf_percent")) is not None:
        bf_hit = _in_lane(
            _delta("bf_percent", "target_bf_percent", "bf_delta", row),
            BF_LANE_PP,
        )

    return {"week": week, "weight_hit": weight_hit, "bf_hit": bf_hit}


def week_chip(rows, current_week):
    scored = []
    for row in rows or []:
        week = row.get("week")
        if current_week is not None and week is not None and week > current_week:
            continue
        result = score_week(row)
        if result["weight_hit"] is None:
            continue
        scored.append(result)
    recent = scored[-CHIP_WINDOW:]
    hits = 0
    for item in recent:
        if item["weight_hit"]:
            hits += 1
    return "%s hit · %s miss" % (hits, len(recent) - hits)


def macro_stack(row):
    row = row or {}
    calories = _to_float(row.get("target_calories"))
    if calories is None or calories == 0:
        return None
    protein = int(_to_float(row.get("protein_g")) or 0)
    fat = int(_to_float(row.get("fat_g")) or 0)
    carbs = int(_to_float(row.get("carbs_g")) or 0)
    protein_kcal = protein * 4
    fat_kcal = fat * 9
    carbs_kcal = carbs * 4
    return {
        "protein_g": protein,
        "fat_g": fat,
        "carbs_g": carbs,
        "protein_kcal": protein_kcal,
        "fat_kcal": fat_kcal,
        "carbs_kcal": carbs_kcal,
        "kcal": protein_kcal + fat_kcal + carbs_kcal,
    }


def journey_points(rows, dexa_weeks=None):
    marked = {}
    for week in dexa_weeks or []:
        if week:
            marked[int(week)] = True
    points = []
    for row in rows or []:
        weight = _to_float(row.get("actual_weight_kg"))
        bf = _to_float(row.get("bf_percent"))
        if weight is None or bf is None:
            continue
        week = row.get("week")
        points.append({
            "week": week,
            "weight": weight,
            "bf": bf,
            "dexa": bool(week in marked),
        })
    return points


def fade_after(values, current_week):
    faded = []
    for index, value in enumerate(values or []):
        if isinstance(value, dict) and value.get("week") is not None:
            week = value.get("week")
            item_value = value.get("value", value)
        else:
            week = index + 1
            item_value = value
        faded.append({
            "value": item_value,
            "faded": False if current_week is None else week > current_week,
        })
    return faded
