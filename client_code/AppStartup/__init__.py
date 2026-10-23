from ._anvil_designer import AppStartupTemplate
from anvil import *
import anvil.server

# Personal app: no login screen — server creates or reuses one local account.


class AppStartup(AppStartupTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._route()

    def form_show(self, **event_args):
        self._route()

    def _route(self):
        self.panel.clear()
        try:
            state = anvil.server.call("bodycomp_startup")
        except Exception as e:
            self.panel.add_component(
                Label(
                    text=f"Could not start your session: {e}",
                    foreground="theme:Error",
                    font_size=14,
                ),
                full_width_row=True,
            )
            return
        if not state.get("has_plan"):
            open_form("CoachShell", page="profile")
        else:
            open_form("CoachShell", page="dashboard")
