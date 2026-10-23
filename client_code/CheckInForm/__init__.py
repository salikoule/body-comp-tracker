from datetime import date

from ._anvil_designer import CheckInFormTemplate
from anvil import *
import anvil.server


class CheckInForm(CheckInFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._week = 1
        self._build()

    def _build(self):
        self.panel.clear()
        state = anvil.server.call("bodycomp_get_plan")
        if not state.get("has_plan"):
            open_form("ProfileForm")
            return
        self._week = state.get("current_week") or 1
        self.panel.add_component(Label(text=f"Week {self._week} check-in", font_size=16), full_width_row=True)
        self.waist = TextBox(label="Waist (cm)", type="number")
        self.neck = TextBox(label="Neck (cm)", type="number")
        self.adherence = DropDown(
            items=[("On target", "on"), ("Roughly", "roughly"), ("Off", "off")],
            label="Adherence",
        )
        self.feel = DropDown(
            items=[("Strong", "strong"), ("Normal", "normal"), ("Flat", "flat")],
            label="Training feel",
        )
        for c in (self.waist, self.neck, self.adherence, self.feel):
            self.panel.add_component(c, full_width_row=True)
        submit = Button(text="Submit check-in", role="primary-color")
        submit.set_event_handler("click", self._submit)
        self.panel.add_component(submit, full_width_row=True)

    def _submit(self, **event_args):
        payload = {
            "waist_cm": float(self.waist.text) if self.waist.text else None,
            "neck_cm": float(self.neck.text) if self.neck.text else None,
            "adherence": self.adherence.selected_value,
            "training_feel": self.feel.selected_value,
            "check_in_date": date.today(),
        }
        try:
            state = anvil.server.call("bodycomp_check_in", self._week, payload)
        except Exception as e:
            alert(str(e))
            return
        alert(state.get("reason", "Check-in saved."))
        open_form("HomeForm")
