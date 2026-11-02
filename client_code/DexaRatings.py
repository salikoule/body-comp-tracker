"""Rate DEXA metrics against ranges for the person's sex, age, and height, and explain each rating."""

from datetime import date

TONE_LABELS = ("great", "good", "fair", "high", "bad", "info")

BF_CUTS = {"male": (12, 18, 24, 30), "female": (20, 27, 33, 39)}
BF_LABELS = ("Athletic", "Fit", "Average", "High", "Very high")
BF_TONES = ("great", "good", "fair", "high", "bad")
BF_SCALE = {"male": (5, 40), "female": (12, 50)}

VAT_CUTS = {"male": (450, 1000, 1500), "female": (350, 750, 1200)}
VAT_LABELS = ("Ideal", "Moderate", "Elevated", "High risk")
VAT_TONES = ("good", "fair", "high", "bad")
VAT_SCALE = (0, 2000)

FFMI_CUTS = {"male": (17, 18.5, 20, 22), "female": (14, 15.5, 17, 19)}
FFMI_LABELS = ("Low", "Below average", "Average", "Above average", "Excellent")
FFMI_TONES = ("high", "fair", "good", "great", "great")
FFMI_SCALE = {"male": (14, 25), "female": (11, 22)}


def as_date(value):
    if isinstance(value, date):
        return value
    try:
        parts = [int(p) for p in str(value)[:10].split("-")]
        return date(parts[0], parts[1], parts[2])
    except (TypeError, ValueError, IndexError):
        return None


def age_on(born, on):
    born, on = as_date(born), as_date(on) or date.today()
    if born is None:
        return None
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def person_from_state(state, on=None):
    sex = "female" if (state.get("sex") or "").lower() == "female" else "male"
    return {
        "sex": sex,
        "age": age_on(state.get("date_of_birth"), on),
        "height_cm": _num(state.get("height_cm")),
        "target_bf_percent": _num(state.get("target_bf_percent")),
        "target_weight_kg": _num(state.get("target_weight_kg")),
    }


def bf_cuts(sex, age):
    shift = 0 if (age or 0) < 40 else (2 if age < 60 else 4)
    return tuple(cut + shift for cut in BF_CUTS[sex])


def bands(cuts, labels, tones, scale):
    low, high = scale
    edges = (low,) + tuple(cuts) + (high,)
    return [
        {"from": edges[i], "to": edges[i + 1], "label": labels[i], "tone": tones[i]}
        for i in range(len(labels))
    ]


def band_for(value, rows):
    for row in rows[:-1]:
        if value < row["to"]:
            return row
    return rows[-1]


def rate_scan(scan, person, previous=None):
    """Return the metric cards for one scan, in display order."""
    cards = []
    for build in (_body_fat, _visceral, _ffmi, _rmr, _bone):
        card = build(scan, person, previous or {})
        if card is not None:
            cards.append(card)
    return cards


def rating(scan, person, key):
    """Tone and one-line explanation for a table cell, or (None, "")."""
    for card in rate_scan(scan, person):
        if card["key"] == key and card["tone"] != "info":
            return card["tone"], "%s: %s" % (card["verdict"], card["summary"])
    return None, ""


def ffmi(scan, person):
    ffm, height = _num(scan.get("ffm_kg")), _num(person.get("height_cm"))
    if ffm is None or not height:
        return None
    return round(ffm / (height / 100.0) ** 2, 1)


def _body_fat(scan, person, previous):
    bf = _num(scan.get("bf_percent"))
    if bf is None:
        return None
    sex, age = person["sex"], person.get("age")
    cuts = bf_cuts(sex, age)
    rows = bands(cuts, BF_LABELS, BF_TONES, BF_SCALE[sex])
    band = band_for(bf, rows)
    person_text = who(person)
    summary = "%s%% is in the %s band (%s) for %s on DEXA. The fit band is %s–%s%%." % (
        fmt(bf, 1), band["label"].lower(), _range(band, "%"), person_text, fmt(cuts[0], 0), fmt(cuts[1], 0))
    detail = _bf_detail(scan, person, bf, cuts)
    return _card("bf_percent", "Body fat", bf, "%", 1, band, rows, summary, detail,
                 _delta(scan, previous, "bf_percent", 1, "pp", lower_is_better=True))


def _bf_detail(scan, person, bf, cuts):
    ffm = _num(scan.get("ffm_kg"))
    if ffm is None:
        return ""
    fat_now = _num(scan.get("fat_mass_kg"))
    if fat_now is None:
        fat_now = ffm / (1 - bf / 100.0) - ffm
    goal = cuts[1] if bf > cuts[1] else cuts[0]
    goal_name = "the top of the fit band" if bf > cuts[1] else "athletic"
    parts = []
    if bf > goal:
        weight = ffm / (1 - goal / 100.0)
        parts.append(
            "Keeping your %s kg fat-free mass, %s (%s%%) would put you at %s kg: about %s kg less fat than the %s kg you carry now."
            % (fmt(ffm, 1), goal_name, fmt(goal, 0), fmt(weight, 1), fmt(fat_now - (weight - ffm), 1), fmt(fat_now, 1)))
    else:
        parts.append("You are already lean for your age. Keeping it there matters more than going lower.")
    target_bf, target_kg = person.get("target_bf_percent"), person.get("target_weight_kg")
    if target_bf is not None and target_bf < bf:
        parts.append("Your plan aims for %s%%%s." % (
            fmt(target_bf, 1), " (%s kg)" % fmt(target_kg, 1) if target_kg else ""))
    return " ".join(parts)


def _visceral(scan, person, previous):
    vat = _num(scan.get("vat_g"))
    if vat is None:
        return None
    sex = person["sex"]
    cuts = VAT_CUTS[sex]
    rows = bands(cuts, VAT_LABELS, VAT_TONES, VAT_SCALE)
    band = band_for(vat, rows)
    summary = "%s g of visceral fat is %s. Under %s g is the ideal range for %s." % (
        fmt(vat, 0), band["label"].lower(), fmt(cuts[0], 0), "women" if sex == "female" else "men")
    if vat > cuts[0]:
        detail = ("That is %s g above ideal. Visceral fat sits around your organs and is the fat most linked to heart "
                  "and metabolic risk. It usually shrinks faster than other fat in a calorie deficit." % fmt(vat - cuts[0], 0))
    else:
        detail = "Visceral fat sits around your organs and is the fat most linked to heart and metabolic risk. Yours is in the ideal range."
    return _card("vat_g", "Visceral fat", vat, "g", 0, band, rows, summary, detail,
                 _delta(scan, previous, "vat_g", 0, "g", lower_is_better=True))


def _ffmi(scan, person, previous):
    value = ffmi(scan, person)
    if value is None:
        return None
    sex = person["sex"]
    cuts = FFMI_CUTS[sex]
    rows = bands(cuts, FFMI_LABELS, FFMI_TONES, FFMI_SCALE[sex])
    band = band_for(value, rows)
    height_m = person["height_cm"] / 100.0
    summary = "%s is %s for %s (average is %s–%s). It is your %s kg fat-free mass divided by your height squared (%s m)²." % (
        fmt(value, 1), band["label"].lower(), "a woman" if sex == "female" else "a man", fmt(cuts[1], 1), fmt(cuts[2], 0),
        fmt(_num(scan.get("ffm_kg")), 1), fmt(height_m, 2))
    ffm = _num(scan.get("ffm_kg"))
    if value < cuts[2]:
        need = cuts[2] * height_m ** 2 - ffm
        detail = "Reaching %s (above average) means about %s kg more lean mass at your height. That is what the bulk phase builds." % (
            fmt(cuts[2], 0), fmt(need, 1))
    elif value < cuts[3]:
        need = cuts[3] * height_m ** 2 - ffm
        detail = "Above average. About %s kg more lean mass would take you to the excellent band (%s)." % (fmt(need, 1), fmt(cuts[3], 0))
    else:
        detail = "Excellent muscle for your height. Protect it while cutting with enough protein and heavy training."
    previous_ffmi = ffmi(previous, person) if previous else None
    delta = None
    if previous_ffmi is not None:
        delta = _delta_card(value - previous_ffmi, 1, "", lower_is_better=False)
    return _card("ffmi", "Lean mass index", value, "", 1, band, rows, summary, detail, delta)


def _rmr(scan, person, previous):
    rmr = _num(scan.get("rmr_kcal"))
    if rmr is None:
        return None
    ffm = _num(scan.get("ffm_kg"))
    summary = "%s kcal a day at complete rest, before steps, training, and digestion." % fmt(rmr, 0)
    detail = ""
    if ffm is not None:
        katch = 370 + 21.6 * ffm
        detail = ("From your fat-free mass, the Katch-McArdle formula gives about %s kcal. Many DEXA reports print an "
                  "estimate rather than a measured value, so treat it as a guide." % fmt(katch, 0))
    return _card("rmr_kcal", "Resting metabolism", rmr, "kcal", 0, None, [], summary, detail,
                 _delta(scan, previous, "rmr_kcal", 0, "kcal", lower_is_better=False))


def _bone(scan, person, previous):
    bmc = _num(scan.get("bmc_kg"))
    if bmc is None:
        return None
    total = _num(scan.get("total_mass_kg"))
    share = " (%s%% of your weight)" % fmt(bmc / total * 100, 1) if total else ""
    summary = "%s kg of bone mineral%s." % (fmt(bmc, 2), share)
    detail = ("A body-composition scan does not rate bone health. Ask for a bone density test with a T-score if you want "
              "that checked.")
    return _card("bmc_kg", "Bone mineral", bmc, "kg", 2, None, [], summary, detail, None)


def _card(key, label, value, unit, digits, band, rows, summary, detail, delta):
    scale = (rows[0]["from"], rows[-1]["to"]) if rows else None
    return {
        "key": key,
        "label": label,
        "value": value,
        "display": fmt(value, digits),
        "unit": unit,
        "tone": band["tone"] if band else "info",
        "verdict": band["label"] if band else "Info",
        "bands": rows,
        "marker": _position(value, scale) if scale else None,
        "summary": summary,
        "detail": detail,
        "delta": delta,
    }


def _delta(scan, previous, key, digits, unit, lower_is_better):
    now, before = _num(scan.get(key)), _num(previous.get(key)) if previous else None
    if now is None or before is None:
        return None
    return _delta_card(now - before, digits, unit, lower_is_better)


def _delta_card(change, digits, unit, lower_is_better):
    if round(change, digits) == 0:
        return {"text": "No change", "tone": "info"}
    better = change < 0 if lower_is_better else change > 0
    return {
        "text": "%s%s%s since last scan" % ("+" if change > 0 else "−", fmt(abs(change), digits), (" " + unit) if unit else ""),
        "tone": "good" if better else "high",
    }


def _position(value, scale):
    low, high = scale
    if high <= low:
        return 0
    return max(0.0, min(100.0, (value - low) / float(high - low) * 100))


def who(person):
    age = person.get("age")
    noun = "a woman" if person["sex"] == "female" else "a man"
    return "%s aged %s" % (noun, age) if age else noun


def _range(band, unit):
    return "%s–%s%s" % (fmt(band["from"], 0), fmt(band["to"], 0), unit)


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value, digits):
    if value is None:
        return "—"
    text = ("%." + str(digits) + "f") % value
    if digits == 0:
        number = text.lstrip("-")
        groups = []
        while len(number) > 3:
            groups.insert(0, number[-3:])
            number = number[:-3]
        groups.insert(0, number)
        text = ("-" if text.startswith("-") else "") + ",".join(groups)
    return text
