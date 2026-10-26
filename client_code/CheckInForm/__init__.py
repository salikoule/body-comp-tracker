from datetime import date

from ._anvil_designer import CheckInFormTemplate
from anvil import *
import anvil.server
from body_comp_tracker import Format, Layout

FEEL = (("Strong", "strong"), ("Normal", "normal"), ("Flat", "flat"))
ADHERENCE = (("On target", "on_target"), ("Roughly", "roughly"), ("Off", "off"))


def _optional_number(box):
    raw = box.text
    text = "" if raw is None else str(raw).strip()
    if not text:
        return None
    return float(text)


def _text(value):
    return "" if value is None else str(value)


class CheckInForm(CheckInFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        state = anvil.server.call("bodycomp_get_plan")
        if not state.get("has_plan"):
            self.add_component(
                Layout.stack(
                    Layout.page_header("Sunday check-in"),
                    Layout.empty_state("Save your profile before checking in.", "Set up plan", self._open_profile),
                ),
                full_width_row=True,
            )
            return
        self._week = state.get("current_week") or 1
        row = Format.current_row(state)
        header = Layout.page_header(
            "Sunday check-in",
            eyebrow=Format.eyebrow(state),
            description="Tape measurements, training, and adherence decide next week's calories.",
            actions=(Layout.button("Weekly tracker", self._open_tracker),),
        )
        self.add_component(
            Layout.stack(
                header,
                Layout.grid("minmax(0, 1.8fr) minmax(260px, 1fr)", self._form_card(state, row), self._week_card(state, row)),
            ),
            full_width_row=True,
        )

    def _form_card(self, state, row):
        latest = state.get("latest_weight_kg")
        self.avg = TextBox(type="number", placeholder=_text(latest) or "Optional")
        self.waist = TextBox(type="number", text=_text(row.get("waist_cm") or state.get("waist_cm")))
        self.neck = TextBox(type="number", text=_text(row.get("neck_cm") or state.get("neck_cm")))
        self.sessions = TextBox(type="number", text=_text(row.get("training_sessions") or state.get("training_days")))
        self.steps = TextBox(type="number", text=_text(row.get("daily_steps") or state.get("daily_steps")))
        self.feel = DropDown(items=list(FEEL), selected_value=row.get("training_feel") or "normal")
        self.adherence = DropDown(items=list(ADHERENCE), selected_value=row.get("adherence") or "on_target")
        self.notes = TextArea(placeholder="Sleep, travel, stress…", text=_text(row.get("notes")), height=88)

        card = Layout.section("Week %s measurements" % self._week, "Waist and neck are required for the body-fat estimate.")
        grid = Layout.grid(
            "repeat(3, minmax(0, 1fr))",
            Layout.field("Weekly average weight (kg)", self.avg, hint="Leave blank to use morning logs."),
            Layout.field("Waist (cm)", self.waist),
            Layout.field("Neck (cm)", self.neck),
            Layout.field("Training sessions", self.sessions),
            Layout.field("Average daily steps", self.steps),
            Layout.field("Training feel", self.feel),
            Layout.field("Adherence", self.adherence),
        )
        Layout.body(
            card,
            grid,
            Layout.field("Notes", self.notes),
            Layout.button("Submit and issue next week", self._submit, primary=True),
        )
        return card

    def _week_card(self, state, row):
        card = Layout.section("This week", Format.phase(row.get("phase")))
        Layout.body(
            card,
            Layout.definition_list((
                ("Week", "%s – %s" % (Format.date_label(row.get("week_start")), Format.date_label(row.get("week_end")))),
                ("Issued calories", Format.number(row.get("target_calories"), 0, "kcal")),
                ("Target weight", Format.number(row.get("target_weight_kg"), 1, "kg")),
                ("Weekly average so far", Format.number(row.get("actual_weight_kg"), 1, "kg")),
            )),
            Layout.note(state.get("reason") or ""),
        )
        return card

    def _submit(self, **event_args):
        try:
            payload = {
                "avg_weight_kg": _optional_number(self.avg),
                "waist_cm": _optional_number(self.waist),
                "neck_cm": _optional_number(self.neck),
                "training_sessions": _optional_number(self.sessions),
                "daily_steps": _optional_number(self.steps),
                "adherence": self.adherence.selected_value or "on_target",
                "training_feel": self.feel.selected_value or "normal",
                "notes": self.notes.text or "",
                "check_in_date": date.today(),
            }
        except ValueError:
            Notification("Measurements must be numbers.", style="warning").show()
            return
        if payload["waist_cm"] is None or payload["neck_cm"] is None:
            Notification("Enter waist and neck.", style="warning").show()
            return
        try:
            state = anvil.server.call("bodycomp_check_in", self._week, payload)
        except Exception as e:
            alert(str(e), title="Check-in failed")
            return
        Notification(state.get("reason") or "Check-in saved. Next week's calories are issued.",
                     title="Check-in saved", style="success", timeout=6).show()
        Layout.navigate("dashboard")

    def _open_tracker(self, **event_args):
        Layout.navigate("tracker")

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
