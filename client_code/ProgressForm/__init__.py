from ._anvil_designer import ProgressFormTemplate
from anvil import *
import anvil.server
from craftify_library.CustomComponents.ChartCard import ChartCard
from craftify_library.CustomComponents.EChart import EChart


def _line(name, weeks, values):
    return {"name": name, "type": "line", "smooth": True, "connectNulls": False, "data": values, "showSymbol": False}


class ProgressForm(ProgressFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        state = anvil.server.call("bodycomp_get_plan")
        schedule = state.get("schedule") or []
        if not state.get("has_plan") or not schedule:
            self.body.add_component(Label(text="Save a profile to see progress.", role="coach-note"))
            return
        weeks = ["W%s" % row.get("week") for row in schedule]
        self._chart(
            "Weight (kg)",
            weeks,
            [
                _line("Target weight", weeks, [row.get("target_weight_kg") for row in schedule]),
                _line("Actual weight", weeks, [row.get("actual_weight_kg") for row in schedule]),
            ],
        )
        self._chart(
            "Body fat %",
            weeks,
            [
                _line("Target BF%", weeks, [row.get("target_bf_percent") for row in schedule]),
                _line("Actual BF%", weeks, [row.get("bf_percent") for row in schedule]),
            ],
        )
        self._chart(
            "Weekly calories",
            weeks,
            [{"name": "Calories", "type": "bar", "data": [row.get("target_calories") for row in schedule]}],
        )

    def _chart(self, title, weeks, series):
        card = ChartCard(title=title, subtitle="Target vs actual")
        option = {
            "tooltip": {"trigger": "axis"},
            "legend": {"top": 0},
            "grid": {"left": 48, "right": 16, "top": 36, "bottom": 28},
            "xAxis": {"type": "category", "data": weeks},
            "yAxis": {"type": "value", "scale": True},
            "dataZoom": [{"type": "inside"}],
            "series": series,
        }
        card.mount(EChart(options=option, height="320px"))
        self.body.add_component(card, full_width_row=True)
        self.body.add_component(Spacer(height=12))
