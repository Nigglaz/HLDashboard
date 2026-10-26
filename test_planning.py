import unittest
from copy import deepcopy
from datetime import datetime, timedelta

from planning import change_rotation, conflicts, insert_adhoc_stop, migrate_service_proformas, minimum_transit_hours, resolve_voyage, validate_ship, voyages_in_range
from test_support import legacy_test_ships, load_test_plan


PORTS = load_test_plan()["ports"]
SERVICES = [{**service, "proformas": []} for service in load_test_plan()["services"]]


class ProformaTests(unittest.TestCase):
    def setUp(self):
        self.ship = legacy_test_ships()[0]

    def test_fourteen_week_fallback_without_creating_actuals(self):
        voyage = resolve_voyage(self.ship, "2027-04-24")
        self.assertEqual(voyage["stops"][0]["arrival"], "2027-04-24T11:00")
        self.assertEqual(voyage["source"], "proforma")
        self.assertEqual(self.ship["voyages"], {})

    def test_migration_shares_service_route_and_preserves_weekly_offsets(self):
        ships = legacy_test_ships()
        migrated, services = migrate_service_proformas(ships, SERVICES)
        ne2 = next(service for service in services if service["id"] == "NE2")
        self.assertEqual(len(ne2["proformas"]), 1)
        offsets = {ship["id"]: ship["proformaAssignments"][0]["offsetWeeks"] for ship in migrated if ship["serviceId"] == "NE2"}
        self.assertEqual(offsets, {"busan": 0, "berlin": 1, "gdansk": 2, "rotterdam": 3, "hamburg": 4, "genova": 5})
        for ship in migrated:
            self.assertNotIn("proformas", ship)
        self.assertEqual(resolve_voyage(next(ship for ship in migrated if ship["id"] == "genova"), "2027-01-01", services)["stops"][0]["arrival"], "2027-02-20T11:00")

    def test_assignment_switches_service_version_with_independent_offset(self):
        ships = legacy_test_ships()
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
        self.assertEqual(minimum_transit_hours(self.ship, "rotterdam", "hamburg", PORTS)["hours"], 5)
        ports = [{"id": "rotterdam", "distancesNm": {"hamburg": 300}}, {"id": "hamburg"}]
        self.ship["maxSpeedKnots"] = 15
        self.assertEqual(minimum_transit_hours(self.ship, "rotterdam", "hamburg", ports)["hours"], 20)
        self.assertEqual(minimum_transit_hours(self.ship, "hamburg", "rotterdam", ports)["hours"], 20)

    def test_planned_transit_field_is_not_the_speed_limit(self):
        self.ship["proformas"][0]["stops"][1]["transitMinutes"] = 99999
        validate_ship(self.ship, self.ship, PORTS)
        issues = conflicts([self.ship], "2027-01-01", "2027-03-01", PORTS)
        self.assertFalse(any("transit:" in key for key in issues))

    def test_missing_distance_and_speed_are_not_replaced_by_defaults(self):
        with self.assertRaisesRegex(ValueError, "Entfernung"):
            minimum_transit_hours(self.ship, "rotterdam", "hamburg", [])
        del self.ship["maxSpeedKnots"]
        with self.assertRaisesRegex(ValueError, "Maximalgeschwindigkeit"):
            minimum_transit_hours(self.ship, "rotterdam", "hamburg", PORTS)

    def test_same_port_requires_no_distance_entry(self):
        self.assertEqual(minimum_transit_hours(self.ship, "hamburg", "hamburg", PORTS)["hours"], 0)

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
        ship = legacy_test_ships()[-1]
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

    def test_adhoc_before_stop_uses_preceding_gap(self):
        stops = self.ship["proformas"][0]["stops"]
        result = insert_adhoc_stop(stops, None, "bremerhaven", PORTS, before_stop_id=stops[-1]["id"])
        self.assertEqual(result[-2]["portId"], "bremerhaven")
        self.assertEqual(result[-1]["id"], stops[-1]["id"])
        self.assertEqual(result[-2]["arrival"], "2027-01-30T04:45")

    def test_adhoc_before_first_stop_preserves_existing_times(self):
        stops = deepcopy(self.ship["proformas"][0]["stops"])
        result = insert_adhoc_stop(stops, None, "bremerhaven", PORTS, before_stop_id=stops[0]["id"])
        self.assertEqual(result[0]["portId"], "bremerhaven")
        self.assertEqual(result[0]["departure"], stops[0]["arrival"])
        self.assertEqual(result[0]["transitMinutes"], 0)
        self.assertEqual(result[1]["transitMinutes"], 0)
        self.assertEqual(result[1:], stops)
        self.assertLess(result[0]["arrival"], result[0]["departure"])

    def test_adhoc_before_rejects_unknown_or_ambiguous_target(self):
        stops = self.ship["proformas"][0]["stops"]
        for after, before in [(None, "missing"), (stops[0]["id"], stops[1]["id"])]:
            with self.assertRaises(ValueError):
                insert_adhoc_stop(stops, after, "bremerhaven", PORTS, before_stop_id=before)

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