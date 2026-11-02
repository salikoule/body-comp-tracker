"""Sunday check-in and week corrections, shown in a side drawer over the weekly tracker."""

from datetime import date

from anvil import *
from routing import router
import anvil.server
from craftify_library.CraftifyUtils import drawer
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


def week_for(state, requested):
    """The week to open: a started week number, else the current week."""
    current = int(state.get("current_week") or 1)
    try:
        week = int(requested)
    except (TypeError, ValueError):
        return current
    return week if 1 <= week <= current else current


class CheckInPanel:
    def __init__(self, state, week, on_saved=None):
        self._on_saved = on_saved
        current = int(state.get("current_week") or 1)
        self._week = int(week or current)
        row = Format.week_row(state, self._week)
        self._correcting = self._week < current or bool(
            row.get("check_in_date") or row.get("status") in ("logged", "excluded"))
        self.title = "Correct week %s" % self._week if self._correcting else "Sunday check-in · week %s" % self._week
        self.subtitle = (
            "Change this week's measurements. Calorie targets already issued for later weeks stay as they are."
            if self._correcting
            else "Tape measurements, training, and adherence decide next week's calories."
        )
        self.eyebrow = "%s – %s · %s" % (
            Format.date_label(row.get("week_start")), Format.date_label(row.get("week_end")), Format.phase(row.get("phase")))
        self.content = self._content(state, row)
        self.save = Layout.button("Save correction" if self._correcting else "Submit and issue next week",
                                  self._submit, primary=True)
        self.cancel = Layout.button("Cancel", self._cancel)
        self._initial = self._values()
        self.drawer = None

    def _content(self, state, row):
        latest = state.get("latest_weight_kg")
        self.avg = TextBox(type="number", placeholder=_text(latest, 1) or "Optional", text=_text(row.get("actual_weight_kg"), 1))
        self.waist = TextBox(type="number", text=_text(row.get("waist_cm") or state.get("waist_cm"), 1))
        self.neck = TextBox(type="number", text=_text(row.get("neck_cm") or state.get("neck_cm"), 1))
        self.sessions = TextBox(type="number", text=_text(row.get("training_sessions") or state.get("training_days"), 0))
        self.steps = TextBox(type="number", text=_text(row.get("daily_steps") or state.get("daily_steps"), 0))
        self.feel = DropDown(items=list(FEEL), selected_value=row.get("training_feel") or "normal")
        self.adherence = DropDown(items=list(ADHERENCE), selected_value=row.get("adherence") or "on_target")
        self.notes = TextArea(placeholder="Sleep, travel, stress…", text=_text(row.get("notes")), height=88)
        two = "repeat(2, minmax(0, 1fr))"
        return Layout.stack(
            Layout.html(self._summary_html(row)),
            Layout.field("Weekly average weight (kg)", self.avg, hint="Leave blank to use this week's morning logs."),
            Layout.grid(two, Layout.field("Waist (cm)", self.waist), Layout.field("Neck (cm)", self.neck)),
            Layout.grid(two, Layout.field("Training sessions", self.sessions), Layout.field("Average daily steps", self.steps)),
            Layout.grid(two, Layout.field("Training feel", self.feel), Layout.field("Adherence", self.adherence)),
            Layout.field("Notes", self.notes),
            Layout.note("Waist and neck are required for the body-fat estimate."),
        )

    def _summary_html(self, row):
        items = (
            ("Issued", Format.number(row.get("target_calories"), 0, "kcal")),
            ("Target", Format.number(row.get("target_weight_kg"), 1, "kg")),
            ("Average so far", Format.number(row.get("actual_weight_kg"), 1, "kg")),
        )
        return '<dl class="bc-ci-summary">%s</dl>' % "".join(
            "<div><dt>%s</dt><dd>%s</dd></div>" % (Layout.esc(label), Layout.esc(value)) for label, value in items)

    def _values(self):
        return tuple(str(box.text or "") for box in (self.avg, self.waist, self.neck, self.sessions, self.steps, self.notes)) + (
            self.feel.selected_value, self.adherence.selected_value)

    def is_dirty(self):
        return self._values() != self._initial

    def open(self, host, on_close=None):
        self.drawer = drawer.open(
            self.content,
            host=host,
            title=self.title,
            subtitle=self.subtitle,
            eyebrow=self.eyebrow,
            footer=(self.cancel, self.save),
            width=500,
            on_close=on_close,
            confirm_close=drawer.discard_check(self.is_dirty),
        )
        return self.drawer

    def _cancel(self, **event_args):
        if self.drawer is not None:
            self.drawer.close(force=False)

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
        self.save.enabled = False
        try:
            state = anvil.server.call("bodycomp_check_in", self._week, payload)
        except Exception as e:
            self.save.enabled = True
            alert(str(e), title="Check-in failed")
            return
        if self._correcting:
            message, title = "Week %s updated. Later issued calories were left as they were." % self._week, "Week saved"
        else:
            message, title = state.get("reason") or "Check-in saved. Next week's calories are issued.", "Check-in saved"
        Notification(message, title=title, style="success", timeout=6).show()
        if self.drawer is not None:
            self.drawer.close()
        if self._on_saved is not None:
            self._on_saved(state)
