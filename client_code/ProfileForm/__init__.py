from datetime import date

from ._anvil_designer import ProfileFormTemplate
from anvil import *
import anvil.server
from body_comp_tracker import Format, Layout

SEX = (("Male", "male"), ("Female", "female"))
OUTCOME = (("Lose fat", "lose_fat"), ("Gain muscle", "gain_muscle"), ("Recomp", "recomp"))


def _text(value):
    return "" if value is None else ("%g" % value if isinstance(value, float) else str(value))


def _as_date(value, fallback=None):
    if isinstance(value, date):
        return value
    if value:
        try:
            parts = [int(p) for p in str(value)[:10].split("-")]
            return date(parts[0], parts[1], parts[2])
        except (ValueError, IndexError):
            pass
    return fallback


class ProfileForm(ProfileFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        state = anvil.server.call("bodycomp_get_plan")
        self._has_plan = bool(state.get("has_plan"))
        self._build(state if self._has_plan else {})

    def _build(self, s):
        self.sex = DropDown(items=list(SEX), selected_value=s.get("sex") or "male")
        self.dob = DatePicker(format="%d %b %Y", placeholder="Choose a date",
                              min_date=date(1940, 1, 1), max_date=date.today(),
                              date=_as_date(s.get("date_of_birth")))
        self.height = TextBox(type="number", placeholder="178", text=_text(s.get("height_cm")))
        self.weight = TextBox(type="number", placeholder="82", text=_text(s.get("start_weight_kg")))
        self.waist = TextBox(type="number", placeholder="86", text=_text(s.get("waist_cm")))
        self.neck = TextBox(type="number", placeholder="38", text=_text(s.get("neck_cm")))
        self.hip = TextBox(type="number", placeholder="Optional", text=_text(s.get("hip_cm")))
        self.training = TextBox(type="number", text=_text(s.get("training_days") or 4))
        self.steps = TextBox(type="number", text=_text(s.get("daily_steps") or 10000))
        self.start = DatePicker(format="%d %b %Y", min_date=date(2020, 1, 1), max_date=date(2035, 12, 31),
                                date=_as_date(s.get("start_date"), date.today()))
        self.outcome = DropDown(items=list(OUTCOME), selected_value=s.get("outcome") or "lose_fat")
        self.chain = CheckBox(text="After the cut, chain a reverse diet and a bulk", checked=bool(s.get("chain_gain")))

        header = Layout.page_header(
            "Profile & plan" if self._has_plan else "Set up your plan",
            eyebrow=Format.eyebrow(s) if self._has_plan else "Profile",
            description=(
                "Saving recalculates the plan from these measurements and clears past check-ins."
                if self._has_plan
                else "Enter your measurements once. The coach proposes calories, macros, and phases."
            ),
        )

        about = Layout.section("About you", "Used for BMR and the navy body-fat estimate.")
        Layout.body(about, Layout.grid(
            "repeat(3, minmax(0, 1fr))",
            Layout.field("Sex", self.sex),
            Layout.field("Date of birth", self.dob),
            Layout.field("Height (cm)", self.height),
        ))

        tape = Layout.section("Measurements", "Morning, before food. Tape at the navel and below the larynx.")
        Layout.body(tape, Layout.grid(
            "repeat(4, minmax(0, 1fr))",
            Layout.field("Weight (kg)", self.weight),
            Layout.field("Waist (cm)", self.waist),
            Layout.field("Neck (cm)", self.neck),
            Layout.field("Hip (cm)", self.hip, hint="Only used for the female formula."),
        ))

        goal = Layout.section("Training and goal")
        Layout.body(
            goal,
            Layout.grid(
                "repeat(4, minmax(0, 1fr))",
                Layout.field("Training days per week", self.training),
                Layout.field("Average daily steps", self.steps),
                Layout.field("Plan start", self.start),
                Layout.field("Goal", self.outcome),
            ),
            self.chain,
            Layout.button("Save plan", self._save, primary=True),
        )
        self.add_component(Layout.stack(header, about, tape, goal), full_width_row=True)

    def _number(self, box, required=True):
        raw = box.text
        text = "" if raw is None else str(raw).strip()
        if not text:
            if required:
                raise ValueError("Fill in every measurement except hip.")
            return None
        return float(text)

    def _save(self, **event_args):
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
                "outcome": self.outcome.selected_value or "lose_fat",
                "chain_gain": self.chain.checked,
            }
            if payload["date_of_birth"] is None or payload["start_date"] is None:
                raise ValueError("Choose a date of birth and a plan start.")
        except ValueError as e:
            Notification(str(e), style="warning").show()
            return
        if self._has_plan and not confirm("Saving rebuilds the plan and clears past check-ins. Continue?"):
            return
        try:
            state = anvil.server.call("bodycomp_save_plan", payload)
        except Exception as e:
            alert(str(e), title="Could not save plan")
            return
        Notification("Week 1: %s kcal. %s" % (Format.number(state.get("calories")), state.get("reason") or ""),
                     title="Plan saved", style="success", timeout=6).show()
        Layout.navigate("dashboard")
