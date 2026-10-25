import unittest
from copy import deepcopy

from app import example_schedule, PORTS
from planning import conflicts, migrate_ship, minimum_transit_hours, resolve_voyage, validate_ship, voyages_in_range


class ProformaTests(unittest.TestCase):
    def setUp(self):
        self.ship = migrate_ship(example_schedule()["ships"][0])

    def test_fourteen_week_fallback_without_creating_actuals(self):
        voyage = resolve_voyage(self.ship, "2027-04-24")
        self.assertEqual(voyage["stops"][0]["arrival"], "2027-04-24T11:00")
        self.assertEqual(voyage["source"], "proforma")
        self.assertEqual(self.ship["voyages"], {})

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


if __name__ == "__main__":
    unittest.main()