import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from app import create_app
from auth import write_users
from flask.testing import FlaskClient
from werkzeug.security import generate_password_hash


TEST_EMAIL = "tester@example.test"
TEST_PASSWORD = "test-password-123"
TEST_HASH = generate_password_hash(TEST_PASSWORD)


class AuthenticatedClient(FlaskClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        super().open("/login")
        with self.session_transaction() as state:
            token = state["csrf_token"]
        response = super().open("/login", method="POST", data={"email": TEST_EMAIL, "password": TEST_PASSWORD, "csrf_token": token})
        if response.status_code != 302:
            raise AssertionError(f"Test login failed: {response.status_code}")

    def open(self, *args, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        with self.session_transaction() as state:
            headers.setdefault("X-CSRF-Token", state.get("csrf_token", ""))
        return super().open(*args, headers=headers, **kwargs)


def load_test_plan():
    return json.loads((Path(__file__).parent / "tests/fixtures/plan.json").read_text(encoding="utf-8"))


def legacy_test_ships():
    plan = load_test_plan()
    for ship in plan["ships"]:
        service = next(service for service in plan["services"] if service["id"] == ship["serviceId"])
        ship["proformas"] = []
        for assignment in ship.pop("proformaAssignments"):
            version = deepcopy(next(version for version in service["proformas"] if version["id"] == assignment["proformaId"]))
            version.update(id="initial", name=f"Proforma {assignment['validFrom'][:4]}")
            for stop in version["stops"]:
                stop["id"] = f"{ship['id']}-{stop['portId']}"
                for field in ("arrival", "departure"):
                    stop[field] = (datetime.fromisoformat(stop[field]) + timedelta(weeks=assignment["offsetWeeks"])).isoformat(timespec="minutes")
            ship["proformas"].append(version)
    return plan["ships"]


def create_test_app(data_root, plugin_root=None):
    root = Path(data_root)
    if not (root / "ports.json").exists():
        plan = load_test_plan()
        for name in ("ports", "services"):
            (root / f"{name}.json").write_text(json.dumps(plan[name]), encoding="utf-8")
        (root / "ships").mkdir()
        for ship in plan["ships"]:
            (root / "ships" / f"{ship['id']}.json").write_text(json.dumps(ship), encoding="utf-8")
    auth_root = root / "auth"
    if not (auth_root / "users.json").exists():
        write_users(auth_root / "users.json", [{"email": TEST_EMAIL, "passwordHash": TEST_HASH}])
    app = create_app(data_root, auth_root=auth_root, plugin_root=plugin_root)
    app.test_client_class = AuthenticatedClient
    return app
