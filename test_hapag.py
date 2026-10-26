import json
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from import_hapag import HAPAG_URL, fetch_schedule, parse_hapag_rows
from test_support import create_test_app


VOYAGES = [
    ["636W", "689014", "NE2", "ROTTERDAM", "LONDON GATEWAY PORT", "8"],
    ["643E", "689009", "NE2", "ROTTERDAM", "YANTIAN", "56"],
]
ROWS = [
    {"cells": ["", "689014", "ROTTERDAM", "Monday", "2026-10-26", "12:00", "Estimated Arrival", "Wednesday", "2026-10-28", "18:00", "Estimated Departure", ""], "omit": False},
    {"cells": ["", "HAMBURG", "Friday", "2026-10-30", "10:00", "Estimated Arrival", "Sunday", "2026-11-01", "00:01", "Estimated Departure", ""], "omit": False},
    {"cells": ["", "689009", "ROTTERDAM", "Monday", "2026-10-26", "12:00", "Estimated Arrival", "Wednesday", "2026-10-28", "18:00", "Estimated Departure", ""], "omit": False},
    {"cells": ["", "HAMBURG", "Friday", "2026-10-30", "10:00", "Estimated Arrival", "Sunday", "2026-11-01", "00:01", "Estimated Departure", ""], "omit": False},
]


class HapagTests(unittest.TestCase):
    def packet(self, rows=None, start="2026-10-26", end="2026-11-01"):
        return parse_hapag_rows(ROWS if rows is None else rows, VOYAGES, "Gdansk Express", start, end)

    def test_rowspans_and_duplicate_voyages_produce_one_physical_call(self):
        packet = self.packet()
        self.assertEqual(packet["source"], "hapag")
        self.assertEqual(packet["sourceUrl"], HAPAG_URL)
        self.assertEqual(packet["timeBasis"], "unconfirmed")
        self.assertEqual(len(packet["calls"]), 2)
        self.assertEqual(packet["calls"][0]["arrival"], "2026-10-26T12:00")
        self.assertEqual(packet["calls"][1]["departure"], "2026-11-01T00:01")
        self.assertEqual(packet["calls"][0]["arrivalVoyage"], "636W")
        self.assertEqual(packet["calls"][0]["departureVoyage"], "643E")
        self.assertEqual([call["id"] for call in packet["calls"]], ["call-1", "call-2"])

    def test_window_is_inclusive_and_filters_by_arrival(self):
        self.assertEqual(len(self.packet(start="2026-10-26", end="2026-10-26")["calls"]), 1)
        packet = self.packet(start="2026-10-27")
        self.assertEqual([call["portName"] for call in packet["calls"]], ["HAMBURG"])

    def test_repeated_ports_on_different_dates_are_not_merged(self):
        rows = deepcopy(ROWS)
        rows[2]["cells"][5] = "15:00"
        self.assertEqual(len(self.packet(rows)["calls"]), 3)

    def test_omitted_calls_are_not_imported(self):
        rows = deepcopy(ROWS)
        rows[0]["omit"] = rows[2]["omit"] = True
        rows[0]["cells"][4] = ""
        self.assertEqual([call["portName"] for call in self.packet(rows)["calls"]], ["HAMBURG"])

    def test_invalid_and_empty_source_data_fail_explicitly(self):
        for rows in [[], [{"cells": ["broken"], "omit": False}], deepcopy(ROWS)]:
            if len(rows) == 4:
                rows[0]["cells"][4] = ""
            with self.assertRaises(ValueError):
                self.packet(rows)
        with self.assertRaises(ValueError):
            self.packet(start="2026-12-01", end="2026-10-01")
        with self.assertRaises(ValueError):
            parse_hapag_rows(ROWS, [["broken"]], "Gdansk Express", "2026-10-26", "2026-11-01")

    def test_live_browser_extracts_verified_table_structure(self):
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            page = browser.new_page.return_value
            tables = page.locator.return_value.locator.return_value
            voyages, calls = MagicMock(), MagicMock()
            tables.filter.side_effect = [voyages, calls]
            voyages.count.return_value = calls.count.return_value = 1
            voyages.locator.return_value.evaluate_all.return_value = VOYAGES
            calls.locator.return_value.evaluate_all.return_value = ROWS
            packet = fetch_schedule("Gdansk Express", "2026-10-26", "2026-11-01", headed=True)
            self.assertEqual(len(packet["calls"]), 2)
            self.assertEqual(page.goto.call_args.args[0], HAPAG_URL)
            browser.close.assert_called_once()

    def test_security_challenge_is_reported_and_browser_closed(self):
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            page = browser.new_page.return_value
            page.locator.return_value.locator.return_value.wait_for.side_effect = PlaywrightTimeoutError("timeout")
            page.locator.return_value.inner_text.return_value = "Security Check"
            with self.assertRaisesRegex(ValueError, "Sicherheitspruefung"):
                fetch_schedule("Gdansk Express", "2026-10-26", "2026-11-01")
            browser.close.assert_called_once()

    def test_visible_browser_waits_for_manual_challenge_then_continues(self):
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            page = browser.new_page.return_value
            field = page.locator.return_value.locator.return_value
            field.wait_for.side_effect = [PlaywrightTimeoutError("challenge"), None]
            page.locator.return_value.inner_text.return_value = "Security Check"
            voyages, calls = MagicMock(), MagicMock()
            field.filter.side_effect = [voyages, calls]
            voyages.count.return_value = calls.count.return_value = 1
            voyages.locator.return_value.evaluate_all.return_value = VOYAGES
            calls.locator.return_value.evaluate_all.return_value = ROWS
            packet = fetch_schedule("Gdansk Express", "2026-10-26", "2026-11-01", headed=True)
            self.assertEqual(len(packet["calls"]), 2)
            self.assertEqual(field.wait_for.call_args.kwargs["timeout"], 120000)
            browser.close.assert_called_once()

    def test_visible_browser_reports_manual_challenge_timeout(self):
        with patch("playwright.sync_api.sync_playwright") as automation:
            browser = automation.return_value.__enter__.return_value.chromium.launch.return_value
            page = browser.new_page.return_value
            page.locator.return_value.locator.return_value.wait_for.side_effect = PlaywrightTimeoutError("timeout")
            page.locator.return_value.inner_text.return_value = "Security Check"
            with self.assertRaisesRegex(ValueError, "innerhalb von 2 Minuten"):
                fetch_schedule("Gdansk Express", "2026-10-26", "2026-11-01", headed=True)
            browser.close.assert_called_once()

    def test_live_endpoint_selects_hapag_and_never_writes(self):
        with tempfile.TemporaryDirectory() as root:
            client = create_test_app(root).test_client()
            before = client.get("/api/plan").get_json()
            with patch("app.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(self.packet()), stderr="")) as runner:
                response = client.post("/api/import/hapag/live", json={"vesselName": "Gdansk Express", "fromDate": "2026-10-26", "toDate": "2026-11-01"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(Path(runner.call_args.args[0][1]).name, "import_hapag.py")
            self.assertIn("--headed", runner.call_args.args[0])
            self.assertEqual(client.get("/api/plan").get_json(), before)

    def test_live_endpoint_rejects_wrong_source_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as root:
            client = create_test_app(root).test_client()
            payload = {"vesselName": "Gdansk Express", "fromDate": "2026-10-26", "toDate": "2026-11-01"}
            for result in [SimpleNamespace(returncode=1, stdout="", stderr="Security Check"),
                           SimpleNamespace(returncode=0, stdout=json.dumps({**self.packet(), "source": "maersk"}), stderr="")]:
                with patch("app.subprocess.run", return_value=result):
                    self.assertEqual(client.post("/api/import/hapag/live", json=payload).status_code, 502)
            with patch("app.subprocess.run", side_effect=subprocess.TimeoutExpired("hapag", 180)):
                response = client.post("/api/import/hapag/live", json=payload)
                self.assertEqual(response.status_code, 504)
                self.assertIn("Hapag-Lloyd", response.get_json()["error"])
            self.assertEqual(client.post("/api/import/unknown/live", json=payload).status_code, 404)

    def test_hapag_preview_apply_and_service_bundle_use_existing_workflow(self):
        with tempfile.TemporaryDirectory() as root:
            client = create_test_app(root).test_client()
            plan = client.get("/api/plan").get_json()
            stops = plan["services"][0]["proformas"][0]["stops"]
            ports = {port["id"]: port["name"] for port in plan["ports"]}
            packet = {**self.packet(), "vesselName": "Busan Express", "fromDate": "2027-01-16", "toDate": "2027-02-03",
                      "calls": [{"id": stop["id"], "portName": ports[stop["portId"]], "arrival": stop["arrival"], "departure": stop["departure"]} for stop in stops]}
            payload = {"packet": packet}
            preview = client.post("/api/import/preview", json=payload)
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.get_json()["unresolved"], [])
            self.assertEqual(client.get("/api/plan").get_json(), plan)
            payload.update(dataSignature=plan["dataSignature"], confirmTimeBasis=True)
            applied = client.post("/api/import/apply", json=payload)
            self.assertEqual(applied.status_code, 200, applied.get_json())
            stored = next(ship for ship in applied.get_json()["ships"] if ship["id"] == "busan")["voyages"]["2027-01-16"]
            self.assertEqual(stored["import"]["source"], "hapag")
            self.assertTrue(all(stop["source"]["provider"] == "hapag" for stop in stored["stops"]))
            bundle = {"schemaVersion": 1, "source": "hapag", "serviceId": "NE2", "packets": [packet], "errors": []}
            response = client.post("/api/import/preview", json={"packet": bundle})
            self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
