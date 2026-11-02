"""Pure HTML builders for the goal, roadmap, and coach cards. No Anvil imports."""

from body_comp_tracker import DexaRatings as Ratings

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
FFMI_LEVELS = {
    "male": (("Average", 19.0), ("Above average", 20.5), ("Excellent", 22.0), ("Elite natural", 23.5)),
    "female": (("Average", 16.0), ("Above average", 17.5), ("Excellent", 19.0), ("Elite natural", 20.5)),
}
TRAINING_YEARS = (("Under 1 year", 0.0), ("1–2 years", 1.0), ("2–3 years", 2.0), ("3 or more years", 3.0))
KIND_NAMES = {"cut": "Cut", "maintain": "Maintenance", "bulk": "Lean bulk", "recomp": "Recomp"}
VERDICT_TEXT = {
    "realistic": ("Realistic", "good"),
    "ambitious": ("Ambitious", "fair"),
    "stretch": ("Stretch goal", "high"),
    "unrealistic": ("Unrealistic", "bad"),
}


def esc(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def month(value):
    day = Ratings.as_date(value)
    return "%s %d" % (MONTHS[day.month - 1], day.year) if day else ""


def ffmi_items(sex, current=None):
    items = [("%s · %s" % (label, Ratings.fmt(value, 1)), value) for label, value in FFMI_LEVELS[sex]]
    if current is not None and current not in [value for _, value in items]:
        items.append(("Custom · %s" % Ratings.fmt(current, 1), current))
    return items


def goal_preview(bf, ffmi, height_cm, now_ffm):
    """One line describing the goal body in kilos."""
    if not bf or not ffmi or not height_cm:
        return ""
    ffm = ffmi * (height_cm / 100.0) ** 2
    weight = ffm / (1 - bf / 100.0)
    text = "That body weighs about %s kg: %s kg fat-free mass and %s kg fat." % (
        Ratings.fmt(weight, 1), Ratings.fmt(ffm, 1), Ratings.fmt(weight - ffm, 1))
    if now_ffm:
        change = ffm - now_ffm
        if change > 0.3:
            text += " That is %s kg more lean mass than today." % Ratings.fmt(change, 1)
        elif change < -0.3:
            text += " That is less lean mass than you have today, so the route is fat loss only."
    return text


def _years(weeks):
    years = weeks / 52.0
    if years < 1:
        return "%d months" % max(1, round(weeks / 4.345))
    return "%s years" % Ratings.fmt(years, 1)


def tiles_html(plans, selected, recommended=None):
    tiles = []
    for plan in plans:
        badge = '<em class="bc-rm-badge">Coach pick</em>' if plan["key"] == recommended else ""
        when = ("Goal by %s" % month(plan["end"]["date"])) if plan["reaches_goal"] else "Not reached within 10 years"
        tiles.append(
            '<button type="button" class="bc-rm-tile%s" data-key="%s">'
            '<span class="bc-rm-tile-top"><b>%s</b>%s</span>'
            '<span class="bc-rm-time">%s</span>'
            '<span class="bc-rm-when">%s</span>'
            '<span class="bc-rm-meta">%s · body fat %s–%s%%</span>'
            '<span class="bc-rm-pitch">%s</span>'
            '</button>' % (
                " is-selected" if plan["key"] == selected else "", esc(plan["key"]), esc(plan["name"]), badge,
                esc(_years(plan["weeks"])), esc(when), _count(len(plan["phases"]), "phase"),
                Ratings.fmt(plan["low_bf"], 0), Ratings.fmt(plan["peak_bf"], 0), esc(plan["pitch"])))
    return '<div class="bc-rm-tiles">%s</div>' % "".join(tiles)


def timeline_html(plan, notes=None):
    """Proportional phase bar plus one row per phase."""
    notes = notes or {}
    phases = plan["phases"]
    if not phases:
        return '<p class="bc-rm-empty">You are already at this goal. Hold it with maintenance calories.</p>'
    bar = "".join(
        '<i class="is-%s" style="flex:%s" title="%s · %s weeks"></i>' % (
            phase["kind"], phase["weeks"], esc(phase["label"]), phase["weeks"])
        for phase in phases
    )
    legend = "".join(
        '<span class="is-%s">%s</span>' % (kind, KIND_NAMES[kind])
        for kind in ("cut", "maintain", "bulk", "recomp") if any(phase["kind"] == kind for phase in phases)
    )
    rows = []
    for index, phase in enumerate(phases):
        end = phase["end"]
        note = notes.get(index)
        rows.append(
            '<div class="bc-rm-row">'
            '<span class="bc-rm-dot is-%s"></span>'
            '<div class="bc-rm-row-main">'
            '<div class="bc-rm-row-top"><b>%s</b><span>%s – %s · %s</span></div>'
            '<p>%s · %s</p>'
            '<p class="bc-rm-end">Ends at %s kg · %s%% body fat · lean index %s</p>%s'
            '</div></div>' % (
                phase["kind"], esc(phase["label"]), month(phase["start"]["date"]), month(end["date"]),
                esc(_weeks(phase["weeks"])), esc(_energy(phase["kcal_per_day"])), esc(_pace(phase["kg_per_week"])),
                Ratings.fmt(end["weight_kg"], 1), Ratings.fmt(end["bf_percent"], 1), Ratings.fmt(end["ffmi"], 1),
                '<p class="bc-rm-note">%s</p>' % esc(note) if note else ""))
    return (
        '<div class="bc-rm-bar">%s</div>'
        '<div class="bc-rm-axis"><span>Today</span><span>%s</span></div>'
        '<div class="bc-rm-legend">%s</div>'
        '<div class="bc-rm-rows">%s</div>' % (bar, esc(month(phases[-1]["end"]["date"])), legend, "".join(rows))
    )


def _count(n, noun):
    return "%d %s%s" % (n, noun, "" if n == 1 else "s")


def _weeks(weeks):
    return "%d week%s" % (weeks, "" if weeks == 1 else "s")


def _energy(kcal):
    if abs(kcal) < 30:
        return "Maintenance calories"
    return "About %s kcal a day %s maintenance" % (Ratings.fmt(abs(kcal), 0), "below" if kcal < 0 else "above")


def _pace(kg):
    if abs(kg) < 0.02:
        return "weight holds steady"
    return "%s %s kg a week" % ("losing" if kg < 0 else "gaining", Ratings.fmt(abs(kg), 2))


def review_is_stale(entry, goal, latest_scan_date):
    if not entry:
        return False
    return entry.get("goal") != goal or (entry.get("scan") or None) != (latest_scan_date or None)


def coach_html(entry, plans, stale=False):
    review = entry["review"]
    label, tone = VERDICT_TEXT.get(review.get("verdict"), VERDICT_TEXT["ambitious"])
    names = {plan["key"]: plan["name"] for plan in plans}

    def items(values):
        return "".join("<li>%s</li>" % esc(value) for value in values)

    columns = []
    for title, values in (("Why this route", review.get("why")), ("This month", review.get("this_month")),
                          ("Watch out for", review.get("watch_outs"))):
        if values:
            columns.append('<div class="bc-co-col"><h5>%s</h5><ul>%s</ul></div>' % (title, items(values)))
    stale_html = ('<p class="bc-co-stale">Your goal or scans changed since this review. Ask again for an updated one.</p>'
                  if stale else "")
    pick = names.get(review.get("recommended"))
    return (
        '<div class="bc-co">%s'
        '<div class="bc-co-head"><span class="bc-co-verdict is-%s">%s</span><h4>%s</h4></div>'
        '%s'
        '<div class="bc-co-cols">%s</div>'
        '%s'
        '</div>' % (
            stale_html, tone, esc(label), esc(review.get("headline") or ""),
            '<p class="bc-co-pick">Recommended route: <b>%s</b></p>' % esc(pick) if pick else "",
            "".join(columns),
            '<p class="bc-co-fit"><b>Your current plan</b> %s</p>' % esc(review["plan_fit"]) if review.get("plan_fit") else "",
        )
    )


def tweak_html(tweak):
    return ('<div class="bc-co-tweak"><b>The coach suggests trying %s%% body fat at lean index %s</b><p>%s</p></div>' % (
        Ratings.fmt(tweak["bf_percent"], 1), Ratings.fmt(tweak["ffmi"], 1), esc(tweak.get("reason") or "")))
