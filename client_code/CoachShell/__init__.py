from ._anvil_designer import CoachShellTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
import anvil.users
from craftify_library.Startup import configure as configure_craftify_client
from craftify_library.CustomComponents.AccountMenu import AccountMenu
from body_comp_tracker import Layout
from body_comp_tracker.AppStartup import _open_login
from body_comp_tracker.CheckInForm import CheckInForm
from body_comp_tracker.HomeForm import HomeForm
from body_comp_tracker.PlanForm import PlanForm
from body_comp_tracker.ProfileForm import ProfileForm
from body_comp_tracker.ProgressForm import ProgressForm
from body_comp_tracker.TrackerForm import TrackerForm

NAV = (
    ("Dashboard", "dashboard", "fa:chart-pie"),
    ("Weekly tracker", "tracker", "fa:table-list"),
    ("Progress", "progress", "fa:chart-line"),
    ("Check-in", "checkin", "fa:clipboard-check"),
    ("Plan summary", "plan", "fa:route"),
    ("Profile & plan", "profile", "fa:user-pen"),
)

PAGES = {
    "dashboard": HomeForm,
    "tracker": TrackerForm,
    "progress": ProgressForm,
    "checkin": CheckInForm,
    "plan": PlanForm,
    "profile": ProfileForm,
}

BRAND = (
    '<div class="bc-brand">'
    '<div class="bc-brand-mark">BC</div>'
    '<div class="bc-brand-text"><strong>Body Comp</strong><span>Cut · reverse · bulk</span></div>'
    "</div>"
)


class CoachShell(CoachShellTemplate):
    def __init__(self, page="dashboard", email="", **properties):
        self.init_components(**properties)
        configure_craftify_client()
        self._links = {}
        self._build_nav()
        self._build_footer(email)
        self.navigate(page or "dashboard")

    def _build_nav(self):
        self.menu_panel.clear()
        self.menu_panel.add_component(Layout.html(BRAND), full_width_row=True)
        for text, page, icon in NAV:
            link = Link(
                text=text,
                icon=icon,
                foreground="#1e3a5f",
                align="left",
                icon_align="left",
                font_size=13,
                spacing_above="none",
                spacing_below="none",
            )
            link.tag.page = page
            link.set_event_handler("click", self._nav_click)
            self._links[page] = link
            self.menu_panel.add_component(link)

    def _build_footer(self, email):
        if not email:
            try:
                email = anvil.server.call("craftify_current_user_email") or ""
            except Exception:
                email = ""
        self.footer_panel.clear()
        menu = AccountMenu(email=email or "")
        menu.set_event_handler("profile_click", self._on_profile)
        menu.set_event_handler("logout_click", self._on_logout)
        self.footer_panel.add_component(menu, full_width_row=True)

    def _on_profile(self, **event_args):
        self.navigate("profile")

    def _on_logout(self, **event_args):
        try:
            anvil.users.logout()
        except Exception:
            pass
        _open_login()

    def _nav_click(self, **event_args):
        self.navigate(event_args["sender"].tag.page)

    def _style_links(self, current):
        for page, link in self._links.items():
            link.role = "bc-nav-current" if page == current else None
            link.background = "#e8f1fb" if page == current else ""
            link.bold = page == current

    def navigate(self, page):
        if page not in PAGES:
            page = "dashboard"
        self._page = page
        self._style_links(page)
        self.content_panel.clear()
        self.content_panel.add_component(PAGES[page](), full_width_row=True)
        try:
            from anvil.js import window
            window.scrollTo(0, 0)
        except Exception:
            pass
