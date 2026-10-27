from ._anvil_designer import CoachShellTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
import anvil.users
from craftify_library.Startup import configure as configure_craftify_client
from craftify_library.CustomComponents.AccountMenu import AccountMenu
from craftify_library.CustomComponents.SettingsOverlay import SettingsOverlay
from craftify_library.CraftifyRouting import NavLink, add_event_handler, get_routing_context, navigate
from body_comp_tracker import Layout
from body_comp_tracker.PlanForm import PlanForm
from body_comp_tracker.ProfileForm import ProfileForm

NAV = (
    ("Dashboard", "/dashboard", "fa:chart-pie", True),
    ("Weekly tracker", "/tracker", "fa:table-list", True),
    ("Progress", "/progress", "fa:chart-line", True),
    ("Check-in", "/checkin", "fa:clipboard-check", False),
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
        self._build_settings()
        add_event_handler("navigate", self._on_router_navigate)
        self._maybe_open_from_query(routing_context)

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
        menu.set_event_handler("settings_click", self._on_settings)
        menu.set_event_handler("logout_click", self._on_logout)
        self.footer_panel.add_component(menu, full_width_row=True)

    def _build_settings(self):
        self._settings = SettingsOverlay(
            app_name="Body Comp",
            app_version="1.0",
            app_description="Cut · reverse · bulk coach.",
            default_section="profile",
            extra_sections=(
                {"id": "plan", "label": "Plan summary", "build": lambda: PlanForm(compact=True)},
                {"id": "profile", "label": "Profile & plan", "build": lambda: ProfileForm(compact=True)},
            ),
        )
        self.add_component(self._settings)

    def open_settings(self, section=None):
        if section in (None, "", "settings"):
            section = "profile"
        self._settings.open(section)

    def close_settings(self):
        self._settings.close()

    def _on_settings(self, section=None, **event_args):
        self.open_settings(section or event_args.get("section"))

    def _on_logout(self, **event_args):
        try:
            anvil.users.logout()
        except Exception:
            pass
        navigate(path="/login")

    def _on_router_navigate(self, routing_context=None, **event_args):
        self._maybe_open_from_query(routing_context)

    def _maybe_open_from_query(self, routing_context=None):
        ctx = routing_context
        if ctx is None:
            try:
                ctx = get_routing_context()
            except Exception:
                ctx = None
        query = getattr(ctx, "query", None) or {}
        section = query.get("settings")
        if section:
            self.open_settings(section)
        elif getattr(self, "_settings", None) is not None:
            self.close_settings()
