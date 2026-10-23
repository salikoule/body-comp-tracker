from ._anvil_designer import LoginFormTemplate
from anvil import *
import anvil.users


class LoginForm(LoginFormTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.login_btn.set_event_handler("click", self.login_btn_click)
        self.signup_btn.set_event_handler("click", self.signup_btn_click)

    def login_btn_click(self, **event_args):
        self.error_label.visible = False
        try:
            anvil.users.login_with_email(self.email_box.text.strip(), self.password_box.text)
        except anvil.users.AuthenticationFailed as e:
            self.error_label.text = str(e)
            self.error_label.visible = True
            return
        open_form("AppStartup")

    def signup_btn_click(self, **event_args):
        self.error_label.visible = False
        try:
            anvil.users.sign_up(self.email_box.text.strip(), self.password_box.text)
        except anvil.users.AuthenticationFailed as e:
            self.error_label.text = str(e)
            self.error_label.visible = True
            return
        open_form("AppStartup")
