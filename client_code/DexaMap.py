"""Fat vs lean map: fat mass index against lean mass index, with body-fat zones. No Anvil imports."""

from body_comp_tracker import DexaRatings as Ratings

DEFAULT_BONE_SHARE = 0.054
POLYGON_SLOTS = 8
FAR = 1000.0

ZONE_FILL = {"great": "#dcfce7", "good": "#eefaf2", "fair": "#fef6d8", "high": "#ffedd5", "bad": "#fee2e2"}
ZONE_TEXT = {"great": "#15803d", "good": "#22a05b", "fair": "#a16207", "high": "#c2410c", "bad": "#b91c1c"}
SCAN_COLOR = "#7c3aed"
GOAL_COLOR = "#15803d"
DREAM_COLOR = "#d97706"
STAR = "path://M50,0 L61,35 L98,35 L68,57 L79,91 L50,70 L21,91 L32,57 L2,35 L39,35 Z"
INK = "#0f172a"
MUTED = "#64748b"
GRID_LINE = "rgba(15, 23, 42, 0.12)"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def map_model(scans, person, dream=None, route=None):
    """Points, plan goal, dream goal, route, zones, and view box for the map, or None without height or usable scans.

    ``dream`` is {"bf_percent", "ffmi"}; ``route`` is a roadmap with ``path`` and ``phases``.
    """
    height = person.get("height_cm")
    if not height:
        return None
    h2 = (height / 100.0) ** 2
    points = [point for point in (_point(scan, h2) for scan in scans or []) if point]
    if not points:
        return None
    latest = points[-1]
    bone_share = latest["bone_share"] or DEFAULT_BONE_SHARE
    goal = _goal(person, h2)
    sex, age = person["sex"], person.get("age")
    bf_cuts = Ratings.bf_cuts(sex, age)
    ffmi_cuts = Ratings.FFMI_CUTS[sex]

    dream_point = _dream(dream, h2, latest)
    route_points = [list(point) for point in (route or {}).get("path") or []]
    extra = ([goal] if goal else []) + ([dream_point] if dream_point else [])
    xs = [p["fmi"] for p in points + extra] + [p[0] for p in route_points]
    ys = [p["ffmi"] for p in points + extra] + [p[1] for p in route_points]
    box = {
        "x0": 0,
        "x1": 2 * int(-(-(max(xs) * 1.3 + 1) // 2)),
        "y0": int(min(ffmi_cuts[0], min(ys)) - 1.5),
        "y1": int(-(-(max(ffmi_cuts[-1], max(ys)) + 1.5) // 1)),
    }
    return {
        "points": points,
        "latest": latest,
        "goal": goal,
        "box": box,
        "bone_share": bone_share,
        "bf_cuts": bf_cuts,
        "ffmi_cuts": ffmi_cuts,
        "zones": _zones(bf_cuts, bone_share, box),
        "person": person,
        "dream": dream_point,
        "route": route if route_points else None,
    }


def _dream(dream, h2, latest):
    if not dream or not dream.get("ffmi") or not dream.get("bf_percent"):
        return None
    ffm = float(dream["ffmi"]) * h2
    fat = ffm * float(dream["bf_percent"]) / (100.0 - float(dream["bf_percent"]))
    return {"fmi": fat / h2, "ffmi": float(dream["ffmi"]), "ffm_kg": ffm, "fat_kg": fat,
            "weight_kg": ffm + fat, "bf": float(dream["bf_percent"])}


def _point(scan, h2):
    ffm = Ratings._num(scan.get("ffm_kg"))
    bf = Ratings._num(scan.get("bf_percent"))
    if ffm is None:
        return None
    bmc = Ratings._num(scan.get("bmc_kg"))
    bone_share = bmc / ffm if bmc else None
    fat = Ratings._num(scan.get("fat_mass_kg"))
    if fat is None:
        if bf is None or bf >= 100:
            return None
        lean = ffm * (1 - (bone_share or DEFAULT_BONE_SHARE))
        fat = lean * bf / (100.0 - bf)
    return {
        "date": scan.get("measured_on"),
        "fat_kg": fat,
        "ffm_kg": ffm,
        "bf": bf,
        "fmi": fat / h2,
        "ffmi": ffm / h2,
        "bone_share": bone_share,
    }


def _goal(person, h2):
    kg, bf = person.get("target_weight_kg"), person.get("target_bf_percent")
    if not kg or bf is None:
        return None
    fat = kg * bf / 100.0
    return {"fat_kg": fat, "ffm_kg": kg - fat, "bf": bf, "weight_kg": kg, "fmi": fat / h2, "ffmi": (kg - fat) / h2}


def bf_slope(bf_percent, bone_share):
    """Lean index per unit of fat index along a line of equal DEXA body fat (fat / (fat + lean, without bone))."""
    b = bf_percent / 100.0
    return (1 - b) / (b * (1 - bone_share))


def _zones(cuts, bone_share, box):
    directions = [(0.0, 1.0)] + [(1.0, bf_slope(cut, bone_share)) for cut in cuts] + [(1.0, 0.0)]
    rows = Ratings.bands(cuts, Ratings.BF_LABELS, Ratings.BF_TONES, (0, 100))
    zones = []
    for i, band in enumerate(rows):
        upper, lower = directions[i], directions[i + 1]
        triangle = [(0.0, 0.0), (upper[0] * FAR, upper[1] * FAR), (lower[0] * FAR, lower[1] * FAR)]
        polygon = clip(triangle, box)
        if len(polygon) < 3:
            continue
        zones.append({"band": band, "polygon": polygon, "anchor": _label_anchor(polygon, box)})
    return zones


def clip(polygon, box):
    """Sutherland-Hodgman clip of a convex polygon to the view box."""
    edges = (
        (lambda p: p[0] >= box["x0"], lambda a, b: _cross_x(a, b, box["x0"])),
        (lambda p: p[0] <= box["x1"], lambda a, b: _cross_x(a, b, box["x1"])),
        (lambda p: p[1] >= box["y0"], lambda a, b: _cross_y(a, b, box["y0"])),
        (lambda p: p[1] <= box["y1"], lambda a, b: _cross_y(a, b, box["y1"])),
    )
    points = list(polygon)
    for inside, cross in edges:
        if not points:
            break
        kept = []
        for i, current in enumerate(points):
            previous = points[i - 1]
            if inside(current):
                if not inside(previous):
                    kept.append(cross(previous, current))
                kept.append(current)
            elif inside(previous):
                kept.append(cross(previous, current))
        points = kept
    return points


def _cross_x(a, b, x):
    t = (x - a[0]) / (b[0] - a[0])
    return (x, a[1] + t * (b[1] - a[1]))


def _cross_y(a, b, y):
    t = (y - a[1]) / (b[1] - a[1])
    return (a[0] + t * (b[0] - a[0]), y)


def _label_anchor(polygon, box):
    """Middle of the zone along the top of the view, or its centroid when the zone misses the top."""
    top = [x for x, y in polygon if abs(y - box["y1"]) < 1e-6]
    if len(top) >= 2:
        return ((min(top) + max(top)) / 2.0, box["y1"] - (box["y1"] - box["y0"]) * 0.05)
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _pad(polygon):
    flat = []
    for x, y in polygon[:POLYGON_SLOTS] + [polygon[-1]] * (POLYGON_SLOTS - len(polygon)):
        flat.extend([round(x, 3), round(y, 3)])
    return flat


def reading(model):
    """Plain-language notes that go beside the map."""
    latest, goal, person = model["latest"], model["goal"], model["person"]
    bf_rows = Ratings.bands(model["bf_cuts"], Ratings.BF_LABELS, Ratings.BF_TONES, (0, 100))
    ffmi_rows = Ratings.bands(model["ffmi_cuts"], Ratings.FFMI_LABELS, Ratings.FFMI_TONES, (0, 100))
    fat_band = Ratings.band_for(latest["bf"], bf_rows) if latest["bf"] is not None else None
    lean_band = Ratings.band_for(latest["ffmi"], ffmi_rows)
    notes = []
    where = "You sit at fat index %s and lean index %s" % (Ratings.fmt(latest["fmi"], 1), Ratings.fmt(latest["ffmi"], 1))
    if fat_band:
        where += ": %s body fat (%s%%) with %s muscle for your height." % (
            fat_band["label"].lower(), Ratings.fmt(latest["bf"], 1), lean_band["label"].lower())
    else:
        where += "."
    notes.append({"title": "Where you are", "text": where})
    if goal:
        fat_change = latest["fat_kg"] - goal["fat_kg"]
        lean_change = goal["ffm_kg"] - latest["ffm_kg"]
        lean_text = ("keeping your lean mass" if abs(lean_change) < 0.5 else
                     "%s %s kg lean mass" % ("adding" if lean_change > 0 else "giving up", Ratings.fmt(abs(lean_change), 1)))
        notes.append({"title": "Where the plan takes you", "text": "%s kg at %s%% body fat: %s kg less fat, %s." % (
            Ratings.fmt(goal["weight_kg"], 1), Ratings.fmt(goal["bf"], 1), Ratings.fmt(fat_change, 1), lean_text)})
    dream, route = model.get("dream"), model.get("route")
    if dream:
        text = "%s kg at %s%% body fat and lean index %s: %s kg %s lean mass than today." % (
            Ratings.fmt(dream["weight_kg"], 1), Ratings.fmt(dream["bf"], 1), Ratings.fmt(dream["ffmi"], 1),
            Ratings.fmt(abs(dream["ffm_kg"] - latest["ffm_kg"]), 1), "more" if dream["ffm_kg"] >= latest["ffm_kg"] else "less")
        if route and route.get("name"):
            text += " The dashed orange line is the %s route." % route["name"].lower()
        notes.append({"title": "Your goal", "text": text, "tone": "goal"})
    if len(model["points"]) > 1:
        first = model["points"][0]
        notes.append({"title": "Since your first scan", "text": "%s kg fat and %s kg lean mass since %s." % (
            _signed(latest["fat_kg"] - first["fat_kg"]), _signed(latest["ffm_kg"] - first["ffm_kg"]), _day(first["date"]))})
    notes.append({"title": "How to read it", "text": (
        "Left means less fat, up means more muscle. A cut should move you straight left and a bulk straight up. "
        "Sliding down means you are losing muscle.")})
    return notes


def options(model):
    """ECharts options. The form adds renderItem for the zone series and the tooltip formatter."""
    box = model["box"]
    series = [
        {
            "name": "Zones",
            "type": "custom",
            "data": [{"value": _pad(zone["polygon"]), "itemStyle": {"color": ZONE_FILL[zone["band"]["tone"]]}}
                     for zone in model["zones"]],
            "silent": True,
            "clip": True,
            "z": 1,
            "tooltip": {"show": False},
        },
        {
            "name": "Zone labels",
            "type": "scatter",
            "symbolSize": 0,
            "silent": True,
            "z": 3,
            "tooltip": {"show": False},
            "data": [{
                "value": [round(zone["anchor"][0], 3), round(zone["anchor"][1], 3)],
                "label": {
                    "show": True,
                    "formatter": _zone_label(zone["band"]),
                    "color": ZONE_TEXT[zone["band"]["tone"]],
                    "fontSize": 11,
                    "fontWeight": 600,
                    "lineHeight": 14,
                },
            } for zone in model["zones"]],
            "markLine": _muscle_lines(model),
        },
    ]
    points = model["points"]
    if len(points) > 1:
        series.append({
            "name": "Your path",
            "type": "line",
            "data": [[round(p["fmi"], 2), round(p["ffmi"], 2)] for p in points],
            "symbol": "none",
            "smooth": False,
            "lineStyle": {"color": SCAN_COLOR, "width": 2, "opacity": 0.5},
            "tooltip": {"show": False},
            "z": 4,
        })
    goal = model["goal"]
    latest = model["latest"]
    if goal:
        series.append({
            "name": "To goal",
            "type": "line",
            "data": [[round(latest["fmi"], 2), round(latest["ffmi"], 2)], [round(goal["fmi"], 2), round(goal["ffmi"], 2)]],
            "symbol": ["none", "arrow"],
            "symbolSize": 9,
            "smooth": False,
            "lineStyle": {"color": GOAL_COLOR, "width": 1.5, "type": "dashed"},
            "itemStyle": {"color": GOAL_COLOR},
            "tooltip": {"show": False},
            "z": 4,
        })
        series.append({
            "name": "Plan goal",
            "type": "scatter",
            "symbol": "circle",
            "symbolSize": 13,
            "z": 6,
            "itemStyle": {"color": "#ffffff", "borderColor": GOAL_COLOR, "borderWidth": 2.5},
            "label": {"show": True, "position": "bottom", "distance": 6, "formatter": "Current plan", "color": GOAL_COLOR,
                      "fontWeight": 700, "fontSize": 11},
            "data": [{"value": [round(goal["fmi"], 2), round(goal["ffmi"], 2)], "tip": _goal_tip(goal)}],
        })
    route = model.get("route")
    if route:
        phases = route.get("phases") or []
        series.append({
            "name": "Route",
            "type": "line",
            "smooth": False,
            "symbol": "circle",
            "symbolSize": 6,
            "lineStyle": {"color": DREAM_COLOR, "width": 2, "type": [6, 4]},
            "itemStyle": {"color": "#ffffff", "borderColor": DREAM_COLOR, "borderWidth": 1.5},
            "z": 5,
            "data": [
                {"value": [round(x, 2), round(y, 2)], "tip": _route_tip(phases[i - 1] if i else None, phases[0] if phases else None)}
                for i, (x, y) in enumerate(route["path"])
            ],
        })
    dream = model.get("dream")
    if dream:
        series.append({
            "name": "Your goal",
            "type": "scatter",
            "symbol": STAR,
            "symbolSize": 22,
            "z": 8,
            "itemStyle": {"color": DREAM_COLOR, "borderColor": "#ffffff", "borderWidth": 1.5},
            "label": {"show": True, "position": "right", "distance": 6, "formatter": "Your goal", "color": DREAM_COLOR,
                      "fontWeight": 700, "fontSize": 12},
            "data": [{"value": [round(dream["fmi"], 2), round(dream["ffmi"], 2)], "tip": _dream_tip(dream)}],
        })
    series.append({
        "name": "Scans",
        "type": "scatter",
        "z": 7,
        "data": [{
            "value": [round(p["fmi"], 2), round(p["ffmi"], 2)],
            "tip": _scan_tip(p),
            "symbolSize": 16 if p is latest else 9,
            "itemStyle": {"color": SCAN_COLOR, "opacity": 1 if p is latest else 0.55,
                          "borderColor": "#ffffff", "borderWidth": 2 if p is latest else 1},
            "label": {"show": p is latest, "position": "top", "distance": 6, "formatter": "You", "color": SCAN_COLOR,
                      "fontWeight": 700, "fontSize": 12},
        } for p in points],
    })
    return {
        "animation": False,
        "grid": {"left": 52, "right": 18, "top": 14, "bottom": 46},
        "tooltip": {"trigger": "item", "confine": True},
        "xAxis": {
            "type": "value", "min": box["x0"], "max": box["x1"], "interval": 2,
            "name": "Fat mass index (kg/m²)  →  more fat", "nameLocation": "middle", "nameGap": 30,
            "nameTextStyle": {"color": MUTED, "fontSize": 11},
            "splitLine": {"show": False},
            "axisLine": {"show": True, "lineStyle": {"color": GRID_LINE}},
        },
        "yAxis": {
            "type": "value", "min": box["y0"], "max": box["y1"], "interval": 1,
            "name": "Lean mass index (kg/m²)  →  more muscle", "nameLocation": "middle", "nameGap": 34,
            "nameTextStyle": {"color": MUTED, "fontSize": 11},
            "splitLine": {"show": False},
            "axisLine": {"show": True, "lineStyle": {"color": GRID_LINE}},
        },
        "series": series,
    }


def _muscle_lines(model):
    box = model["box"]
    rows = Ratings.bands(model["ffmi_cuts"], Ratings.FFMI_LABELS, Ratings.FFMI_TONES, (box["y0"], box["y1"]))
    return {
        "silent": True,
        "symbol": "none",
        "lineStyle": {"color": GRID_LINE, "type": "dashed", "width": 1},
        "label": {"color": MUTED, "fontSize": 10, "position": "insideStartTop"},
        "data": [{"yAxis": row["from"], "label": {"formatter": "%s muscle ↑" % row["label"]}} for row in rows[1:]],
    }


def _zone_label(band):
    if band["from"] <= 0:
        return "%s\n<%s%%" % (band["label"], Ratings.fmt(band["to"], 0))
    if band["to"] >= 100:
        return "%s\n>%s%%" % (band["label"], Ratings.fmt(band["from"], 0))
    return "%s\n%s–%s%%" % (band["label"], Ratings.fmt(band["from"], 0), Ratings.fmt(band["to"], 0))


def _scan_tip(point):
    return ("<b>Scan · %s</b><br/>Body fat %s%%<br/>Fat %s kg · lean index %s<br/>Fat-free %s kg · fat index %s"
            % (_day(point["date"]), Ratings.fmt(point["bf"], 1), Ratings.fmt(point["fat_kg"], 1),
               Ratings.fmt(point["ffmi"], 1), Ratings.fmt(point["ffm_kg"], 1), Ratings.fmt(point["fmi"], 1)))


def _goal_tip(goal):
    return ("<b>Current plan target</b><br/>%s kg at %s%% body fat<br/>Fat %s kg · fat-free %s kg"
            % (Ratings.fmt(goal["weight_kg"], 1), Ratings.fmt(goal["bf"], 1), Ratings.fmt(goal["fat_kg"], 1),
               Ratings.fmt(goal["ffm_kg"], 1)))


def _route_tip(phase, first):
    if phase is None:
        return "<b>Today</b><br/>%s kg · %s%% body fat" % (
            Ratings.fmt(first["start"]["weight_kg"], 1), Ratings.fmt(first["start"]["bf_percent"], 1)) if first else ""
    end = phase["end"]
    return "<b>After: %s</b><br/>%s · %s weeks<br/>%s kg · %s%% body fat · lean index %s" % (
        phase["label"], _day(end["date"]), phase["weeks"], Ratings.fmt(end["weight_kg"], 1),
        Ratings.fmt(end["bf_percent"], 1), Ratings.fmt(end["ffmi"], 1))


def _dream_tip(dream):
    return "<b>Your goal</b><br/>%s%% body fat · lean index %s<br/>%s kg: %s kg fat-free, %s kg fat" % (
        Ratings.fmt(dream["bf"], 1), Ratings.fmt(dream["ffmi"], 1), Ratings.fmt(dream["weight_kg"], 1),
        Ratings.fmt(dream["ffm_kg"], 1), Ratings.fmt(dream["fat_kg"], 1))


def _signed(value):
    return "%s%s" % ("+" if value > 0 else "−" if value < 0 else "", Ratings.fmt(abs(value), 1))


def _day(value):
    day = Ratings.as_date(value)
    return "%d %s %d" % (day.day, MONTHS[day.month - 1], day.year) if day else "your first scan"
