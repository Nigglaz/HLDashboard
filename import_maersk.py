import argparse
import json
import re
import sys
from pathlib import Path

from schedule_import import MAERSK_URL, parse_maersk_text, vessel_identifier


def fetch_schedule(vessel_name, from_date, browser_channel=None, headed=False):
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
    except ImportError as error:
        raise ValueError("Playwright fehlt. Bitte python -m pip install -r requirements.txt ausfuehren.") from error
    channel = browser_channel or ("msedge" if sys.platform == "win32" else "chromium")
    with sync_playwright() as automation:
        options = {"headless": not headed, "timeout": 20000}
        if channel != "chromium":
            options["channel"] = channel
        browser = automation.chromium.launch(**options)
        stage = "Seite laden"
        try:
            page = browser.new_page(locale="en-GB")
            page.set_default_timeout(20000)
            page.set_default_navigation_timeout(20000)
            try:
                response = page.goto(MAERSK_URL, wait_until="commit", timeout=20000)
            except PlaywrightTimeoutError as error:
                raise ValueError("Maersk hat innerhalb von 20 Sekunden keine Seitennavigation bestaetigt. Der Abruf scheitert vor dem Laden der Schiffsauswahl.") from error
            if response is not None and not response.ok:
                raise ValueError(f"Maersk-Seite konnte nicht geladen werden: HTTP {response.status}.")
            stage = "Suchformular laden"
            vessel = page.locator('input[name="vesselName"]:visible').last
            try:
                vessel.wait_for(state="visible", timeout=20000)
            except PlaywrightTimeoutError as error:
                raise ValueError("Maersk hat die Seite geliefert, aber das Suchformular ist nach 20 Sekunden nicht sichtbar. Benoetigte Seiteninhalte oder JavaScript-Dateien wurden moeglicherweise nicht geladen. Bitte die Maersk-Seite im normalen Browser auf demselben Rechner/Netzwerk pruefen.") from error
            try:
                page.get_by_role("button", name="Essential only", exact=True).click(timeout=8000)
            except PlaywrightTimeoutError:
                pass
            stage = "Schiffsname eingeben"
            vessel.fill(vessel_name)
            stage = "Schiff auswaehlen"
            vessel.click()
            option = page.locator('mc-option[role="option"]').filter(has_text=re.compile(r"^\s*" + re.escape(vessel_name) + r"\s*$")).first
            try:
                option.wait_for(state="visible", timeout=20000)
            except PlaywrightTimeoutError as error:
                status = page.locator('[aria-live]').all_text_contents()
                raise ValueError(f"Kein auswaehlbarer Schiffsvorschlag fuer {vessel_name} innerhalb von 20 Sekunden. Status: {status}") from error
            option.click()
            selected = page.locator('mc-typeahead[name="vesselName"]').evaluate("element => element.selecteddata")
            if not selected:
                raise ValueError("Der Schiffsvorschlag wurde nicht als Auswahl uebernommen.")
            stage = "Datum setzen"
            date = page.locator('input[name="vesselSchedulesDatePicker"]:visible').last
            bounds = date.evaluate("""element => {
                const isoDate = value => {
                    if (!value) return null;
                    const parsed = new Date(value);
                    if (!Number.isFinite(parsed.getTime())) throw new Error(`Ungueltige Maersk-Datumsgrenze: ${value}`);
                    return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}-${String(parsed.getDate()).padStart(2, '0')}`;
                };
                return {min: isoDate(element.min), max: isoDate(element.max)};
            }""")
            if (bounds["min"] and from_date < bounds["min"]) or (bounds["max"] and from_date > bounds["max"]):
                raise ValueError(f"Das Suchdatum {from_date} liegt ausserhalb des von Maersk erlaubten Zeitraums ({bounds['min'] or 'offen'} bis {bounds['max'] or 'offen'}). Bitte das Ab-Datum im Datenimport anpassen. Historische Fahrplaene koennen weiterhin aus einer gespeicherten Datei importiert werden.")
            year, month, day = from_date.split("-")
            date.fill(f"{day}/{month}/{year}")
            date.press("Tab")
            stage = "Suche absenden"
            page.get_by_text("Search", exact=True).click()
            page.wait_for_url(re.compile(r"[?&]vesselCode=[^&]+"), wait_until="commit", timeout=15000)
            stage = "Suchergebnis laden"
            page.get_by_text(f"Search results for {vessel_name}", exact=True).wait_for(timeout=20000)
            page.get_by_text(re.compile(r"^Arrival\s*[-\u2013\u2014]")).first.wait_for(timeout=20000)
            return page.locator("main").inner_text(), page.url
        except Exception as error:
            if stage in ("Seite laden", "Suchformular laden"):
                raise ValueError(f"Phase: {stage}; URL: {page.url}; Ursache: {error}") from error
            try:
                fields = page.locator('input[name="vesselName"], input[name="vesselSchedulesDatePicker"]').evaluate_all("elements => elements.map(element => ({name: element.name, value: element.value}))")
                content = page.locator("main").inner_text(timeout=3000)[:1600]
                status = page.locator('[aria-live]').all_text_contents()
                raise ValueError(f"Phase: {stage}; URL: {page.url}; Felder: {fields}; Status: {status}; Seite: {content}; Ursache: {error}") from error
            except ValueError:
                raise
            except Exception:
                raise error
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="Maersk-Fahrplan als Importvorschau abrufen; keine Schiffsdateien werden veraendert.")
    parser.add_argument("--vessel", required=True)
    parser.add_argument("--from", dest="from_date", required=True)
    parser.add_argument("--to", dest="to_date", required=True)
    parser.add_argument("--input", type=Path, help="Statt Live-Suche eine gespeicherte Maersk-Textausgabe lesen")
    parser.add_argument("--output", type=Path, help="Import-JSON schreiben; ohne Angabe auf stdout")
    parser.add_argument("--browser", choices=("msedge", "chrome", "chromium"))
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    try:
        name = vessel_identifier(args.vessel)
        if args.input:
            text, url = args.input.read_text(encoding="utf-8-sig"), MAERSK_URL
        else:
            text, url = fetch_schedule(name, args.from_date, args.browser, args.headed)
        packet = parse_maersk_text(text, name, args.from_date, args.to_date)
        packet["sourceUrl"] = url
        output = json.dumps(packet, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
        return 0
    except Exception as error:
        print(f"Maersk-Import fehlgeschlagen: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())