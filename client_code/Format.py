import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
"""Display formatting shared by every page."""

PHASE = {"cut": "Cut", "reverse": "Reverse diet", "bulk": "Bulk", "recomp": "Recomp"}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def phase(name):
    return PHASE.get(name or "", (name or "").title())


def date_label(value):
    if value is None or value == "":
        return "—"
    text = str(value)[:10]
    parts = text.split("-")
    if len(parts) != 3:
        return text
    try:
        return "%s %s %s" % (int(parts[2]), MONTHS[int(parts[1]) - 1], parts[0])
    except (ValueError, IndexError):
        return text


def number(value, digits=0, unit=""):
    if value is None or value == "":
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    text = _group(("%." + str(digits) + "f") % num)
    return text + (" " + unit if unit else "")


def percent(value, digits=1):
    text = number(value, digits)
    return text if text == "—" else text + "%"


def _group(text):
    sign = ""
    if text.startswith("-"):
        sign, text = "-", text[1:]
    whole, _, frac = text.partition(".")
    chunks = []
    while len(whole) > 3:
        chunks.insert(0, whole[-3:])
        whole = whole[:-3]
    chunks.insert(0, whole)
    return sign + ",".join(chunks) + ("." + frac if frac else "")


def current_row(state):
    week = state.get("current_week") or 1
    rows = state.get("schedule") or []
    for row in rows:
        if row.get("week") == week:
            return row
    return rows[0] if rows else {}


def eyebrow(state):
    return "Week %s · %s" % (state.get("current_week") or 1, phase(state.get("phase")))
