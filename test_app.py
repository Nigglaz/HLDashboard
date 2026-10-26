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
        shared = self.plan["services"][0]["proformas"][0]
        self.assertEqual(shared["stops"][0]["arrival"], "2027-01-16T11:00")
        self.assertEqual(resolve_voyage(self.plan["ships"][1], "2027-01-01", self.plan["services"])["stops"][0]["arrival"], "2027-01-23T11:00")
        self.assertEqual(shared["stops"][1]["transitMinutes"], 2220)
        candidate = deepcopy(self.plan)
        self.make_actual(candidate, 0, "2027-01-16")[1]["berth"] = 3
        response = self.save_candidate(candidate)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("revision", response.get_json())
        self.assertNotEqual(response.get_json()["dataSignature"], self.plan["dataSignature"])
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
        stops[0].update({key: self.plan["services"][0]["proformas"][0]["stops"][0][key] for key in ("arrival", "departure", "berth")})
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
        self.assertTrue(all(stop["berth"] == 1 for stop in self.plan["services"][0]["proformas"][0]["stops"]))
        repeated = resolve_voyage(busan, "2027-04-24", self.plan["services"])["stops"]
        self.assertEqual(repeated[0]["arrival"], "2027-04-24T11:00")
        candidate = deepcopy(self.plan)
        candidate["ships"][0]["voyages"]["2027-04-24"] = {"proformaId": self.plan["services"][0]["proformas"][0]["id"], "stops": repeated}
        repeated[1]["berth"] = 3
        response = self.save_candidate(candidate)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["services"][0]["proformas"][0]["stops"][0]["berth"], 1)

    def test_mathilde_is_corrected_and_invalid_actual_cannot_be_saved(self):
        mathilde = self.plan["ships"][-1]
        self.assertEqual(self.plan["services"][1]["proformas"][0]["stops"][3]["arrival"], "2027-01-26T11:00")
        candidate = deepcopy(self.plan)
        self.make_actual(candidate, -1, "2027-01-16")[3]["arrival"] = "2027-01-15T11:00"
        self.assertEqual(self.save_candidate(candidate, "mathilde").status_code, 400)

    def test_no_organizational_files_are_created(self):
        root = Path(self.directory.name)
        self.assertEqual({path.name for path in root.glob("*.json")}, {"ports.json", "services.json"})
        self.assertEqual(self.client.get("/api/views").status_code, 404)
        self.assertEqual(self.client.put("/api/views", json={"name": "Ansicht", "config": {}}).status_code, 404)

    def test_removed_ships_are_not_recreated_on_restart(self):
        for path in (Path(self.directory.name) / "ships").glob("*.json"):
            path.unlink()
        client = create_app(self.directory.name).test_client()
        self.assertEqual(client.get("/api/plan").get_json()["ships"], [])

    def test_create_unscheduled_ship_and_edit_metadata_without_touching_plans(self):
        payload = {"dataSignature": self.plan["dataSignature"], "id": "new-ship", "name": "New Ship", "vesselName": "NEW SHIP", "serviceId": "NE4", "maxSpeedKnots": 18}
        result = self.client.post("/api/fleet", json=payload)
        self.assertEqual(result.status_code, 200)
        ship = next(ship for ship in result.get_json()["ships"] if ship["id"] == "new-ship")
        self.assertEqual(ship["proformaAssignments"], [])
        self.assertEqual(ship["voyages"], {})
        original = result.get_json()["ships"][0]
        edit = {"dataSignature": result.get_json()["dataSignature"], "name": "Busan neu", "vesselName": "BUSAN EXPRESS", "serviceId": "NE4", "maxSpeedKnots": 19}
        changed = self.client.put("/api/fleet/busan", json=edit)
        self.assertEqual(changed.status_code, 200)
        updated = next(ship for ship in changed.get_json()["ships"] if ship["id"] == "busan")
        self.assertEqual(updated["proformaAssignments"], [])
        self.assertEqual(updated["voyages"], original["voyages"])

    def test_import_name_case_is_preserved_but_duplicate_check_is_case_insensitive(self):
        payload = {"dataSignature": self.plan["dataSignature"], "id": "lower-case", "name": "Lower Case", "vesselName": "new vessel", "serviceId": "NE2", "maxSpeedKnots": 20}
        created = self.client.post("/api/fleet", json=payload)
        self.assertEqual(created.status_code, 200)
        ship = next(item for item in created.get_json()["ships"] if item["id"] == "lower-case")
        self.assertEqual(ship["vesselName"], "new vessel")
        duplicate = {**payload, "dataSignature": created.get_json()["dataSignature"], "id": "another", "vesselName": "NEW VESSEL"}
        self.assertEqual(self.client.post("/api/fleet", json=duplicate).status_code, 400)

    def test_service_proformas_are_shared_and_ship_assignments_are_versioned(self):
        service = next(item for item in self.plan["services"] if item["id"] == "NE4")
        older = deepcopy(service["proformas"][0])
        older.update(id="ne4-2026", name="NE4/2026", validFrom="2026-01-01")
        for stop in older["stops"]:
            for field in ("arrival", "departure"):
                stop[field] = (datetime.fromisoformat(stop[field]) - timedelta(days=365)).isoformat(timespec="minutes")
        created = self.client.post("/api/services/NE4/proformas", json={"dataSignature": self.plan["dataSignature"], "proforma": older})
        self.assertEqual(created.status_code, 200)
        plan = created.get_json()
        assignments = [{"proformaId": "ne4-2026", "validFrom": "2026-01-01", "offsetWeeks": 3},
                       {"proformaId": "ne4-2027", "validFrom": "2027-01-01", "offsetWeeks": 4}]
        mathilde = next(ship for ship in plan["ships"] if ship["id"] == "mathilde")
        payload = {"dataSignature": plan["dataSignature"], "id": mathilde["id"], "name": mathilde["name"],
                   "vesselName": mathilde.get("vesselName", mathilde["name"].upper()), "serviceId": "NE4", "maxSpeedKnots": mathilde["maxSpeedKnots"],
                   "proformaAssignments": assignments}
        updated = self.client.put("/api/fleet/mathilde", json=payload)
        self.assertEqual(updated.status_code, 200, updated.get_json())
        result = updated.get_json()
        ship = next(item for item in result["ships"] if item["id"] == "mathilde")
        self.assertEqual(ship["proformaAssignments"], assignments)
        self.assertEqual(resolve_voyage(ship, "2027-01-01", result["services"])["stops"][0]["arrival"], "2027-02-13T14:00")
        disk_ship = json.loads((Path(self.directory.name) / "ships/mathilde.json").read_text(encoding="utf-8"))
        self.assertNotIn("proformas", disk_ship)
        self.assertEqual(len(next(service for service in result["services"] if service["id"] == "NE4")["proformas"]), 2)

    def test_port_metadata_rejects_invalid_berth_reduction_and_supports_distance_edit(self):
        services = deepcopy(self.plan["services"])
        next(stop for stop in services[0]["proformas"][0]["stops"] if stop["portId"] == "hamburg")["berth"] = 6
        (Path(self.directory.name) / "services.json").write_text(json.dumps(services), encoding="utf-8")
        self.plan = self.client.get("/api/plan").get_json()
        old = self.plan["ports"][1]
        payload = {**old, "dataSignature": self.plan["dataSignature"], "berths": 1}
        self.assertEqual(self.client.put("/api/ports/hamburg", json=payload).status_code, 400)
        payload.update(berths=6, name="Hamburg neu", distancesNm={"rotterdam": 150})
        changed = self.client.put("/api/ports/hamburg", json=payload)
        self.assertEqual(changed.status_code, 200)
        ports = changed.get_json()["ports"]
        self.assertEqual(next(port for port in ports if port["id"] == "hamburg")["distancesNm"]["rotterdam"], 150)
        self.assertNotIn("hamburg", ports[0]["distancesNm"])

    def test_create_port_with_aliases_and_distance(self):
        payload = {"dataSignature": self.plan["dataSignature"], "id": "suez", "name": "Suez Canal", "berths": 2, "aliases": {"maersk": ["Canal Zone Terminal"]}, "distancesNm": {"london": 100}}
        result = self.client.post("/api/ports", json=payload)
        self.assertEqual(result.status_code, 200)
        port = next(port for port in result.get_json()["ports"] if port["id"] == "suez")
        self.assertEqual(port["aliases"]["maersk"], ["Canal Zone Terminal"])
        self.assertEqual(port["distancesNm"]["london"], 100)
        self.assertEqual(result.get_json()["ships"], self.plan["ships"])

    def test_rename_terminal_id_updates_all_references_and_preserves_times(self):
        candidate = deepcopy(self.plan)
        self.make_actual(candidate, 0, "2027-01-16")
        saved = self.save_candidate(candidate).get_json()
        port = next(port for port in saved["ports"] if port["id"] == "rotterdam")
        response = self.client.put("/api/ports/rotterdam", json={**port, "id": "rotterdam-mv2", "dataSignature": saved["dataSignature"]})
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["portIdChange"], {"from": "rotterdam", "to": "rotterdam-mv2"})
        self.assertFalse(any(port["id"] == "rotterdam" for port in result["ports"]))
        for before, after in zip(saved["services"], result["services"]):
            for old_proforma, new_proforma in zip(before["proformas"], after["proformas"]):
                for old_stop, new_stop in zip(old_proforma["stops"], new_proforma["stops"]):
                    expected = {**old_stop, "portId": "rotterdam-mv2"} if old_stop["portId"] == "rotterdam" else old_stop
                    self.assertEqual(new_stop, expected)
        for before, after in zip(saved["ships"], result["ships"]):
            for key, old_voyage in before["voyages"].items():
                for old_stop, new_stop in zip(old_voyage["stops"], after["voyages"][key]["stops"]):
                    expected = {**old_stop, "portId": "rotterdam-mv2"} if old_stop["portId"] == "rotterdam" else old_stop
                    self.assertEqual(new_stop, expected)
        self.assertIn("rotterdam-mv2", result["services"][0]["defaultBerths"])
        self.assertNotIn("rotterdam", result["services"][0]["defaultBerths"])

    def test_terminal_id_collision_is_rejected_without_changing_data(self):
        port = self.plan["ports"][0]
        result = self.client.put("/api/ports/rotterdam", json={**port, "id": "hamburg", "dataSignature": self.plan["dataSignature"]})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.client.get("/api/plan").get_json(), self.plan)
        empty = self.client.put("/api/ports/rotterdam", json={**port, "id": None, "dataSignature": self.plan["dataSignature"]})
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(self.client.get("/api/plan").get_json(), self.plan)

    def test_rename_preserves_distances_defined_only_at_other_terminal(self):
        path = Path(self.directory.name) / "ports.json"
        ports = deepcopy(self.plan["ports"])
        ports[0]["distancesNm"]["hamburg"] = 412
        path.write_text(json.dumps(ports), encoding="utf-8")
        current = self.client.get("/api/plan").get_json()
        hamburg = next(port for port in current["ports"] if port["id"] == "hamburg")
        response = self.client.put("/api/ports/hamburg", json={**hamburg, "id": "hamburg-eurogate", "dataSignature": current["dataSignature"]})
        self.assertEqual(response.status_code, 200)
        updated = next(port for port in response.get_json()["ports"] if port["id"] == "hamburg-eurogate")
        self.assertEqual(updated["distancesNm"]["rotterdam"], 412)
        restarted = create_app(self.directory.name).test_client().get("/api/plan").get_json()
        self.assertNotIn("hamburg-eurogate", restarted["ports"][0]["distancesNm"])

    def test_new_terminal_distance_is_available_in_both_directions(self):
        from planning import minimum_transit_hours
        payload = {"id": "rotterdam-second", "name": "Rotterdam MV2", "berths": 2, "distancesNm": {"hamburg": 240}, "aliases": {}, "dataSignature": self.plan["dataSignature"]}
        response = self.client.post("/api/ports", json=payload)
        self.assertEqual(response.status_code, 200)
        ports = response.get_json()["ports"]
        self.assertEqual(sum(port["name"] == "Rotterdam MV2" for port in ports), 2)
        self.assertEqual(minimum_transit_hours(self.plan["ships"][0], "rotterdam-second", "hamburg", ports)["hours"], 12)
        self.assertEqual(minimum_transit_hours(self.plan["ships"][0], "hamburg", "rotterdam-second", ports)["hours"], 12)

    def test_change_rotation_previews_and_saves_only_the_affected_voyage(self):
        candidate = deepcopy(self.plan)
        stops = self.make_actual(candidate, 0, "2027-01-16")
        original = deepcopy(stops)
        stops[1], stops[2] = stops[2], stops[1]
        response = self.client.post("/api/ships/busan/rotation", json={"dataSignature": self.plan["dataSignature"], "voyageDate": "2027-01-16", "stops": stops})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["stops"], original)
        self.assertEqual(self.client.get("/api/plan").get_json(), self.plan)
        candidate["ships"][0]["voyages"]["2027-01-16"]["stops"] = response.get_json()["stops"]
        saved = self.save_candidate(candidate)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["services"], self.plan["services"])

    def test_change_rotation_rejects_impossible_times_without_writing(self):
        stops = deepcopy(self.plan["services"][0]["proformas"][0]["stops"])
        stops[1]["arrival"] = "2027-01-18T04:00"
        response = self.client.post("/api/ships/busan/rotation", json={"dataSignature": self.plan["dataSignature"], "voyageDate": "2027-01-16", "stops": stops})
        self.assertEqual(response.status_code, 400)
        self.assertIn("mindestens 5 h", response.get_json()["error"])
        self.assertEqual(self.client.get("/api/plan").get_json(), self.plan)

    def test_out_of_order_actual_json_remains_loadable_for_rotation_repair(self):
        ship = deepcopy(self.plan["ships"][0])
        stops = deepcopy(self.plan["services"][0]["proformas"][0]["stops"])
        stops[1], stops[2] = stops[2], stops[1]
        stops[2]["transitMinutes"] = -60
        ship["voyages"]["2027-01-16"] = {"proformaId": self.plan["services"][0]["proformas"][0]["id"], "stops": stops}
        (Path(self.directory.name) / "ships/busan.json").write_text(json.dumps(ship), encoding="utf-8")
        current = self.client.get("/api/plan")
        self.assertEqual(current.status_code, 200)
        response = self.client.post("/api/ships/busan/rotation", json={"dataSignature": current.get_json()["dataSignature"], "voyageDate": "2027-01-16", "stops": stops})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(stop["transitMinutes"] >= 0 for stop in response.get_json()["stops"]))

    def test_adhoc_preview_and_save_do_not_change_proforma_or_other_rounds(self):
        ship = self.plan["ships"][0]
        stops = self.plan["services"][0]["proformas"][0]["stops"]
        response = self.client.post("/api/ships/busan/adhoc-stop", json={"dataSignature": self.plan["dataSignature"], "voyageDate": "2027-01-16", "stops": stops, "afterStopId": stops[3]["id"], "portId": "bremerhaven"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["stops"]), 6)
        self.assertEqual(self.client.get("/api/plan").get_json(), self.plan)
        candidate = deepcopy(self.plan)
        candidate["ships"][0]["voyages"]["2027-01-16"] = {"proformaId": self.plan["services"][0]["proformas"][0]["id"], "stops": response.get_json()["stops"]}
        saved = self.save_candidate(candidate)
        self.assertEqual(saved.status_code, 200)
        updated = saved.get_json()["ships"][0]
        self.assertEqual(updated["proformaAssignments"], ship["proformaAssignments"])
        self.assertEqual(len(resolve_voyage(updated, "2027-04-24", saved.get_json()["services"])["stops"]), 5)

    def test_overlapping_adhoc_is_previewed_but_cannot_be_saved(self):
        stops = self.plan["services"][0]["proformas"][0]["stops"]
        response = self.client.post("/api/ships/busan/adhoc-stop", json={"dataSignature": self.plan["dataSignature"], "voyageDate": "2027-01-16", "stops": stops, "afterStopId": stops[0]["id"], "portId": "bremerhaven"})
        self.assertEqual(response.status_code, 200)
        candidate = deepcopy(self.plan)
        candidate["ships"][0]["voyages"]["2027-01-16"] = {"proformaId": self.plan["services"][0]["proformas"][0]["id"], "stops": response.get_json()["stops"]}
        self.assertEqual(self.save_candidate(candidate).status_code, 400)

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
        voyage = resolve_voyage(ship, date, plan["services"])
        ship["voyages"][voyage["key"]] = {"proformaId": voyage["proformaId"], "stops": voyage["stops"]}
        return ship["voyages"][voyage["key"]]["stops"]

    def test_individual_files_and_restart(self):
        files = list((Path(self.directory.name) / "ships").glob("*.json"))
        self.assertEqual(len(files), 7)
        self.assertFalse((Path(self.directory.name) / "schedules.json").exists())
        other = create_app(self.directory.name).test_client()
        self.assertEqual(other.get("/api/plan").get_json(), self.plan)

    def save_candidate(self, plan, ship_id="busan"):
        ship = next(ship for ship in plan["ships"] if ship["id"] == ship_id)
        return self.client.put(f"/api/ships/{ship_id}/plan", json={"dataSignature": plan["dataSignature"], "ship": ship, "mode": plan.get("mode", "planning")})

    def test_only_selected_ship_is_saved(self):
        candidate = deepcopy(self.plan)
        self.make_actual(candidate, 0, "2027-01-16")[1]["berth"] = 3
        self.make_actual(candidate, 1, "2027-01-23")[1]["berth"] = 4
        response = self.save_candidate(candidate)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(resolve_voyage(response.get_json()["ships"][0], "2027-01-16", response.get_json()["services"])["stops"][1]["berth"], 3)
        self.assertEqual(response.get_json()["ships"][1], self.plan["ships"][1])
        candidate["dataSignature"] = response.get_json()["dataSignature"]
        self.assertEqual(self.save_candidate(candidate, "berlin").status_code, 200)

    def test_planning_cannot_modify_proformas(self):
        candidate = deepcopy(self.plan)
        candidate["ships"][0]["proformaAssignments"][0]["offsetWeeks"] += 1
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
        new_ship.update(id="new-vessel", name="New Vessel", vesselName="NEW VESSEL", serviceId="NEW", proformaAssignments=[])
        (root / "ships/new-vessel.json").write_text(json.dumps(new_ship), encoding="utf-8")
        current = self.client.get("/api/plan").get_json()
        self.assertEqual(len(current["ships"]), 8)
        self.assertEqual(current["ships"][0]["maxSpeedKnots"], 15)
        self.assertEqual(current["ports"][0]["distancesNm"]["hamburg"], 150)
        self.assertTrue(any(service["id"] == "NEW" for service in current["services"]))
        self.assertNotEqual(current["dataSignature"], self.plan["dataSignature"])
        stale = {"dataSignature": self.plan["dataSignature"], "ship": self.plan["ships"][0]}
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

    def test_service_colors_are_configurable_and_validated(self):
        path = Path(self.directory.name) / "services.json"
        services = deepcopy(self.plan["services"])
        services[0]["color"] = "#a12345"
        path.write_text(json.dumps(services), encoding="utf-8")
        current = self.client.get("/api/plan").get_json()
        self.assertEqual(current["services"][0]["color"], "#a12345")
        self.assertNotEqual(current["dataSignature"], self.plan["dataSignature"])
        services[0]["color"] = "not-a-color"
        path.write_text(json.dumps(services), encoding="utf-8")
        self.assertEqual(self.client.get("/api/plan").status_code, 503)

    def test_restart_preserves_configured_cycle_and_removed_example_port(self):
        root = Path(self.directory.name)
        services = deepcopy(self.plan["services"])
        services[0]["repeatWeeks"] = 15
        (root / "services.json").write_text(json.dumps(services), encoding="utf-8")
        ports = [port for port in self.plan["ports"] if port["id"] != "algeciras"]
        (root / "ports.json").write_text(json.dumps(ports), encoding="utf-8")
        mathilde = deepcopy(self.plan["ships"][-1])
        current_service = next(service for service in services if service["id"] == "NE4")
        current_service["proformas"][0]["stops"].pop()
        (root / "services.json").write_text(json.dumps(services), encoding="utf-8")
        (root / "ships/mathilde.json").write_text(json.dumps(mathilde), encoding="utf-8")
        current = create_app(self.directory.name).test_client().get("/api/plan").get_json()
        self.assertEqual(current["services"][0]["repeatWeeks"], 15)
        self.assertFalse(any(port["id"] == "algeciras" for port in current["ports"]))


if __name__ == "__main__":
    unittest.main()