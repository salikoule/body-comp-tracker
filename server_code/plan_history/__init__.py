"""Plan updates must keep issued calories and logged weeks."""

from __future__ import annotations

from datetime import date


def merge_issued_calories(existing: dict | None, week1_calories: int) -> dict:
    """Keep already-issued weeks. Only fill week 1 if it was never issued."""
    issued = {}
    for key, value in (existing or {}).items():
        try:
            issued[str(int(key))] = int(value)
        except (TypeError, ValueError):
            continue
    issued.setdefault("1", int(week1_calories))
    return issued


def dexa_weeks(measured_on, start_date, week_index_for) -> list[int]:
    if measured_on is None or start_date is None:
        return []
    if not isinstance(measured_on, date):
        try:
            measured_on = date.fromisoformat(str(measured_on)[:10])
        except ValueError:
            return []
    return [week_index_for(measured_on, start_date)]
