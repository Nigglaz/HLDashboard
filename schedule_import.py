import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from planning import parse, resolve_voyage


MAERSK_URL = "https://www.maersk.com/schedules/vesselSchedules"
MONTHS = {name: index for index, name in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def vessel_identifier(value):
    return " ".join(str(value).split())


def vessel_key(value):
    return vessel_identifier(value).casefold()


def maersk_date(value):
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+(\d{1,2}):(\d{2})", value.strip())
    if not match or match[2].title() not in MONTHS:
        raise ValueError(f"Ungueltiger Maersk-Zeitpunkt: {value}")
    return datetime(int(match[3]), MONTHS[match[2].title()], int(match[1]), int(match[4]), int(match[5])).isoformat(timespec="minutes")


def parse_maersk_text(text, vessel_name, from_date, to_date):
    start, end = parse(from_date), parse(to_date)
    if end < start:
        raise ValueError("Das Enddatum liegt vor dem Startdatum.")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    calls = []
    event = re.compile(r"^(Arrival|Departure)\s*(?:[-\u2013\u2014]\s*(.*))?$", re.IGNORECASE)
    for index, line in enumerate(lines):
        arrival_event = event.match(line)
        if not arrival_event or arrival_event[1].lower() != "arrival":
            continue
        if index < 2 or index + 3 >= len(lines):
            raise ValueError("Unvollstaendiger Hafenaufenthalt in der Maersk-Ausgabe.")
        departure_event = event.match(lines[index + 2])
        if not departure_event or departure_event[1].lower() != "departure":
            raise ValueError("Zur Ankunft fehlt die passende Abfahrt.")
        arrival, departure = maersk_date(lines[index + 1]), maersk_date(lines[index + 3])
        if parse(departure) <= parse(arrival):
            raise ValueError("Maersk-Aufenthalt mit Abfahrt vor Ankunft.")
        port = re.sub(r"^\[([^]]+)\]\([^)]*\)$", r"\1", lines[index - 2])
        terminal = lines[index - 1]
        if not start.date() <= parse(arrival).date() <= end.date():
            continue
        calls.append({"id": f"call-{len(calls) + 1}", "portName": port, "terminalName": terminal,
                      "arrival": arrival, "departure": departure,
                      "arrivalVoyage": arrival_event[2] or "", "departureVoyage": departure_event[2] or ""})
    if not calls:
        raise ValueError("Keine vollstaendigen Hafenaufenthalte im Zeitraum gefunden.")
    return {"schemaVersion": 1, "source": "maersk", "sourceUrl": MAERSK_URL,
            "vesselName": vessel_identifier(vessel_name), "fromDate": from_date, "toDate": to_date,
            "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "timeBasis": "unconfirmed", "calls": calls}


def resolve_port(call, ports, source):
    for field in ("terminalName", "portName"):
        name = vessel_key(call.get(field, ""))
        if not name:
            continue
        candidates = set()
        for port in ports:
            aliases = port.get("aliases", {})
            aliases = aliases.get(source, []) if isinstance(aliases, dict) else aliases
            known = {vessel_key(value) for value in [port["name"], *aliases]}
            if name in known:
                candidates.add(port["id"])
        if len(candidates) > 1:
            raise ValueError(f"Mehrdeutige Hafenzuordnung: {call.get(field)}")
        if candidates:
            return next(iter(candidates))
    return None


def prepare_import(plan, packet, choices=None, voyage_date=None, from_date=None, to_date=None):
    if packet.get("schemaVersion") != 1 or not isinstance(packet.get("calls"), list) or not packet["calls"]:
        raise ValueError("Ungueltiges Importformat.")
    name = vessel_identifier(packet.get("vesselName", ""))
    matches = [ship for ship in plan["ships"] if vessel_key(ship.get("vesselName", ship["name"])) == vessel_key(name)]
    if len(matches) != 1:
        raise ValueError(f"Schiff nicht eindeutig zugeordnet: {name}")
    ship = matches[0]
    source = packet.get("source", "")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", source):
        raise ValueError("Ungueltige Datenquelle.")
    choices = choices or {}
    start = parse(from_date or packet["fromDate"]).date()
    end = parse(to_date or packet["toDate"]).date()
    if end < start:
        raise ValueError("Das Enddatum liegt vor dem Startdatum.")
    in_window = lambda arrival: start <= parse(arrival).date() <= end
    if len({call.get("id") for call in packet["calls"]}) != len(packet["calls"]):
        raise ValueError("Doppelte Importzeilen-IDs.")
    ports = {port["id"]: port for port in plan["ports"]}
    rows, selected, unresolved = [], [], []
    for call in packet["calls"]:
        if not isinstance(call.get("id"), str):
            raise ValueError("Importzeile ohne ID.")
        arrival, departure = parse(call["arrival"]), parse(call["departure"])
        if departure <= arrival:
            raise ValueError("Importierte Abfahrt muss nach Ankunft liegen.")
        choice = choices.get(call["id"], {})
        include = choice.get("include", True)
        if type(include) is not bool:
            raise ValueError("Importauswahl muss wahr oder falsch sein.")
        outside = not in_window(call["arrival"])
        include = include and not outside
        port_id = (choice.get("portId") or resolve_port(call, plan["ports"], source)) if include else None
        if port_id is not None and port_id not in ports:
            raise ValueError("Unbekannter Zielhafen.")
        row = {**call, "portId": port_id, "include": include, "outsideWindow": outside}
        rows.append(row)
        if include and port_id is None:
            unresolved.append(call["id"])
        if include and port_id:
            selected.append(row)
    selected.sort(key=lambda call: call["arrival"])
    if not selected:
        return {"shipId": ship["id"], "vesselName": name, "rows": rows, "unresolved": unresolved, "changes": [], "candidate": None, "voyageDate": None}
    date = voyage_date or selected[0]["arrival"][:10]
    services = plan.get("services", [])
    voyage = resolve_voyage(ship, date, services)
    if voyage is None:
        if ship.get("proformaAssignments"):
            raise ValueError("Keine Proforma fuer den importierten Zeitraum vorhanden.")
        voyage = {"key": date, "proformaId": None, "stops": []}
    key = voyage["key"]
    service = next((item for item in services if item["id"] == ship["serviceId"]), {})
    version = next((item for item in service.get("proformas", []) if item["id"] == voyage["proformaId"]), None)
    if version and parse(selected[-1]["arrival"]) >= parse(key) + timedelta(weeks=version["repeatWeeks"]):
        raise ValueError("Der Import umfasst mehrere Runden. Bitte Zeitraum oder Zeilenauswahl auf eine Reise begrenzen.")
    defaults = next((service.get("defaultBerths", {}) for service in plan["services"] if service["id"] == ship["serviceId"]), {})
    preserved = [deepcopy(stop) for stop in voyage["stops"] if not in_window(stop["arrival"])]
    old_by_port = {}
    for stop in voyage["stops"]:
        if in_window(stop["arrival"]) or voyage.get("source") == "proforma":
            old_by_port.setdefault(stop["portId"], []).append(stop)
    stops, changes, used = [], [], set()
    for index, call in enumerate(selected):
        existing = old_by_port.get(call["portId"], [])
        available = [stop for stop in existing if stop["id"] not in used]
        old = min(available, key=lambda stop: abs((parse(stop["arrival"]) - parse(call["arrival"])).total_seconds())) if available else None
        if old:
            used.add(old["id"])
        berth = old["berth"] if old else defaults.get(call["portId"], 1)
        stop = {"id": old["id"] if old else f"import-{source}-{key}-{index + 1}", "portId": call["portId"], "berth": berth,
                "arrival": call["arrival"], "departure": call["departure"],
            "transitMinutes": 0 if not stops else max(0, round((parse(call["arrival"]) - parse(stops[-1]["departure"])).total_seconds() / 60)),
            "source": {"provider": source, "portName": call.get("portName"), "terminalName": call.get("terminalName"),
                   "arrivalVoyage": call.get("arrivalVoyage"), "departureVoyage": call.get("departureVoyage")}}
        stops.append(stop)
        status = "new" if old is None else "changed" if any(stop[field] != old[field] for field in ("arrival", "departure", "berth")) else "unchanged"
        changes.append({"status": status, "portId": stop["portId"], "before": old, "after": stop})
    for old in voyage["stops"]:
        if old["id"] not in used and in_window(old["arrival"]):
            changes.append({"status": "removed", "portId": old["portId"], "before": old, "after": None})
    preserved = [stop for stop in preserved if stop["id"] not in used]
    stops = sorted([*preserved, *stops], key=lambda stop: stop["arrival"])
    preserved_ids = {stop["id"] for stop in preserved}
    for index, stop in enumerate(stops):
        if stop["id"] not in preserved_ids:
            stop["transitMinutes"] = 0 if index == 0 else max(0, round((parse(stop["arrival"]) - parse(stops[index - 1]["departure"])).total_seconds() / 60))
    candidate = deepcopy(ship)
    candidate["voyages"][key] = {"proformaId": voyage["proformaId"], "stops": stops,
        "import": {"source": source, "vesselName": name, "fetchedAt": packet.get("fetchedAt"), "sourceUrl": packet.get("sourceUrl"), "timeBasis": packet.get("timeBasis", "unconfirmed"), "fromDate": start.isoformat(), "toDate": end.isoformat()}}
    return {"shipId": ship["id"], "vesselName": name, "voyageDate": key, "rows": rows, "unresolved": unresolved, "changes": changes, "candidate": candidate, "preservedCount": len(preserved)}


def prepare_service_import(plan, bundle, choices=None, excluded_ships=None, voyage_date=None, from_date=None, to_date=None):
    if bundle.get("schemaVersion") != 1:
        raise ValueError("Ungueltiges Dienstimportformat.")
    service_id = bundle.get("serviceId")
    members = [ship for ship in plan["ships"] if ship["serviceId"] == service_id]
    if not members:
        raise ValueError("Unbekannter oder leerer Dienst.")
    excluded = set(excluded_ships or [])
    if not excluded <= {ship["id"] for ship in members}:
        raise ValueError("Ausgeschlossene Schiffe gehoeren nicht zu diesem Dienst.")
    packets = bundle.get("packets")
    if not isinstance(packets, list):
        raise ValueError("Dienstimport erwartet eine Liste von Schiffsergebnissen.")
    by_name = {}
    names = {vessel_key(ship.get("vesselName", ship["name"])) for ship in members}
    for packet in packets:
        name = vessel_key(packet.get("vesselName", ""))
        if name not in names or name in by_name:
            raise ValueError("Doppeltes oder dienstfremdes Schiff im Import.")
        by_name[name] = packet
    source_errors = {vessel_key(item.get("vesselName", "")): item.get("error", "Abruf fehlgeschlagen.") for item in bundle.get("errors", [])}
    rows, changes, unresolved, candidates, previews, errors = [], [], [], [], [], []
    choices = choices or {}
    for ship in members:
        name = vessel_identifier(ship.get("vesselName", ship["name"]))
        name_key = vessel_key(name)
        status = {"shipId": ship["id"], "vesselName": name, "excluded": ship["id"] in excluded, "error": None}
        if status["excluded"]:
            previews.append(status)
            continue
        packet = by_name.get(name_key)
        try:
            if packet is None:
                raise ValueError(source_errors.get(name_key, "Kein Abrufresultat fuer dieses Schiff vorhanden."))
            scoped_choices = {call["id"]: choices[f"{ship['id']}:{call['id']}"] for call in packet.get("calls", []) if f"{ship['id']}:{call['id']}" in choices}
            preview = prepare_import(plan, packet, scoped_choices, voyage_date, from_date, to_date)
            for row in preview["rows"]:
                rows.append({**row, "id": f"{ship['id']}:{row['id']}", "shipId": ship["id"], "vesselName": name})
            changes.extend({**change, "shipId": ship["id"], "vesselName": name} for change in preview["changes"])
            unresolved.extend(f"{ship['id']}:{identity}" for identity in preview["unresolved"])
            if preview["candidate"] is not None:
                candidates.append(preview["candidate"])
            else:
                raise ValueError("Keine eingeschlossenen, zugeordneten Aufenthalte vorhanden.")
            status.update(voyageDate=preview["voyageDate"], changes=len([change for change in preview["changes"] if change["status"] != "unchanged"]))
        except (ValueError, KeyError, TypeError) as error:
            status["error"] = str(error)
            errors.append({"shipId": ship["id"], "vesselName": name, "error": str(error)})
        previews.append(status)
    return {"scope": "service", "serviceId": service_id, "shipId": None, "vesselName": service_id, "voyageDate": None,
            "shipPreviews": previews, "errors": errors, "rows": rows, "changes": changes, "unresolved": unresolved,
            "candidate": {"serviceId": service_id} if candidates else None, "candidates": candidates}