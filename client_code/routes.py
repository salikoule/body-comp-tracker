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
            raise Redirect(path="/dashboard")


class RootRoute(Route):
    path = "/"

    def before_load(self, **loader_args):
        if anvil.users.get_user() is None:
            raise Redirect(path="/login")
        raise Redirect(path="/dashboard")


class DashboardRoute(AppPage):
    path = "/dashboard"
    form = "HomeForm"

    def before_load(self, **loader_args):
        super().before_load(**loader_args)
        try:
            state = anvil.server.call("bodycomp_startup")
        except Exception:
            return
        if state.get("logged_in") is False:
            raise Redirect(path="/login")


class TrackerRoute(AppPage):
    path = "/tracker"
    form = "TrackerForm"


class ProgressRoute(AppPage):
    path = "/progress"
    form = "ProgressForm"


class DexaRoute(AppPage):
    path = "/dexa"
    form = "DexaForm"


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


class PlanRoute(Route):
    path = "/plan"

    def before_load(self, **loader_args):
        if anvil.users.get_user() is None:
            raise Redirect(path="/login")
        raise Redirect(path="/dashboard", query={"settings": "plan"})


class ProfileRoute(Route):
    path = "/profile"

    def before_load(self, **loader_args):
        if anvil.users.get_user() is None:
            raise Redirect(path="/login")
        raise Redirect(path="/dashboard", query={"settings": "profile"})
