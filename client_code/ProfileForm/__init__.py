from datetime import date

from ._anvil_designer import ProfileFormTemplate
from anvil import *
import anvil.server


class ProfileForm(ProfileFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._build_fields()

    def _field(self, caption, component):
        box = ColumnPanel(role="coach-field", spacing="none")
        box.add_component(Label(text=caption, role="coach-label"))
        box.add_component(component)
        return box

    def _build_fields(self):
        self.form_panel.clear()
        self.sex = DropDown(items=["male", "female"])
        self.dob = DatePicker(
            format="%d %b %Y",
            placeholder="Date of birth",
            min_date=date(1940, 1, 1),
            max_date=date.today(),
        )
        self.height = TextBox(type="number", placeholder="178")
        self.weight = TextBox(type="number", placeholder="82")
        self.waist = TextBox(type="number", placeholder="86")
        self.neck = TextBox(type="number", placeholder="38")
        self.hip = TextBox(type="number", placeholder="optional")
        self.training = TextBox(text="4", type="number")
        self.steps = TextBox(text="10000", type="number")
        self.start = DatePicker(
            format="%d %b %Y",
            placeholder="Plan start",
            min_date=date(2020, 1, 1),
            max_date=date(2035, 12, 31),
        )
        self.start.date = date.today()
        self.outcome = DropDown(items=["Lose fat", "Gain muscle", "Recomp"])
        self.outcome.selected_value = "Lose fat"
        self._outcome_map = {
            "Lose fat": "lose_fat",
            "Gain muscle": "gain_muscle",
            "Recomp": "recomp",
        }
        self.chain = CheckBox(text="After the cut, chain a bulk phase")

        body = FlowPanel(role="coach-grid")
        for caption, component in (
            ("Sex", self.sex),
            ("Date of birth", self.dob),
            ("Height (cm)", self.height),
            ("Weight (kg)", self.weight),
            ("Waist (cm)", self.waist),
            ("Neck (cm)", self.neck),
            ("Hip (cm)", self.hip),
            ("Training days", self.training),
            ("Daily steps", self.steps),
            ("Plan start", self.start),
            ("Goal", self.outcome),
        ):
            body.add_component(self._field(caption, component), width=220)
        self.form_panel.add_component(Label(text="Body", role="coach-section"), full_width_row=True)
        self.form_panel.add_component(body, full_width_row=True)
        self.form_panel.add_component(Spacer(height=8))
        self.form_panel.add_component(self.chain, full_width_row=True)
        save = Button(text="Save plan", role="primary-color")
        save.set_event_handler("click", self._save)
        actions = FlowPanel(role="coach-actions")
        actions.add_component(save)
        self.form_panel.add_component(Spacer(height=12))
        self.form_panel.add_component(actions, full_width_row=True)

    def _number(self, box, required=True):
        raw = box.text
        text = "" if raw is None else str(raw).strip()
        if not text or text.lower() == "optional":
            if required:
                raise ValueError("Fill in every measurement except hip.")
            return None
        return float(text)

    def _save(self, **event_args):
        outcome_label = self.outcome.selected_value or "Lose fat"
        try:
            payload = {
                "sex": self.sex.selected_value,
                "date_of_birth": self.dob.date,
                "height_cm": self._number(self.height),
                "weight_kg": self._number(self.weight),
                "waist_cm": self._number(self.waist),
                "neck_cm": self._number(self.neck),
                "hip_cm": self._number(self.hip, required=False),
                "training_days": int(self._number(self.training)),
                "daily_steps": int(self._number(self.steps)),
                "start_date": self.start.date,
                "outcome": self._outcome_map.get(outcome_label, "lose_fat"),
                "chain_gain": self.chain.checked,
            }
            if payload["date_of_birth"] is None or payload["start_date"] is None:
                raise ValueError("Choose a date of birth and a plan start.")
            state = anvil.server.call("bodycomp_save_plan", payload)
        except Exception as e:
            alert(f"Could not save plan: {e}")
            return
        msg = f"Week 1: {state['calories']} kcal — {state.get('reason', '')}"
        alert(msg, title="Plan saved")
        open_form("CoachShell", page="dashboard")
