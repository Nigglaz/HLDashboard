import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from schedule_import import vessel_identifier, vessel_key


HAPAG_URL = "https://www.hapag-lloyd.com/en/online-business/track/vessel-tracker-solution.html"


def parse_hapag_rows(rows, voyages, vessel_name, from_date, to_date):
    start, end = datetime.fromisoformat(from_date).date(), datetime.fromisoformat(to_date).date()
    if end < start:
        raise ValueError("Das Enddatum liegt vor dem Startdatum.")
    voyage_map = {}
    for row in voyages:
        if len(row) != 6 or not row[0] or not row[1]:
            raise ValueError("Unbekanntes Format der Hapag-Reiseliste.")
        voyage_map[row[1]] = row[0]
    calls = {}
    internal = None
    for row in rows:
        cells = row["cells"]
        if len(cells) == 12:
            internal = cells[1]
            cells = [cells[0], *cells[2:]]
        if len(cells) != 11 or internal not in voyage_map:
            raise ValueError("Unbekanntes Format der Hapag-Hafenliste.")
        if row["omit"]:
            continue
        port = cells[1].strip()
        try:
            arrival = datetime.strptime(f"{cells[3]} {cells[4]}", "%Y-%m-%d %H:%M")
            departure = datetime.strptime(f"{cells[7]} {cells[8]}", "%Y-%m-%d %H:%M")
        except ValueError as error:
            raise ValueError(f"Unvollstaendige Hapag-Zeiten fuer {port}: {cells[3:9]}") from error
        if not port or departure <= arrival:
            raise ValueError(f"Ungueltiger Hapag-Aufenthalt: {port}")
        if not start <= arrival.date() <= end:
            continue
        key = (vessel_key(port), arrival, departure)
        voyage = voyage_map[internal]
        if key in calls:
            calls[key]["departureVoyage"] = voyage
            continue
        calls[key] = {"portName": port, "terminalName": "", "arrival": arrival.isoformat(timespec="minutes"),
                      "departure": departure.isoformat(timespec="minutes"), "arrivalVoyage": voyage, "departureVoyage": voyage}
    ordered = sorted(calls.values(), key=lambda call: call["arrival"])
    if not ordered:
        raise ValueError("Keine vollstaendigen Hapag-Hafenaufenthalte im Zeitraum gefunden.")
    return {"schemaVersion": 1, "source": "hapag", "sourceUrl": HAPAG_URL,
            "vesselName": vessel_identifier(vessel_name), "fromDate": from_date, "toDate": to_date,
            "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "timeBasis": "unconfirmed",
            "calls": [{"id": f"call-{index + 1}", **call} for index, call in enumerate(ordered)]}


def fetch_schedule(vessel_name, from_date, to_date, browser_channel=None, headed=False):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

    with sync_playwright() as automation:
        options = {"headless": not headed, "timeout": 20000}
        channel = browser_channel or ("msedge" if sys.platform == "win32" else "chromium")
        if channel != "chromium":
            options["channel"] = channel
        browser = automation.chromium.launch(**options)
        stage = "Seite laden"
        try:
            page = browser.new_page(locale="en-GB", viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(20000)
            page.set_default_navigation_timeout(20000)
            page.goto(HAPAG_URL, wait_until="commit")
            form = page.locator('form[id="schedules_vessel_tracing_f"]')
            stage = "Schiffsauswahl laden"
            try:
                form.locator('input[type="text"]').wait_for(state="visible")
            except PlaywrightTimeoutError as error:
                content = page.locator("body").inner_text(timeout=3000)
                if re.search(r"Security Check|checking your browser|Just a moment|Captcha", content, re.I):
                    if not headed:
                        raise ValueError("Hapag-Lloyd fordert eine Browser-Sicherheitspruefung. Bitte mit sichtbarem Browser erneut abrufen und das CAPTCHA dort selbst bestaetigen.") from error
                    stage = "Manuelle Sicherheitspruefung im Browser (bis zu 2 Minuten)"
                    print("Bitte die Hapag-Sicherheitspruefung im geoeffneten Browser selbst bestaetigen. Der Import wartet bis zu 2 Minuten und setzt danach automatisch fort.", file=sys.stderr, flush=True)
                    try:
                        form.locator('input[type="text"]').wait_for(state="visible", timeout=120000)
                    except PlaywrightTimeoutError as challenge_error:
                        raise ValueError("Die manuelle Sicherheitspruefung wurde innerhalb von 2 Minuten nicht abgeschlossen oder Hapag hat den Browser weiterhin blockiert. Bitte erneut abrufen oder eine gespeicherte Hapag-Import-JSON laden.") from challenge_error
                else:
                    raise ValueError("Die Hapag-Schiffsauswahl ist nach 20 Sekunden nicht sichtbar.") from error
            stage = "Schiff auswaehlen"
            form.locator(".x-form-arrow-trigger").click()
            page.locator(".x-combo-list-item:visible").first.wait_for(state="visible")
            option = page.locator(".x-combo-list-item:visible").filter(has_text=re.compile(r"^\s*" + re.escape(vessel_name) + r"\s*$", re.I))
            if option.count() == 0:
                form.get_by_role("button", name="Show feeder only", exact=True).click()
                form.locator(".x-form-arrow-trigger").click()
            option.first.click()
            stage = "Fahrplan laden"
            form.get_by_role("button", name="Find", exact=True).click()
            page.wait_for_function("""name => {
                const form = document.getElementById('schedules_vessel_tracing_f');
                return form && form.innerText.toLowerCase().includes(name.toLowerCase())
                    && [...form.querySelectorAll('table.hl-tbl')].some(t => t.innerText.includes('Omit'));
            }""", arg=vessel_name)
            tables = form.locator("table.hl-tbl")
            voyage_table = tables.filter(has_text="Transit Time")
            call_table = tables.filter(has_text="Omit")
            if voyage_table.count() != 1 or call_table.count() != 1:
                raise ValueError("Hapag hat keine eindeutigen Fahrplantabellen geliefert.")
            voyages = voyage_table.locator("tbody > tr.odd, tbody > tr.even").evaluate_all("rows => rows.map(r => [...r.cells].map(c => c.innerText.trim()))")
            rows = call_table.locator("tbody > tr.odd, tbody > tr.even").evaluate_all("""rows => rows.map(r => ({
                cells: [...r.cells].map(c => c.innerText.trim()),
                omit: Boolean(r.querySelector('input[type=checkbox]:checked'))
            }))""")
            return parse_hapag_rows(rows, voyages, vessel_name, from_date, to_date)
        except (ValueError, PlaywrightTimeoutError) as error:
            raise ValueError(f"Phase: {stage}; URL: {page.url}; Ursache: {error}") from error
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="Hapag-Fahrplan als Import-JSON abrufen; keine Planungsdaten werden veraendert.")
    parser.add_argument("--vessel", required=True)
    parser.add_argument("--from", dest="from_date", required=True)
    parser.add_argument("--to", dest="to_date", required=True)
    parser.add_argument("--browser", choices=("msedge", "chrome", "chromium"))
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        packet = fetch_schedule(vessel_identifier(args.vessel), args.from_date, args.to_date, args.browser, args.headed)
        output = json.dumps(packet, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
        return 0
    except Exception as error:
        print(f"Hapag-Import fehlgeschlagen: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
