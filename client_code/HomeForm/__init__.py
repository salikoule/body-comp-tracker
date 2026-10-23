from datetime import date

from ._anvil_designer import HomeFormTemplate
from anvil import *
import anvil.server
from craftify_library.CustomComponents.KpiCard import KpiCard


class HomeForm(HomeFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._state = None
        self.form_show()

    def form_show(self, **event_args):
        self._state = anvil.server.call("bodycomp_get_plan")
        if not self._state.get("has_plan"):
            open_form("ProfileForm")
            return
        self._render()

    def _render(self):
        self.content.clear()
        s = self._state
        phase = s.get("phase", "—").upper()
        kpi_row = FlowPanel(align="left", spacing=12)
        kpi_row.add_component(
            KpiCard(title="Phase", value=phase, subtitle=s.get("outcome", ""), tone="good"),
            width=200,
        )
        kpi_row.add_component(
            KpiCard(title="Calories", value=str(s.get("calories", "—")), subtitle="This week", tone="good"),
            width=200,
        )
        kpi_row.add_component(
            KpiCard(
                title="Protein",
                value=f"{s.get('protein_g', '—')} g",
                subtitle=f"Fat {s.get('fat_g')} g · Carbs {s.get('carbs_g')} g",
                tone="good",
            ),
            width=280,
        )
        self.content.add_component(kpi_row, full_width_row=True)
        self.content.add_component(Label(text=s.get("reason", ""), font_size=13), full_width_row=True)
        weight_row = FlowPanel(align="left", spacing=8)
        self._weight_input = TextBox(label="Today's weight (kg)", type="number")
        weight_row.add_component(self._weight_input)
        log_btn = Button(text="Log weight", role="primary-color")
        log_btn.set_event_handler("click", self._log_weight)
        weight_row.add_component(log_btn)
        self.content.add_component(weight_row, full_width_row=True)
        nav = FlowPanel(align="left", spacing=8)
        for label, form_name in (("Edit profile", "ProfileForm"), ("Sunday check-in", "CheckInForm")):
            b = Button(text=label, role="secondary-color")
            b.set_event_handler("click", lambda **e, f=form_name: open_form(f))
            nav.add_component(b)
        self.content.add_component(nav, full_width_row=True)

    def _log_weight(self, **event_args):
        try:
            kg = float(self._weight_input.text)
        except (TypeError, ValueError):
            alert("Enter a valid weight in kg.")
            return
        self._state = anvil.server.call("bodycomp_log_weight", kg, date.today())
        alert("Weight logged.")
        self._render()
