from ._anvil_designer import CoachShellTemplate
from anvil import *
from craftify_library.Startup import configure as configure_craftify_client
from body_comp_tracker.CheckInForm import CheckInForm
from body_comp_tracker.HomeForm import HomeForm
from body_comp_tracker.PlanForm import PlanForm
from body_comp_tracker.ProfileForm import ProfileForm
from body_comp_tracker.ProgressForm import ProgressForm
from body_comp_tracker.TrackerForm import TrackerForm


class CoachShell(CoachShellTemplate):
    def __init__(self, page="dashboard", **properties):
        self.init_components(**properties)
        configure_craftify_client()
        self._page = page or "dashboard"
        self._build_nav()
        self._show_page()

    def _build_nav(self):
        self.nav_panel.clear()
        self.nav_panel.add_component(Label(text="Body composition", role="coach-brand"))
        self.nav_panel.add_component(Label(text="Cut, reverse diet, bulk", role="coach-brand-sub"))
        groups = (
            ("Track", (("Dashboard", "dashboard", self._open_dashboard), ("Weekly tracker", "tracker", self._open_tracker), ("Progress", "progress", self._open_progress))),
            ("Plan", (("Plan summary", "plan", self._open_plan), ("Check-in", "checkin", self._open_checkin))),
            ("You", (("Profile & plan", "profile", self._open_profile),)),
        )
        for title, items in groups:
            self.nav_panel.add_component(Label(text=title, role="coach-nav-group"))
            for label, page, handler in items:
                role = "coach-nav-current" if page == self._page else "coach-nav-link"
                button = Button(text=label, role=role)
                button.set_event_handler("click", handler)
                self.nav_panel.add_component(button)

    def _show_page(self):
        self.main_panel.clear()
        page = self._page
        if page == "tracker":
            form = TrackerForm()
        elif page == "progress":
            form = ProgressForm()
        elif page == "plan":
            form = PlanForm()
        elif page == "checkin":
            form = CheckInForm()
        elif page == "profile":
            form = ProfileForm()
        else:
            form = HomeForm()
        self.main_panel.add_component(form)

    def _open_dashboard(self, **event_args):
        open_form("CoachShell", page="dashboard")

    def _open_tracker(self, **event_args):
        open_form("CoachShell", page="tracker")

    def _open_progress(self, **event_args):
        open_form("CoachShell", page="progress")

    def _open_plan(self, **event_args):
        open_form("CoachShell", page="plan")

    def _open_checkin(self, **event_args):
        open_form("CoachShell", page="checkin")

    def _open_profile(self, **event_args):
        open_form("CoachShell", page="profile")
