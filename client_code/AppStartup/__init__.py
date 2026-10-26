from ._anvil_designer import AppStartupTemplate
from anvil import *
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files
from craftify_library.CraftifyLoginForm import CraftifyLoginForm
from craftify_library.CraftifyRouting import navigate


def _open_login():
    navigate(path="/login")


class AppStartup(AppStartupTemplate):
    def __init__(self, routing_context=None, **properties):
        self.init_components(**properties)
        self.panel.clear()
        self.panel.add_component(
            CraftifyLoginForm(
                redirect_path="/",
                brand_text="Body Comp",
                brand_sub="Cut · reverse · bulk",
                copyright="© Body Comp",
                allow_signup=True,
                allow_google=True,
            ),
            full_width_row=True,
        )
