from ._anvil_designer import ProgressFormTemplate
from anvil import *
from routing import router
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
from anvil.js import window
from craftify_library.CustomComponents.ChartCard import ChartCard
from craftify_library.CustomComponents.EChart import EChart
from craftify_library.CraftifyUtils.echarts_theme import apply_craftify_echarts_theme, padded_value_axis
from body_comp_tracker import Format, Layout
from body_comp_tracker.ProgressCharts import (
    journey_options,
    journey_planned,
    journey_points,
    macro_stack,
    spine_options,
    week_chip,
)


def _chart_card(title, subtitle, options, height="420px"):
    card = ChartCard(title=title, subtitle=subtitle)
    card.mount(EChart(options=apply_craftify_echarts_theme(options), height=height))
    return Layout.flat(card)


def _js_spine_tooltip():
    return window.Function(
        "params",
        "if (!params || !params.length) return '';"
        "var lines = [params[0].axisValue || ''];"
        "var extra = null;"
        "for (var i = 0; i < params.length; i++) {"
        "  var item = params[i];"
        "  var name = item.seriesName || '';"
        "  if (name === 'Lane' || name === 'Lane width') continue;"
        "  var data = item.data;"
        "  if (extra == null && data && typeof data === 'object' && data.protein_g != null) extra = data;"
        "  var value = item.value;"
        "  if (value && typeof value === 'object' && 'value' in value) value = value.value;"
        "  if (value == null) continue;"
        "  lines.push(name + '  ' + value);"
        "}"
        "if (extra) {"
        "  lines.push('P ' + extra.protein_g + 'g · F ' + extra.fat_g + 'g · C ' + extra.carbs_g + 'g');"
        "  lines.push(extra.kcal + ' kcal');"
        "}"
        "return lines.join('<br/>');",
    )


def _kcal_axis(rows):
    values = []
    for row in rows:
        stack = macro_stack(row)
        values.append(stack["kcal"] if stack else None)
    axis = padded_value_axis(values, name="kcal", floor=800, step=100, pad=250)
    axis["gridIndex"] = 2
    return axis


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
        current_week = state.get("current_week") or 1
        chip = week_chip(schedule, current_week)
        spine = spine_options(schedule, current_week)
        spine["yAxis"][2] = _kcal_axis(schedule)
        spine["tooltip"]["formatter"] = _js_spine_tooltip()
        journey = journey_options(
            journey_points(schedule, state.get("dexa_weeks")),
            journey_planned(schedule),
        )
        header = Layout.page_header(
            "Progress",
            eyebrow=Format.eyebrow(state),
            description="Weight, body fat, and issued macros on one week spine. Green hits the lane; red misses.",
            actions=(Layout.button("Weekly tracker", self._open_tracker),),
        )
        summary = Layout.html(
            '<p class="bc-progress-chip"><span class="bc-macros-chip">%s</span> recent logged weeks, scored on weight</p>'
            % Layout.esc(chip)
        )
        charts = Layout.grid(
            "minmax(0, 1.45fr) minmax(280px, 0.75fr)",
            _chart_card("Week spine", "Phase bands · hit or miss · faded forecast", spine),
            _chart_card("Weight × body fat", "Each point is a week. Hollow marks are DEXA.", journey),
        )
        charts.dom_nodes["grid"].classList.add("bc-progress-charts")
        self.add_component(
            Layout.stack(header, summary, charts),
            full_width_row=True,
        )

    def _open_tracker(self, **event_args):
        Layout.navigate("tracker")

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
