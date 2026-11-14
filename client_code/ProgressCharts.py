"""Pure Progress model and ECharts option builders. No Anvil imports."""

from datetime import date, datetime, timedelta

SCORED_STATUSES = ("logged", "excluded", "partial")
WEIGHT_LANE_KG = 0.4
BF_LANE_PP = 0.6
LEAN_LANE_KG = 0.8
LANE_EPSILON = 1e-9
TREND_WINDOW_DAYS = 14
RATE_WINDOW_DAYS = 21
MIN_TREND_POINTS = 3
MIN_RATE_SPAN_DAYS = 7
STRIP_WEEKS = 8
DAY_MS = 86400000
EPOCH = date(1970, 1, 1)

NAVY = "#1e3a5f"
HIT_COLOR = "#059669"
MISS_COLOR = "#dc2626"
FORECAST_COLOR = "#d97706"
FAT_COLOR = "#b45309"
DEXA_COLOR = "#7c3aed"
DOT_COLOR = "#94a3b8"
INK = "#0f172a"
AXIS_TEXT = "#94a3b8"
GRID_LINE = "#f1f5f9"
LANE_FILL = "rgba(30, 58, 95, 0.08)"
CONE_FILL = "rgba(217, 119, 6, 0.14)"
PLAN_LINE = "rgba(30, 58, 95, 0.45)"
MACRO_COLORS = {"Protein": NAVY, "Fat": "#d97706", "Carbs": "#7dd3fc"}
PHASE_COLORS = {"cut": "#1e3a5f", "reverse": "#c2410c", "bulk": "#0f766e", "recomp": "#475569"}
PHASE_NAMES = {"cut": "Cut", "reverse": "Reverse", "bulk": "Bulk", "recomp": "Recomp"}
SPANS = {"4w": (28, 14), "12w": (63, 35)}
METRICS = {
    "weight": {"title": "Weight trend", "unit": "kg", "lane": WEIGHT_LANE_KG},
    "bf": {"title": "Body fat", "unit": "%", "lane": BF_LANE_PP},
    "lean": {"title": "Lean mass", "unit": "kg", "lane": LEAN_LANE_KG},
}


def _to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    try:
        year, month, day = text.split("-")
        return date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None


def to_ms(day):
    return (day - EPOCH).days * DAY_MS


def phase_color(phase):
    return PHASE_COLORS.get(phase or "cut", PHASE_COLORS["recomp"])


def phase_name(phase):
    return PHASE_NAMES.get(phase or "cut", (phase or "").title())


def lean_kg(weight, bf):
    if weight is None or bf is None:
        return None
    return weight * (1 - bf / 100.0)


def fat_kg(weight, bf):
    if weight is None or bf is None:
        return None
    return weight * bf / 100.0


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
    return abs(delta) <= lane + LANE_EPSILON


def _at_or_under(delta, lane):
    """True when the reading is on the line or below it, with ``lane`` of room above."""
    if delta is None:
        return None
    return delta <= lane + LANE_EPSILON


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
        bf_hit = _at_or_under(
            _delta("bf_percent", "target_bf_percent", "bf_delta", row),
            BF_LANE_PP,
        )

    return {"week": week, "weight_hit": weight_hit, "bf_hit": bf_hit}


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


def weigh_ins(weights):
    points = []
    for item in weights or []:
        day = as_date(item.get("date"))
        kg = _to_float(item.get("kg"))
        if day is None or kg is None:
            continue
        points.append((day, kg))
    points.sort(key=lambda point: point[0])
    return points


def trend_points(points):
    """Trailing linear fit per weigh-in day, so a steady cut does not lag behind the dots."""
    if len(points) < MIN_TREND_POINTS:
        return []
    trend = []
    for day, _kg in points:
        window = [(d, kg) for d, kg in points if d <= day and (day - d).days < TREND_WINDOW_DAYS]
        mean_kg = sum(kg for _d, kg in window) / len(window)
        if len(window) < MIN_TREND_POINTS:
            trend.append((day, mean_kg))
            continue
        xs = [(d - day).days for d, _kg in window]
        mean_x = sum(xs) / float(len(xs))
        spread = sum((x - mean_x) ** 2 for x in xs)
        if spread == 0:
            trend.append((day, mean_kg))
            continue
        slope = sum((x - mean_x) * (kg - mean_kg) for x, (_d, kg) in zip(xs, window)) / spread
        trend.append((day, mean_kg - slope * mean_x))
    return trend


def trend_rate(trend):
    if len(trend) < 2:
        return None
    end_day, end_kg = trend[-1]
    start = None
    for day, kg in trend:
        if (end_day - day).days <= RATE_WINDOW_DAYS:
            start = (day, kg)
            break
    if start is None:
        return None
    span = (end_day - start[0]).days
    if span < MIN_RATE_SPAN_DAYS:
        return None
    return (end_kg - start[1]) / span * 7


def week_mid_ms(row):
    start = as_date(row.get("week_start"))
    if start is None:
        return None
    return to_ms(start) + int(3.5 * DAY_MS)


def plan_weight_on(rows, day):
    """Plan weight on a day, interpolated between week midpoints."""
    stamp = to_ms(day)
    points = [(week_mid_ms(row), _to_float(row.get("target_weight_kg"))) for row in rows or []]
    points = [(t, kg) for t, kg in points if t is not None and kg is not None]
    if not points:
        return None
    if stamp <= points[0][0]:
        return points[0][1]
    for (t0, kg0), (t1, kg1) in zip(points, points[1:]):
        if t0 <= stamp <= t1:
            return kg0 + (kg1 - kg0) * (stamp - t0) / float(t1 - t0)
    return points[-1][1]


def phase_ranges(rows):
    ranges = []
    for row in rows or []:
        phase = row.get("phase") or "cut"
        if ranges and ranges[-1]["phase"] == phase:
            ranges[-1]["end"] = row.get("week")
            ranges[-1]["rows"].append(row)
            continue
        ranges.append({
            "phase": phase,
            "start": row.get("week"),
            "end": row.get("week"),
            "start_date": as_date(row.get("week_start")),
            "calories": _to_float(row.get("target_calories")),
            "rows": [row],
        })
    return ranges


def phase_plan_rate(phase_rows):
    targets = [_to_float(row.get("target_weight_kg")) for row in phase_rows]
    targets = [kg for kg in targets if kg is not None]
    if len(targets) < 2:
        return None
    return (targets[-1] - targets[0]) / (len(targets) - 1)


def forecast_cone(trend, rate, end_day, step_days=3):
    if not trend or rate is None or end_day is None:
        return []
    start_day, start_kg = trend[-1]
    if end_day <= start_day:
        return []
    cone = []
    offset = 0
    total = (end_day - start_day).days
    while True:
        day = start_day + timedelta(days=offset)
        mid = start_kg + rate / 7.0 * offset
        half = 0.12 + 0.07 * (offset ** 0.5)
        cone.append({"date": day, "mid": mid, "lo": mid - half, "hi": mid + half})
        if offset >= total:
            break
        offset = min(total, offset + step_days)
    return cone


def dexa_points(state, rows):
    by_week = {row.get("week"): row for row in rows or []}
    points = []
    for scan in state.get("dexa_scans") or []:
        week = scan.get("week_index")
        bf = _to_float(scan.get("bf_percent"))
        if not week or bf is None:
            continue
        row = by_week.get(int(week)) or {}
        lean = _to_float(scan.get("ffm_kg"))
        weight = _to_float(row.get("actual_weight_kg"))
        if lean is None and weight is not None:
            lean = lean_kg(weight, bf)
        if weight is None and lean is not None:
            weight = lean / (1 - bf / 100.0)
        points.append({"week": int(week), "bf": bf, "lean": lean, "fat": fat_kg(weight, bf), "row": row})
    points.sort(key=lambda point: point["week"])
    return points


def progress_model(state, today):
    rows = state.get("schedule") or []
    current_week = state.get("current_week") or 1
    current_row = next((row for row in rows if row.get("week") == current_week), rows[0] if rows else {})
    scores = {}
    scored = []
    for row in rows:
        result = score_week(row)
        scores[row.get("week")] = result
        if result["weight_hit"] is not None and (row.get("week") or 0) <= current_week:
            scored.append(result)
    hits = len([item for item in scored if item["weight_hit"]])
    streak = 0
    for item in reversed(scored):
        if not item["weight_hit"]:
            break
        streak += 1
    logged = [row for row in rows if _to_float(row.get("actual_weight_kg")) is not None and (row.get("week") or 0) <= current_week]
    bf_rows = [row for row in logged if _to_float(row.get("bf_percent")) is not None]

    points = weigh_ins(state.get("weights"))
    trend = trend_points(points)
    rate = trend_rate(trend)
    if rate is None and len(logged) >= 2:
        first, last = logged[-2], logged[-1]
        weeks = (last.get("week") or 0) - (first.get("week") or 0)
        if weeks > 0:
            rate = (_to_float(last["actual_weight_kg"]) - _to_float(first["actual_weight_kg"])) / weeks

    ranges = phase_ranges(rows)
    current_phase = next((item for item in ranges if item["start"] <= current_week <= item["end"]), ranges[0] if ranges else None)
    phase_end_row = current_phase["rows"][-1] if current_phase else {}
    phase_end_day = as_date(phase_end_row.get("week_start"))
    if phase_end_day is not None:
        phase_end_day = phase_end_day + timedelta(days=7)
    cone = forecast_cone(trend, rate, phase_end_day) if trend else []

    return {
        "rows": rows,
        "today": today,
        "current_week": current_week,
        "current_row": current_row,
        "scores": scores,
        "hits": hits,
        "misses": len(scored) - hits,
        "streak": streak,
        "logged": logged,
        "bf_rows": bf_rows,
        "points": points,
        "trend": trend,
        "rate": rate,
        "plan_rate": phase_plan_rate(current_phase["rows"]) if current_phase else None,
        "trend_now": trend[-1][1] if trend else None,
        "plan_now": plan_weight_on(rows, today),
        "ranges": ranges,
        "current_phase": current_phase,
        "phase_end_row": phase_end_row,
        "cone": cone,
        "projected": cone[-1]["mid"] if cone else None,
        "dexa": dexa_points(state, rows),
    }


def _band_segments(points, lane):
    segments = []
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        segments.append([t0, v0 - lane, v0 + lane, t1, v1 - lane, v1 + lane])
    return segments


def _cone_segments(cone):
    segments = []
    for a, b in zip(cone, cone[1:]):
        segments.append([to_ms(a["date"]), round(a["lo"], 2), round(a["hi"], 2), to_ms(b["date"]), round(b["lo"], 2), round(b["hi"], 2)])
    return segments


def _custom_band(name, segments, color, z):
    return {
        "name": name,
        "type": "custom",
        "data": segments,
        "itemStyle": {"color": color},
        "encode": {"x": [0, 3], "y": [1, 2, 4, 5]},
        "clip": True,
        "silent": True,
        "z": z,
        "tooltip": {"show": False},
    }


def _metric_values(row, metric):
    weight = _to_float(row.get("actual_weight_kg"))
    bf = _to_float(row.get("bf_percent"))
    if metric == "weight":
        return weight
    if metric == "bf":
        return bf
    return lean_kg(weight, bf)


def _metric_plan(row, metric):
    weight = _to_float(row.get("target_weight_kg"))
    bf = _to_float(row.get("target_bf_percent"))
    if metric == "weight":
        return weight
    if metric == "bf":
        return bf
    return lean_kg(weight, bf)


def hero_window(model, span):
    rows = model["rows"]
    first = as_date(rows[0].get("week_start")) if rows else model["today"]
    last = as_date(rows[-1].get("week_start")) if rows else model["today"]
    if span == "plan" or span not in SPANS:
        return to_ms(first), to_ms(last + timedelta(days=7))
    back, ahead = SPANS[span]
    start = max(first, model["today"] - timedelta(days=back))
    return to_ms(start), to_ms(model["today"] + timedelta(days=ahead))


def _axis_range(values, pad):
    nums = [value for value in values if value is not None]
    if not nums:
        return None, None
    low = min(nums) - pad
    high = max(nums) + pad
    return int(low // 1), int(-(-high // 1))


def hero_options(model, metric="weight", span="12w"):
    spec = METRICS.get(metric, METRICS["weight"])
    lane = spec["lane"]
    x_min, x_max = hero_window(model, span)

    def visible(points):
        return [value for stamp, value in points if x_min <= stamp <= x_max]

    plan = []
    measured = []
    for row in model["rows"]:
        stamp = week_mid_ms(row)
        if stamp is None:
            continue
        target = _metric_plan(row, metric)
        if target is not None:
            plan.append((stamp, round(target, 2)))
        if (row.get("week") or 0) <= model["current_week"]:
            actual = _metric_values(row, metric)
            if actual is not None:
                measured.append((stamp, round(actual, 2)))

    in_view = visible(plan)
    in_view = [value + lane for value in in_view] + [value - lane for value in in_view]
    series = [
        _custom_band("Plan lane", _band_segments(plan, lane), LANE_FILL, 1),
        {
            "name": "Plan",
            "type": "line",
            "data": [[stamp, value] for stamp, value in plan],
            "symbol": "none",
            "smooth": False,
            "lineStyle": {"color": PLAN_LINE, "type": "dashed", "width": 1.5},
            "z": 2,
        },
    ]

    if metric == "weight" and model["trend"]:
        daily = [(to_ms(day), kg) for day, kg in model["points"]]
        in_view += visible(daily)
        series.append({
            "name": "Weigh-in",
            "type": "scatter",
            "data": [[stamp, kg] for stamp, kg in daily],
            "symbolSize": 5,
            "itemStyle": {"color": DOT_COLOR, "opacity": 0.55},
            "z": 3,
        })
        if model["cone"]:
            series.append(_custom_band("Forecast range", _cone_segments(model["cone"]), CONE_FILL, 2))
            forecast = [(to_ms(item["date"]), round(item["mid"], 2)) for item in model["cone"]]
            in_view += visible([(to_ms(item["date"]), item["hi"]) for item in model["cone"]])
            in_view += visible([(to_ms(item["date"]), item["lo"]) for item in model["cone"]])
            series.append({
                "name": "Forecast",
                "type": "line",
                "data": [[stamp, value] for stamp, value in forecast],
                "symbol": "none",
                "smooth": False,
                "lineStyle": {"color": FORECAST_COLOR, "type": [4, 4], "width": 2},
                "z": 4,
            })
        series.append({
            "name": "Trend",
            "type": "line",
            "data": [[to_ms(day), round(kg, 2)] for day, kg in model["trend"]],
            "symbol": "none",
            "smooth": 0.3,
            "lineStyle": {"color": NAVY, "width": 3},
            "z": 5,
        })
    else:
        in_view += visible(measured)
        series.append({
            "name": "Measured",
            "type": "line",
            "data": [[stamp, value] for stamp, value in measured],
            "symbol": "circle",
            "symbolSize": 9,
            "smooth": 0.3,
            "lineStyle": {"color": NAVY, "width": 2.5},
            "itemStyle": {"color": NAVY, "borderColor": "#fff", "borderWidth": 2},
            "z": 5,
        })

    if metric != "weight" and model["dexa"]:
        by_week = {row.get("week"): row for row in model["rows"]}
        scans = []
        for scan in model["dexa"]:
            value = scan["bf"] if metric == "bf" else scan["lean"]
            stamp = week_mid_ms(by_week.get(scan["week"]) or {})
            if value is None or stamp is None:
                continue
            scans.append([stamp, round(value, 2)])
        in_view += visible([(stamp, value) for stamp, value in scans])
        series.append({
            "name": "DEXA",
            "type": "scatter",
            "data": scans,
            "symbol": "diamond",
            "symbolSize": 14,
            "itemStyle": {"color": DEXA_COLOR, "borderColor": "#fff", "borderWidth": 1.5},
            "z": 6,
        })

    series.append({
        "name": "",
        "type": "line",
        "data": [],
        "markLine": {
            "silent": True,
            "symbol": "none",
            "label": {"formatter": "Today", "color": INK, "fontWeight": 600, "fontSize": 11},
            "lineStyle": {"color": INK, "type": "solid", "width": 1, "opacity": 0.5},
            "data": [{"xAxis": to_ms(model["today"])}],
        },
    })

    y_min, y_max = _axis_range(in_view, 1.0 if metric == "bf" else 0.8)
    y_axis = {
        "type": "value",
        "splitNumber": 4,
        "axisLabel": {"color": AXIS_TEXT, "formatter": "{value}%" if metric == "bf" else "{value}"},
        "splitLine": {"lineStyle": {"color": GRID_LINE}},
    }
    if y_min is not None:
        y_axis["min"] = y_min
        y_axis["max"] = y_max
    return {
        "grid": {"left": 48, "right": 24, "top": 26, "bottom": 32},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "line", "lineStyle": {"color": "#cbd5e1"}}},
        "xAxis": {
            "type": "time",
            "min": x_min,
            "max": x_max,
            "minInterval": (28 if span == "plan" else 7) * DAY_MS,
            "axisTick": {"show": False},
            "axisLine": {"lineStyle": {"color": "#e2e8f0"}},
            "splitLine": {"show": False},
            "axisLabel": {"color": AXIS_TEXT, "formatter": "{d} {MMM}", "hideOverlap": True},
        },
        "yAxis": y_axis,
        "series": series,
    }


def has_trend_gap(model, metric):
    return metric == "weight" and not model["trend"]


def fuel_ring_options(row):
    stack = macro_stack(row)
    if stack is None:
        return None
    return {
        "series": [{
            "type": "pie",
            "radius": ["70%", "88%"],
            "silent": True,
            "label": {
                "show": True,
                "position": "center",
                "formatter": "{a|%s}\n{b|kcal / day}" % stack["kcal"],
                "rich": {
                    "a": {"fontSize": 24, "fontWeight": 700, "color": INK},
                    "b": {"fontSize": 12, "color": "#64748b", "padding": [4, 0, 0, 0]},
                },
            },
            "itemStyle": {"borderColor": "#fff", "borderWidth": 3, "borderRadius": 4},
            "data": [
                {"name": "Protein", "value": stack["protein_kcal"], "itemStyle": {"color": MACRO_COLORS["Protein"]}},
                {"name": "Fat", "value": stack["fat_kcal"], "itemStyle": {"color": MACRO_COLORS["Fat"]}},
                {"name": "Carbs", "value": stack["carbs_kcal"], "itemStyle": {"color": MACRO_COLORS["Carbs"]}},
            ],
        }],
    }


def calorie_plan_options(model):
    rows = model["rows"]
    labels = ["W%s" % row.get("week") for row in rows]
    kcal = [_to_float(row.get("target_calories")) for row in rows]
    series = []
    for item in model["ranges"]:
        data = []
        for index, row in enumerate(rows):
            week = row.get("week") or 0
            inside = item["start"] <= week <= item["end"]
            joins_next = week == item["end"] + 1
            data.append(kcal[index] if inside else (kcal[index - 1] if joins_next else None))
        color = phase_color(item["phase"])
        series.append({
            "name": phase_name(item["phase"]),
            "type": "line",
            "step": "end",
            "symbol": "none",
            "smooth": False,
            "data": data,
            "lineStyle": {"color": color, "width": 2.5},
            "areaStyle": {"color": color, "opacity": 0.07},
        })
    current_label = "W%s" % model["current_week"]
    current_kcal = _to_float((model["current_row"] or {}).get("target_calories"))
    series.append({
        "name": "",
        "type": "line",
        "data": [],
        "markLine": {"silent": True, "symbol": "none", "label": {"show": False},
                     "lineStyle": {"color": INK, "opacity": 0.5, "type": "solid"}, "data": [{"xAxis": current_label}]},
        "markPoint": {"symbol": "circle", "symbolSize": 9, "label": {"show": False},
                      "itemStyle": {"color": INK, "borderColor": "#fff", "borderWidth": 2},
                      "data": [{"coord": [current_label, current_kcal]}] if current_kcal else []},
    })
    values = [value for value in kcal if value]
    low = int(((min(values) if values else 1800) - 200) // 100 * 100)
    high = int(-(-((max(values) if values else 2600) + 200) // 100) * 100)
    return {
        "grid": {"left": 46, "right": 14, "top": 14, "bottom": 24},
        "tooltip": {"trigger": "axis"},
        "xAxis": {
            "type": "category",
            "data": labels,
            "boundaryGap": False,
            "axisTick": {"show": False},
            "axisLine": {"lineStyle": {"color": "#e2e8f0"}},
            "axisLabel": {"color": AXIS_TEXT, "interval": 5},
        },
        "yAxis": {"type": "value", "min": low, "max": high, "splitNumber": 2,
                  "axisLabel": {"color": AXIS_TEXT}, "splitLine": {"lineStyle": {"color": GRID_LINE}}},
        "series": series,
    }


def composition_options(model, kind):
    rows = model["rows"]
    labels = ["W%s" % row.get("week") for row in rows]
    color = FAT_COLOR if kind == "fat" else NAVY
    measure = fat_kg if kind == "fat" else lean_kg
    plan = []
    measured = []
    for row in rows:
        target = measure(_to_float(row.get("target_weight_kg")), _to_float(row.get("target_bf_percent")))
        plan.append(round(target, 1) if target is not None else None)
        actual = None
        if (row.get("week") or 0) <= model["current_week"]:
            actual = measure(_to_float(row.get("actual_weight_kg")), _to_float(row.get("bf_percent")))
        measured.append(round(actual, 1) if actual is not None else None)
    index_by_week = dict((row.get("week"), index) for index, row in enumerate(rows))
    scans = []
    for scan in model["dexa"]:
        value = scan["fat"] if kind == "fat" else scan["lean"]
        if value is not None and scan["week"] in index_by_week:
            scans.append([index_by_week[scan["week"]], round(value, 1)])
    values = [value for value in plan + measured if value is not None] + [value for _i, value in scans]
    y_min, y_max = _axis_range(values, 1.0)
    count = len([value for value in measured if value is not None])
    y_axis = {"type": "value", "splitNumber": 3, "axisLabel": {"color": AXIS_TEXT, "formatter": "{value} kg"},
              "splitLine": {"lineStyle": {"color": GRID_LINE}}}
    if y_min is not None:
        y_axis["min"] = y_min
        y_axis["max"] = y_max
    return {
        "title": {"text": "Fat mass" if kind == "fat" else "Lean mass", "left": 12, "top": 4,
                  "textStyle": {"fontSize": 13, "fontWeight": 600, "color": color}},
        "grid": {"left": 54, "right": 16, "top": 40, "bottom": 28},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": labels, "boundaryGap": False, "axisTick": {"show": False},
                  "axisLine": {"lineStyle": {"color": "#e2e8f0"}}, "axisLabel": {"color": AXIS_TEXT, "interval": 5}},
        "yAxis": y_axis,
        "series": [
            {"name": "Plan", "type": "line", "data": plan, "symbol": "none", "smooth": 0.3,
             "lineStyle": {"color": color, "opacity": 0.45, "type": "dashed", "width": 1.5}},
            {"name": "Measured", "type": "line", "data": measured, "symbol": "circle", "symbolSize": 7,
             "showSymbol": count < 3, "connectNulls": False, "smooth": 0.3,
             "lineStyle": {"color": color, "width": 2.5}, "itemStyle": {"color": color},
             "markLine": {"silent": True, "symbol": "none", "label": {"show": False},
                          "lineStyle": {"color": INK, "opacity": 0.35, "type": "solid"},
                          "data": [{"xAxis": "W%s" % model["current_week"]}]}},
            {"name": "DEXA", "type": "scatter", "data": scans, "symbol": "diamond", "symbolSize": 13, "z": 10,
             "itemStyle": {"color": DEXA_COLOR, "borderColor": "#fff", "borderWidth": 1.5}},
        ],
    }
