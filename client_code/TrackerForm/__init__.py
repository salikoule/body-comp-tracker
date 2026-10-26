from ._anvil_designer import TrackerFormTemplate
from anvil import *
import anvil.server
from craftify_library.Startup import configure as configure_craftify_client
from craftify_library.CustomComponents.KpiCard import KpiCard
from tabulator.Tabulator import Tabulator
from body_comp_tracker import Format, Icons, Layout

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
TABULATOR_OPTIONS = {
    "pagination": False,
    "index": "week",
    "css_class": ["table-striped", "table-bordered"],
    "layout": "fitDataStretch",
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
    return '<span class="bc-week-badge">%s</span>' % Layout.esc(_value(cell) or "")


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


COLUMNS = [
    {"title": "Week", "field": "weekLabel", "width": 64, "formatter": _week_fmt, "frozen": True},
    {"title": "Week of", "field": "weekDate", "width": 108, "frozen": True},
    {"title": "Phase", "field": "phase", "width": 148, "formatter": _phase_fmt},
    {"title": "Weight (kg)", "columns": [
        {"title": "Target", "field": "target_weight_kg", "width": 88, "hozAlign": "right", "formatter": _target_kg, "cssClass": "bc-col-target"},
        {"title": "Actual", "field": "actual_weight_kg", "width": 92, "hozAlign": "right", "formatter": _actual_kg, "cssClass": "bc-col-actual"},
        {"title": "Δ", "field": "weight_delta_kg", "width": 68, "hozAlign": "right", "formatter": _delta_fmt, "cssClass": "bc-col-actual"},
    ]},
    {"title": "Tape (cm)", "columns": [
        {"title": "Waist", "field": "waist_cm", "width": 70, "hozAlign": "right", "formatter": _tape_fmt},
        {"title": "Neck", "field": "neck_cm", "width": 66, "hozAlign": "right", "formatter": _tape_fmt},
    ]},
    {"title": "Body fat", "columns": [
        {"title": "Target", "field": "target_bf_percent", "width": 80, "hozAlign": "right", "formatter": _target_pct, "cssClass": "bc-col-target"},
        {"title": "Actual", "field": "bf_percent", "width": 80, "hozAlign": "right", "formatter": _actual_pct, "cssClass": "bc-col-actual"},
        {"title": "Δ", "field": "bf_delta", "width": 68, "hozAlign": "right", "formatter": _delta_fmt, "cssClass": "bc-col-actual"},
    ]},
    {"title": "Training", "columns": [
        {"title": "Sessions", "field": "training_sessions", "width": 78, "hozAlign": "right", "formatter": _plain_fmt},
        {"title": "Steps", "field": "daily_steps", "width": 80, "hozAlign": "right", "formatter": _plain_fmt},
    ]},
    {"title": "Nutrition", "columns": [
        {"title": "kcal", "field": "target_calories", "width": 108, "hozAlign": "right", "formatter": _kcal_fmt, "cssClass": "bc-col-target"},
        {"title": "Macros", "field": "protein_g", "width": 220, "formatter": _macros_fmt},
    ]},
    {"title": "Status", "field": "status", "width": 100, "formatter": _status_fmt},
    {"title": "Notes", "field": "notes", "minWidth": 180, "formatter": _notes_fmt},
]


class TrackerForm(TrackerFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        configure_craftify_client()
        state = anvil.server.call("bodycomp_get_plan")
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
        row = Format.current_row(state)
        header = Layout.page_header(
            "Weekly tracker",
            eyebrow=Format.eyebrow(state),
            description="Every week of the plan. Rows update after morning weigh-ins and Sunday check-ins.",
            actions=(Layout.button("Sunday check-in", self._open_checkin, primary=True),),
        )
        kpis = Layout.grid(
            "repeat(auto-fit, minmax(170px, 1fr))",
            KpiCard(title="This week", value="Week %s" % self._current, subtitle=Format.date_label(row.get("week_start"))),
            KpiCard(title="Target weight", value=Format.number(row.get("target_weight_kg"), 1, "kg"),
                    subtitle="Actual %s" % Format.number(row.get("actual_weight_kg"), 1, "kg")),
            KpiCard(title="Body fat target", value=Format.percent(row.get("target_bf_percent")),
                    subtitle="Actual %s" % Format.percent(row.get("bf_percent"))),
            KpiCard(title="Calories", value=Format.number(row.get("target_calories"), 0, "kcal"),
                    subtitle="P %s · F %s · C %s g" % (row.get("protein_g"), row.get("fat_g"), row.get("carbs_g"))),
        )
        table_card = Layout.section(
            "All weeks",
            "Target columns are muted; actual columns are bold. The current week is highlighted.",
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
            rows.append(item)
        table = Tabulator()
        options = dict(TABULATOR_OPTIONS)
        options["height"] = 420
        table.options = options
        table.columns = COLUMNS
        table.data = rows
        table.set_event_handler("row_formatter", self._paint_row)
        table.set_event_handler("table_built", self._on_table_built)
        self._tabulator = table
        return table

    def _on_table_built(self, **event_args):
        self._fill_table_height()
        self._scroll_to_current()
        try:
            from anvil.js import window
            window.addEventListener("resize", self._fill_table_height)
        except Exception:
            pass

    def _fill_table_height(self, *args):
        try:
            from anvil.js import get_dom_node, window
            node = get_dom_node(self._tabulator)
            el = node.querySelector(".tabulator") if hasattr(node, "querySelector") else node
            top = el.getBoundingClientRect().top
            height = max(280, int(window.innerHeight - top - 16))
            self._tabulator.height = "%spx" % height
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

    def _open_checkin(self, **event_args):
        Layout.navigate("checkin")

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
