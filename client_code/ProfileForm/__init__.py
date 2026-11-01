from datetime import date

from ._anvil_designer import ProfileFormTemplate
from anvil import *
from routing import router
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
from craftify_library.CustomComponents.FileDrop import FileDrop
from body_comp_tracker import Format, Layout

SEX = (("Male", "male"), ("Female", "female"))
OUTCOME = (("Lose fat", "lose_fat"), ("Gain muscle", "gain_muscle"), ("Recomp", "recomp"))
DEXA_COLUMNS = (
    ("Scan date", "measured_on", 0, ""),
    ("Week", "week_index", 0, ""),
    ("Body fat", "bf_percent", 1, "%"),
    ("Fat mass", "fat_mass_kg", 1, "kg"),
    ("Lean mass", "lean_mass_kg", 1, "kg"),
    ("Bone", "bmc_kg", 2, "kg"),
    ("Fat-free mass", "ffm_kg", 1, "kg"),
    ("Visceral fat", "vat_g", 0, "g"),
    ("RMR", "rmr_kcal", 0, "kcal"),
    ("File", "filename", 0, ""),
)
DEXA_LABELS = {
    "dexa_measured_on": "scan date",
    "dexa_bf_percent": "body fat",
    "dexa_ffm_kg": "fat-free mass",
    "dexa_rmr_kcal": "RMR",
}


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
    def __init__(self, routing_context=None, **properties):
        self._compact = bool(properties.pop("compact", False))
        self.init_components(**properties)
        state = anvil.server.call("bodycomp_get_plan")
        self._has_plan = bool(state.get("has_plan"))
        self._build(state if self._has_plan else {})

    def _build(self, s):
        self.clear()
        self._state = s
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
        self.dexa_on = DatePicker(format="%d %b %Y", placeholder="Scan date",
                                  min_date=date(2018, 1, 1), max_date=date.today(),
                                  date=_as_date(s.get("dexa_measured_on")))
        self.dexa_bf = TextBox(type="number", placeholder="e.g. 28.8", text=_text(s.get("dexa_bf_percent")))
        self.dexa_ffm = TextBox(type="number", placeholder="e.g. 57.7", text=_text(s.get("dexa_ffm_kg")))
        self.dexa_rmr = TextBox(type="number", placeholder="e.g. 1550", text=_text(s.get("dexa_rmr_kcal")))
        self.dexa_file = FileDrop(
            title="Drop a DEXA scan here",
            hint="or click to browse · PDF or photo · read automatically with your AI key",
            file_types="application/pdf,image/png,image/jpeg",
        )
        self.dexa_file.set_event_handler("change", self._read_dexa)
        self._dexa_extra = {}
        self.dexa_status = Layout.html('<p class="bc-dexa-status" anvil-name="text"></p>')
        self.dexa_store = Layout.button("Store scan and recalibrate", self._store_dexa, primary=True)
        for box in (self.dexa_bf, self.dexa_ffm, self.dexa_rmr):
            box.set_event_handler("change", self._sync_dexa_store)
            box.set_event_handler("lost_focus", self._sync_dexa_store)
        self.dexa_on.set_event_handler("change", self._sync_dexa_store)
        self._sync_dexa_store()

        header = Layout.page_header(
            "Profile & plan" if self._has_plan else "Set up your plan",
            eyebrow="" if self._compact else (Format.eyebrow(s) if self._has_plan else "Profile"),
            description=(
                "Saving updates the plan from these measurements. Check-ins, daily weights, and issued calories stay."
                if self._has_plan
                else "Enter your measurements once. Add a DEXA scan if you have one."
            ),
        )

        about = Layout.section("About you", "Used for BMR unless you enter a measured DEXA RMR.")
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

        dexa = Layout.section(
            "DEXA baseline",
            "DEXA is plan truth for body fat, fat-free mass, and optional RMR. Weekly tape stays for check-ins and is shifted to the DEXA scale.",
        )
        Layout.body(
            dexa,
            Layout.grid(
                "repeat(4, minmax(0, 1fr))",
                Layout.field("Scan date", self.dexa_on),
                Layout.field("Body fat %", self.dexa_bf),
                Layout.field("Fat-free mass (kg)", self.dexa_ffm),
                Layout.field("Measured RMR (kcal)", self.dexa_rmr),
            ),
            Layout.field("Scan file", self.dexa_file),
            self.dexa_status,
            Layout.grid("max-content", self.dexa_store),
        )
        records = Layout.section("DEXA records", "Every stored scan. The latest one anchors the plan.", padded=False)
        Layout.body(records, Layout.html(self._dexa_table(s)))

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

        parts = [header, about, tape, dexa, records, goal]
        if self._has_plan:
            parts.append(self._history_card(s))
        self.add_component(Layout.stack(*parts), full_width_row=True)

    def _dexa_table(self, s):
        scans = s.get("dexa_scans") or []
        if not scans:
            return '<p class="bc-dexa-empty">No scans stored yet. Drop a report above.</p>'
        head = "".join("<th>%s</th>" % label for label, _key, _digits, _unit in DEXA_COLUMNS)
        body = []
        for scan in reversed(scans):
            cells = []
            for _label, key, digits, unit in DEXA_COLUMNS:
                if key == "measured_on":
                    text = Format.date_label(scan.get(key))
                elif key == "week_index":
                    text = "W%s" % scan.get(key) if scan.get(key) else ""
                elif key == "filename":
                    text = Layout.esc(scan.get(key) or "")
                elif scan.get(key) is None:
                    text = ""
                elif unit == "%":
                    text = Format.percent(scan.get(key), digits)
                else:
                    text = Format.number(scan.get(key), digits, unit)
                cells.append("<td>%s</td>" % (text or '<span class="bc-empty">—</span>'))
            body.append("<tr>%s</tr>" % "".join(cells))
        return '<div class="bc-dexa-table"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (
            head, "".join(body))

    def _history_card(self, s):
        card = Layout.section(
            "Calibrate history",
            "Delete a mistaken log, or re-issue next week's calories from a logged week. This is the only way history is removed.",
        )
        logged = [row for row in (s.get("schedule") or []) if row.get("status") in ("logged", "excluded")]
        weights = s.get("weights") or []
        if logged:
            for row in logged:
                week = row.get("week")
                Layout.body(
                    card,
                    Layout.grid(
                        "minmax(0, 1fr) max-content max-content",
                        Layout.note("Week %s · %s · waist %s · %s kg" % (
                            week,
                            Format.date_label(row.get("week_start")),
                            Format.number(row.get("waist_cm"), 1),
                            Format.number(row.get("actual_weight_kg"), 1),
                        )),
                        Layout.button("Delete week %s" % week, lambda ea, w=week: self._delete_week(w)),
                        Layout.button("Re-issue week %s+1" % week, lambda ea, w=week: self._reissue(w)),
                    ),
                )
        else:
            Layout.body(card, Layout.note("No Sunday check-ins stored."))
        if weights:
            for item in weights[-12:]:
                day = item.get("date")
                Layout.body(
                    card,
                    Layout.grid(
                        "minmax(0, 1fr) max-content",
                        Layout.note("%s · %s" % (Format.date_label(day), Format.number(item.get("kg"), 1, "kg"))),
                        Layout.button("Delete weight", lambda ea, d=day: self._delete_weight(d)),
                    ),
                )
        else:
            Layout.body(card, Layout.note("No daily weights stored."))
        return card

    def _number(self, box, required=True):
        raw = box.text
        text = "" if raw is None else str(raw).strip()
        if not text:
            if required:
                raise ValueError("Fill in every measurement except hip and DEXA.")
            return None
        return float(text)

    def _payload(self):
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
            "dexa_measured_on": self.dexa_on.date,
            "dexa_bf_percent": self._number(self.dexa_bf, required=False),
            "dexa_ffm_kg": self._number(self.dexa_ffm, required=False),
            "dexa_rmr_kcal": self._number(self.dexa_rmr, required=False),
        }
        if payload["date_of_birth"] is None or payload["start_date"] is None:
            raise ValueError("Choose a date of birth and a plan start.")
        return payload

    def _apply_extract(self, values):
        self.dexa_on.date = _as_date(values.get("dexa_measured_on"))
        self.dexa_bf.text = _text(values.get("dexa_bf_percent"))
        self.dexa_ffm.text = _text(values.get("dexa_ffm_kg"))
        self.dexa_rmr.text = _text(values.get("dexa_rmr_kcal"))

    def _dexa_values(self):
        values = dict(self._dexa_extra)
        values["dexa_measured_on"] = self.dexa_on.date
        for key, box in (("dexa_bf_percent", self.dexa_bf), ("dexa_ffm_kg", self.dexa_ffm), ("dexa_rmr_kcal", self.dexa_rmr)):
            try:
                values[key] = self._number(box, required=False)
            except ValueError:
                values[key] = None
        return values

    def _missing_dexa(self):
        values = self._dexa_values()
        return [label for key, label in DEXA_LABELS.items() if values.get(key) is None]

    def _set_dexa_status(self, text, tone="muted"):
        node = self.dexa_status.dom_nodes["text"]
        node.textContent = text or ""
        node.className = "bc-dexa-status is-%s" % tone

    def _sync_dexa_store(self, **event_args):
        ready = self.dexa_file.file is not None and not self._missing_dexa()
        self.dexa_store.enabled = ready

    def _save(self, **event_args):
        try:
            payload = self._payload()
        except ValueError as e:
            Notification(str(e), style="warning").show()
            return
        try:
            state = anvil.server.call("bodycomp_save_plan", payload)
        except Exception as e:
            alert(str(e), title="Could not save plan")
            return
        Notification(state.get("reason") or "Plan saved. History was kept.",
                     title="Plan saved", style="success", timeout=6).show()
        Layout.close_settings()
        Layout.navigate("dashboard")

    def _read_dexa(self, **event_args):
        media = self.dexa_file.file
        self._dexa_extra = {}
        if media is None:
            self._set_dexa_status("")
            self._sync_dexa_store()
            return
        self.dexa_store.enabled = False
        self._set_dexa_status("Reading %s…" % (getattr(media, "name", None) or "the scan"))
        try:
            result = anvil.server.call("bodycomp_read_dexa", media)
        except Exception as e:
            self._set_dexa_status(str(e), "bad")
            self._sync_dexa_store()
            return
        values = result.get("values") or {}
        self._dexa_extra = dict((key, values.get(key)) for key in values if not key.startswith("dexa_"))
        self._apply_extract(values)
        missing = self._missing_dexa()
        if result.get("error"):
            self._set_dexa_status(result["error"], "bad")
        elif missing:
            self._set_dexa_status("Read the scan, but could not find the %s. Type %s from the report to continue."
                                  % (", ".join(missing), "it" if len(missing) == 1 else "them"), "warn")
        else:
            self._set_dexa_status("Read every metric from the scan. Check them, then store.", "ok")
        self._sync_dexa_store()

    def _store_dexa(self, **event_args):
        media = self.dexa_file.file
        missing = self._missing_dexa()
        if media is None or missing:
            self._set_dexa_status("Add the %s first." % ", ".join(missing or ["scan file"]), "warn")
            return
        try:
            state = anvil.server.call("bodycomp_store_dexa", media, self._dexa_values())
        except Exception as e:
            alert(str(e), title="Could not store scan")
            return
        Notification("Scan stored. The plan was recalibrated from it. Issued weekly calories were left as issued.",
                     title="DEXA saved", style="success", timeout=6).show()
        self._has_plan = bool(state.get("has_plan"))
        self._build(state if self._has_plan else {})

    def _delete_week(self, week):
        if not confirm("Delete week %s check-in? Issued calories stay unless you re-issue." % week):
            return
        try:
            state = anvil.server.call("bodycomp_delete_week_log", week)
        except Exception as e:
            alert(str(e), title="Could not delete week")
            return
        Notification("Week %s check-in removed." % week, style="success").show()
        self._build(state)

    def _delete_weight(self, day):
        if not confirm("Delete the weight logged on %s?" % Format.date_label(day)):
            return
        try:
            state = anvil.server.call("bodycomp_delete_weight", day)
        except Exception as e:
            alert(str(e), title="Could not delete weight")
            return
        Notification("Weight removed.", style="success").show()
        self._build(state)

    def _reissue(self, week):
        if not confirm("Overwrite week %s calories from week %s's trend?" % (week + 1, week)):
            return
        try:
            state = anvil.server.call("bodycomp_reissue_next_week", week)
        except Exception as e:
            alert(str(e), title="Could not re-issue")
            return
        Notification("Week %s calories were re-issued." % (week + 1), style="success").show()
        self._build(state)
