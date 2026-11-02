from ._anvil_designer import TrackerFormTemplate
from anvil import *
from routing import router
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
from craftify_library.Startup import configure as configure_craftify_client
from craftify_library.CustomComponents.KpiCard import KpiCard
from tabulator.Tabulator import Tabulator
from body_comp_tracker import CheckIn, Format, Icons, Layout

EMPTY = '<span class="bc-empty">—</span>'
STATUS = {
    "planned": ("Planned", "muted"),
    "current": ("This week", "accent"),
    "due": ("Due", "warn"),
    "partial": ("Partial", "warn"),
    "logged": ("Logged", "ok"),
    "missed": ("Missed", "danger"),
    "excluded": ("Excluded", "muted"),
}
DEXA_TIP_ROWS = (
    ("Body fat", "bf_percent", 1, "%"),
    ("Fat mass", "fat_mass_kg", 1, "kg"),
    ("Lean mass", "lean_mass_kg", 1, "kg"),
    ("Fat-free mass", "ffm_kg", 1, "kg"),
    ("Visceral fat", "vat_g", 0, "g"),
    ("RMR", "rmr_kcal", 0, "kcal"),
)
TABULATOR_OPTIONS = {
    "pagination": False,
    "index": "week",
    "css_class": ["table-striped", "table-bordered"],
    "layout": "fitColumns",
    "columnDefaults": {"headerSort": False, "headerHozAlign": "left"},
    "columnHeaderVertAlign": "middle",
    "placeholder": '<div style="color:#64748b;font-size:13px;padding:24px 0;">No weeks yet</div>',
}


def _value(cell):
    try:
        return cell.getValue()
    except Exception:
        return None


def _data(cell):
    try:
        return dict(cell.getRow().getData())
    except Exception:
        return {}


def _num(value, digits):
    if value is None or value == "":
        return None
    try:
        return ("%." + str(digits) + "f") % float(value)
    except (TypeError, ValueError):
        return None


def _week_fmt(cell, **params):
    klass = "bc-week-badge is-dexa" if _data(cell).get("dexa") else "bc-week-badge"
    return '<span class="%s">%s</span>' % (klass, Layout.esc(_value(cell) or ""))


def dexa_tooltip(scan):
    rows = []
    for label, key, digits, unit in DEXA_TIP_ROWS:
        if scan.get(key) is not None:
            value = Format.percent(scan.get(key)) if unit == "%" else Format.number(scan.get(key), digits, unit)
            rows.append("<dt>%s</dt><dd>%s</dd>" % (label, value))
    return (
        '<div class="bc-dexa-tip"><div class="bc-dexa-tip-h"><i></i>DEXA scan<span>%s</span></div><dl>%s</dl></div>'
        % (Format.date_label(scan.get("measured_on")), "".join(rows))
    )


def _week_tip(event, cell, on_rendered=None):
    scan = _data(cell).get("dexa")
    return dexa_tooltip(dict(scan)) if scan else False


def _dexa_by_week(state):
    scans = {}
    for scan in state.get("dexa_scans") or []:
        if scan.get("week_index"):
            scans[int(scan["week_index"])] = scan
    if state.get("dexa_bf_percent") is not None:
        for week in state.get("dexa_weeks") or []:
            scans.setdefault(int(week), {
                "measured_on": state.get("dexa_measured_on"),
                "bf_percent": state.get("dexa_bf_percent"),
                "ffm_kg": state.get("dexa_ffm_kg"),
                "rmr_kcal": state.get("dexa_rmr_kcal"),
            })
    return scans


def _phase_fmt(cell, **params):
    phase = _data(cell).get("phase") or ""
    icon = Icons.ICON[Icons.PHASE_ICON.get(phase, "flame")]
    tone = Icons.PHASE_TONE.get(phase, "muted")
    return '<span class="bc-pill bc-pill-%s">%s%s</span>' % (
        tone,
        icon,
        Layout.esc(Format.phase(phase)),
    )


def _target_kg(cell, **params):
    text = _num(_value(cell), 1)
    return '<span class="bc-val-target">%s kg</span>' % text if text else EMPTY


def _actual_kg(cell, **params):
    text = _num(_value(cell), 1)
    return '<span class="bc-val-actual">%s kg</span>' % text if text else EMPTY


def _target_pct(cell, **params):
    text = _num(_value(cell), 1)
    return '<span class="bc-val-target">%s%%</span>' % text if text else EMPTY


def _actual_pct(cell, **params):
    text = _num(_value(cell), 1)
    return '<span class="bc-val-actual">%s%%</span>' % text if text else EMPTY


def _delta_fmt(cell, **params):
    raw = _value(cell)
    if raw is None or raw == "":
        return EMPTY
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return EMPTY
    klass = "bc-delta-good" if number <= 0 else "bc-delta-bad"
    sign = "+" if number > 0 else ""
    return '<span class="bc-delta %s">%s%s</span>' % (klass, sign, "%.1f" % number)


def _plain_fmt(cell, **params):
    text = _num(_value(cell), 0)
    return '<span class="bc-actual">%s</span>' % Format.number(text) if text else EMPTY


def _tape_fmt(cell, **params):
    text = _num(_value(cell), 1)
    return '<span class="bc-actual">%s</span>' % text if text else EMPTY


def _kcal_fmt(cell, **params):
    text = _num(_value(cell), 0)
    if text is None:
        return EMPTY
    return '<span class="bc-kcal">%s<span>%s</span></span>' % (Icons.ICON["flame"], Format.number(text))


def _macros_fmt(cell, **params):
    data = _data(cell)
    if data.get("protein_g") is None and data.get("fat_g") is None and data.get("carbs_g") is None:
        return EMPTY
    chips = []
    for name, value in (("protein", data.get("protein_g")), ("fat", data.get("fat_g")), ("carbs", data.get("carbs_g"))):
        chips.append(
            '<span class="bc-macros-chip">%s<span>%s</span></span>'
            % (Icons.ICON[name], _num(value, 0) or "0")
        )
    return '<span class="bc-macros">%s</span>' % "".join(chips)


def _status_fmt(cell, **params):
    label, tone = STATUS.get(_value(cell) or "", ((_value(cell) or "—").title(), "muted"))
    return '<span class="bc-pill bc-pill-%s">%s</span>' % (tone, Layout.esc(label))


def _notes_fmt(cell, **params):
    text = _value(cell)
    return Layout.esc(text) if text else EMPTY


def _edit_fmt(cell, **params):
    if _data(cell).get("status") == "planned":
        return EMPTY
    return '<button type="button" class="bc-row-edit">Edit</button>'


COLUMNS = [
    {"title": "Week", "field": "weekLabel", "width": 64, "formatter": _week_fmt, "tooltip": _week_tip, "frozen": True},
    {"title": "Week of", "field": "weekDate", "width": 108, "frozen": True},
    {"title": "Phase", "field": "phase", "hozAlign": "center", "width": 100, "formatter": _phase_fmt},
    {"title": "Weight (kg)", "headerHozAlign": "center", "columns": [
        {"title": "Target", "field": "target_weight_kg", "width": 75, "hozAlign": "right", "formatter": _target_kg, "cssClass": "bc-col-target"},
        {"title": "Actual", "field": "actual_weight_kg", "width": 75, "hozAlign": "right", "formatter": _actual_kg, "cssClass": "bc-col-actual"},
        {"title": "Δ", "field": "weight_delta_kg", "width": 50, "hozAlign": "right", "formatter": _delta_fmt, "cssClass": "bc-col-actual"},
    ]},
    {"title": "Tape (cm)", "headerHozAlign": "center", "columns": [
        {"title": "Waist", "field": "waist_cm", "width": 70, "hozAlign": "right", "formatter": _tape_fmt},
        {"title": "Neck", "field": "neck_cm", "width": 66, "hozAlign": "right", "formatter": _tape_fmt},
    ]},
    {"title": "Body fat", "headerHozAlign": "center", "columns": [
        {"title": "Target", "field": "target_bf_percent", "width": 75, "hozAlign": "right", "formatter": _target_pct, "cssClass": "bc-col-target"},
        {"title": "Actual", "field": "bf_percent", "width": 75, "hozAlign": "right", "formatter": _actual_pct, "cssClass": "bc-col-actual"},
        {"title": "Δ", "field": "bf_delta", "width": 50, "hozAlign": "right", "formatter": _delta_fmt, "cssClass": "bc-col-actual"},
    ]},
    {"title": "Training", "headerHozAlign": "center", "columns": [
        {"title": "Sessions", "field": "training_sessions", "width": 78, "hozAlign": "right", "formatter": _plain_fmt},
        {"title": "Steps", "field": "daily_steps", "width": 80, "hozAlign": "right", "formatter": _plain_fmt},
    ]},
    {"title": "Nutrition", "headerHozAlign": "center", "columns": [
        {"title": "kcal", "field": "target_calories", "width": 80, "hozAlign": "right", "formatter": _kcal_fmt, "cssClass": "bc-col-target"},
        {"title": "Macros", "headerHozAlign": "center", "field": "protein_g", "width": 220, "formatter": _macros_fmt},
    ]},
    {"title": "Status", "field": "status", "width": 100, "formatter": _status_fmt},
    {"title": "Notes", "field": "notes", "minWidth": 140, "formatter": _notes_fmt},
    {"title": "", "field": "edit", "width": 72, "hozAlign": "right", "formatter": _edit_fmt, "cssClass": "bc-col-edit"},
]


class TrackerForm(TrackerFormTemplate):
    def __init__(self, routing_context=None, **properties):
        self.init_components(**properties)
        configure_craftify_client()
        self._resize_bound = False
        self._drawer = None
        self._render(anvil.server.call("bodycomp_get_plan"))
        query = getattr(routing_context, "query", None) or {}
        if query.get("checkin") and self._state.get("has_plan"):
            self._clear_query()
            from anvil.js.window import setTimeout
            setTimeout(lambda: self._checkin(query.get("checkin")), 0)

    def _render(self, state):
        self._state = state
        self.clear()
        if not state.get("has_plan"):
            self.add_component(
                Layout.stack(
                    Layout.page_header("Weekly tracker"),
                    Layout.empty_state("Save your profile before the tracker has weeks.", "Set up plan", self._open_profile),
                ),
                full_width_row=True,
            )
            return
        self._current = state.get("current_week") or 1
        self._dexa = _dexa_by_week(state)
        row = Format.current_row(state)
        header = Layout.page_header(
            "Weekly tracker",
            eyebrow=Format.eyebrow(state),
            description="Every week of the plan. Edit a started week to correct measurements. Future weeks stay planned.",
            actions=(Layout.button("Sunday check-in", self._open_checkin, primary=True),),
        )
        kpis = Layout.grid(
            "repeat(auto-fit, minmax(170px, 1fr))",
            KpiCard(title="This week", icon=Icons.KPI["week"][0], icon_color=Icons.KPI["week"][1], value="Week %s" % self._current, subtitle=Format.date_label(row.get("week_start"))),
            KpiCard(title="Target weight", icon=Icons.KPI["weight"][0], icon_color=Icons.KPI["weight"][1], value=Format.number(row.get("target_weight_kg"), 1, "kg"),
                    subtitle="Actual %s" % Format.number(row.get("actual_weight_kg"), 1, "kg")),
            KpiCard(title="Body fat target", icon=Icons.KPI["body_fat"][0], icon_color=Icons.KPI["body_fat"][1], value=Format.percent(row.get("target_bf_percent")),
                    subtitle="Actual %s" % Format.percent(row.get("bf_percent"))),
            KpiCard(title="Calories", icon=Icons.KPI["calories"][0], icon_color=Icons.KPI["calories"][1], value=Format.number(row.get("target_calories"), 0, "kcal"),
                    subtitle="P %s · F %s · C %s g" % (row.get("protein_g"), row.get("fat_g"), row.get("carbs_g"))),
        )
        table_card = Layout.section(
            "All weeks",
            "Target columns are muted; actual columns are bold. The current week is highlighted. Edit opens that week's check-in in a side panel.",
            padded=False,
        )
        Layout.body(table_card, self._table(state))
        self.add_component(Layout.stack(header, kpis, table_card), full_width_row=True)

    def _table(self, state):
        rows = []
        for row in state.get("schedule") or []:
            item = dict(row)
            item["weekLabel"] = "W%s" % row.get("week")
            item["weekDate"] = Format.date_label(row.get("week_start"))
            item["dexa"] = self._dexa.get(row.get("week"))
            rows.append(item)
        table = Tabulator()
        options = dict(TABULATOR_OPTIONS)
        options["height"] = 420
        table.options = options
        table.columns = COLUMNS
        table.data = rows
        table.set_event_handler("row_formatter", self._paint_row)
        table.set_event_handler("cell_click", self._on_cell_click)
        table.set_event_handler("table_built", self._on_table_built)
        self._tabulator = table
        try:
            from anvil.js.window import setTimeout
            setTimeout(self._fill_table_height, 0)
            setTimeout(self._fill_table_height, 200)
        except Exception:
            pass
        return table

    def _on_table_built(self, **event_args):
        self._fill_table_height()
        self._scroll_to_current()
        if self._resize_bound:
            return
        try:
            from anvil.js import window
            window.addEventListener("resize", self._fill_table_height)
            self._resize_bound = True
        except Exception:
            pass

    def _table_el(self):
        from anvil.js import get_dom_node
        node = get_dom_node(self._tabulator)
        if node is None:
            return None
        if getattr(node, "classList", None) and node.classList.contains("tabulator"):
            return node
        if hasattr(node, "querySelector"):
            return node.querySelector(".tabulator") or node
        return node

    def _fill_table_height(self, *args):
        try:
            from anvil.js import window
            el = self._table_el()
            if el is None:
                return
            top = el.getBoundingClientRect().top
            height = max(280, int(window.innerHeight - top - 20))
            el.style.height = "%spx" % height
            self._tabulator.height = height
            if hasattr(self._tabulator, "redraw"):
                self._tabulator.redraw(True)
        except Exception:
            pass

    def _paint_row(self, row, **event_args):
        try:
            data = dict(row.getData())
        except Exception:
            return
        if data.get("week") == self._current:
            row.getElement().classList.add("bc-week-current")

    def _scroll_to_current(self, **event_args):
        if self._current <= 6:
            return
        try:
            self._tabulator.scrollToRow(self._current, "center", False)
        except Exception:
            pass

    def _on_cell_click(self, cell=None, **event_args):
        cell = cell or event_args.get("cell")
        if cell is None:
            return
        try:
            field = cell.getField()
            data = dict(cell.getRow().getData())
        except Exception:
            return
        if field != "edit" or data.get("status") == "planned":
            return
        week = data.get("week")
        if week:
            self._checkin(week)

    def _open_checkin(self, **event_args):
        self._checkin(None)

    def _checkin(self, week):
        if self._drawer is not None and self._drawer.is_open:
            return
        panel = CheckIn.CheckInPanel(self._state, CheckIn.week_for(self._state, week), on_saved=self._render)
        self._drawer = panel.open(self)

    def _clear_query(self):
        try:
            from anvil.js import window
            window.history.replaceState(window.history.state, "", window.location.pathname)
        except Exception:
            pass

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
