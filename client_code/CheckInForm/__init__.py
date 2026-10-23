from datetime import date

from ._anvil_designer import CheckInFormTemplate
from anvil import *
import anvil.server


def _optional_number(box):
    raw = box.text
    text = "" if raw is None else str(raw).strip()
    if not text:
        return None
    return float(text)


class CheckInForm(CheckInFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._week = 1
        self._build()

    def _field(self, caption, component):
        box = ColumnPanel(role="coach-field", spacing="none")
        box.add_component(Label(text=caption, role="coach-label"))
        box.add_component(component)
        return box

    def _build(self):
        self.panel.clear()
        state = anvil.server.call("bodycomp_get_plan")
        if not state.get("has_plan"):
            self.panel.add_component(Label(text="Save a profile before checking in.", role="coach-note"))
            return
        self._week = state.get("current_week") or 1
        row = None
        for item in state.get("schedule") or []:
            if item.get("week") == self._week:
                row = item
                break
        self.title.text = "Week %s check-in" % self._week
        if row:
            self.panel.add_component(Label(
                text="Week of %s (Mon–Sun). Check-in Sunday %s. Issued %s kcal." % (
                    row.get("week_start") or "—",
                    row.get("week_end") or "—",
                    row.get("target_calories") or "—",
                ),
                role="coach-note",
            ))
        self.avg = TextBox(type="number", placeholder="Optional")
        self.waist = TextBox(type="number", text="" if not (row or {}).get("waist_cm") else str((row or {}).get("waist_cm")))
        if not self.waist.text and state.get("waist_cm"):
            self.waist.text = str(state.get("waist_cm"))
        self.neck = TextBox(type="number", text="" if not (row or {}).get("neck_cm") else str((row or {}).get("neck_cm")))
        if not self.neck.text and state.get("neck_cm"):
            self.neck.text = str(state.get("neck_cm"))
        self.sessions = TextBox(type="number", text=str(state.get("training_days") or ""))
        self.steps = TextBox(type="number", text=str(state.get("daily_steps") or ""))
        self.feel = DropDown(items=["Strong", "Normal", "Flat"])
        self.feel.selected_value = "Normal"
        self.adherence = DropDown(items=["On target", "Roughly", "Off"])
        self.adherence.selected_value = "On target"
        self.notes = TextArea(placeholder="Sleep, travel, stress…")
        self._feel_map = {"Strong": "strong", "Normal": "normal", "Flat": "flat"}
        self._adherence_map = {"On target": "on_target", "Roughly": "roughly", "Off": "off"}
        grid = FlowPanel(role="coach-grid")
        for caption, component in (
            ("Weekly avg weight (kg)", self.avg),
            ("Waist (cm)", self.waist),
            ("Neck (cm)", self.neck),
            ("Training sessions", self.sessions),
            ("Avg daily steps", self.steps),
            ("Training feel", self.feel),
            ("Adherence", self.adherence),
        ):
            grid.add_component(self._field(caption, component), width=220)
        self.panel.add_component(Spacer(height=8))
        self.panel.add_component(grid, full_width_row=True)
        self.panel.add_component(self._field("Notes", self.notes), full_width_row=True)
        submit = Button(text="Submit and issue next week", role="primary-color")
        submit.set_event_handler("click", self._submit)
        actions = FlowPanel(role="coach-actions")
        actions.add_component(submit)
        self.panel.add_component(Spacer(height=12))
        self.panel.add_component(actions, full_width_row=True)

    def _submit(self, **event_args):
        payload = {
            "avg_weight_kg": _optional_number(self.avg),
            "waist_cm": _optional_number(self.waist),
            "neck_cm": _optional_number(self.neck),
            "training_sessions": _optional_number(self.sessions),
            "daily_steps": _optional_number(self.steps),
            "adherence": self._adherence_map.get(self.adherence.selected_value, "on_target"),
            "training_feel": self._feel_map.get(self.feel.selected_value, "normal"),
            "notes": self.notes.text or "",
            "check_in_date": date.today(),
        }
        try:
            state = anvil.server.call("bodycomp_check_in", self._week, payload)
        except Exception as e:
            alert(str(e))
            return
        alert(state.get("reason") or "Check-in saved. Next week's calories are issued.", title="Check-in saved")
        open_form("CoachShell", page="dashboard")
