from datetime import date

from ._anvil_designer import ProfileFormTemplate
from anvil import *
import anvil.server


class ProfileForm(ProfileFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._build_fields()

    def _build_fields(self):
        self.form_panel.clear()
        self.sex = DropDown(items=["male", "female"], label="Sex")
        self.dob = DatePicker(label="Date of birth")
        self.height = TextBox(label="Height (cm)", type="number")
        self.weight = TextBox(label="Weight (kg)", type="number")
        self.waist = TextBox(label="Waist (cm)", type="number")
        self.neck = TextBox(label="Neck (cm)", type="number")
        self.hip = TextBox(label="Hip (cm, women)", type="number")
        self.training = TextBox(label="Training days / week", text="4", type="number")
        self.steps = TextBox(label="Daily steps", text="10000", type="number")
        self.start = DatePicker(label="Plan start")
        self.start.date = date.today()
        self.outcome = DropDown(
            items=[("Lose fat", "lose_fat"), ("Gain muscle", "gain_muscle"), ("Recomp", "recomp")],
            label="Goal",
        )
        self.outcome.selected_value = "lose_fat"
        self.chain = CheckBox(text="After cut, chain a bulk phase")
        for c in (
            self.sex,
            self.dob,
            self.height,
            self.weight,
            self.waist,
            self.neck,
            self.hip,
            self.training,
            self.steps,
            self.start,
            self.outcome,
            self.chain,
        ):
            self.form_panel.add_component(c, full_width_row=True)
        save = Button(text="Save & propose plan", role="primary-color")
        save.set_event_handler("click", self._save)
        self.form_panel.add_component(save, full_width_row=True)

    def _save(self, **event_args):
        hip_val = self.hip.text.strip()
        payload = {
            "sex": self.sex.selected_value,
            "date_of_birth": self.dob.date,
            "height_cm": self.height.text,
            "weight_kg": self.weight.text,
            "waist_cm": self.waist.text,
            "neck_cm": self.neck.text,
            "hip_cm": float(hip_val) if hip_val else None,
            "training_days": self.training.text,
            "daily_steps": self.steps.text,
            "start_date": self.start.date,
            "outcome": self.outcome.selected_value,
            "chain_gain": self.chain.checked,
        }
        try:
            state = anvil.server.call("bodycomp_save_plan", payload)
        except Exception as e:
            alert(f"Could not save plan: {e}")
            return
        msg = f"Week 1: {state['calories']} kcal — {state.get('reason', '')}"
        alert(msg, title="Plan saved")
        open_form("HomeForm")
