from datetime import date

from ._anvil_designer import HomeFormTemplate
from anvil import *
import anvil.server
from craftify_library.CustomComponents.ChartCard import ChartCard
from craftify_library.CustomComponents.EChart import EChart
from craftify_library.CustomComponents.KpiCard import KpiCard


class HomeForm(HomeFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._state = None
        self.form_show()

    def form_show(self, **event_args):
        self._state = anvil.server.call("bodycomp_get_plan")
        if not self._state.get("has_plan"):
            open_form("CoachShell", page="profile")
            return
        self._render()

    def _render(self):
        self.content.clear()
        s = self._state
        phase = (s.get("phase") or "—").upper()
        kpi_row = FlowPanel(role="coach-grid")
        kpi_row.add_component(
            KpiCard(title="Phase", value=phase, subtitle=s.get("outcome", ""), tone="good"),
            width=220,
        )
        kpi_row.add_component(
            KpiCard(title="Calories", value=str(s.get("calories", "—")), subtitle="This week", tone="good"),
            width=220,
        )
        kpi_row.add_component(
            KpiCard(
                title="Protein",
                value=f"{s.get('protein_g', '—')} g",
                subtitle=f"Fat {s.get('fat_g')} g · Carbs {s.get('carbs_g')} g",
                tone="good",
            ),
            width=260,
        )
        self.content.add_component(kpi_row, full_width_row=True)
        self.content.add_component(Spacer(height=12))
        card = ColumnPanel(role="coach-card", spacing="none")
        card.add_component(Label(text="Today", role="coach-section"), full_width_row=True)
        if s.get("reason"):
            card.add_component(Label(text=s.get("reason"), role="coach-note"), full_width_row=True)
            card.add_component(Spacer(height=8))
        row = FlowPanel(role="coach-actions")
        box = ColumnPanel(role="coach-field", spacing="none")
        box.add_component(Label(text="Weight (kg)", role="coach-label"))
        self._weight_input = TextBox(type="number", placeholder="82.4")
        box.add_component(self._weight_input)
        row.add_component(box, width=180)
        log_btn = Button(text="Log weight", role="primary-color")
        log_btn.set_event_handler("click", self._log_weight)
        row.add_component(log_btn)
        card.add_component(row, full_width_row=True)
        self.content.add_component(card, full_width_row=True)
        phases = ColumnPanel(role="coach-card", spacing="none")
        phases.add_component(Label(text="Phases", role="coach-section"))
        for phase in s.get("phases") or []:
            phases.add_component(Label(
                text="%s · %s → %s · %s kcal" % (
                    phase.get("name") or "",
                    phase.get("start") or "—",
                    phase.get("end") or "open",
                    phase.get("calories") or "—",
                ),
                role="coach-note",
            ))
        self.content.add_component(Spacer(height=12))
        self.content.add_component(phases, full_width_row=True)
        schedule = (s.get("schedule") or [])[:24]
        if schedule:
            weeks = ["W%s" % row.get("week") for row in schedule]
            card = ChartCard(title="Weight trajectory", subtitle="First 24 weeks")
            card.mount(EChart(options={
                "tooltip": {"trigger": "axis"},
                "legend": {"top": 0},
                "grid": {"left": 48, "right": 16, "top": 36, "bottom": 28},
                "xAxis": {"type": "category", "data": weeks},
                "yAxis": {"type": "value", "scale": True},
                "series": [
                    {"name": "Target", "type": "line", "smooth": True, "showSymbol": False, "data": [row.get("target_weight_kg") for row in schedule]},
                    {"name": "Actual", "type": "line", "smooth": True, "connectNulls": False, "showSymbol": False, "data": [row.get("actual_weight_kg") for row in schedule]},
                ],
            }, height="280px"))
            self.content.add_component(Spacer(height=12))
            self.content.add_component(card, full_width_row=True)

    def _log_weight(self, **event_args):
        try:
            kg = float(self._weight_input.text)
        except (TypeError, ValueError):
            alert("Enter a valid weight in kg.")
            return
        self._state = anvil.server.call("bodycomp_log_weight", kg, date.today())
        alert("Weight logged.")
        self._render()
