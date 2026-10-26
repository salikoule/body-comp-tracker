from ._anvil_designer import CoachShellTemplate
from anvil import *
from routing import router
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
import anvil.users
from craftify_library.Startup import configure as configure_craftify_client
from craftify_library.CustomComponents.AccountMenu import AccountMenu
from craftify_library.CraftifyRouting import NavLink, add_event_handler, navigate
from body_comp_tracker import Layout

NAV = (
    ("Dashboard", "/", "fa:chart-pie"),
    ("Weekly tracker", "/tracker", "fa:table-list"),
    ("Progress", "/progress", "fa:chart-line"),
    ("Check-in", "/checkin", "fa:clipboard-check"),
    ("Plan summary", "/plan", "fa:route"),
    ("Profile & plan", "/profile", "fa:user-pen"),
)

BRAND = (
    '<div class="bc-brand">'
    '<div class="bc-brand-mark">BC</div>'
    '<div class="bc-brand-text"><strong>Body Comp</strong><span>Cut · reverse · bulk</span></div>'
    "</div>"
)


class CoachShell(CoachShellTemplate):
    def __init__(self, routing_context=None, **properties):
        self.init_components(**properties)
        configure_craftify_client()
        self._links = {}
        self._build_nav()
        self._build_footer()
        add_event_handler("navigate", self._on_router_navigate)

    def _build_nav(self):
        self.menu_panel.clear()
        self.menu_panel.add_component(Layout.html(BRAND), full_width_row=True)
        for text, path, icon in NAV:
            link = NavLink(
                text=text,
                path=path,
                icon=icon,
                foreground="#1e3a5f",
                align="left",
                icon_align="left",
                font_size=13,
                spacing_above="none",
                spacing_below="none",
            )
            self._links[path] = link
            self.menu_panel.add_component(link)

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

    def _on_router_navigate(self, **event_args):
        for link in self._links.values():
            active = bool(getattr(link, "active", False))
            link.role = "bc-nav-current" if active else None
            link.background = "#e8f1fb" if active else ""
            link.bold = active
