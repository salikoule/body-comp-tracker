from ._anvil_designer import AppStartupTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
import anvil.server
from craftify_library.CraftifyLoginForm import CraftifyLoginForm


def _open_login():
    open_form(
        CraftifyLoginForm(
            redirect_form="AppStartup",
            brand_text="Body Comp",
            brand_sub="Cut · reverse · bulk",
            copyright="© Body Comp",
            allow_signup=True,
        )
    )


class AppStartup(AppStartupTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._routed = False
        self._route()

    def form_show(self, **event_args):
        if self._routed:
            return
        self._route()

    def _route(self):
        if self._routed:
            return
        self._routed = True
        self.panel.clear()
        try:
            state = anvil.server.call("bodycomp_startup")
        except Exception as e:
            self.panel.add_component(
                Label(
                    text="Could not start your session: %s" % e,
                    foreground="theme:Error",
                    font_size=14,
                ),
                full_width_row=True,
            )
            return
        if not state or state.get("logged_in") is False:
            _open_login()
            return
        page = "dashboard" if state.get("has_plan") else "profile"
        open_form("CoachShell", page=page, email=state.get("email") or "")
