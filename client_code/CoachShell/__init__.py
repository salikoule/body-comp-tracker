from ._anvil_designer import CoachShellTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
import anvil.users
from craftify_library.Startup import configure as configure_craftify_client
from craftify_library.CustomComponents.AccountMenu import AccountMenu
from craftify_library.CraftifyRouting import NavLink, navigate
from body_comp_tracker import Layout

NAV = (
    ("Dashboard", "/dashboard", "fa:chart-pie", True),
    ("Weekly tracker", "/tracker", "fa:table-list", True),
    ("Progress", "/progress", "fa:chart-line", True),
    ("Check-in", "/checkin", "fa:clipboard-check", False),
    ("Plan summary", "/plan", "fa:route", True),
    ("Profile & plan", "/profile", "fa:user-pen", True),
)

BRAND = (
    '<div class="nav-brand bc-brand">'
    '<div class="nav-brand-mark bc-brand-mark">BC</div>'
    '<div class="nav-brand-text bc-brand-text"><strong>Body Comp</strong><span>Cut · reverse · bulk</span></div>'
    "</div>"
)


class CoachShell(CoachShellTemplate):
    def __init__(self, routing_context=None, **properties):
        self.init_components(**properties)
        configure_craftify_client()
        self._build_nav()
        self._build_footer()

    def _build_nav(self):
        self.menu_panel.clear()
        self.menu_panel.add_component(Layout.html(BRAND), full_width_row=True)
        for text, path, icon, exact_path in NAV:
            self.menu_panel.add_component(
                NavLink(
                    text=text,
                    path=path,
                    icon=icon,
                    exact_path=exact_path,
                    foreground="#1e3a5f",
                    align="left",
                    icon_align="left",
                    font_size=13,
                    spacing_above="none",
                    spacing_below="none",
                )
            )

    def _build_footer(self):
        email = ""
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
        navigate(path="/profile")

    def _on_logout(self, **event_args):
        try:
            anvil.users.logout()
        except Exception:
            pass
        navigate(path="/login")
