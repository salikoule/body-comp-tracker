"""Pure Progress scoring and ECharts option builders. No Anvil imports."""

SCORED_STATUSES = ("logged", "excluded", "partial")
WEIGHT_LANE_KG = 0.4
BF_LANE_PP = 0.6
CHIP_WINDOW = 8
FADE_OPACITY = 0.28
HIT_COLOR = "#16a34a"
MISS_COLOR = "#dc2626"
PHASE_BAND = {
    "cut": "rgba(244, 63, 94, 0.10)",
    "reverse": "rgba(245, 158, 11, 0.10)",
    "bulk": "rgba(45, 212, 191, 0.12)",
    "recomp": "rgba(148, 163, 184, 0.10)",
}
MACRO_COLORS = {"Protein": "#38bdf8", "Fat": "#f59e0b", "Carbs": "#a78bfa"}
JOURNEY_SIZE = 8
DEXA_SIZE = 14


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


def _week_label(week):
    return "W%s" % week


def _is_future(week, current_week):
    return current_week is not None and week is not None and week > current_week


def _phase_ranges(rows):
    ranges = []
    start = None
    current = None
    last_week = None
    for row in rows or []:
        phase = row.get("phase") or "cut"
        week = row.get("week")
        if start is None:
            start = week
            current = phase
        elif phase != current:
            ranges.append((start, last_week, current))
            start = week
            current = phase
        last_week = week
    if start is not None:
        ranges.append((start, last_week, current))
    return ranges


def _phase_mark_area(rows):
    data = []
    for start, end, phase in _phase_ranges(rows):
        data.append([
            {
                "xAxis": _week_label(start),
                "itemStyle": {"color": PHASE_BAND.get(phase, PHASE_BAND["recomp"])},
            },
            {"xAxis": _week_label(end)},
        ])
    if not data:
        return None
    return {"silent": True, "data": data}


def _hit_color(hit):
    if hit is True:
        return HIT_COLOR
    if hit is False:
        return MISS_COLOR
    return None


def _actual_point(value, hit, stop):
    if stop or value is None:
        return None
    point = {"value": value}
    color = _hit_color(hit)
    if color:
        point["itemStyle"] = {"color": color}
    return point


def _macro_points(row, current_week):
    stack = macro_stack(row)
    if stack is None:
        return None, None, None
    faded = _is_future(row.get("week"), current_week)
    extras = {
        "protein_g": stack["protein_g"],
        "fat_g": stack["fat_g"],
        "carbs_g": stack["carbs_g"],
        "kcal": stack["kcal"],
    }

    def point(field):
        item = dict(extras)
        item["value"] = stack[field]
        if faded:
            item["itemStyle"] = {"opacity": FADE_OPACITY}
        return item

    return point("protein_kcal"), point("fat_kcal"), point("carbs_kcal")


def spine_options(rows, current_week):
    rows = rows or []
    weeks = [_week_label(row.get("week")) for row in rows]
    scored_by_week = []
    last_scored = None
    for row in rows:
        scored = score_week(row)
        scored_by_week.append(scored)
        if scored["weight_hit"] is not None or scored["bf_hit"] is not None:
            last_scored = row.get("week")
    bands = _phase_mark_area(rows)
    weight_target = []
    weight_actual = []
    lane_low = []
    lane_span = []
    bf_target = []
    bf_actual = []
    protein = []
    fat = []
    carbs = []
    for index, row in enumerate(rows):
        week = row.get("week")
        scored = scored_by_week[index]
        stop = last_scored is None or (week is not None and week > last_scored)
        target_w = _to_float(row.get("target_weight_kg"))
        weight_target.append(target_w)
        if target_w is None:
            lane_low.append(None)
            lane_span.append(None)
        else:
            lane_low.append(target_w - WEIGHT_LANE_KG)
            lane_span.append(WEIGHT_LANE_KG * 2)
        weight_actual.append(_actual_point(_to_float(row.get("actual_weight_kg")), scored["weight_hit"], stop))
        bf_target.append(_to_float(row.get("target_bf_percent")))
        bf_actual.append(_actual_point(_to_float(row.get("bf_percent")), scored["bf_hit"], stop))
        protein_pt, fat_pt, carbs_pt = _macro_points(row, current_week)
        protein.append(protein_pt)
        fat.append(fat_pt)
        carbs.append(carbs_pt)

    def axis(grid_index, show_labels=False):
        return {
            "type": "category",
            "data": weeks,
            "gridIndex": grid_index,
            "axisLabel": {"show": show_labels},
            "axisTick": {"show": False},
        }

    def line(name, data, grid_index, dashed=False, color=None, mark_area=None, silent=False):
        series = {
            "name": name,
            "type": "line",
            "data": data,
            "xAxisIndex": grid_index,
            "yAxisIndex": grid_index,
            "connectNulls": False,
            "showSymbol": not dashed,
        }
        if dashed:
            series["lineStyle"] = {"type": "dashed"}
            series["showSymbol"] = False
        if color:
            series["itemStyle"] = {"color": color}
            series.setdefault("lineStyle", {})["color"] = color
        if mark_area:
            series["markArea"] = mark_area
        if silent:
            series["silent"] = True
            series["tooltip"] = {"show": False}
            series["symbol"] = "none"
        return series

    def bars(name, data, mark_area=None):
        series = {
            "name": name,
            "type": "bar",
            "stack": "macros",
            "data": data,
            "xAxisIndex": 2,
            "yAxisIndex": 2,
            "itemStyle": {"color": MACRO_COLORS[name]},
        }
        if mark_area:
            series["markArea"] = mark_area
        return series

    return {
        "tooltip": {"trigger": "axis"},
        "axisPointer": {"link": [{"xAxisIndex": "all"}]},
        "legend": {
            "top": 0,
            "right": 8,
            "data": ["Target", "Weight", "BF target", "Body fat", "Protein", "Fat", "Carbs"],
        },
        "grid": [
            {"left": 52, "right": 16, "top": 36, "height": "22%"},
            {"left": 52, "right": 16, "top": "38%", "height": "22%"},
            {"left": 52, "right": 16, "top": "66%", "height": "22%"},
        ],
        "xAxis": [axis(0), axis(1), axis(2, show_labels=True)],
        "yAxis": [
            {"type": "value", "name": "kg", "scale": True, "gridIndex": 0},
            {"type": "value", "name": "%", "scale": True, "gridIndex": 1},
            {"type": "value", "name": "kcal", "scale": False, "gridIndex": 2},
        ],
        "dataZoom": [{"type": "inside", "xAxisIndex": [0, 1, 2]}],
        "series": [
            line("Target", weight_target, 0, dashed=True, mark_area=bands),
            {
                "name": "Lane",
                "type": "line",
                "data": lane_low,
                "xAxisIndex": 0,
                "yAxisIndex": 0,
                "stack": "lane",
                "symbol": "none",
                "silent": True,
                "tooltip": {"show": False},
                "lineStyle": {"opacity": 0},
                "itemStyle": {"opacity": 0},
            },
            {
                "name": "Lane width",
                "type": "line",
                "data": lane_span,
                "xAxisIndex": 0,
                "yAxisIndex": 0,
                "stack": "lane",
                "symbol": "none",
                "silent": True,
                "tooltip": {"show": False},
                "lineStyle": {"opacity": 0},
                "areaStyle": {"opacity": 0.12, "color": "#94a3b8"},
            },
            line("Weight", weight_actual, 0),
            line("BF target", bf_target, 1, dashed=True, mark_area=bands),
            line("Body fat", bf_actual, 1),
            bars("Protein", protein, mark_area=bands),
            bars("Fat", fat),
            bars("Carbs", carbs),
        ],
    }


def _journey_axis(values, name, min_span):
    nums = [_to_float(value) for value in values or []]
    nums = [value for value in nums if value is not None]
    axis = {"type": "value", "name": name, "scale": True}
    if not nums:
        return axis
    low, high = min(nums), max(nums)
    span = max(high - low, min_span)
    pad = span * 0.2
    axis["min"] = round(low - pad, 2)
    axis["max"] = round(high + pad, 2)
    return axis


def journey_planned(rows):
    points = []
    for row in rows or []:
        weight = _to_float(row.get("target_weight_kg"))
        bf = _to_float(row.get("target_bf_percent"))
        if weight is None or bf is None:
            continue
        points.append({"week": row.get("week"), "weight": weight, "bf": bf})
    return points


def journey_options(points, planned=None):
    data = []
    xs = []
    ys = []
    for point in points or []:
        dexa = bool(point.get("dexa"))
        weight = point.get("weight")
        bf = point.get("bf")
        xs.append(weight)
        ys.append(bf)
        item = {
            "value": [weight, bf],
            "symbolSize": DEXA_SIZE if dexa else JOURNEY_SIZE,
            "symbol": "emptyCircle" if dexa else "circle",
            "week": point.get("week"),
            "dexa": dexa,
        }
        if dexa:
            item["itemStyle"] = {
                "color": "transparent",
                "borderColor": "#0f766e",
                "borderWidth": 2,
            }
        data.append(item)
    planned_data = []
    for point in planned or []:
        weight = point.get("weight")
        bf = point.get("bf")
        xs.append(weight)
        ys.append(bf)
        planned_data.append({
            "value": [weight, bf],
            "week": point.get("week"),
            "symbol": "none",
        })
    series = []
    if planned_data:
        series.append({
            "name": "Plan",
            "type": "line",
            "data": planned_data,
            "symbol": "none",
            "lineStyle": {"type": "dashed", "opacity": 0.45},
        })
    series.append({
        "name": "Journey",
        "type": "line",
        "data": data,
        "symbol": "circle",
        "symbolSize": JOURNEY_SIZE,
        "connectNulls": False,
    })
    return {
        "tooltip": {"trigger": "item"},
        "legend": {"top": 0, "right": 8},
        "grid": {"left": 48, "right": 20, "top": 28, "bottom": 40},
        "xAxis": _journey_axis(xs, "kg", 2),
        "yAxis": _journey_axis(ys, "%", 2),
        "series": series,
    }
