from datetime import date, datetime

from ._anvil_designer import WeightsFormTemplate
from anvil import *
from routing import router
import anvil.server
from craftify_library.CraftifyUtils import dialogs
from craftify_library.CustomComponents.KpiCard import KpiCard
from tabulator.Tabulator import Tabulator
from body_comp_tracker import Format, Icons, Layout, WeightsView as View

EMPTY = '<span class="bc-empty">—</span>'
TABLE_OPTIONS = {
    "pagination": False,
    "index": "date",
    "css_class": ["table-striped", "table-bordered"],
    "layout": "fitColumns",
    "columnDefaults": {"headerSort": False, "headerHozAlign": "left"},
    "columnHeaderVertAlign": "middle",
    "placeholder": '<div style="color:#64748b;font-size:13px;padding:24px 0;">No weigh-ins yet</div>',
}


def _value(cell):
    try:
        return cell.getValue()
    except Exception:
        return None


def _kg_fmt(cell, **params):
    raw = _value(cell)
    if raw is None or raw == "":
        return EMPTY
    return '<span class="bc-val-actual">%.1f kg</span>' % float(raw)


def _week_fmt(cell, **params):
    week = _value(cell)
    return "W%s" % int(week) if week else EMPTY


def _delta_fmt(cell, **params):
    return View.delta_html(_value(cell))


def _edit_fmt(cell, **params):
    return '<button type="button" class="bc-row-edit">Edit</button>'


def _delete_fmt(cell, **params):
    return '<button type="button" class="bc-row-edit bc-w-delete">Delete</button>'


COLUMNS = [
    {"title": "Date", "field": "label", "minWidth": 160},
    {"title": "Week", "field": "week", "width": 80, "formatter": _week_fmt},
    {"title": "Weight", "field": "kg", "width": 110, "hozAlign": "right", "formatter": _kg_fmt},
    {"title": "Change", "field": "delta", "width": 110, "hozAlign": "right", "formatter": _delta_fmt},
    {"title": "", "field": "edit", "width": 76, "hozAlign": "right", "formatter": _edit_fmt, "cssClass": "bc-col-edit"},
    {"title": "", "field": "delete", "width": 88, "hozAlign": "right", "formatter": _delete_fmt, "cssClass": "bc-col-edit"},
]


def _picked(picker):
    value = picker.date
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


class WeightsForm(WeightsFormTemplate):
    def __init__(self, routing_context=None, **properties):
        self.init_components(**properties)
        self._render(anvil.server.call("bodycomp_get_plan"))

    def _render(self, state):
        self._state = state
        self.clear()
        if not state.get("has_plan"):
            self.add_component(
                Layout.stack(
                    Layout.page_header("Weigh-ins"),
                    Layout.empty_state("Save your profile before logging a weigh-in.", "Set up plan", self._open_profile),
                ),
                full_width_row=True,
            )
            return
        rows = View.entries(state.get("weights"), state.get("start_date"))
        self._by_date = {row["date"]: row["kg"] for row in rows}
        header = Layout.page_header(
            "Weigh-ins",
            eyebrow=Format.eyebrow(state),
            description="Every morning weigh-in, newest first. Add a missed day by choosing its date.",
        )
        self.add_component(
            Layout.stack(header, self._kpis(state), self._log_card(), self._list_card(rows)),
            full_width_row=True,
        )

    def _kpis(self, state):
        stats = View.summary(state.get("weights"), date.today())
        if stats is None:
            return None
        if stats["week_avg"] is None:
            week_value, week_note = "—", "None in the last 7 days"
        else:
            week_value = Format.number(stats["week_avg"], 1, "kg")
            week_note = "%s weigh-in%s" % (stats["week_count"], "" if stats["week_count"] == 1 else "s")
        streak_note = "Through %s" % Format.date_label(stats["latest_date"])
        if not stats["streak_current"]:
            streak_note = "Last ended %s" % Format.date_label(stats["latest_date"])
        delta = stats["delta"]
        latest_note = Format.date_label(stats["latest_date"])
        if delta is not None:
            change = Format.number(delta, 1)
            if delta > 0:
                change = "+" + change
            latest_note += " · %s kg from the one before" % change
        return Layout.grid(
            "repeat(auto-fit, minmax(170px, 1fr))",
            KpiCard(title="Latest", icon=Icons.KPI["weight"][0], icon_color=Icons.KPI["weight"][1],
                    value=Format.number(stats["latest_kg"], 1, "kg"), subtitle=latest_note),
            KpiCard(title="Last 7 days", icon=Icons.KPI["rate"][0], icon_color=Icons.KPI["rate"][1],
                    value=week_value, subtitle=week_note),
            KpiCard(title="Since first", icon=Icons.KPI["target"][0], icon_color=Icons.KPI["target"][1],
                    value=Format.number(stats["since_first"], 1, "kg"),
                    subtitle="From %s" % Format.date_label(stats["first_date"])),
            KpiCard(title="Streak", icon=Icons.KPI["week"][0], icon_color=Icons.KPI["week"][1],
                    value="%s day%s" % (stats["streak"], "" if stats["streak"] == 1 else "s"), subtitle=streak_note),
        )

    def _log_card(self):
        card = Layout.section("Log a weigh-in", "Choose today, or an earlier date to fill in a missed morning.")
        today = date.today()
        self.when = DatePicker(
            format="%d %b %Y", placeholder="Choose a date", date=today,
            min_date=date(today.year - 5, 1, 1), max_date=today,
        )
        self.kg = TextBox(type="number", placeholder="kg")
        self.save = Layout.button("Save weigh-in", self._save, primary=True)
        self.when.set_event_handler("change", self._sync_date)
        self.kg.set_event_handler("pressed_enter", self._save)
        self._hint = Layout.html('<p anvil-name="hint" class="bc-note bc-note-muted"></p>')
        Layout.body(
            card,
            Layout.grid(
                "minmax(0, 240px) minmax(0, 180px)",
                Layout.field("Date", self.when),
                Layout.field("Weight (kg)", self.kg),
            ),
            self._hint,
            self.save,
        )
        self._sync_date()
        return card

    def _hint_node(self):
        nodes = getattr(self._hint, "dom_nodes", None)
        if nodes is not None:
            try:
                return nodes["hint"]
            except Exception:
                pass
        return None

    def _sync_date(self, **event_args):
        day = _picked(self.when)
        existing = self._by_date.get(day.isoformat()) if day else None
        node = self._hint_node()
        if existing is not None:
            self.kg.text = "%.1f" % existing
            self.save.text = "Update this date"
            text = "This date already has a weigh-in. Saving replaces it. A week already checked in keeps its saved average."
        else:
            self.save.text = "Save weigh-in"
            text = "A new date is added to the list and counts toward that week's average, unless the week was already checked in."
        if node is not None:
            node.textContent = text

    def _list_card(self, rows):
        count = len(rows)
        subtitle = "No weigh-ins yet." if not count else "%s morning%s. Change is from the previous logged day, and a drop is shown in green." % (
            count, "" if count == 1 else "s")
        card = Layout.section("All weigh-ins", subtitle, padded=False)
        table = Tabulator()
        options = dict(TABLE_OPTIONS)
        options["height"] = min(560, 72 + 44 * max(count, 3))
        table.options = options
        table.columns = COLUMNS
        table.data = rows
        table.set_event_handler("cell_click", self._on_cell_click)
        Layout.body(card, table)
        return card

    def _on_cell_click(self, cell=None, **event_args):
        cell = cell or event_args.get("cell")
        if cell is None:
            return
        try:
            field = cell.getField()
            day = dict(cell.getRow().getData()).get("date")
        except Exception:
            return
        if field == "edit":
            self._edit(day)
        elif field == "delete":
            self._delete(day)

    def _edit(self, day):
        try:
            parts = [int(part) for part in str(day).split("-")]
            picked = date(parts[0], parts[1], parts[2])
        except (TypeError, ValueError, IndexError):
            return
        self.when.date = picked
        kg = self._by_date.get(picked.isoformat())
        if kg is not None:
            self.kg.text = "%.1f" % kg
            self.save.text = "Update this date"
        self._sync_date()
        try:
            from anvil.js import get_dom_node
            get_dom_node(self.when).scrollIntoView()
        except Exception:
            pass

    def _save(self, **event_args):
        day = _picked(self.when)
        if day is None:
            Notification("Choose a date.", style="warning").show()
            return
        if day > date.today():
            Notification("Choose today or an earlier date.", style="warning").show()
            return
        try:
            kg = float(self.kg.text)
        except (TypeError, ValueError):
            Notification("Enter your weight in kg.", style="warning").show()
            return
        self.save.enabled = False
        try:
            state = anvil.server.call("bodycomp_log_weight", kg, day)
        except Exception as e:
            self.save.enabled = True
            dialogs.alert(str(e), title="Could not save weigh-in")
            return
        Notification("Logged %s kg for %s." % (Format.number(kg, 1), Format.date_label(day)),
                     title="Weigh-in saved", style="success").show()
        self._render(state)

    def _delete(self, day):
        if not dialogs.confirm(
            "This removes it from the trend and from weekly averages that have not been checked in yet.",
            title="Delete the weigh-in from %s?" % Format.date_label(day),
            confirm_text="Delete weigh-in", danger=True):
            return
        try:
            state = anvil.server.call("bodycomp_delete_weight", day)
        except Exception as e:
            dialogs.alert(str(e), title="Could not delete weigh-in")
            return
        Notification("Weigh-in removed.", style="success").show()
        self._render(state)

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
