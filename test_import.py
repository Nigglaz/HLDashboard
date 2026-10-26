import unittest
import tempfile
import json
import sys
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from pathlib import Path

from planning import migrate_service_proformas, resolve_voyage, validate_ship
from test_support import create_test_app as create_app, legacy_test_ships, load_test_plan
from schedule_import import MAERSK_URL, parse_maersk_text, prepare_import, prepare_service_import, resolve_port, vessel_identifier, vessel_key
from import_maersk import fetch_schedule


SAMPLE = """Suez Canal
Canal Zone Terminal
Arrival - 650W
06 Jan 2027 23:00
Departure - 650W
07 Jan 2027 17:00
London Gateway
London Gateway Terminal
Arrival - 650W
16 Jan 2027 14:00
Departure - 703E
18 Jan 2027 04:00
Bremerhaven
NTB North Sea Terminal Bremerhaven
Arrival - 650W
20 Jan 2027 06:00
Departure - 703E
21 Jan 2027 22:00
Hamburg
Eurogate Container Terminal Hamburg
Arrival - 650W
22 Jan 2027 15:00
Departure - 703E
24 Jan 2027 18:00
Rotterdam
APM 2 Terminal Maasvlakte II
Arrival - 650W
26 Jan 2027 11:00
Departure - 703E
27 Jan 2027 12:00
Algeciras
Algeciras - ML Terminal
Arrival - 703E
01 Feb 2027 20:00
Departure - 703E
02 Feb 2027 14:00
Suez Canal
Canal Zone Terminal
Arrival - 703E
07 Feb 2027 23:00
Departure - 703E
08 Feb 2027 17:00
"""


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.packet = parse_maersk_text(SAMPLE, "MATHILDE MAERSK", "2027-01-01", "2027-03-01")
        ships = legacy_test_ships()
        self.plan = load_test_plan()
        for service in self.plan["services"]:
            service["proformas"] = []
        self.plan["ships"], self.plan["services"] = migrate_service_proformas(ships, self.plan["services"])
        aliases = {"london": ["London Gateway Terminal"], "hamburg": ["Eurogate Container Terminal Hamburg"], "rotterdam": ["APM 2 Terminal Maasvlakte II"], "algeciras": ["Algeciras - ML Terminal"]}
        for port in self.plan["ports"]:
            port["aliases"] = {"maersk": aliases.get(port["id"], [])}

    def test_parses_all_seven_calls_and_distinct_voyage_numbers(self):
        self.assertEqual(len(self.packet["calls"]), 7)
        self.assertEqual(self.packet["calls"][0]["arrival"], "2027-01-06T23:00")
        self.assertEqual(self.packet["calls"][1]["arrivalVoyage"], "650W")
        self.assertEqual(self.packet["calls"][1]["departureVoyage"], "703E")
        self.assertEqual(self.packet["vesselName"], "MATHILDE MAERSK")

    def test_vessel_name_normalizes_spaces_without_changing_case(self):
        self.assertEqual(vessel_identifier("  mAtHiLdE   MaErSk  "), "mAtHiLdE MaErSk")
        self.assertEqual(vessel_key("mAtHiLdE MaErSk"), "mathilde maersk")

    def test_unknown_calls_are_not_silently_dropped_and_preview_does_not_write(self):
        preview = prepare_import(self.plan, self.packet)
        self.assertEqual(preview["unresolved"], ["call-1", "call-7"])
        self.assertEqual(len(preview["rows"]), 7)
        self.assertEqual(preview["voyageDate"], "2027-01-16")
        self.assertEqual(len(preview["candidate"]["voyages"]["2027-01-16"]["stops"]), 5)
        self.assertEqual(self.plan["ships"][-1]["voyages"], {})

    def test_explicitly_excluding_unknown_calls_leaves_matching_preview(self):
        preview = prepare_import(self.plan, self.packet, {"call-1": {"include": False}, "call-7": {"include": False}})
        self.assertEqual(preview["unresolved"], [])
        self.assertTrue(all(change["status"] == "unchanged" for change in preview["changes"]))

    def test_any_call_can_be_ignored_without_a_port_mapping(self):
        choices = {call["id"]: {"include": False} for call in self.packet["calls"]}
        choices["call-2"] = {"include": True}
        preview = prepare_import(self.plan, self.packet, choices)
        self.assertEqual(preview["unresolved"], [])
        self.assertEqual([row["id"] for row in preview["rows"] if row["include"]], ["call-2"])
        self.assertTrue(all(row["portId"] is None for row in preview["rows"] if not row["include"]))
        self.assertEqual([stop["portId"] for stop in preview["candidate"]["voyages"]["2027-01-16"]["stops"]], ["london"])

    def test_ignored_call_does_not_require_disambiguating_aliases(self):
        self.plan["ports"][0]["aliases"] = {"maersk": ["London Gateway Terminal"]}
        preview = prepare_import(self.plan, self.packet, {"call-2": {"include": False}})
        self.assertFalse(preview["rows"][1]["include"])
        self.assertIsNone(preview["rows"][1]["portId"])

    def test_ignoring_all_calls_never_creates_an_empty_plan_candidate(self):
        preview = prepare_import(self.plan, self.packet, {call["id"]: {"include": False} for call in self.packet["calls"]})
        self.assertEqual(preview["unresolved"], [])
        self.assertIsNone(preview["candidate"])

    def test_ambiguous_alias_fails(self):
        self.plan["ports"][0]["aliases"] = {"maersk": ["London Gateway Terminal"]}
        with self.assertRaisesRegex(ValueError, "Mehrdeutige"):
            resolve_port(self.packet["calls"][1], self.plan["ports"], "maersk")

    def test_terminal_alias_takes_precedence_over_shared_city_name(self):
        ports = [{"id": "rotterdam-mv2", "name": "Rotterdam", "aliases": {"maersk": ["APM 2 Terminal Maasvlakte II"]}},
                 {"id": "rotterdam-rwg", "name": "Rotterdam", "aliases": {"maersk": ["Rotterdam World Gateway"]}}]
        self.assertEqual(resolve_port({"portName": "Rotterdam", "terminalName": "APM 2 Terminal Maasvlakte II"}, ports, "maersk"), "rotterdam-mv2")
        with self.assertRaisesRegex(ValueError, "Mehrdeutige"):
            resolve_port({"portName": "Rotterdam", "terminalName": "Unknown"}, ports, "maersk")

    def service_bundle(self, plan):
        packets = []
        ports = {port["id"]: port for port in plan["ports"]}
        for ship in plan["ships"]:
            if ship["serviceId"] != "NE2":
                continue
            packet = {**self.packet, "vesselName": ship["name"].upper(), "calls": []}
            voyage = resolve_voyage(ship, "2027-01-01", plan["services"])
            for index, stop in enumerate(voyage["stops"]):
                packet["calls"].append({"id": f"call-{index + 1}", "portName": ports[stop["portId"]]["name"], "terminalName": "", "arrival": stop["arrival"], "departure": stop["departure"]})
            packets.append(packet)
        return {"schemaVersion": 1, "source": "maersk", "serviceId": "NE2", "packets": packets, "errors": []}

    def test_service_preview_has_independent_scoped_mappings(self):
        bundle = self.service_bundle(self.plan)
        preview = prepare_service_import(self.plan, bundle)
        self.assertEqual(len(preview["candidates"]), 6)
        self.assertEqual(preview["errors"], [])
        self.assertEqual(len({row["id"] for row in preview["rows"]}), 30)
        modified = prepare_service_import(self.plan, bundle, {"busan:call-1": {"include": False}})
        self.assertFalse(next(row for row in modified["rows"] if row["id"] == "busan:call-1")["include"])
        self.assertTrue(next(row for row in modified["rows"] if row["id"] == "berlin:call-1")["include"])

    def test_service_preview_does_not_hide_missing_ships(self):
        bundle = self.service_bundle(self.plan)
        bundle["packets"].pop()
        preview = prepare_service_import(self.plan, bundle)
        self.assertEqual(len(preview["errors"]), 1)
        missing_id = preview["errors"][0]["shipId"]
        excluded = prepare_service_import(self.plan, bundle, excluded_ships=[missing_id])
        self.assertEqual(excluded["errors"], [])
        self.assertEqual(len(excluded["candidates"]), 5)

    def test_service_preview_rejects_foreign_or_duplicate_vessels(self):
        bundle = self.service_bundle(self.plan)
        bundle["packets"].append(self.packet)
        with self.assertRaisesRegex(ValueError, "dienstfremdes"):
            prepare_service_import(self.plan, bundle)

    def test_duplicate_name_is_reported_after_restart_without_crashing_server(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            plan = client.get("/api/plan").get_json()
            path = Path(directory) / "ships/rotterdam.json"
            ship = next(ship for ship in plan["ships"] if ship["id"] == "rotterdam")
            ship["vesselName"] = "MATHILDE MAERSK"
            path.write_text(json.dumps(ship), encoding="utf-8")
            restarted = create_app(directory).test_client()
            self.assertEqual(restarted.get("/api/plan").status_code, 503)
            ship["vesselName"] = "ROTTERDAM EXPRESS"
            path.write_text(json.dumps(ship), encoding="utf-8")
            self.assertEqual(restarted.get("/api/plan").status_code, 200)
        bundle = self.service_bundle(self.plan)
        bundle["packets"].append(deepcopy(bundle["packets"][0]))
        with self.assertRaisesRegex(ValueError, "Doppeltes"):
            prepare_service_import(self.plan, bundle)

    def test_service_apply_checks_every_ship_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            before = client.get("/api/plan").get_json()
            bundle = self.service_bundle(before)
            bundle["packets"][1]["calls"][1]["arrival"] = "2027-01-25T04:00"
            payload = {"scope": "service", "serviceId": "NE2", "packet": bundle, "dataSignature": before["dataSignature"], "confirmTimeBasis": True, "confirmRemovals": True}
            result = client.post("/api/import/apply", json=payload)
            self.assertEqual(result.status_code, 200)
            updated = result.get_json()
            self.assertTrue(updated["importWarnings"])
            self.assertTrue(all(any("import" in voyage for voyage in ship["voyages"].values()) for ship in updated["ships"] if ship["serviceId"] == "NE2"))
            self.assertEqual(updated["ships"][-1], before["ships"][-1])
            self.assertEqual(client.get("/api/import/example").status_code, 404)

    def test_service_apply_blocks_partial_results_until_explicit_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            before = client.get("/api/plan").get_json()
            bundle = self.service_bundle(before)
            bundle["packets"].pop()
            payload = {"scope": "service", "serviceId": "NE2", "packet": bundle, "dataSignature": before["dataSignature"], "confirmTimeBasis": True}
            preview = client.post("/api/import/preview", json=payload).get_json()
            self.assertEqual(len(preview["errors"]), 1)
            self.assertEqual(client.post("/api/import/apply", json=payload).status_code, 400)
            self.assertEqual(client.get("/api/plan").get_json(), before)
            payload["excludedShips"] = [preview["errors"][0]["shipId"]]
            self.assertEqual(client.post("/api/import/apply", json=payload).status_code, 200)

    def test_dashboard_always_uses_headed_import_even_if_payload_requests_headless(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            with patch("app.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(self.packet), stderr="")) as runner:
                response = client.post("/api/import/maersk/live", json={"vesselName": "MATHILDE MAERSK", "fromDate": "2027-01-01", "toDate": "2027-03-01", "headed": False})
                self.assertEqual(response.status_code, 200)
                self.assertIn("--headed", runner.call_args.args[0])

    def test_multiple_rounds_cannot_be_merged_accidentally(self):
        packet = deepcopy(self.packet)
        packet["toDate"] = "2027-05-01"
        extra = dict(packet["calls"][1], id="next-round", arrival="2027-04-24T14:00", departure="2027-04-26T04:00")
        packet["calls"].append(extra)
        with self.assertRaisesRegex(ValueError, "mehrere Runden"):
            prepare_import(self.plan, packet)

    def test_import_preserves_past_and_after_window_byte_equivalent(self):
        ship = self.plan["ships"][-1]
        original = deepcopy(resolve_voyage(ship, "2027-01-01", self.plan["services"])["stops"])
        proforma_id = ship["proformaAssignments"][0]["proformaId"]
        ship["voyages"]["2027-01-16"] = {"proformaId": proforma_id, "stops": original}
        packet = deepcopy(self.packet)
        packet["calls"] = [call for call in packet["calls"] if call["portName"] == "Hamburg"]
        preview = prepare_import(self.plan, packet, voyage_date="2027-01-16", from_date="2027-01-22", to_date="2027-01-24")
        actual = preview["candidate"]["voyages"]["2027-01-16"]["stops"]
        self.assertEqual(len(actual), 5)
        self.assertEqual([stop for stop in actual if stop["portId"] != "hamburg"], [stop for stop in original if stop["portId"] != "hamburg"])
        self.assertFalse(any(change["status"] == "removed" for change in preview["changes"]))

    def test_cutoff_uses_arrival_and_protects_running_stay(self):
        preview = prepare_import(self.plan, self.packet, voyage_date="2027-01-16", from_date="2027-01-17")
        original = resolve_voyage(self.plan["ships"][-1], "2027-01-01", self.plan["services"])["stops"][0]
        actual = preview["candidate"]["voyages"]["2027-01-16"]["stops"]
        self.assertEqual(actual[0], original)
        self.assertTrue(preview["rows"][1]["outsideWindow"])
        self.assertFalse(preview["rows"][1]["include"])

    def test_shifted_proforma_call_crossing_import_start_replaces_template_instead_of_duplicating(self):
        ship = self.plan["ships"][-1]
        packet = deepcopy(self.packet)
        packet["calls"] = [call for call in packet["calls"] if call["portName"] == "London Gateway"]
        packet["calls"][0].update(arrival="2027-01-17T14:00", departure="2027-01-19T04:00")
        preview = prepare_import(self.plan, packet, from_date="2027-01-17", to_date="2027-01-19")
        stops = preview["candidate"]["voyages"]["2027-01-16"]["stops"]
        london = [stop for stop in stops if stop["portId"] == "london"]
        self.assertEqual(len(london), 1)
        self.assertEqual(london[0]["arrival"], "2027-01-17T14:00")
        self.assertEqual(preview["changes"][0]["status"], "changed")
        self.assertEqual(ship["voyages"], {})

    def test_shifted_actual_call_does_not_overwrite_protected_history(self):
        ship = self.plan["ships"][-1]
        voyage = resolve_voyage(ship, "2027-01-16", self.plan["services"])
        ship["voyages"][voyage["key"]] = {"proformaId": voyage["proformaId"], "stops": deepcopy(voyage["stops"])}
        packet = deepcopy(self.packet)
        packet["calls"] = [call for call in packet["calls"] if call["portName"] == "London Gateway"]
        packet["calls"][0].update(arrival="2027-01-17T14:00", departure="2027-01-19T04:00")
        preview = prepare_import(self.plan, packet, from_date="2027-01-17", to_date="2027-01-19")
        london = [stop for stop in preview["candidate"]["voyages"][voyage["key"]]["stops"] if stop["portId"] == "london"]
        self.assertEqual(len(london), 2)
        self.assertEqual(london[0], voyage["stops"][0])

    def test_first_import_into_ship_without_schedule(self):
        ship = self.plan["ships"][-1]
        ship["proformaAssignments"] = []
        ship["voyages"] = {}
        preview = prepare_import(self.plan, self.packet, {"call-1": {"include": False}, "call-7": {"include": False}})
        candidate = preview["candidate"]
        self.assertEqual(candidate["proformaAssignments"], [])
        self.assertIsNone(candidate["voyages"]["2027-01-16"]["proformaId"])
        validate_ship(candidate, ship, self.plan["ports"], services=self.plan["services"])
        self.assertEqual(len(resolve_voyage(candidate, "2027-01-22", self.plan["services"])["stops"]), 5)

    def test_api_import_cutoff_does_not_remove_historical_stays(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            (Path(directory) / "ports.json").write_text(json.dumps(self.plan["ports"]), encoding="utf-8")
            before = client.get("/api/plan").get_json()
            packet = deepcopy(self.packet)
            packet["calls"] = [call for call in packet["calls"] if call["portName"] == "Hamburg"]
            payload = {"packet": packet, "fromDate": "2027-01-22", "toDate": "2027-01-24", "dataSignature": before["dataSignature"], "confirmTimeBasis": True}
            result = client.post("/api/import/apply", json=payload)
            self.assertEqual(result.status_code, 200)
            ship = result.get_json()["ships"][-1]
            self.assertEqual(len(ship["voyages"]["2027-01-16"]["stops"]), 5)
            self.assertEqual(ship["voyages"]["2027-01-16"]["stops"][:2], resolve_voyage(before["ships"][-1], "2027-01-01", before["services"])["stops"][:2])

    def test_created_ship_receives_first_actual_schedule_via_import(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            plan = client.get("/api/plan").get_json()
            created = client.post("/api/fleet", json={"dataSignature": plan["dataSignature"], "id": "fresh", "name": "Fresh Vessel", "vesselName": "FRESH VESSEL", "serviceId": "NEW", "maxSpeedKnots": 20})
            self.assertEqual(created.status_code, 200)
            packet = {"schemaVersion": 1, "source": "maersk", "vesselName": "FRESH VESSEL", "fromDate": "2027-01-01", "toDate": "2027-01-02", "calls": [{"id": "first", "portName": "Hamburg Eurogate", "terminalName": "", "arrival": "2027-01-01T00:00", "departure": "2027-01-01T12:00"}]}
            imported = client.post("/api/import/apply", json={"packet": packet, "dataSignature": created.get_json()["dataSignature"], "confirmTimeBasis": True})
            self.assertEqual(imported.status_code, 200)
            ship = next(ship for ship in imported.get_json()["ships"] if ship["id"] == "fresh")
            self.assertEqual(ship["proformaAssignments"], [])
            self.assertEqual(len(ship["voyages"]["2027-01-01"]["stops"]), 1)

    def test_script_file_mode_produces_common_json(self):
        import subprocess
        import sys
        root = Path(__file__).parent
        result = subprocess.run([sys.executable, str(root / "import_maersk.py"), "--input", str(root / "examples/maersk_mathilde_2027.txt"), "--vessel", self.packet["vesselName"], "--from", self.packet["fromDate"], "--to", self.packet["toDate"]], capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["source"], "maersk")
        self.assertEqual(len(packet["calls"]), 7)

    def test_live_browser_selects_real_option_before_search(self):
        page, vessel, date, status, option, typeahead = [MagicMock() for _ in range(6)]
        for locator in (vessel, date, status, option):
            locator.last = locator
            locator.first = locator
            locator.filter.return_value = locator
        typeahead.evaluate.return_value = {"vesselCode": "2BM", "vesselName": "MATHILDE MAERSK"}
        date.evaluate.return_value = {"min": "2026-07-28", "max": "2027-01-24"}
        page.locator.side_effect = lambda selector: vessel if 'input[name="vesselName"]' in selector else date if 'input[name="vesselSchedulesDatePicker"]' in selector else option if selector.startswith('mc-option') else typeahead if selector.startswith('mc-typeahead') else status
        page.url = "https://www.maersk.com/schedules/vesselSchedules?vesselCode=2BM&fromDate=2027-01-01"
        status.inner_text.return_value = SAMPLE
        actions = MagicMock()
        actions.attach_mock(vessel.fill, "fill")
        actions.attach_mock(vessel.click, "open_dropdown")
        actions.attach_mock(option.wait_for, "wait_option")
        actions.attach_mock(option.click, "select_option")
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            browser.new_page.return_value = page
            text, url = fetch_schedule("MATHILDE MAERSK", "2027-01-01", headed=True)
            option.click.assert_called_once()
            vessel.press.assert_not_called()
            page.wait_for_url.assert_called_once()
            self.assertEqual(page.wait_for_url.call_args.kwargs, {"wait_until": "commit", "timeout": 15000})
            browser.close.assert_called_once()
            page.set_default_timeout.assert_called_once_with(20000)
            page.set_default_navigation_timeout.assert_called_once_with(20000)
            page.goto.assert_called_once_with(MAERSK_URL, wait_until="commit", timeout=20000)
            vessel.wait_for.assert_called_once_with(state="visible", timeout=20000)
            option.wait_for.assert_called_once_with(state="visible", timeout=20000)
            status.wait_for.assert_not_called()
            self.assertEqual([call[0] for call in actions.mock_calls], ["fill", "open_dropdown", "wait_option", "select_option"])
            expected_options = {"headless": False, "timeout": 20000}
            if sys.platform == "win32":
                expected_options["channel"] = "msedge"
            automation.return_value.__enter__.return_value.chromium.launch.assert_called_once_with(**expected_options)
        self.assertEqual(text, SAMPLE)
        self.assertIn("vesselCode=2BM", url)

    def test_live_browser_rejects_dates_outside_source_range_before_search(self):
        for start in ("2026-01-03", "2027-01-25"):
            with self.subTest(start=start):
                page, locator, date = MagicMock(), MagicMock(), MagicMock()
                locator.last = locator.first = locator
                locator.filter.return_value = locator
                locator.evaluate.return_value = {"value": "GDANSK EXPRESS"}
                date.last = date
                date.evaluate.return_value = {"min": "2026-07-28", "max": "2027-01-24"}
                page.locator.side_effect = lambda selector: date if selector == 'input[name="vesselSchedulesDatePicker"]:visible' else locator
                with patch("playwright.sync_api.sync_playwright") as automation:
                    browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
                    browser.new_page.return_value = page
                    with self.assertRaisesRegex(ValueError, f"Suchdatum {start}.*2026-07-28 bis 2027-01-24"):
                        fetch_schedule("GDANSK EXPRESS", start, headed=True)
                    date.fill.assert_not_called()
                    page.get_by_text.assert_not_called()
                    page.wait_for_url.assert_not_called()
                    browser.close.assert_called_once()

    def test_live_browser_accepts_source_range_boundaries_and_missing_bounds(self):
        for start, bounds in (
            ("2026-07-28", {"min": "2026-07-28", "max": "2027-01-24"}),
            ("2027-01-24", {"min": "2026-07-28", "max": "2027-01-24"}),
            ("2026-01-03", {"min": None, "max": None}),
        ):
            with self.subTest(start=start):
                page, locator, date = MagicMock(), MagicMock(), MagicMock()
                locator.last = locator.first = locator
                locator.filter.return_value = locator
                locator.evaluate.return_value = {"value": "GDANSK EXPRESS"}
                date.last = date
                date.evaluate.return_value = bounds
                page.locator.side_effect = lambda selector: date if selector == 'input[name="vesselSchedulesDatePicker"]:visible' else locator
                with patch("playwright.sync_api.sync_playwright") as automation:
                    browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
                    browser.new_page.return_value = page
                    fetch_schedule("GDANSK EXPRESS", start)
                    year, month, day = start.split("-")
                    date.fill.assert_called_once_with(f"{day}/{month}/{year}")
                    page.wait_for_url.assert_called_once()
                    browser.close.assert_called_once()

    def test_live_browser_reports_missing_suggestion_and_closes_without_search(self):
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        page, vessel, option, status = [MagicMock() for _ in range(4)]
        vessel.last = vessel
        option.filter.return_value.first = option
        option.wait_for.side_effect = PlaywrightTimeoutError("Timeout 20000ms exceeded")
        status.all_text_contents.return_value = ["No suggestions found"]
        page.locator.side_effect = lambda selector: vessel if selector == 'input[name="vesselName"]:visible' else option if selector.startswith("mc-option") else status
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            browser.new_page.return_value = page
            with self.assertRaisesRegex(ValueError, "20 Sekunden.*No suggestions found"):
                fetch_schedule("MATHILDE MAERSK", "2027-01-01")
            vessel.fill.assert_called_once_with("MATHILDE MAERSK")
            option.wait_for.assert_called_once_with(state="visible", timeout=20000)
            option.click.assert_not_called()
            page.get_by_text.assert_not_called()
            browser.close.assert_called_once()

    def test_live_browser_rejects_unconfirmed_selection(self):
        page, locator = MagicMock(), MagicMock()
        locator.last = locator.first = locator
        locator.filter.return_value = locator
        locator.evaluate.return_value = None
        page.locator.return_value = locator
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            browser.new_page.return_value = page
            with self.assertRaisesRegex(ValueError, "nicht als Auswahl uebernommen"):
                fetch_schedule("MATHILDE MAERSK", "2027-01-01")
            page.get_by_text.assert_not_called()
            browser.close.assert_called_once()

    def test_live_browser_reports_navigation_timeout_without_querying_dom(self):
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        page = MagicMock()
        page.goto.side_effect = PlaywrightTimeoutError("Timeout 20000ms exceeded")
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            browser.new_page.return_value = page
            with self.assertRaisesRegex(ValueError, "Phase: Seite laden.*keine Seitennavigation"):
                fetch_schedule("MATHILDE MAERSK", "2027-01-01")
            page.locator.assert_not_called()
            browser.close.assert_called_once()

    def test_live_browser_reports_http_error_without_waiting_for_form(self):
        page = MagicMock()
        page.goto.return_value.ok = False
        page.goto.return_value.status = 503
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            browser.new_page.return_value = page
            with self.assertRaisesRegex(ValueError, "HTTP 503"):
                fetch_schedule("MATHILDE MAERSK", "2027-01-01")
            page.locator.assert_not_called()
            browser.close.assert_called_once()

    def test_live_browser_reports_missing_form_without_starting_search(self):
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        page, vessel = MagicMock(), MagicMock()
        vessel.last = vessel
        vessel.wait_for.side_effect = PlaywrightTimeoutError("Timeout 20000ms exceeded")
        page.locator.return_value = vessel
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            browser.new_page.return_value = page
            with self.assertRaisesRegex(ValueError, "Phase: Suchformular laden.*Suchformular ist nach 20 Sekunden nicht sichtbar"):
                fetch_schedule("MATHILDE MAERSK", "2027-01-01")
            vessel.fill.assert_not_called()
            vessel.evaluate_all.assert_not_called()
            page.get_by_text.assert_not_called()
            browser.close.assert_called_once()

    def test_live_api_runs_separate_script_without_saving(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            before = client.get("/api/plan").get_json()
            with patch("app.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(self.packet), stderr="")) as runner:
                response = client.post("/api/import/maersk/live", json={"vesselName": "MATHILDE MAERSK", "fromDate": "2027-01-01", "toDate": "2027-03-01", "headed": True})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.get_json()["packet"]["calls"]), 7)
                self.assertIn("--headed", runner.call_args.args[0])
                self.assertEqual(client.get("/api/plan").get_json(), before)

    def test_live_api_rejects_unknown_vessel_and_script_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            payload = {"vesselName": "UNKNOWN VESSEL", "fromDate": "2027-01-01", "toDate": "2027-03-01"}
            with patch("app.subprocess.run") as runner:
                self.assertEqual(client.post("/api/import/maersk/live", json=payload).status_code, 400)
                runner.assert_not_called()
            payload["vesselName"] = "MATHILDE MAERSK"
            with patch("app.subprocess.run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="Suchfehler")):
                response = client.post("/api/import/maersk/live", json=payload)
                self.assertEqual(response.status_code, 502)
                self.assertIn("Suchfehler", response.get_json()["error"])

    def test_live_api_passes_import_name_case_to_search(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            packet = {**self.packet, "vesselName": "mathilde maersk"}
            output = json.dumps(packet)
            with patch("app.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=output, stderr="")) as runner:
                response = client.post("/api/import/maersk/live", json={"vesselName": "mathilde maersk", "fromDate": "2027-01-01", "toDate": "2027-03-01", "headed": True})
            self.assertEqual(response.status_code, 200)
            command = runner.call_args.args[0]
            self.assertEqual(command[command.index("--vessel") + 1], "mathilde maersk")

    def test_api_preview_and_explicit_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            ports = Path(directory) / "ports.json"
            ports.write_text(json.dumps(self.plan["ports"]), encoding="utf-8")
            before = client.get("/api/plan").get_json()
            payload = {"packet": self.packet, "choices": {"call-1": {"include": False}, "call-7": {"include": False}}}
            preview = client.post("/api/import/preview", json=payload)
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(client.get("/api/plan").get_json(), before)
            payload["dataSignature"] = preview.get_json()["dataSignature"]
            self.assertEqual(client.post("/api/import/apply", json=payload).status_code, 400)
            payload["confirmTimeBasis"] = True
            applied = client.post("/api/import/apply", json=payload)
            self.assertEqual(applied.status_code, 200)
            self.assertEqual(applied.get_json()["services"], before["services"])

    def test_api_blocks_unknown_ports_and_duplicate_vessel_names(self):
        with tempfile.TemporaryDirectory() as directory:
            client = create_app(directory).test_client()
            plan = client.get("/api/plan").get_json()
            response = client.post("/api/import/apply", json={"packet": self.packet, "dataSignature": plan["dataSignature"], "confirmTimeBasis": True})
            self.assertEqual(response.status_code, 400)
            duplicate = dict(plan["ships"][-1], id="duplicate", name="MATHILDE MAERSK")
            (Path(directory) / "ships/duplicate.json").write_text(json.dumps(duplicate), encoding="utf-8")
            self.assertEqual(client.get("/api/plan").status_code, 503)


if __name__ == "__main__":
    unittest.main()