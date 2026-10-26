from routing import router
import anvil.server
import anvil.users
from craftify_library.CraftifyRouting import AuthenticatedShellRoute, Redirect, Route


class AppPage(AuthenticatedShellRoute):
    template = "CoachShell"
    login_path = "/login"


class LoginRoute(Route):
    path = "/login"
    form = "AppStartup"

    def before_load(self, **loader_args):
        if anvil.users.get_user() is not None:
            raise Redirect(path="/")


class DashboardRoute(AppPage):
    path = "/"
    form = "HomeForm"

    def before_load(self, **loader_args):
        super().before_load(**loader_args)
        try:
            state = anvil.server.call("bodycomp_startup")
        except Exception:
            return
        if state.get("logged_in") is False:
            raise Redirect(path="/login")
        if not state.get("has_plan"):
            raise Redirect(path="/profile")


class TrackerRoute(AppPage):
    path = "/tracker"
    form = "TrackerForm"


class ProgressRoute(AppPage):
    path = "/progress"
    form = "ProgressForm"


class CheckInRoute(AppPage):
    path = "/checkin"
    form = "CheckInForm"


class CheckInWeekRoute(AppPage):
    path = "/checkin/:week"
    form = "CheckInForm"

    def parse_params(self, params):
        week = params.get("week")
        try:
            return {"week": int(week)}
        except (TypeError, ValueError):
            return {"week": week}


class PlanRoute(AppPage):
    path = "/plan"
    form = "PlanForm"


class ProfileRoute(AppPage):
    path = "/profile"
    form = "ProfileForm"
