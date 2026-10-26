from datetime import date

from ._anvil_designer import HomeFormTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
from craftify_library.CustomComponents.ChartCard import ChartCard
from craftify_library.CustomComponents.EChart import EChart
from craftify_library.CustomComponents.KpiCard import KpiCard
from craftify_library.CraftifyUtils.echarts_theme import apply_craftify_echarts_theme
from body_comp_tracker import Format, Layout


class HomeForm(HomeFormTemplate):
    def __init__(self, routing_context=None, **properties):
        self.init_components(**properties)
        self._state = anvil.server.call("bodycomp_get_plan")
        self._render()

    def _render(self):
        self.clear()
        s = self._state
        if not s.get("has_plan"):
            self.add_component(
                Layout.stack(
                    Layout.page_header("Dashboard"),
                    Layout.empty_state("Save your profile to get week 1 calories.", "Set up plan", self._open_profile),
                ),
                full_width_row=True,
            )
            return
        row = Format.current_row(s)
        header = Layout.page_header(
            "Dashboard",
            eyebrow=Format.eyebrow(s),
            description=s.get("reason") or "",
            actions=(
                Layout.button("Weekly tracker", self._open_tracker),
                Layout.button("Sunday check-in", self._open_checkin, primary=True),
            ),
        )
        page = Layout.stack(
            header,
            self._kpis(s, row),
            Layout.grid("minmax(0, 1.4fr) minmax(280px, 1fr)", self._bf_card(s, row), self._weigh_in_card(s)),
            self._trajectory(s),
            self._phases(s),
        )
        self.add_component(page, full_width_row=True)

    def _kpis(self, s, row):
        calories = row.get("target_calories") or s.get("calories")
        return Layout.grid(
            "repeat(auto-fit, minmax(170px, 1fr))",
            KpiCard(title="Eat this week", value=Format.number(calories, 0, "kcal"),
                    subtitle="Maintenance ~%s" % Format.number(s.get("tdee"), 0, "kcal")),
            KpiCard(title="Protein", value=Format.number(row.get("protein_g") or s.get("protein_g"), 0, "g"), subtitle="Per day"),
            KpiCard(title="Fat", value=Format.number(row.get("fat_g") or s.get("fat_g"), 0, "g"), subtitle="Per day"),
            KpiCard(title="Carbs", value=Format.number(row.get("carbs_g") or s.get("carbs_g"), 0, "g"), subtitle="Per day"),
            KpiCard(title="Target this week", value=Format.number(row.get("target_weight_kg"), 1, "kg"),
                    subtitle="Latest %s" % Format.number(s.get("latest_weight_kg"), 1, "kg")),
        )

    def _bf_card(self, s, row):
        start = s.get("bf_percent")
        target = s.get("target_bf_percent")
        current = row.get("bf_percent") if row.get("bf_percent") is not None else start
        pct = 0
        if start is not None and target is not None and start > target and current is not None:
            pct = max(0, min(100, int(round((start - current) / (start - target) * 100))))
        card = Layout.section(
            "Body fat toward target",
            "DEXA sets the plan baseline. Sunday tape is shifted onto that scale."
            if s.get("navy_dexa_offset") is not None
            else "Navy-method estimate from Sunday tape measurements.",
        )
        Layout.body(
            card,
            Layout.html(
                '<div class="bc-progress-head"><strong>%s</strong><span>%s → %s · %s%% of the way</span></div>'
                '<div class="bc-progress-track"><div class="bc-progress-fill" style="width:%s%%"></div></div>'
                % (
                    Layout.esc(Format.percent(current)),
                    Layout.esc(Format.percent(start)),
                    Layout.esc(Format.percent(target)),
                    pct,
                    pct,
                )
            ),
            Layout.note(
                "Target weight %s from %s. Forecast finish %s."
                % (
                    Format.number(s.get("target_weight_kg"), 1, "kg"),
                    Format.number(s.get("start_weight_kg"), 1, "kg"),
                    Format.date_label(s.get("forecast_end")),
                )
            ),
        )
        return card

    def _weigh_in_card(self, s):
        card = Layout.section("This morning", "Daily logs build the weekly average. They do not change mid-week calories.")
        self._weight_input = TextBox(type="number", placeholder="kg")
        self._weight_input.set_event_handler("pressed_enter", self._log_weight)
        latest = s.get("latest_weight_kg")
        Layout.body(
            card,
            Layout.field("Weight (kg)", self._weight_input,
                         hint="Last logged %s" % Format.number(latest, 1, "kg") if latest else ""),
            Layout.button("Log weight", self._log_weight, primary=True),
        )
        return card

    def _trajectory(self, s):
        schedule = (s.get("schedule") or [])[:24]
        card = ChartCard(title="Weight trajectory", subtitle="Target vs weekly average, first 24 weeks")
        options = apply_craftify_echarts_theme({
            "tooltip": {"trigger": "axis"},
            "legend": {"top": 0, "right": 8},
            "grid": {"left": 44, "right": 16, "top": 32, "bottom": 28},
            "xAxis": {"type": "category", "data": ["W%s" % r.get("week") for r in schedule]},
            "yAxis": {"type": "value", "scale": True, "name": "kg"},
            "series": [
                {"name": "Target", "type": "line", "showSymbol": False,
                 "data": [r.get("target_weight_kg") for r in schedule]},
                {"name": "Actual", "type": "line", "connectNulls": False,
                 "lineStyle": {"type": "dashed"},
                 "data": [r.get("actual_weight_kg") for r in schedule]},
            ],
        })
        card.mount(EChart(options=options, height="280px"))
        return Layout.flat(card)

    def _phases(self, s):
        current = s.get("phase")
        cards = []
        for phase in s.get("phases") or []:
            name = phase.get("name") or ""
            cards.append(Layout.html(
                '<div class="bc-phase%s"><span class="bc-pill bc-pill-%s">%s</span>'
                '<p class="bc-phase-dates">%s – %s</p>'
                '<p class="bc-phase-kcal">%s</p>'
                '<p class="bc-phase-summary">%s</p></div>'
                % (
                    " is-current" if name == current else "",
                    Layout.esc(name),
                    Layout.esc(Format.phase(name)),
                    Layout.esc(Format.date_label(phase.get("start"))),
                    Layout.esc(Format.date_label(phase.get("end")) if phase.get("end") else "open"),
                    Layout.esc(Format.number(phase.get("calories"), 0, "kcal")),
                    Layout.esc(phase.get("summary") or ""),
                )
            ))
        if not cards:
            return None
        return Layout.grid("repeat(auto-fit, minmax(220px, 1fr))", *cards)

    def _log_weight(self, **event_args):
        try:
            kg = float(self._weight_input.text)
        except (TypeError, ValueError):
            Notification("Enter your weight in kg.", style="warning").show()
            return
        self._state = anvil.server.call("bodycomp_log_weight", kg, date.today())
        Notification("Logged %s kg." % Format.number(kg, 1), style="success").show()
        self._render()

    def _open_tracker(self, **event_args):
        Layout.navigate("tracker")

    def _open_checkin(self, **event_args):
        Layout.navigate("checkin")

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
