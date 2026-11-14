from ._anvil_designer import ProgressFormTemplate
from anvil import *
from routing import router
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
from datetime import date
from anvil.js import window
from craftify_library.CustomComponents.EChart import EChart
from body_comp_tracker import Format, Layout
from body_comp_tracker import ProgressView as View
from body_comp_tracker.ProgressCharts import (
    METRICS,
    calorie_plan_options,
    composition_options,
    fuel_ring_options,
    has_trend_gap,
    hero_options,
    progress_model,
)

HERO_HEIGHT = "380px"

HERO_CARD = """
<div class="bc-pg-card">
  <div class="bc-pg-card-h">
    <div><h3 anvil-name="title"></h3><p anvil-name="subtitle"></p></div>
    <div class="bc-pg-tools">
      <div class="bc-pg-seg" anvil-name="metric">
        <button type="button" data-value="weight" class="is-on">Weight</button>
        <button type="button" data-value="bf">Body fat</button>
        <button type="button" data-value="lean">Lean mass</button>
      </div>
      <div class="bc-pg-seg" anvil-name="span">
        <button type="button" data-value="4w">4W</button>
        <button type="button" data-value="12w" class="is-on">12W</button>
        <button type="button" data-value="plan">Plan</button>
      </div>
    </div>
  </div>
  <div class="bc-pg-hero">
    <div anvil-slot="chart"></div>
    <div class="bc-pg-hero-note" anvil-name="note">
      <b>Your trend appears after 3 weigh-ins</b>
      <span>Step on the scale each morning and log it on the Dashboard. The forecast follows after a week of data.</span>
    </div>
  </div>
  <div class="bc-pg-legend" anvil-name="legend">
    <span class="for-weight"><i class="is-dot"></i>Daily weigh-in</span><span class="for-weight"><i class="is-line"></i>Trend</span>
    <span class="for-body"><i class="is-line"></i>Measured</span>
    <span><i class="is-lane"></i>Plan lane</span><span class="for-weight"><i class="is-cone"></i>Forecast at current pace</span>
    <span class="for-body"><i class="is-dexa"></i>DEXA scan</span>
  </div>
</div>
"""

SCORE_CARD = """
<div class="bc-pg-card">
  <div class="bc-pg-card-h">
    <div><h3>Week by week</h3><p>Weight within ±0.4 kg of the line. Body fat misses only when it is more than 0.6 points above the line. Click a square.</p></div>
    <div anvil-name="chip"></div>
  </div>
  <div class="bc-pg-score" anvil-name="grid"></div>
  <div class="bc-pg-detail" anvil-name="detail"></div>
</div>
"""

FUEL_CARD = """
<div class="bc-pg-card">
  <div class="bc-pg-card-h"><div><h3>Fuel</h3><p anvil-name="subtitle"></p></div></div>
  <div class="bc-pg-fuel"><div anvil-slot="ring"></div><div anvil-name="macros"></div></div>
  <p class="bc-pg-mini-title">Calories across the plan</p>
  <div anvil-slot="kcal"></div>
</div>
"""

COMP_CARD = """
<div class="bc-pg-card bc-pg-comp">
  <div class="bc-pg-comp-main">
    <div class="bc-pg-card-h"><div><h3>What the weight is made of</h3>
      <p>Fat mass and lean mass, from weight × body-fat %. Solid line is measured, dashed is plan.</p></div></div>
    <div class="bc-pg-comp-charts"><div anvil-slot="fat"></div><div anvil-slot="lean"></div></div>
  </div>
  <div class="bc-pg-comp-side" anvil-name="side"></div>
</div>
"""


def _js_band():
    return window.Function(
        "params",
        "api",
        "var a = api.coord([api.value(0), api.value(1)]);"
        "var b = api.coord([api.value(0), api.value(2)]);"
        "var c = api.coord([api.value(3), api.value(5)]);"
        "var d = api.coord([api.value(3), api.value(4)]);"
        "return {type: 'polygon', shape: {points: [a, b, c, d]}, style: {fill: api.visual('color')}};",
    )


def _js_hero_tooltip(unit):
    return window.Function(
        "params",
        "if (!params || !params.length) return '';"
        "var day = new Date(params[0].axisValue);"
        "var lines = ['<b>' + day.toLocaleDateString('en-GB', {day: 'numeric', month: 'short'}) + '</b>'];"
        "var seen = {};"
        "for (var i = 0; i < params.length; i++) {"
        "  var p = params[i];"
        "  if (!p.seriesName || p.seriesType === 'custom' || seen[p.seriesName]) continue;"
        "  var v = p.value;"
        "  if (Array.isArray(v)) v = v[1];"
        "  if (v == null) continue;"
        "  seen[p.seriesName] = true;"
        "  lines.push(p.marker + p.seriesName + '  <b>' + Number(v).toFixed(1) + ' %s</b>');"
        "}"
        "return lines.join('<br/>');" % unit,
    )


def _with_js(options, unit):
    for series in options.get("series") or []:
        if series.get("type") == "custom":
            series["renderItem"] = _js_band()
    options["tooltip"]["formatter"] = _js_hero_tooltip(unit)
    return options


def _chart(options, height):
    return Layout.flat(EChart(options=options, height=height))


def _toggle(group, value):
    for button in group.querySelectorAll("button"):
        if button.getAttribute("data-value") == value:
            button.classList.add("is-on")
        else:
            button.classList.remove("is-on")


class ProgressForm(ProgressFormTemplate):
    def __init__(self, routing_context=None, **properties):
        self.init_components(**properties)
        state = anvil.server.call("bodycomp_get_plan")
        schedule = state.get("schedule") or []
        if not state.get("has_plan") or not schedule:
            self.add_component(
                Layout.stack(
                    Layout.page_header("Progress"),
                    Layout.empty_state("Save your profile to see progress.", "Set up plan", self._open_profile),
                ),
                full_width_row=True,
            )
            return
        self.model = progress_model(state, date.today())
        self.metric = "weight"
        self.span = "12w"
        tone, text = View.verdict(self.model)
        header = Layout.page_header(
            "Progress",
            eyebrow=self._eyebrow(state),
            actions=(Layout.button("Weekly tracker", self._open_tracker),),
        )
        verdict = Layout.html('<div class="bc-pg-verdict"><p>%s</p>%s</div>' % (text, View.status_pill(tone)))
        tiles = Layout.html(View.tiles_html(self.model))
        timeline = Layout.html(View.timeline_html(self.model))
        lower = Layout.grid("minmax(0, 1fr) minmax(0, 1.9fr)", self._fuel_card(), self._comp_card())
        lower.dom_nodes["grid"].classList.add("bc-pg-split")
        self.add_component(
            Layout.stack(header, verdict, tiles, timeline, self._hero_card(), self._score_card(), lower),
            full_width_row=True,
        )

    def _eyebrow(self, state):
        phase_end = self.model["phase_end_row"] or {}
        left = (phase_end.get("week") or 0) - self.model["current_week"] + 1
        text = Format.eyebrow(state)
        if self.model["current_phase"] and left > 0:
            text += " · %s week%s left in %s" % (left, "" if left == 1 else "s", Format.phase(self.model["current_phase"]["phase"]).lower())
        return text

    def _hero_card(self):
        card = Layout.html(HERO_CARD)
        self.hero = card
        self.hero_chart = EChart(options=self._hero_options(), height=HERO_HEIGHT)
        card.add_component(Layout.flat(self.hero_chart), slot="chart")
        card.dom_nodes["metric"].addEventListener("click", self._pick_metric)
        card.dom_nodes["span"].addEventListener("click", self._pick_span)
        self._sync_hero_text()
        return card

    def _hero_options(self):
        options = hero_options(self.model, self.metric, self.span)
        return _with_js(options, METRICS[self.metric]["unit"])

    def _sync_hero_text(self):
        nodes = self.hero.dom_nodes
        nodes["title"].textContent = METRICS[self.metric]["title"]
        nodes["subtitle"].textContent = View.hero_subtitle(self.model, self.metric)
        nodes["note"].style.display = "block" if has_trend_gap(self.model, self.metric) else "none"
        nodes["legend"].setAttribute("data-metric", "weight" if self.metric == "weight" else "body")

    def _redraw_hero(self):
        self.hero_chart.set_option(self._hero_options())
        self._sync_hero_text()

    def _pick_metric(self, event):
        value = event.target.getAttribute("data-value")
        if not value or value == self.metric:
            return
        self.metric = value
        _toggle(self.hero.dom_nodes["metric"], value)
        self._redraw_hero()

    def _pick_span(self, event):
        value = event.target.getAttribute("data-value")
        if not value or value == self.span:
            return
        self.span = value
        _toggle(self.hero.dom_nodes["span"], value)
        self._redraw_hero()

    def _score_card(self):
        card = Layout.html(SCORE_CARD)
        self.score = card
        card.dom_nodes["chip"].innerHTML = View.lane_chip(self.model)
        card.dom_nodes["grid"].innerHTML = View.scorecard_html(self.model)
        card.dom_nodes["grid"].addEventListener("click", self._pick_week)
        last = self.model["logged"][-1] if self.model["logged"] else self.model["current_row"]
        self._show_week(last.get("week"))
        return card

    def _show_week(self, week):
        row = next((item for item in self.model["rows"] if item.get("week") == week), None)
        self.score.dom_nodes["detail"].innerHTML = View.week_detail_html(self.model, row)
        for square in self.score.dom_nodes["grid"].querySelectorAll(".bc-pg-sq[data-week]"):
            if square.getAttribute("data-week") == str(week):
                square.classList.add("is-sel")
            else:
                square.classList.remove("is-sel")

    def _pick_week(self, event):
        week = event.target.getAttribute("data-week")
        if week:
            self._show_week(int(week))

    def _fuel_card(self):
        card = Layout.html(FUEL_CARD)
        row = self.model["current_row"] or {}
        card.dom_nodes["subtitle"].textContent = "This week's target · %s phase" % Format.phase(row.get("phase"))
        card.dom_nodes["macros"].innerHTML = View.macros_html(row)
        ring = fuel_ring_options(row)
        if ring:
            card.add_component(_chart(ring, "180px"), slot="ring")
        card.add_component(_chart(calorie_plan_options(self.model), "150px"), slot="kcal")
        return card

    def _comp_card(self):
        card = Layout.html(COMP_CARD)
        card.add_component(_chart(composition_options(self.model, "fat"), "280px"), slot="fat")
        card.add_component(_chart(composition_options(self.model, "lean"), "280px"), slot="lean")
        card.dom_nodes["side"].innerHTML = View.composition_side_html(self.model)
        return card

    def _open_tracker(self, **event_args):
        Layout.navigate("tracker")

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
