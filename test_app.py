import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from app import create_app
from planning import resolve_voyage


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = create_app(self.directory.name)
        self.client = self.app.test_client()
        self.plan = self.client.get("/api/plan").get_json()

    def test_example_dates_and_atomic_save(self):
        self.assertEqual(len(self.plan["ships"]), 7)
        self.assertEqual(self.plan["ships"][0]["proformas"][0]["stops"][0]["arrival"], "2027-01-16T11:00")
        self.assertEqual(self.plan["ships"][1]["proformas"][0]["stops"][0]["arrival"], "2027-01-23T11:00")
        self.assertEqual(self.plan["ships"][0]["proformas"][0]["stops"][1]["transitMinutes"], 2220)
        response = self.save_candidate(self.plan)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["revision"], self.plan["revision"] + 1)
        self.assertEqual(self.save_candidate(self.plan).status_code, 409)

    def test_invalid_plans_leave_saved_data_untouched(self):
        for field, value in [("berth", 99), ("departure", "2027-01-01T00:00"), ("transitMinutes", -1)]:
            with self.subTest(field=field):
                candidate = deepcopy(self.plan)
                stops = self.make_actual(candidate, 0, "2027-01-16")
                stops[0][field] = value
                self.assertEqual(self.save_candidate(candidate).status_code, 400)
        self.assertEqual(self.client.get("/api/plan").get_json(), self.plan)

    def test_berth_conflict_and_impossible_transit(self):
        candidate = deepcopy(self.plan)
        stops = self.make_actual(candidate, 1, "2027-01-23")
        stops[0].update({key: self.plan["ships"][0]["proformas"][0]["stops"][0][key] for key in ("arrival", "departure", "berth")})
        self.assertIn("Liegeplatzkonflikt", self.save_candidate(candidate, "berlin").get_json()["error"])
        candidate = deepcopy(self.plan)
        self.make_actual(candidate, 0, "2027-01-16")[1]["arrival"] = "2027-01-18T04:00"
        self.assertEqual(self.save_candidate(candidate).status_code, 400)

    def test_speed_config_is_exposed_and_planned_duration_is_independent(self):
        self.assertNotIn("navigation", self.plan)
        self.assertEqual(self.plan["ports"][0]["distancesNm"]["hamburg"], 100)
        self.assertEqual(self.plan["ships"][0]["maxSpeedKnots"], 20)
        self.assertFalse((Path(self.directory.name) / "navigation.json").exists())
        candidate = deepcopy(self.plan)
        self.make_actual(candidate, 0, "2027-01-16")[1]["transitMinutes"] = 99999
        self.assertEqual(self.save_candidate(candidate).status_code, 200)

    def test_services_and_independent_repeated_voyage(self):
        busan = self.plan["ships"][0]
        self.assertEqual(busan["serviceId"], "NE2")
        self.assertTrue(all(stop["berth"] == 1 for ship in self.plan["ships"][:6] for stop in ship["proformas"][0]["stops"]))
        repeated = resolve_voyage(busan, "2027-04-24")["stops"]
        self.assertEqual(repeated[0]["arrival"], "2027-04-24T11:00")
        candidate = deepcopy(self.plan)
        candidate["ships"][0]["voyages"]["2027-04-24"] = {"proformaId": "initial", "stops": repeated}
        repeated[1]["berth"] = 3
        response = self.save_candidate(candidate)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["ships"][0]["proformas"][0]["stops"][0]["berth"], 1)

    def test_mathilde_is_corrected_and_invalid_actual_cannot_be_saved(self):
        mathilde = self.plan["ships"][-1]
        self.assertEqual(mathilde["proformas"][0]["stops"][3]["arrival"], "2027-01-26T11:00")
        candidate = deepcopy(self.plan)
        self.make_actual(candidate, -1, "2027-01-16")[3]["arrival"] = "2027-01-15T11:00"
        self.assertEqual(self.save_candidate(candidate, "mathilde").status_code, 400)

    def test_named_view_persistence(self):
        config = {"collapsed": ["hamburg"], "hiddenBerths": ["london:4"], "dayWidth": 64,
                  "voyageDate": "2027-04-24", "start": "2027-04-22T00:00", "end": "2027-10-21T00:00", "selected": "busan", "compareProforma": True, "scrollLeft": 60, "scrollTop": 90}
        self.assertEqual(self.client.put("/api/views", json={"name": "Meine Ansicht", "config": config}).status_code, 200)
        self.assertEqual(self.client.get("/api/views").get_json()["Meine Ansicht"], config)
        config["hiddenBerths"] = ["london:99"]
        self.assertEqual(self.client.put("/api/views", json={"name": "Falsch", "config": config}).status_code, 400)

    def test_view_end_cannot_precede_start(self):
        config = {"collapsed": [], "hiddenBerths": [], "dayWidth": 64,
                  "start": "2027-04-22T00:00", "end": "2027-04-21T00:00", "selected": "busan", "scrollLeft": 0, "scrollTop": 0}
        self.assertEqual(self.client.put("/api/views", json={"name": "Falsch", "config": config}).status_code, 400)

    def test_voyage_cannot_overlap_its_next_repetition(self):
        candidate = deepcopy(self.plan)
        for stop in self.make_actual(candidate, 0, "2027-01-16"):
            for field in ("arrival", "departure"):
                stop[field] = (datetime.fromisoformat(stop[field]) + timedelta(days=106)).isoformat(timespec="minutes")
        response = self.save_candidate(candidate)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Folgereise", response.get_json()["error"])

    def make_actual(self, plan, index, date):
        ship = plan["ships"][index]
        voyage = resolve_voyage(ship, date)
        ship["voyages"][voyage["key"]] = {"proformaId": voyage["proformaId"], "stops": voyage["stops"]}
        return ship["voyages"][voyage["key"]]["stops"]

    def test_individual_files_and_restart(self):
        manifest = json.loads((Path(self.directory.name) / "schedules.json").read_text())
        self.assertEqual(len(manifest["shipFiles"]), 7)
        self.assertTrue(all((Path(self.directory.name) / path).is_file() for path in manifest["shipFiles"].values()))
        other = create_app(self.directory.name).test_client()
        self.assertEqual(other.get("/api/plan").get_json(), self.plan)

    def save_candidate(self, plan, ship_id="busan"):
        ship = next(ship for ship in plan["ships"] if ship["id"] == ship_id)
        return self.client.put(f"/api/ships/{ship_id}/plan", json={"revision": plan["revision"], "ship": ship, "mode": plan.get("mode", "planning")})

    def test_only_selected_ship_is_saved(self):
        candidate = deepcopy(self.plan)
        self.make_actual(candidate, 0, "2027-01-16")[1]["berth"] = 3
        self.make_actual(candidate, 1, "2027-01-23")[1]["berth"] = 4
        response = self.save_candidate(candidate)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(resolve_voyage(response.get_json()["ships"][0], "2027-01-16")["stops"][1]["berth"], 3)
        self.assertEqual(response.get_json()["ships"][1], self.plan["ships"][1])
        candidate["revision"] = response.get_json()["revision"]
        self.assertEqual(self.save_candidate(candidate, "berlin").status_code, 200)

    def test_planning_cannot_modify_proformas(self):
        candidate = deepcopy(self.plan)
        candidate["ships"][0]["proformas"][0]["name"] = "Andere Version"
        self.assertEqual(self.save_candidate(candidate).status_code, 400)

    def test_proforma_mode_and_batch_save_are_disabled(self):
        candidate = deepcopy(self.plan)
        candidate["mode"] = "proformas"
        self.assertEqual(self.save_candidate(candidate).status_code, 400)
        self.assertEqual(self.client.put("/api/plan", json=candidate).status_code, 405)

    def test_no_new_plan_version_files_are_created(self):
        candidate = deepcopy(self.plan)
        self.make_actual(candidate, 0, "2027-01-16")[1]["berth"] = 3
        self.assertEqual(self.save_candidate(candidate).status_code, 200)
        files = list((Path(self.directory.name) / "ships").glob("**/*.json"))
        self.assertEqual(len(files), 7)
        self.assertTrue((Path(self.directory.name) / "ships/busan.json").is_file())

    def test_external_edits_and_new_ship_are_loaded_without_restart(self):
        root = Path(self.directory.name)
        ship = deepcopy(self.plan["ships"][0])
        ship["maxSpeedKnots"] = 15
        (root / "ships/busan.json").write_text(json.dumps(ship), encoding="utf-8")
        ports = deepcopy(self.plan["ports"])
        ports[0]["distancesNm"]["hamburg"] = 150
        (root / "ports.json").write_text(json.dumps(ports), encoding="utf-8")
        new_ship = deepcopy(ship)
        new_ship.update(id="new-vessel", name="New Vessel", serviceId="NEW")
        (root / "ships/new-vessel.json").write_text(json.dumps(new_ship), encoding="utf-8")
        current = self.client.get("/api/plan").get_json()
        self.assertEqual(len(current["ships"]), 8)
        self.assertEqual(current["ships"][0]["maxSpeedKnots"], 15)
        self.assertEqual(current["ports"][0]["distancesNm"]["hamburg"], 150)
        self.assertTrue(any(service["id"] == "NEW" for service in current["services"]))
        self.assertNotEqual(current["dataSignature"], self.plan["dataSignature"])
        stale = {"revision": self.plan["revision"], "dataSignature": self.plan["dataSignature"], "ship": self.plan["ships"][0]}
        self.assertEqual(self.client.put("/api/ships/busan/plan", json=stale).status_code, 409)

    def test_navigation_migration_preserves_speed_and_uses_100_nm(self):
        root = Path(self.directory.name)
        ship = deepcopy(self.plan["ships"][0])
        del ship["maxSpeedKnots"]
        (root / "ships/busan.json").write_text(json.dumps(ship), encoding="utf-8")
        (root / "navigation.json").write_text(json.dumps({"maxSpeedKnotsByShip": {"busan": 18}, "defaultDistanceNm": 1000}), encoding="utf-8")
        client = create_app(self.directory.name).test_client()
        current = client.get("/api/plan").get_json()
        self.assertEqual(current["ships"][0]["maxSpeedKnots"], 18)
        self.assertEqual(current["ports"][0]["distancesNm"]["hamburg"], 100)
        self.assertFalse((root / "navigation.json").exists())

    def test_invalid_added_file_returns_recoverable_error(self):
        path = Path(self.directory.name) / "ships/broken.json"
        path.write_text(json.dumps({"id": "broken"}), encoding="utf-8")
        response = self.client.get("/api/plan")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Schiffsdatei", response.get_json()["error"])
        path.unlink()
        self.assertEqual(self.client.get("/api/plan").status_code, 200)


if __name__ == "__main__":
    unittest.main()