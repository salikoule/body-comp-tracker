from datetime import date

from ._anvil_designer import DexaFormTemplate
from anvil import *
from routing import router
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.js
import anvil.media
import anvil.server
from craftify_library.CraftifyUtils import dialogs
from craftify_library.CustomComponents.FileDrop import FileDrop
from body_comp_tracker import Format, Layout, ScanImages
from body_comp_tracker import DexaRatings as Ratings

HISTORY_COLUMNS = (
    ("Scan date", "measured_on", 0, ""),
    ("Week", "week_index", 0, ""),
    ("Body fat", "bf_percent", 1, "%"),
    ("Fat mass", "fat_mass_kg", 1, "kg"),
    ("Lean mass", "lean_mass_kg", 1, "kg"),
    ("Bone", "bmc_kg", 2, "kg"),
    ("Fat-free mass", "ffm_kg", 1, "kg"),
    ("Lean index", "ffmi", 1, ""),
    ("Visceral fat", "vat_g", 0, "g"),
    ("RMR", "rmr_kcal", 0, "kcal"),
    ("Uploaded", "created_at", 0, ""),
)
REQUIRED_LABELS = {
    "dexa_measured_on": "scan date",
    "dexa_bf_percent": "body fat",
    "dexa_ffm_kg": "fat-free mass",
    "dexa_rmr_kcal": "RMR",
}
COMPOSITION = (
    ("Total mass", "total_mass_kg", 1, "kg"),
    ("Fat mass", "fat_mass_kg", 1, "kg"),
    ("Lean mass", "lean_mass_kg", 1, "kg"),
    ("Fat-free mass", "ffm_kg", 1, "kg"),
)


def _text(value):
    return "" if value is None else ("%g" % value if isinstance(value, float) else str(value))


def _uploaded(value):
    if not value:
        return ""
    text = str(value)
    if len(text) < 16:
        return Format.date_label(text)
    zoned = "+" in text[10:] or text.endswith("Z") or "-" in text[10:]
    stamp = anvil.js.new(anvil.js.window.Date, text if zoned else text + "Z")
    if not stamp.getTime() == stamp.getTime():
        return "%s %s" % (Format.date_label(text[:10]), text[11:16])
    day = "%04d-%02d-%02d" % (stamp.getFullYear(), stamp.getMonth() + 1, stamp.getDate())
    return "%s %02d:%02d" % (Format.date_label(day), stamp.getHours(), stamp.getMinutes())


class DexaForm(DexaFormTemplate):
    def __init__(self, routing_context=None, **properties):
        self.init_components(**properties)
        self._extra = {}
        self._render(anvil.server.call("bodycomp_get_plan"))

    def _render(self, state):
        self.clear()
        self._state = state
        if not state.get("has_plan"):
            self.add_component(Layout.stack(
                Layout.page_header("DEXA scans"),
                Layout.empty_state("Save your profile before adding scans.", "Set up plan",
                                   lambda **e: Layout.navigate("profile")),
            ), full_width_row=True)
            return
        self._person = Ratings.person_from_state(state)
        scans = state.get("dexa_scans") or []
        header = Layout.page_header(
            "DEXA scans",
            eyebrow=Format.eyebrow(state),
            description="Rated for %s at %s cm. The newest scan anchors your plan's body fat, lean mass, and RMR." % (
                Ratings.who(self._person), Format.number(state.get("height_cm"), 0)),
        )
        parts = [header]
        if scans:
            parts.append(self._latest_card(scans))
        parts.append(self._upload_card())
        parts.append(self._history_card(scans))
        self.add_component(Layout.stack(*parts), full_width_row=True)

    def _latest_card(self, scans):
        latest = scans[-1]
        previous = scans[-2] if len(scans) > 1 else None
        week = " · week %s" % latest["week_index"] if latest.get("week_index") else ""
        card = Layout.section(
            "Latest scan · %s%s" % (Format.date_label(latest.get("measured_on")), week),
            "Green is where you want to be, yellow is close, orange and red need work. Each card says why.",
        )
        cards = "".join(self._metric_html(item) for item in Ratings.rate_scan(latest, self._person, previous))
        chips = "".join(
            '<span><b>%s</b>%s</span>' % (Format.number(latest.get(key), digits, unit), label)
            for label, key, digits, unit in COMPOSITION if latest.get(key) is not None
        )
        Layout.body(card, Layout.html('<div class="bc-dx-comp">%s</div><div class="bc-dx-grid">%s</div>' % (chips, cards)))
        return card

    def _metric_html(self, item):
        bar = ""
        if item["bands"]:
            low, high = item["bands"][0]["from"], item["bands"][-1]["to"]
            segments = "".join(
                '<i class="is-%s" style="flex:%s" title="%s"></i>' % (
                    band["tone"], max(band["to"] - band["from"], 0.0001), Layout.esc(band["label"]))
                for band in item["bands"]
            )
            ticks = "".join(
                '<span style="left:%s%%">%s</span>' % (
                    (band["from"] - low) / float(high - low) * 100,
                    Ratings.fmt(band["from"], 0 if float(band["from"]).is_integer() else 1))
                for band in item["bands"][1:]
            )
            bar = ('<div class="bc-dx-bar">%s<b style="left:%s%%"></b></div><div class="bc-dx-ticks">%s</div>'
                   % (segments, item["marker"], ticks))
        delta = ""
        if item.get("delta"):
            delta = '<span class="bc-dx-delta is-%s">%s</span>' % (item["delta"]["tone"], Layout.esc(item["delta"]["text"]))
        unit = '<small>%s</small>' % Layout.esc(item["unit"]) if item["unit"] else ""
        return (
            '<div class="bc-dx-card is-%s">'
            '<div class="bc-dx-top"><span>%s</span><em>%s</em></div>'
            '<div class="bc-dx-value">%s%s%s</div>%s'
            '<p class="bc-dx-sum">%s</p><p class="bc-dx-detail">%s</p>'
            '</div>'
        ) % (item["tone"], Layout.esc(item["label"]), Layout.esc(item["verdict"]), Layout.esc(item["display"]), unit,
             delta, bar, Layout.esc(item["summary"]), Layout.esc(item["detail"]))

    def _upload_card(self):
        self.on = DatePicker(format="%d %b %Y", placeholder="Scan date", min_date=date(2018, 1, 1), max_date=date.today())
        self.bf = TextBox(type="number", placeholder="e.g. 28.8")
        self.ffm = TextBox(type="number", placeholder="e.g. 57.7")
        self.rmr = TextBox(type="number", placeholder="e.g. 1550")
        self.file = FileDrop(
            title="Drop a DEXA report here",
            hint="or click to browse · PDF or photo · read automatically with your AI key",
            file_types="application/pdf,image/png,image/jpeg",
        )
        self.file.set_event_handler("change", self._read)
        self.status = Layout.html('<p class="bc-dexa-status" anvil-name="text"></p>')
        self.store = Layout.button("Store scan and recalibrate", self._store, primary=True)
        for box in (self.bf, self.ffm, self.rmr):
            box.set_event_handler("change", self._sync)
            box.set_event_handler("lost_focus", self._sync)
        self.on.set_event_handler("change", self._sync)
        self._sync()
        card = Layout.section("Add a scan", "Drop the report and the numbers fill in. Check them, then store.")
        Layout.body(
            card,
            self.file,
            self.status,
            Layout.grid(
                "repeat(4, minmax(0, 1fr))",
                Layout.field("Scan date", self.on),
                Layout.field("Body fat %", self.bf),
                Layout.field("Fat-free mass (kg)", self.ffm),
                Layout.field("RMR (kcal)", self.rmr),
            ),
            Layout.grid("max-content", self.store),
        )
        return card

    def _history_card(self, scans):
        card = Layout.section("All scans", "Hover a coloured value to see why it has that colour.", padded=False)
        if not scans:
            Layout.body(card, Layout.html('<p class="bc-dexa-empty">No scans stored yet. Drop a report above.</p>'))
            return card
        head = "".join("<th>%s</th>" % label for label, _key, _digits, _unit in HISTORY_COLUMNS) + "<th></th>"
        rows = []
        for scan in reversed(scans):
            cells = [self._history_cell(scan, key, digits, unit) for _label, key, digits, unit in HISTORY_COLUMNS]
            actions = (
                '<td class="bc-dx-actions">'
                '<button type="button" data-action="open" data-id="%s" title="%s">Open</button>'
                '<button type="button" data-action="delete" data-id="%s" class="is-danger">Delete</button></td>'
            ) % (Layout.esc(scan["id"]), Layout.esc(scan.get("filename") or "Scan file"), Layout.esc(scan["id"]))
            rows.append("<tr>%s%s</tr>" % ("".join(cells), actions))
        table = Layout.html(
            '<div class="bc-dexa-table" anvil-name="root"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
            % (head, "".join(rows)))
        table.dom_nodes["root"].addEventListener("click", self._on_history_click)
        Layout.body(card, table)
        return card

    def _history_cell(self, scan, key, digits, unit):
        if key == "measured_on":
            return "<td>%s</td>" % Format.date_label(scan.get(key))
        if key == "week_index":
            return "<td>%s</td>" % ("W%s" % scan[key] if scan.get(key) else '<span class="bc-empty">—</span>')
        if key == "created_at":
            return '<td class="bc-dx-muted">%s</td>' % (_uploaded(scan.get(key)) or '<span class="bc-empty">—</span>')
        value = Ratings.ffmi(scan, self._person) if key == "ffmi" else scan.get(key)
        if value is None:
            return '<td><span class="bc-empty">—</span></td>'
        text = Format.percent(value, digits) if unit == "%" else Format.number(value, digits, unit)
        tone, why = Ratings.rating(scan, self._person, key)
        if not tone:
            return "<td>%s</td>" % text
        return '<td><span class="bc-dx-cell is-%s" title="%s">%s</span></td>' % (tone, Layout.esc(why), text)

    def _on_history_click(self, event):
        target = event.target
        button = target.closest("button") if target is not None and hasattr(target, "closest") else None
        if button is None:
            return
        action, scan_id = button.getAttribute("data-action"), button.getAttribute("data-id")
        scan = next((s for s in self._state.get("dexa_scans") or [] if s.get("id") == scan_id), None)
        if scan is None:
            return
        if action == "open":
            try:
                anvil.media.download(anvil.server.call("bodycomp_dexa_file", scan_id))
            except Exception as e:
                alert(str(e), title="Could not open the file")
        elif action == "delete":
            self._delete(scan)

    def _delete(self, scan):
        day = Format.date_label(scan.get("measured_on"))
        if not dialogs.confirm(
            "The plan recalibrates from the newest scan left, or from tape if none are left.",
            title="Delete the scan from %s?" % day, confirm_text="Delete scan", danger=True):
            return
        try:
            state = anvil.server.call("bodycomp_delete_dexa", scan["id"])
        except Exception as e:
            alert(str(e), title="Could not delete scan")
            return
        Notification("Scan from %s deleted. The plan was recalibrated." % day, style="success").show()
        self._render(state)

    def _number(self, box):
        text = "" if box.text is None else str(box.text).strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _values(self):
        values = dict(self._extra)
        values["dexa_measured_on"] = self.on.date
        values["dexa_bf_percent"] = self._number(self.bf)
        values["dexa_ffm_kg"] = self._number(self.ffm)
        values["dexa_rmr_kcal"] = self._number(self.rmr)
        return values

    def _missing(self):
        values = self._values()
        return [label for key, label in REQUIRED_LABELS.items() if values.get(key) is None]

    def _set_status(self, text, tone="muted"):
        node = self.status.dom_nodes["text"]
        node.textContent = text or ""
        node.className = "bc-dexa-status is-%s" % tone

    def _sync(self, **event_args):
        self.store.enabled = self.file.file is not None and not self._missing()

    def _read(self, **event_args):
        media = self.file.file
        self._extra = {}
        if media is None:
            self._set_status("")
            self._sync()
            return
        self.store.enabled = False
        self._set_status("Reading %s…" % (getattr(media, "name", None) or "the scan"))
        try:
            result = anvil.server.call("bodycomp_read_dexa", media, ScanImages.strips_for(media))
        except Exception as e:
            self._set_status(str(e), "bad")
            self._sync()
            return
        values = result.get("values") or {}
        self._extra = dict((key, values.get(key)) for key in values if not key.startswith("dexa_"))
        self.on.date = Ratings.as_date(values.get("dexa_measured_on"))
        self.bf.text = _text(values.get("dexa_bf_percent"))
        self.ffm.text = _text(values.get("dexa_ffm_kg"))
        self.rmr.text = _text(values.get("dexa_rmr_kcal"))
        missing = self._missing()
        if result.get("error"):
            self._set_status(result["error"], "bad")
        elif missing:
            self._set_status("Read the scan, but could not find the %s. Type %s from the report to continue."
                             % (", ".join(missing), "it" if len(missing) == 1 else "them"), "warn")
        else:
            self._set_status("Read every metric from the scan. Check them, then store.", "ok")
        self._sync()

    def _store(self, **event_args):
        media = self.file.file
        missing = self._missing()
        if media is None or missing:
            self._set_status("Add the %s first." % ", ".join(missing or ["scan file"]), "warn")
            return
        try:
            state = anvil.server.call("bodycomp_store_dexa", media, self._values())
        except Exception as e:
            alert(str(e), title="Could not store scan")
            return
        Notification("Scan stored. The plan was recalibrated from it. Issued weekly calories were left as issued.",
                     title="DEXA saved", style="success", timeout=6).show()
        self._render(state)
