import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent

sys.path.insert(0, str(WORKSPACE / "craftify-library" / "server_code"))
sys.path.insert(0, str(ROOT / "server_code"))


def _stub_anvil():
    if "anvil.server" in sys.modules:
        return
    anvil = ModuleType("anvil")
    anvil.server = ModuleType("anvil.server")
    anvil.users = ModuleType("anvil.users")
    anvil.tables = ModuleType("anvil.tables")
    anvil.tables.app_tables = ModuleType("app_tables")
    sys.modules["anvil"] = anvil
    sys.modules["anvil.server"] = anvil.server
    sys.modules["anvil.users"] = anvil.users
    sys.modules["anvil.tables"] = anvil.tables


def _stub_routing():
    if "routing" in sys.modules:
        return
    routing = ModuleType("routing")
    routing.router = ModuleType("routing.router")
    sys.modules["routing"] = routing
    sys.modules["routing.router"] = routing.router


_stub_anvil()
_stub_routing()
