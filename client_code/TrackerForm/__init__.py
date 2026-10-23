from ._anvil_designer import TrackerFormTemplate
from anvil import *
import anvil.server
from tabulator.Tabulator import Tabulator

PHASE = {"cut": "Cut", "reverse": "Reverse", "bulk": "Bulk", "recomp": "Recomp"}

COLUMNS = [
    {"title": "Week", "field": "weekLabel", "width": 72},
    {"title": "Week of", "field": "week_start", "width": 118},
    {"title": "Phase", "field": "phaseLabel", "width": 120},
    {"title": "Target kg", "field": "target_weight_kg", "width": 100, "hozAlign": "right"},
    {"title": "Actual kg", "field": "actual_weight_kg", "width": 100, "hozAlign": "right"},
    {"title": "Δ kg", "field": "weight_delta_kg", "width": 84, "hozAlign": "right"},
    {"title": "Waist", "field": "waist_cm", "width": 84, "hozAlign": "right"},
    {"title": "Neck", "field": "neck_cm", "width": 84, "hozAlign": "right"},
    {"title": "BF", "field": "bf_percent", "width": 80, "hozAlign": "right"},
    {"title": "BF target", "field": "target_bf_percent", "width": 96, "hozAlign": "right"},
    {"title": "Δ BF", "field": "bf_delta", "width": 84, "hozAlign": "right"},
    {"title": "Sess", "field": "training_sessions", "width": 80, "hozAlign": "right"},
    {"title": "Steps", "field": "daily_steps", "width": 88, "hozAlign": "right"},
    {"title": "kcal", "field": "target_calories", "width": 96, "hozAlign": "right"},
    {"title": "Protein", "field": "protein_g", "width": 88, "hozAlign": "right"},
    {"title": "Fat", "field": "fat_g", "width": 72, "hozAlign": "right"},
    {"title": "Carbs", "field": "carbs_g", "width": 80, "hozAlign": "right"},
    {"title": "Trend", "field": "trend_rate_kg", "width": 96, "hozAlign": "right"},
    {"title": "Status", "field": "status", "width": 110},
    {"title": "Notes", "field": "notes", "width": 200},
]


class TrackerForm(TrackerFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._current = 1
        state = anvil.server.call("bodycomp_get_plan")
        if not state.get("has_plan"):
            self.body.add_component(Label(text="Save a profile before the tracker has weeks.", role="coach-note"))
            return
        self._current = state.get("current_week") or 1
        self.intro.text = "Week %s · %s. Scroll the table sideways for every column." % (
            self._current,
            PHASE.get(state.get("phase"), state.get("phase") or ""),
        )
        rows = []
        for row in state.get("schedule") or []:
            item = dict(row)
            item["weekLabel"] = "W%s" % row.get("week")
            item["phaseLabel"] = PHASE.get(row.get("phase"), row.get("phase") or "")
            rows.append(item)
        table = Tabulator()
        table.height = "640px"
        table.columns = COLUMNS
        table.options = {"layout": "fitData", "columnDefaults": {"headerSort": False}}
        table.data = rows
        table.set_event_handler("row_formatter", self._paint_row)
        self.body.add_component(table, full_width_row=True)

    def _paint_row(self, row, **event_args):
        data = row.getData()
        week = data["week"] if data is not None else None
        if week == self._current:
            row.getElement().style.background = "#e8f1fb"
