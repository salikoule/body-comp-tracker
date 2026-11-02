"""Pure HTML builders for the Progress page. No Anvil imports."""

from datetime import timedelta

from body_comp_tracker.ProgressCharts import (
    BF_LANE_PP,
    HIT_COLOR,
    MACRO_COLORS,
    MISS_COLOR,
    NAVY,
    STRIP_WEEKS,
    WEIGHT_LANE_KG,
    _to_float,
    as_date,
    fat_kg,
    lean_kg,
    macro_stack,
    phase_color,
    phase_name,
)

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
RATE_TOLERANCE_KG = 0.08


def esc(value):
    text = "" if value is None else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def fmt_day(day):
    if day is None:
        return ""
    return "%s %s" % (day.day, MONTHS[day.month - 1])


def signed(value, digits=1):
    if value is None:
        return "—"
    rounded = round(value, digits)
    text = ("%." + str(digits) + "f") % abs(rounded)
    if rounded > 0:
        return "+" + text
    if rounded < 0:
        return "−" + text
    return "±" + text


def week_range(row):
    start = as_date(row.get("week_start"))
    if start is None:
        return ""
    return "%s–%s" % (fmt_day(start), fmt_day(start + timedelta(days=6)))


def _last(rows):
    return rows[-1] if rows else None


def verdict(model):
    """Return (tone, html). Tone is "ok", "warn", or "" when there is nothing to judge yet."""
    last = _last(model["logged"])
    if last is None:
        return "", "Your plan starts here. Log your first check-in to see how you are tracking."
    if model["trend_now"] is None or model["plan_now"] is None:
        actual = _to_float(last.get("actual_weight_kg"))
        target = _to_float(last.get("target_weight_kg"))
        gap = actual - target if target is not None else None
        hit = gap is not None and abs(gap) <= WEIGHT_LANE_KG + 1e-9
        lead = "Good start." if hit else "Off the lane."
        return ("ok" if hit else "warn"), (
            "<b>%s</b> Week %s landed at %.1f kg, %s kg against a %.1f kg target%s. "
            "Log a weigh-in each morning and your trend and forecast appear here."
            % (lead, last.get("week"), actual, signed(gap), target or 0, " — inside the lane" if hit else "")
        )
    gap = model["trend_now"] - model["plan_now"]
    ok = abs(gap) <= WEIGHT_LANE_KG + 1e-9
    text = "<b>%s</b> Trend weight is %.1f kg, %s kg vs plan" % (
        "On track." if ok else "Drifting.", model["trend_now"], signed(gap))
    if model["rate"] is not None:
        text += ", %s %.2f kg/week" % ("losing" if model["rate"] < 0 else "gaining", abs(model["rate"]))
        if model["plan_rate"] is not None:
            text += " (plan %.2f)" % abs(model["plan_rate"])
    text += "."
    end_row = model["phase_end_row"] or {}
    end_target = _to_float(end_row.get("target_weight_kg"))
    if model["projected"] is not None and end_target is not None:
        text += " At this pace you finish the %s at <b>%.1f kg</b> vs a %.1f kg target." % (
            phase_name(model["current_phase"]["phase"]).lower(), model["projected"], end_target)
    return ("ok" if ok else "warn"), text


def status_pill(tone):
    if not tone:
        return ""
    label = "On track" if tone == "ok" else "Watch"
    return '<span class="bc-pg-pill is-%s"><i></i>%s</span>' % (tone, label)


def sparkline(values, color=NAVY):
    nums = [value for value in values if value is not None]
    if len(nums) < 2:
        return ""
    low, high = min(nums), max(nums)
    span = (high - low) or 1.0
    step = 100.0 / (len(nums) - 1)
    coords = ["%.1f,%.1f" % (index * step, 30 - (value - low) / span * 26) for index, value in enumerate(nums)]
    line = " ".join(coords)
    area = "0,32 " + line + " 100,32"
    return (
        '<svg class="bc-pg-spark" viewBox="0 0 100 32" preserveAspectRatio="none">'
        '<polygon points="%s" fill="%s" fill-opacity="0.10"></polygon>'
        '<polyline points="%s" fill="none" stroke="%s" stroke-width="2" vector-effect="non-scaling-stroke"'
        ' stroke-linejoin="round" stroke-linecap="round"></polyline></svg>' % (area, color, line, color)
    )


TILE_ICONS = (
    ("Body fat", "body_fat", "#b45309"),
    ("Weekly rate", "speed", "#2563eb"),
    ("Weeks in lane", "verified", "#059669"),
    ("Trend weight", "monitor_weight", "#0f766e"),
    ("Weight", "monitor_weight", "#0f766e"),
)


def _tile_icon(label):
    for prefix, name, color in TILE_ICONS:
        if label.startswith(prefix):
            return '<span class="bc-sym material-symbols-outlined" style="color:%s" aria-hidden="true">%s</span>' % (color, name)
    return ""


def _tile(label, value, unit, delta, tone, foot):
    return (
        '<div class="bc-pg-tile"><div class="bc-pg-tile-label">%s<span>%s</span></div>'
        '<div class="bc-pg-tile-value">%s<small>%s</small></div>'
        '<div class="bc-pg-tile-delta is-%s">%s</div>'
        '<div class="bc-pg-tile-foot">%s</div></div>'
        % (_tile_icon(label), esc(label), esc(value), esc(unit), tone, esc(delta), foot)
    )


def _foot_note(text):
    return '<span class="bc-pg-tile-note">%s</span>' % esc(text)


def _weight_tile(model):
    if model["trend_now"] is not None and model["plan_now"] is not None:
        gap = model["trend_now"] - model["plan_now"]
        recent = [kg for _day, kg in model["trend"][-42:]]
        tone = "good" if abs(gap) <= WEIGHT_LANE_KG + 1e-9 else "bad"
        return _tile("Trend weight", "%.1f" % model["trend_now"], "kg", "%s kg vs plan" % signed(gap), tone, sparkline(recent))
    last = _last(model["logged"])
    if last is None:
        return _tile("Weight", "—", "", "No check-ins yet", "neutral", _foot_note("Log your first week with Sunday check-in"))
    actual = _to_float(last.get("actual_weight_kg"))
    gap = actual - (_to_float(last.get("target_weight_kg")) or actual)
    hit = abs(gap) <= WEIGHT_LANE_KG + 1e-9
    return _tile(
        "Weight · week %s" % last.get("week"),
        "%.1f" % actual,
        "kg",
        "%s kg vs plan%s" % (signed(gap), " · in lane" if hit else ""),
        "good" if hit else "bad",
        _foot_note("Trend starts after 3 daily weigh-ins"),
    )


def _bf_goal_note(model):
    targets = [(row.get("week"), _to_float(row.get("target_bf_percent"))) for row in model["rows"]]
    targets = [(week, bf) for week, bf in targets if bf is not None]
    if not targets:
        return ""
    goal = min(bf for _week, bf in targets)
    week = next(week for week, bf in targets if bf == goal)
    return "Goal %.1f%% by week %s" % (goal, week)


def _bf_tile(model):
    last = _last(model["bf_rows"])
    if last is None:
        return _tile("Body fat", "—", "", "Log waist and neck at check-in", "neutral", _foot_note(_bf_goal_note(model)))
    bf = _to_float(last.get("bf_percent"))
    target = _to_float(last.get("target_bf_percent"))
    gap = bf - target if target is not None else None
    tone = "good" if gap is not None and gap <= BF_LANE_PP + 1e-9 else "bad"
    values = [_to_float(row.get("bf_percent")) for row in model["bf_rows"]]
    foot = sparkline(values) if len(values) > 1 else _foot_note(_bf_goal_note(model))
    return _tile("Body fat", "%.1f" % bf, "%", "%s pp vs plan" % signed(gap), tone, foot)


def _rate_tile(model):
    rate = model["rate"]
    plan = model["plan_rate"]
    plan_text = "Plan %s kg/wk" % signed(plan, 2) if plan is not None else ""
    if rate is None:
        return _tile("Weekly rate", "—", "", "Needs two logged weeks", "neutral", _foot_note(plan_text))
    if plan is None:
        return _tile("Weekly rate", signed(rate, 2), "kg/wk", "", "neutral", _foot_note("From the last 3 weeks of trend"))
    gap = abs(rate) - abs(plan)
    if abs(rate - plan) <= RATE_TOLERANCE_KG:
        delta, tone = "On plan pace (%s)" % signed(plan, 2), "good"
    elif gap > 0:
        delta, tone = "Faster than plan (%s)" % signed(plan, 2), "neutral"
    else:
        delta, tone = "Slower than plan (%s)" % signed(plan, 2), "neutral"
    source = "From the last 3 weeks of trend" if model["trend"] else "From your last two check-ins"
    return _tile("Weekly rate", signed(rate, 2), "kg/wk", delta, tone, _foot_note(source))


def _lane_tile(model):
    scored = model["hits"] + model["misses"]
    rows = [row for row in model["rows"] if (row.get("week") or 0) < model["current_week"]][-STRIP_WEEKS:]
    cells = []
    for row in rows:
        hit = model["scores"].get(row.get("week"), {}).get("weight_hit")
        state = "is-empty" if hit is None else ("is-hit" if hit else "is-miss")
        cells.append('<span class="%s"></span>' % state)
    cells += ['<span></span>'] * (STRIP_WEEKS - len(rows))
    strip = '<div class="bc-pg-strip">%s</div>' % "".join(cells)
    if not scored:
        return _tile("Weeks in lane", "—", "", "Nothing scored yet", "neutral", strip)
    tone = "good" if model["streak"] else "bad"
    return _tile("Weeks in lane", str(model["hits"]), " of %s" % scored, "%s-week streak" % model["streak"], tone, strip)


def tiles_html(model):
    return '<div class="bc-pg-tiles">%s%s%s%s</div>' % (
        _weight_tile(model), _bf_tile(model), _rate_tile(model), _lane_tile(model))


def timeline_html(model):
    rows = model["rows"]
    if not rows:
        return ""
    total = len(rows)
    current = model["current_week"]
    segments = []
    meta = []
    for item in model["ranges"]:
        length = (item["end"] - item["start"]) + 1
        done = max(0.0, min(float(length), current - item["start"] + 0.5))
        color = phase_color(item["phase"])
        segments.append(
            '<div class="bc-pg-tl-seg%s" style="flex:%s;--phase:%s">'
            '<div class="bc-pg-tl-done" style="width:%.1f%%"></div><span>%s</span></div>'
            % (" has-progress" if done > 0 else "", length, color, done / length * 100, esc(phase_name(item["phase"])))
        )
        kcal = "%d kcal" % item["calories"] if item["calories"] else ""
        meta.append(
            '<div style="flex:%s"><b>%s</b><span>W%s–%s · %s</span></div>'
            % (length, kcal, item["start"], item["end"], fmt_day(item["start_date"]))
        )
    marker = '<div class="bc-pg-tl-here" style="left:%.2f%%">You · W%s</div>' % ((current - 0.5) / total * 100, current)
    first = _to_float(rows[0].get("target_weight_kg"))
    end_day = as_date(rows[-1].get("week_start"))
    summary = []
    for item in model["ranges"]:
        target = _to_float(item["rows"][-1].get("target_weight_kg"))
        if target is not None:
            summary.append("%s to %.1f kg" % (phase_name(item["phase"]).lower(), target))
    sub = "Start %.1f kg · %s" % (first, " · ".join(summary)) if first is not None else ""
    if end_day is not None:
        sub += " · ends %s %s" % (fmt_day(end_day + timedelta(days=6)), (end_day + timedelta(days=6)).year)
    return (
        '<div class="bc-pg-card bc-pg-timeline"><div class="bc-pg-card-h"><h3>Plan</h3><p>%s</p></div>'
        '<div class="bc-pg-tl-bar">%s%s</div><div class="bc-pg-tl-meta">%s</div></div>'
        % (esc(sub), "".join(segments), marker, "".join(meta))
    )


def _square_state(model, row, key):
    week = row.get("week") or 0
    if week == model["current_week"]:
        return "is-now"
    if week > model["current_week"]:
        return ""
    hit = model["scores"].get(week, {}).get(key)
    if hit is None:
        return "is-skip"
    return "is-hit" if hit else "is-miss"


def _square_tip(model, row):
    week = row.get("week")
    lines = ["Week %s · %s" % (week, week_range(row))]
    target = _to_float(row.get("target_weight_kg"))
    actual = _to_float(row.get("actual_weight_kg"))
    bf = _to_float(row.get("bf_percent"))
    target_bf = _to_float(row.get("target_bf_percent"))
    if actual is not None and target is not None and week <= model["current_week"]:
        lines.append("%.1f kg vs %.1f (%s)" % (actual, target, signed(actual - target)))
    elif target is not None:
        lines.append("Target %.1f kg" % target)
    if bf is not None and target_bf is not None and week <= model["current_week"]:
        lines.append("%.1f%% vs %.1f%%" % (bf, target_bf))
    elif target_bf is not None:
        lines.append("Target %.1f%% body fat" % target_bf)
    if week == model["current_week"]:
        lines.append("In progress")
    return "&#10;".join(esc(line) for line in lines)


def scorecard_html(model):
    rows = model["rows"]
    dexa_weeks = set(scan["week"] for scan in model["dexa"])
    cells = []
    for item in model["ranges"]:
        cells.append(
            '<div class="bc-pg-sc-phase" style="grid-column:%s/%s;--phase:%s">%s</div>'
            % (item["start"] + 1, item["end"] + 2, phase_color(item["phase"]), esc(phase_name(item["phase"])))
        )
    cells.append('<div class="bc-pg-sc-label" style="grid-row:2">Weight</div>')
    cells.append('<div class="bc-pg-sc-label" style="grid-row:3">Body fat</div>')
    for index, row in enumerate(rows):
        week = row.get("week")
        tip = _square_tip(model, row)
        dexa = " has-dexa" if week in dexa_weeks else ""
        for line, key in ((2, "weight_hit"), (3, "bf_hit")):
            cells.append(
                '<button type="button" class="bc-pg-sq %s%s" data-week="%s" data-tip="%s" style="grid-row:%s;grid-column:%s"></button>'
                % (_square_state(model, row, key), dexa if line == 2 else "", week, tip, line, index + 2)
            )
    for index, row in enumerate(rows):
        week = row.get("week") or 0
        if week == 1 or week == len(rows) or week % 6 == 0:
            cells.append('<div class="bc-pg-sc-week" style="grid-row:4;grid-column:%s">%s</div>' % (index + 2, week))
    legend = (
        '<div class="bc-pg-sc-legend">'
        '<span><i class="bc-pg-sq is-hit"></i>Hit</span><span><i class="bc-pg-sq is-miss"></i>Missed</span>'
        '<span><i class="bc-pg-sq is-skip"></i>Not scored</span><span><i class="bc-pg-sq is-now"></i>This week</span>'
        '<span><i class="bc-pg-sq"></i>Upcoming</span><span><i class="bc-pg-dexa-dot"></i>DEXA scan</span></div>'
    )
    return '<div class="bc-pg-sc" style="grid-template-columns:58px repeat(%s, minmax(0, 1fr))">%s</div>%s' % (
        len(rows), "".join(cells), legend)


def lane_chip(model):
    tone = "warn" if model["misses"] else "ok"
    return '<span class="bc-pg-pill is-%s">%s hit · %s missed</span>' % (tone, model["hits"], model["misses"])


def week_detail_html(model, row):
    if not row:
        return ""
    week = row.get("week") or 0
    score = model["scores"].get(week, {})
    hit = score.get("weight_hit")
    if week == model["current_week"]:
        verdict_text, tone = "In progress", "neutral"
    elif week > model["current_week"]:
        verdict_text, tone = "Upcoming", "neutral"
    elif hit is None:
        verdict_text, tone = "Not scored", "neutral"
    elif hit:
        verdict_text, tone = "Hit the lane", "good"
    else:
        verdict_text, tone = "Missed the lane", "bad"
    stack = macro_stack(row) or {}
    actual = _to_float(row.get("actual_weight_kg"))
    bf = _to_float(row.get("bf_percent"))
    target = _to_float(row.get("target_weight_kg"))
    target_bf = _to_float(row.get("target_bf_percent"))
    show_actual = week <= model["current_week"]

    def cell(label, value, suffix):
        return '<div><span>%s</span><b>%s <small>%s</small></b></div>' % (label, value, suffix)

    macros = "P %s · F %s · C %s g" % (stack.get("protein_g", "—"), stack.get("fat_g", "—"), stack.get("carbs_g", "—"))
    return (
        '<div class="bc-pg-detail-h"><b>Week %s · %s</b><span class="is-%s">%s</span></div>'
        '<div class="bc-pg-detail-grid">%s%s%s<div><span>Macros</span><b class="is-small">%s</b></div></div>'
        % (
            week, week_range(row), tone, verdict_text,
            cell("Weight", "%.1f" % actual if show_actual and actual is not None else "—", "/ %.1f kg" % target if target is not None else ""),
            cell("Body fat", "%.1f" % bf if show_actual and bf is not None else "—", "/ %.1f%%" % target_bf if target_bf is not None else ""),
            cell("Issued", stack.get("kcal", "—"), "kcal"),
            macros,
        )
    )


def macros_html(row):
    stack = macro_stack(row)
    if stack is None:
        return ""
    lines = []
    for name, grams, kcal in (
        ("Protein", stack["protein_g"], stack["protein_kcal"]),
        ("Fat", stack["fat_g"], stack["fat_kcal"]),
        ("Carbs", stack["carbs_g"], stack["carbs_kcal"]),
    ):
        lines.append(
            '<div class="bc-pg-macro"><i style="background:%s"></i><span>%s</span>'
            '<div class="bc-pg-macro-bar"><b style="width:%.1f%%;background:%s"></b></div><strong>%s g</strong></div>'
            % (MACRO_COLORS[name], name, kcal * 100.0 / stack["kcal"], MACRO_COLORS[name], grams)
        )
    weight = _to_float(row.get("target_weight_kg"))
    if weight:
        lines.append('<p class="bc-pg-macro-note">Protein %.1f g/kg of plan weight</p>' % (stack["protein_g"] / weight))
    return '<div class="bc-pg-macros">%s</div>' % "".join(lines)


def composition_side_html(model):
    rows = model["rows"]
    if not rows:
        return ""
    start = rows[0]
    start_weight = _to_float(start.get("target_weight_kg"))
    start_bf = _to_float(start.get("target_bf_percent"))
    fat0 = fat_kg(start_weight, start_bf)
    lean0 = lean_kg(start_weight, start_bf)
    last = _last(model["bf_rows"])
    end_row = model["phase_end_row"] or {}
    end_weight = _to_float(end_row.get("target_weight_kg"))
    end_bf = _to_float(end_row.get("target_bf_percent"))
    parts = []
    if last is not None and fat0 is not None:
        weight = _to_float(last.get("actual_weight_kg"))
        bf = _to_float(last.get("bf_percent"))
        plan_fat = fat_kg(_to_float(last.get("target_weight_kg")), _to_float(last.get("target_bf_percent")))
        plan_lean = lean_kg(_to_float(last.get("target_weight_kg")), _to_float(last.get("target_bf_percent")))
        parts.append(
            '<div class="bc-pg-stat"><span>Fat mass since start</span><b class="is-fat">%s kg</b><small>Plan by now %s kg</small></div>'
            % (signed(fat_kg(weight, bf) - fat0), signed(plan_fat - fat0) if plan_fat is not None else "—")
        )
        parts.append(
            '<div class="bc-pg-stat"><span>Lean mass since start</span><b class="is-lean">%s kg</b><small>Plan by now %s kg · flat is the goal</small></div>'
            % (signed(lean_kg(weight, bf) - lean0), signed(plan_lean - lean0) if plan_lean is not None else "—")
        )
    else:
        parts.append('<div class="bc-pg-stat"><span>Since start</span><b>—</b><small>Needs a check-in with waist and neck</small></div>')
    if end_weight is not None and end_bf is not None:
        parts.append(
            '<div class="bc-pg-stat"><span>End of %s (W%s)</span><b>%.1f <em>kg fat</em></b><small>%.1f kg lean · %.1f%% body fat</small></div>'
            % (phase_name(model["current_phase"]["phase"]).lower(), end_row.get("week"),
               fat_kg(end_weight, end_bf), lean_kg(end_weight, end_bf), end_bf)
        )
    note = ("Purple diamonds are DEXA scans. They recalibrate the tape estimate."
            if model["dexa"] else "Add a DEXA scan in Settings to anchor these numbers.")
    parts.append('<p class="bc-pg-macro-note">%s</p>' % note)
    return "".join(parts)


HERO_SUBTITLES = {
    "weight": "Faint dots are daily weigh-ins. The line smooths out water swings.",
    "bf": "Weekly tape estimate, with DEXA scans as diamonds.",
    "lean": "Weight minus fat mass. On a good cut this line stays flat.",
}


def hero_subtitle(model, metric):
    if metric == "weight" and not model["trend"]:
        count = len(model["logged"])
        return "%s check-in%s so far. Daily weigh-ins turn this into a trend." % (count, "" if count == 1 else "s")
    return HERO_SUBTITLES.get(metric, "")
