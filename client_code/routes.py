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


class WeightsRoute(AppPage):
    path = "/weights"
    form = "WeightsForm"


class ProgressRoute(AppPage):
    path = "/progress"
    form = "ProgressForm"


class DexaRoute(AppPage):
    path = "/dexa"
    form = "DexaForm"


class CheckInRoute(Route):
    path = "/checkin"

    def before_load(self, **loader_args):
        raise Redirect(path="/tracker", query={"checkin": "current"})


class CheckInWeekRoute(Route):
    path = "/checkin/:week"

    def before_load(self, **loader_args):
        week = (loader_args.get("params") or {}).get("week") or "current"
        raise Redirect(path="/tracker", query={"checkin": week})


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
