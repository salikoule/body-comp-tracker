"""Pure builders for the weigh-ins page. No Anvil imports."""

from datetime import date, timedelta

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _day(value):
    if isinstance(value, date):
        return value
    parts = str(value)[:10].split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _clean(weights):
    """One kg per date, oldest first. Later duplicates replace earlier ones."""
    by_day = {}
    for item in weights or []:
        try:
            by_day[_day(item.get("date"))] = float(item.get("kg"))
        except (TypeError, ValueError, AttributeError):
            continue
    return sorted(by_day.items())


def _week(day, start):
    """Plan week for a date, or None when it falls before the plan's first Monday."""
    if not start:
        return None
    try:
        start = _day(start)
    except (TypeError, ValueError):
        return None
    anchor = start - timedelta(days=start.weekday())
    if day < anchor:
        return None
    return 1 + (day - anchor).days // 7


def _label(day):
    return "%s %s %s %s" % (DAYS[day.weekday()], day.day, MONTHS[day.month - 1], day.year)


def entries(weights, start=None):
    """Newest first. ``delta`` is the change from the previous logged morning."""
    rows = _clean(weights)
    built = []
    previous = None
    for day, kg in rows:
        built.append({
            "date": day.isoformat(),
            "label": _label(day),
            "kg": round(kg, 1),
            "delta": None if previous is None else round(kg - previous, 1),
            "week": _week(day, start),
        })
        previous = kg
    built.reverse()
    return built


def summary(weights, today):
    """Headline numbers, or None when nothing is logged."""
    rows = _clean(weights)
    if not rows:
        return None
    latest_day, latest_kg = rows[-1]
    first_day, first_kg = rows[0]
    window = [kg for day, kg in rows if today - timedelta(days=6) <= day <= today]
    streak = 1
    cursor = latest_day
    for day, _kg in reversed(rows[:-1]):
        if cursor - day == timedelta(days=1):
            streak += 1
            cursor = day
        else:
            break
    return {
        "count": len(rows),
        "latest_kg": round(latest_kg, 1),
        "latest_date": latest_day.isoformat(),
        "first_date": first_day.isoformat(),
        "since_first": round(latest_kg - first_kg, 1),
        "week_avg": round(sum(round(kg * 10) for kg in window) / len(window)) / 10 if window else None,
        "week_count": len(window),
        "streak": streak,
        "streak_current": (today - latest_day).days <= 1,
        "delta": None if len(rows) < 2 else round(latest_kg - rows[-2][1], 1),
    }


def delta_html(value):
    """The change from the previous logged morning. A drop is green."""
    if value is None:
        return '<span class="bc-empty">—</span>'
    if value == 0:
        return '<span class="bc-delta">0.0</span>'
    klass = "bc-delta-good" if value < 0 else "bc-delta-bad"
    sign = "+" if value > 0 else ""
    return '<span class="bc-delta %s">%s%.1f</span>' % (klass, sign, value)
