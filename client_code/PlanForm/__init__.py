from ._anvil_designer import PlanFormTemplate
from anvil import *
import anvil.server

PHASE = {"cut": "Cut", "reverse": "Reverse diet", "bulk": "Bulk", "recomp": "Recomp"}
RULES = (
    "Cut rate defaults to 0.5% of body weight per week.",
    "Bulk rate defaults to 0.25% per week.",
    "From week 5, trend compares 3-week rolling averages. Faster loss than 150% of target adds 100 kcal; two slow check-ins subtract 100 kcal.",
    "Reverse diet: one third of the gap to maintenance for two weeks, then full maintenance.",
    "Protein 2.2 g/kg on a cut, 1.9 g/kg on a bulk. Fat is 25%. Carbs fill the rest.",
    "Sunday check-in records waist, neck, sessions, steps, feel, adherence, and notes.",
)


class PlanForm(PlanFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        state = anvil.server.call("bodycomp_get_plan")
        if not state.get("has_plan"):
            self.body.add_component(Label(text="Save a profile to see the plan.", role="coach-note"))
            return
        stats = FlowPanel(role="coach-grid")
        bmr_label = "RMR (DEXA)" if state.get("bmr_source") == "dexa_rmr" else "BMR"
        for label, value in (
            (bmr_label, "%s kcal" % (state.get("bmr") or "—")),
            ("TDEE", "%s kcal" % (state.get("tdee") or "—")),
            ("Weekly rate", "%s kg" % (state.get("weekly_rate_kg") or "—")),
        ):
            box = ColumnPanel(role="coach-card", spacing="none")
            box.add_component(Label(text=label, role="coach-label"))
            box.add_component(Label(text=str(value), role="coach-section"))
            stats.add_component(box, width=200)
        self.body.add_component(stats, full_width_row=True)
        self.body.add_component(Spacer(height=12))
        for phase in state.get("phases") or []:
            card = ColumnPanel(role="coach-card", spacing="none")
            name = PHASE.get(phase.get("name"), phase.get("name") or "")
            card.add_component(Label(text=name, role="coach-section"))
            card.add_component(Label(text="%s → %s" % (phase.get("start") or "—", phase.get("end") or "open"), role="coach-note"))
            card.add_component(Label(text="%s kcal · %s" % (phase.get("calories") or "—", phase.get("summary") or ""), role="coach-note"))
            self.body.add_component(card, full_width_row=True)
            self.body.add_component(Spacer(height=8))
        start = ColumnPanel(role="coach-card", spacing="none")
        start.add_component(Label(text="Starting point", role="coach-section"))
        start.add_component(Label(
            text="Weight %s kg → %s kg. Body fat %s%% → %s%%. Training %s days · %s steps. Forecast %s." % (
                state.get("start_weight_kg"),
                ("%.1f" % float(state.get("target_weight_kg"))) if state.get("target_weight_kg") is not None else "—",
                state.get("bf_percent"),
                state.get("target_bf_percent"),
                state.get("training_days"),
                state.get("daily_steps"),
                state.get("forecast_end") or "—",
            ),
            role="coach-note",
        ))
        self.body.add_component(start, full_width_row=True)
        rules = ColumnPanel(role="coach-card", spacing="none")
        rules.add_component(Label(text="Adaptive rules", role="coach-section"))
        for rule in RULES:
            rules.add_component(Label(text=rule, role="coach-note"))
        self.body.add_component(Spacer(height=8))
        self.body.add_component(rules, full_width_row=True)
