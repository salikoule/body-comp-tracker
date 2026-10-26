from ._anvil_designer import PlanFormTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
from craftify_library.CustomComponents.KpiCard import KpiCard
from body_comp_tracker import Format, Layout

RULES = (
    "Cut rate defaults to 0.5% of body weight per week.",
    "Bulk rate defaults to 0.25% of body weight per week.",
    "From week 5 the trend compares 3-week rolling averages. Losing faster than 150% of target adds 100 kcal; two slow check-ins in a row remove 100 kcal.",
    "Reverse diet: one third of the gap to maintenance for two weeks, then full maintenance.",
    "Protein 2.2 g/kg on a cut, 1.9 g/kg on a bulk. Fat is 25% of calories. Carbs fill the rest.",
    "Sunday check-in records waist, neck, sessions, steps, training feel, adherence, and notes.",
)


class PlanForm(PlanFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        s = anvil.server.call("bodycomp_get_plan")
        if not s.get("has_plan"):
            self.add_component(
                Layout.stack(
                    Layout.page_header("Plan summary"),
                    Layout.empty_state("Save your profile to see the plan.", "Set up plan", self._open_profile),
                ),
                full_width_row=True,
            )
            return
        header = Layout.page_header(
            "Plan summary",
            eyebrow=Format.eyebrow(s),
            description="Phase dates, energy targets, and the coaching rules that adjust calories each Sunday.",
            actions=(Layout.button("Edit profile", self._open_profile),),
        )
        kpis = Layout.grid(
            "repeat(auto-fit, minmax(170px, 1fr))",
            KpiCard(title="RMR (DEXA)" if s.get("bmr_source") == "dexa_rmr" else "BMR",
                    value=Format.number(s.get("bmr"), 0, "kcal"), subtitle="Energy at rest"),
            KpiCard(title="TDEE", value=Format.number(s.get("tdee"), 0, "kcal"), subtitle="Maintenance estimate"),
            KpiCard(title="Weekly rate", value=Format.number(s.get("weekly_rate_kg"), 2, "kg"), subtitle="Planned change per week"),
            KpiCard(title="Forecast finish", value=Format.date_label(s.get("forecast_end")), subtitle="End of current plan"),
        )
        phases = []
        for phase in s.get("phases") or []:
            name = phase.get("name") or ""
            phases.append(Layout.html(
                '<div class="bc-phase%s"><span class="bc-pill bc-pill-%s">%s</span>'
                '<p class="bc-phase-dates">%s – %s</p>'
                '<p class="bc-phase-kcal">%s</p>'
                '<p class="bc-phase-summary">%s</p></div>'
                % (
                    " is-current" if name == s.get("phase") else "",
                    Layout.esc(name),
                    Layout.esc(Format.phase(name)),
                    Layout.esc(Format.date_label(phase.get("start"))),
                    Layout.esc(Format.date_label(phase.get("end")) if phase.get("end") else "open"),
                    Layout.esc(Format.number(phase.get("calories"), 0, "kcal")),
                    Layout.esc(phase.get("summary") or ""),
                )
            ))
        phase_card = Layout.section("Phases", "The current phase is outlined.")
        Layout.body(phase_card, Layout.grid("repeat(auto-fit, minmax(220px, 1fr))", *phases))

        start = Layout.section("Starting point", "From your profile measurements.")
        Layout.body(start, Layout.definition_list((
            ("Weight", "%s → %s" % (Format.number(s.get("start_weight_kg"), 1, "kg"), Format.number(s.get("target_weight_kg"), 1, "kg"))),
            ("Body fat", "%s → %s" % (Format.percent(s.get("bf_percent")), Format.percent(s.get("target_bf_percent")))),
            ("Training", "%s days · %s steps" % (s.get("training_days") or "—", Format.number(s.get("daily_steps")))),
            ("Plan start", Format.date_label(s.get("start_date"))),
        )))

        rules = Layout.section("Adaptive rules", "How the coach changes calories after each check-in.")
        Layout.body(rules, Layout.html(
            '<ul class="bc-rules">%s</ul>' % "".join("<li>%s</li>" % Layout.esc(rule) for rule in RULES)
        ))
        self.add_component(
            Layout.stack(header, kpis, phase_card, Layout.grid("minmax(0, 1fr) minmax(0, 1.3fr)", start, rules)),
            full_width_row=True,
        )

    def _open_profile(self, **event_args):
        Layout.navigate("profile")
