from ._anvil_designer import ProgressFormTemplate
from anvil import *
from routing import router
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
from craftify_library.CustomComponents.ChartCard import ChartCard
from craftify_library.CustomComponents.EChart import EChart
from craftify_library.CraftifyUtils.echarts_theme import apply_craftify_echarts_theme
from body_comp_tracker import Format, Layout


def _line(name, values, dashed=False):
    series = {"name": name, "type": "line", "connectNulls": False, "data": values}
    if dashed:
        series["lineStyle"] = {"type": "dashed"}
    else:
        series["showSymbol"] = False
    return series


def _chart(title, subtitle, weeks, series, unit, height="300px"):
    card = ChartCard(title=title, subtitle=subtitle)
    options = apply_craftify_echarts_theme({
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 0, "right": 8},
        "grid": {"left": 48, "right": 16, "top": 32, "bottom": 28},
        "xAxis": {"type": "category", "data": weeks},
        "yAxis": {"type": "value", "scale": True, "name": unit},
        "dataZoom": [{"type": "inside"}],
        "series": series,
    })
    card.mount(EChart(options=options, height=height))
    return Layout.flat(card)


class ProgressForm(ProgressFormTemplate):
    def __init__(self, routing_context=None, **properties):
        self.init_components(**properties)
        state = anvil.server.call("bodycomp_get_plan")
        schedule = state.get("schedule") or []
        if not state.get("has_plan") or not schedule:
            self.add_component(
                Layout.stack(
                    Layout.page_header("Progress"),
                    Layout.empty_state("Save your profile to see progress.", "Set up plan", self._open_profile),
                ),
                full_width_row=True,
            )
            return
        weeks = ["W%s" % row.get("week") for row in schedule]
        weight = _chart(
            "Weight", "Weekly average vs plan target",
            weeks,
            [
                _line("Target", [row.get("target_weight_kg") for row in schedule]),
                _line("Actual", [row.get("actual_weight_kg") for row in schedule], dashed=True),
            ],
            "kg",
            height="320px",
        )
        body_fat = _chart(
            "Body fat", "Navy estimate vs plan target",
            weeks,
            [
                _line("Target", [row.get("target_bf_percent") for row in schedule]),
                _line("Actual", [row.get("bf_percent") for row in schedule], dashed=True),
            ],
            "%",
        )
        calories = _chart(
            "Calories", "Issued each week after the Sunday check-in",
            weeks,
            [{"name": "kcal", "type": "bar", "data": [row.get("target_calories") for row in schedule]}],
            "kcal",
        )
        header = Layout.page_header(
            "Progress",
            eyebrow=Format.eyebrow(state),
            description="Weight, body fat, and weekly calories across the whole plan. Scroll inside a chart to zoom.",
            actions=(Layout.button("Weekly tracker", self._open_tracker),),
        )
        self.add_component(
            Layout.stack(header, weight, Layout.grid("repeat(2, minmax(0, 1fr))", body_fat, calories)),
            full_width_row=True,
        )

    def _open_tracker(self, **event_args):
        Layout.navigate("tracker")

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
