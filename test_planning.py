import unittest
from copy import deepcopy
from datetime import datetime, timedelta

from app import example_schedule, PORTS, SERVICES
from planning import change_rotation, conflicts, insert_adhoc_stop, migrate_service_proformas, migrate_ship, minimum_transit_hours, resolve_voyage, validate_ship, voyages_in_range


class ProformaTests(unittest.TestCase):
    def setUp(self):
        self.ship = migrate_ship(example_schedule()["ships"][0])

    def test_fourteen_week_fallback_without_creating_actuals(self):
        voyage = resolve_voyage(self.ship, "2027-04-24")
        self.assertEqual(voyage["stops"][0]["arrival"], "2027-04-24T11:00")
        self.assertEqual(voyage["source"], "proforma")
        self.assertEqual(self.ship["voyages"], {})

    def test_migration_shares_service_route_and_preserves_weekly_offsets(self):
        ships = [migrate_ship(ship) for ship in example_schedule()["ships"]]
        migrated, services = migrate_service_proformas(ships, SERVICES)
        ne2 = next(service for service in services if service["id"] == "NE2")
        self.assertEqual(len(ne2["proformas"]), 1)
        offsets = {ship["id"]: ship["proformaAssignments"][0]["offsetWeeks"] for ship in migrated if ship["serviceId"] == "NE2"}
        self.assertEqual(offsets, {"busan": 0, "berlin": 1, "gdansk": 2, "rotterdam": 3, "hamburg": 4, "genova": 5})
        for ship in migrated:
            self.assertNotIn("proformas", ship)
        self.assertEqual(resolve_voyage(next(ship for ship in migrated if ship["id"] == "genova"), "2027-01-01", services)["stops"][0]["arrival"], "2027-02-20T11:00")

    def test_assignment_switches_service_version_with_independent_offset(self):
        ships = [migrate_ship(ship) for ship in example_schedule()["ships"]]
        migrated, services = migrate_service_proformas(ships, SERVICES)
        mathilde = next(ship for ship in migrated if ship["id"] == "mathilde")
        ne4 = next(service for service in services if service["id"] == "NE4")
        next_version = deepcopy(ne4["proformas"][0])
        next_version.update(id="ne4-2028", name="NE4/2028", validFrom="2028-01-01")
        for stop in next_version["stops"]:
            for field in ("arrival", "departure"):
                stop[field] = (datetime.fromisoformat(stop[field]) + timedelta(days=365)).isoformat(timespec="minutes")
        ne4["proformas"].append(next_version)
        mathilde["proformaAssignments"].append({"proformaId": "ne4-2028", "validFrom": "2028-01-01", "offsetWeeks": 4})
        voyage = resolve_voyage(mathilde, "2028-01-01", services)
        self.assertEqual(voyage["proformaId"], "ne4-2028")
        self.assertEqual(voyage["key"], "2028-02-13")
        self.assertEqual(voyage["stops"][0]["arrival"], "2028-02-13T14:00")

    def test_transit_uses_nautical_distance_and_speed(self):
        self.assertEqual(minimum_transit_hours(self.ship, "rotterdam", "hamburg")["hours"], 5)
        ports = [{"id": "rotterdam", "distancesNm": {"hamburg": 300}}, {"id": "hamburg"}]
        self.ship["maxSpeedKnots"] = 15
        self.assertEqual(minimum_transit_hours(self.ship, "rotterdam", "hamburg", ports)["hours"], 20)
        self.assertEqual(minimum_transit_hours(self.ship, "hamburg", "rotterdam", ports)["hours"], 20)

    def test_planned_transit_field_is_not_the_speed_limit(self):
        self.ship["proformas"][0]["stops"][1]["transitMinutes"] = 99999
        validate_ship(self.ship, self.ship, PORTS)
        issues = conflicts([self.ship], "2027-01-01", "2027-03-01")
        self.assertFalse(any("transit:" in key for key in issues))

    def test_effective_version_switch_and_actual_priority(self):
        version = deepcopy(self.ship["proformas"][0])
        version.update(id="new", validFrom="2027-04-01", name="Sommer")
        version["stops"][0]["berth"] = 2
        self.ship["proformas"].append(version)
        self.assertEqual(resolve_voyage(self.ship, "2027-01-16")["proformaId"], "initial")
        voyage = resolve_voyage(self.ship, "2027-04-24")
        self.assertEqual(voyage["proformaId"], "new")
        self.ship["voyages"][voyage["key"]] = {"proformaId": voyage["proformaId"], "stops": voyage["stops"]}
        version["stops"][0]["berth"] = 1
        self.assertEqual(resolve_voyage(self.ship, "2027-04-24")["stops"][0]["berth"], 2)
        self.assertEqual(resolve_voyage(self.ship, "2027-04-24")["source"], "actual")

    def test_range_generates_multiple_rounds(self):
        voyages = voyages_in_range(self.ship, "2027-01-01", "2028-01-01")
        self.assertEqual([voyage["key"] for voyage in voyages], ["2027-01-16", "2027-04-24", "2027-07-31", "2027-11-06"])

    def test_mathilde_correction(self):
        ship = migrate_ship(example_schedule()["ships"][-1])
        self.assertEqual(ship["proformas"][0]["stops"][3]["arrival"], "2027-01-26T11:00")
        validate_ship(ship, ship, PORTS)

    def test_actual_keeps_priority_when_new_proforma_changes_anchor(self):
        voyage = resolve_voyage(self.ship, "2027-04-24")
        self.ship["voyages"][voyage["key"]] = {"proformaId": voyage["proformaId"], "stops": voyage["stops"]}
        version = deepcopy(self.ship["proformas"][0])
        version.update(id="summer", name="Sommer", validFrom="2027-04-01", repeatWeeks=12)
        self.ship["proformas"].append(version)
        actual = resolve_voyage(self.ship, "2027-04-24")
        self.assertEqual(actual["source"], "actual")
        self.assertEqual(actual["stops"][0]["arrival"], "2027-04-24T11:00")

    def test_change_rotation_reorders_multiple_ports_without_changing_times(self):
        original = deepcopy(self.ship["proformas"][0]["stops"])
        swapped = [original[2], original[0], original[3], original[1], original[4]]
        before = deepcopy(swapped)
        result = change_rotation(self.ship, swapped, PORTS)
        self.assertEqual([stop["id"] for stop in result], [stop["id"] for stop in original])
        self.assertEqual([stop["transitMinutes"] for stop in result], [0, 2220, 2640, 780, 6000])
        self.assertEqual(swapped, before)
        self.assertEqual({stop["id"]: (stop["arrival"], stop["departure"], stop["berth"]) for stop in result},
                         {stop["id"]: (stop["arrival"], stop["departure"], stop["berth"]) for stop in original})

    def test_change_rotation_rejects_overlap_and_short_transit(self):
        stops = deepcopy(self.ship["proformas"][0]["stops"])
        stops[1]["arrival"] = "2027-01-17T12:00"
        with self.assertRaisesRegex(ValueError, "berlappen"):
            change_rotation(self.ship, stops, PORTS)
        stops[1]["arrival"] = "2027-01-18T04:00"
        with self.assertRaisesRegex(ValueError, "mindestens 5 h"):
            change_rotation(self.ship, stops, PORTS)

    def test_change_rotation_accepts_exchanged_port_time_windows(self):
        stops = deepcopy(self.ship["proformas"][0]["stops"])
        for field in ("arrival", "departure"):
            stops[1][field], stops[2][field] = stops[2][field], stops[1][field]
        result = change_rotation(self.ship, stops, PORTS)
        self.assertEqual([stop["portId"] for stop in result], ["rotterdam", "antwerp", "hamburg", "london", "tangier"])
        self.assertEqual(result[1]["arrival"], "2027-01-19T13:00")
        self.assertEqual(result[2]["arrival"], "2027-01-23T06:00")

    def test_reversed_voyage_is_still_in_its_calendar_range(self):
        stops = list(reversed(deepcopy(self.ship["proformas"][0]["stops"])))
        self.ship["voyages"]["2027-01-16"] = {"proformaId": "initial", "stops": stops}
        voyages = voyages_in_range(self.ship, "2027-01-19", "2027-01-22")
        self.assertEqual([voyage["key"] for voyage in voyages], ["2027-01-16"])

    def test_adhoc_stop_is_centered_and_uses_average_laytime(self):
        original = deepcopy(self.ship["proformas"][0]["stops"])
        result = insert_adhoc_stop(original, original[3]["id"], "bremerhaven", PORTS)
        stop = result[4]
        self.assertEqual(stop["portId"], "bremerhaven")
        self.assertTrue(stop["adhoc"])
        self.assertEqual(stop["arrival"], "2027-01-30T04:45")
        self.assertEqual(stop["departure"], "2027-01-31T21:15")
        self.assertEqual(stop["transitMinutes"], 1785)
        self.assertEqual(result[5]["transitMinutes"], 1785)
        self.assertEqual(original, self.ship["proformas"][0]["stops"])
        for before, after in zip(original, [item for item in result if not item.get("adhoc")]):
            self.assertEqual((before["arrival"], before["departure"], before["berth"]), (after["arrival"], after["departure"], after["berth"]))

    def test_adhoc_stop_allows_repeated_port_and_pending_overlap(self):
        stops = self.ship["proformas"][0]["stops"]
        result = insert_adhoc_stop(stops, stops[0]["id"], "hamburg", PORTS)
        self.assertEqual(sum(stop["portId"] == "hamburg" for stop in result), 2)
        self.assertEqual(len({stop["id"] for stop in result}), len(result))
        self.assertLess(result[1]["arrival"], result[0]["departure"])

    def test_adhoc_stop_needs_a_following_stop_and_known_port(self):
        stops = self.ship["proformas"][0]["stops"]
        with self.assertRaises(ValueError):
            insert_adhoc_stop(stops, stops[-1]["id"], "hamburg", PORTS)
        with self.assertRaises(ValueError):
            insert_adhoc_stop(stops, stops[0]["id"], "unknown", PORTS)


if __name__ == "__main__":
    unittest.main()