from datetime import date

from ._anvil_designer import CheckInFormTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
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


def _text(value, digits=None):
    if value is None:
        return ""
    if digits is None:
        return str(value)
    try:
        return ("%." + str(digits) + "f") % float(value)
    except (TypeError, ValueError):
        return str(value)


class CheckInForm(CheckInFormTemplate):
    def __init__(self, week=None, **properties):
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
        current = state.get("current_week") or 1
        self._week = int(week or current)
        row = Format.week_row(state, self._week)
        self._correcting = self._week < current or bool(row.get("check_in_date") or row.get("status") in ("logged", "excluded"))
        title = "Correct week %s" % self._week if self._correcting else "Sunday check-in"
        description = (
            "Change this week's measurements. Issued calorie targets already on later weeks stay as issued."
            if self._correcting
            else "Tape measurements, training, and adherence decide next week's calories."
        )
        header = Layout.page_header(
            title,
            eyebrow=Format.eyebrow(state),
            description=description,
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
        self.avg = TextBox(type="number", placeholder=_text(latest, 1) or "Optional", text=_text(row.get("actual_weight_kg"), 1))
        self.waist = TextBox(type="number", text=_text(row.get("waist_cm") or state.get("waist_cm"), 1))
        self.neck = TextBox(type="number", text=_text(row.get("neck_cm") or state.get("neck_cm"), 1))
        self.sessions = TextBox(type="number", text=_text(row.get("training_sessions") or state.get("training_days"), 0))
        self.steps = TextBox(type="number", text=_text(row.get("daily_steps") or state.get("daily_steps"), 0))
        self.feel = DropDown(items=list(FEEL), selected_value=row.get("training_feel") or "normal")
        self.adherence = DropDown(items=list(ADHERENCE), selected_value=row.get("adherence") or "on_target")
        self.notes = TextArea(placeholder="Sleep, travel, stress…", text=_text(row.get("notes")), height=88)
        save_label = "Save correction" if self._correcting else "Submit and issue next week"

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
            Layout.button(save_label, self._submit, primary=True),
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
        if self._correcting:
            Notification("Week %s updated. Later issued calories were left as they were." % self._week,
                         title="Week saved", style="success", timeout=6).show()
            Layout.navigate("tracker")
            return
        Notification(state.get("reason") or "Check-in saved. Next week's calories are issued.",
                     title="Check-in saved", style="success", timeout=6).show()
        Layout.navigate("dashboard")

    def _open_tracker(self, **event_args):
        Layout.navigate("tracker")

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
