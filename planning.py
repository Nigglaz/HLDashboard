from copy import deepcopy
from datetime import datetime, timedelta
from math import isfinite
import re
from uuid import uuid4


def parse(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo:
        raise ValueError("Gemeinsame UTC-Planzeit ohne Zeitzonenoffset erwartet.")
    return result


def minimum_transit_hours(ship, origin, destination, ports=None):
    port_map = {port["id"]: port for port in ports or []}
    distance = 0 if origin == destination else port_map.get(origin, {}).get("distancesNm", {}).get(destination, port_map.get(destination, {}).get("distancesNm", {}).get(origin))
    if distance is None:
        raise ValueError(f"Entfernung zwischen {origin} und {destination} fehlt in ports.json.")
    speed = ship.get("maxSpeedKnots")
    if type(distance) not in (int, float) or not isfinite(distance) or distance < 0:
        raise ValueError("Die Entfernung muss eine endliche, nichtnegative Zahl in Seemeilen sein.")
    if type(speed) not in (int, float) or not isfinite(speed) or speed <= 0:
        raise ValueError("Die Maximalgeschwindigkeit muss eine positive Zahl in Knoten sein.")
    return {"distanceNm": distance, "maxSpeedKnots": speed, "hours": distance / speed}


def change_rotation(ship, stops, ports):
    if not isinstance(stops, list) or not stops:
        raise ValueError("Keine Hafenaufenthalte zum Umordnen vorhanden.")
    reordered = sorted(deepcopy(stops), key=lambda stop: (parse(stop["arrival"]), parse(stop["departure"])))
    for stop in reordered:
        stop["transitMinutes"] = 0
    validate_stations(reordered, {port["id"]: port for port in ports})
    names = {port["id"]: port["name"] for port in ports}
    for index, stop in enumerate(reordered):
        if index == 0:
            stop["transitMinutes"] = 0
            continue
        previous = reordered[index - 1]
        hours = (parse(stop["arrival"]) - parse(previous["departure"])).total_seconds() / 3600
        minimum = minimum_transit_hours(ship, previous["portId"], stop["portId"], ports)
        if hours + 1e-9 < minimum["hours"]:
            raise ValueError(f"Change Rotation nicht m\u00f6glich: {names[previous['portId']]} \u2192 {names[stop['portId']]} bietet {hours:g} h; mindestens {minimum['hours']:g} h erforderlich.")
        stop["transitMinutes"] = round(hours * 60)
    return reordered


def insert_adhoc_stop(stops, after_stop_id, port_id, ports, berth=1, *, before_stop_id=None):
    port_map = {port["id"]: port for port in ports}
    if port_id not in port_map:
        raise ValueError("Unbekannter Hafen.")
    if type(berth) is not int or not 1 <= berth <= port_map[port_id]["berths"]:
        raise ValueError("Ung\u00fcltiger Liegeplatz.")
    if not isinstance(stops, list) or not stops:
        raise ValueError("Keine Reise vorhanden.")
    if before_stop_id is not None:
        if after_stop_id is not None:
            raise ValueError("Nur eine Einf\u00fcgeposition angeben.")
        before_index = next((index for index, stop in enumerate(stops) if stop["id"] == before_stop_id), -1)
        if before_index < 0:
            raise ValueError("Der folgende Aufenthalt wurde nicht gefunden.")
        if before_index == 0:
            following = stops[0]
            duration = parse(following["departure"]) - parse(following["arrival"])
            if duration <= timedelta(0):
                raise ValueError("Die folgende Liegezeit muss positiv sein.")
            departure = parse(following["arrival"])
            arrival = departure - duration
            result = deepcopy(stops)
            result.insert(0, {"id": f"adhoc-{uuid4().hex}", "portId": port_id, "berth": berth,
                              "arrival": arrival.isoformat(timespec="minutes"), "departure": departure.isoformat(timespec="minutes"),
                              "transitMinutes": 0, "adhoc": True})
            result[1]["transitMinutes"] = 0
            return result
        after_stop_id = stops[before_index - 1]["id"]
    index = next((index for index, stop in enumerate(stops) if stop["id"] == after_stop_id), -1)
    if index < 0 or index + 1 >= len(stops):
        raise ValueError("Der Hafen kann nur zwischen zwei vorhandenen Aufenthalten eingef\u00fcgt werden.")
    previous, following = stops[index:index + 2]
    duration = ((parse(previous["departure"]) - parse(previous["arrival"])) + (parse(following["departure"]) - parse(following["arrival"]))) / 2
    if duration <= timedelta(0):
        raise ValueError("Die benachbarten Liegezeiten m\u00fcssen positiv sein.")
    midpoint = parse(previous["departure"]) + (parse(following["arrival"]) - parse(previous["departure"])) / 2
    arrival = midpoint - duration / 2
    arrival = (arrival + timedelta(seconds=30)).replace(second=0, microsecond=0)
    departure = arrival + timedelta(minutes=max(1, round(duration.total_seconds() / 60)))
    result = deepcopy(stops)
    result.insert(index + 1, {"id": f"adhoc-{uuid4().hex}", "portId": port_id, "berth": berth,
                              "arrival": arrival.isoformat(timespec="minutes"), "departure": departure.isoformat(timespec="minutes"),
                              "transitMinutes": max(0, round((arrival - parse(previous["departure"])).total_seconds() / 60)), "adhoc": True})
    result[index + 2]["transitMinutes"] = max(0, round((parse(following["arrival"]) - departure).total_seconds() / 60))
    return result


def migrate_service_proformas(ships, services):
    migrated_ships, migrated_services = deepcopy(ships), deepcopy(services)
    service_map = {service["id"]: service for service in migrated_services}
    for ship in sorted(migrated_ships, key=lambda item: (item["serviceId"], min((version["stops"][0]["arrival"] for version in item.get("proformas", [])), default="9999"), item["id"])):
        if ship.get("proformaAssignments") is not None:
            continue
        service = service_map.setdefault(ship["serviceId"], {"id": ship["serviceId"], "proformas": []})
        if service not in migrated_services:
            migrated_services.append(service)
        service.setdefault("proformas", [])
        assignments, version_map = [], {}
        for version in ship.get("proformas", []):
            anchor = parse(version["stops"][0]["arrival"])
            signature = (version["validFrom"], version["repeatWeeks"], tuple(
                (stop["portId"], stop["berth"], int((parse(stop["arrival"]) - anchor).total_seconds() // 60),
                 int((parse(stop["departure"]) - anchor).total_seconds() // 60)) for stop in version["stops"]))
            group = next((item for item in service["proformas"] if item.get("_migrationSignature") == signature
                          and (anchor - parse(item["stops"][0]["arrival"])).total_seconds() % (7 * 86400) == 0), None)
            if group is None:
                year = version["validFrom"][:4]
                base_id = f"{ship['serviceId'].lower()}-{year}"
                identity, suffix = base_id, 2
                existing_ids = {item["id"] for item in service["proformas"]}
                while identity in existing_ids:
                    identity = f"{base_id}-{suffix}"
                    suffix += 1
                group = {"id": identity, "name": f"{ship['serviceId']}/{year}", "validFrom": version["validFrom"],
                         "repeatWeeks": version["repeatWeeks"], "stops": deepcopy(version["stops"]), "_migrationSignature": signature}
                service["proformas"].append(group)
            offset = int((anchor - parse(group["stops"][0]["arrival"])).total_seconds() // (7 * 86400))
            assignments.append({"proformaId": group["id"], "validFrom": version["validFrom"], "offsetWeeks": offset})
            version_map[version["id"]] = group["id"]
        for key, voyage in ship.get("voyages", {}).items():
            if voyage.get("proformaId") in version_map:
                voyage["proformaId"] = version_map[voyage["proformaId"]]
        ship.pop("proformas", None)
        ship["proformaAssignments"] = sorted(assignments, key=lambda item: item["validFrom"])
    renamed_ids = {}
    for service in migrated_services:
        used_ids = {item["id"] for item in service.get("proformas", [])}
        for version in service.get("proformas", []):
            legacy_id = re.fullmatch(rf"{service['id'].lower()}-(20\d{{2}})", version["id"])
            if not legacy_id or version.get("name") != f"{service['id']}/{legacy_id[1]}" or legacy_id[1] == version["validFrom"][:4]:
                continue
            new_id = f"{service['id'].lower()}-{version['validFrom'][:4]}"
            if new_id in used_ids and new_id != version["id"]:
                continue
            used_ids.remove(version["id"])
            used_ids.add(new_id)
            renamed_ids[(service["id"], version["id"])] = new_id
            version["id"] = new_id
            version["name"] = f"{service['id']}/{version['validFrom'][:4]}"
    for ship in migrated_ships:
        for assignment in ship.get("proformaAssignments", []):
            assignment["proformaId"] = renamed_ids.get((ship["serviceId"], assignment["proformaId"]), assignment["proformaId"])
        for voyage in ship.get("voyages", {}).values():
            voyage["proformaId"] = renamed_ids.get((ship["serviceId"], voyage.get("proformaId")), voyage.get("proformaId"))
    for service in migrated_services:
        for version in service.get("proformas", []):
            version.pop("_migrationSignature", None)
    return migrated_ships, migrated_services


def _assignments(ship):
    if "proformaAssignments" in ship:
        return ship["proformaAssignments"]
    return [{"proformaId": version["id"], "validFrom": version["validFrom"], "offsetWeeks": 0}
            for version in ship.get("proformas", [])]


def _proforma_for(ship, assignment, services):
    if services is None:
        return next((version for version in ship.get("proformas", []) if version["id"] == assignment["proformaId"]), None)
    service = next((item for item in services if item["id"] == ship["serviceId"]), None)
    return next((version for version in (service or {}).get("proformas", []) if version["id"] == assignment["proformaId"]), None)


def resolve_voyage(ship, date, services=None):
    day = parse(date).date().isoformat()
    if day in ship["voyages"]:
        actual = ship["voyages"][day]
        return {"key": day, "proformaId": actual["proformaId"], "source": "actual", "stops": deepcopy(actual["stops"])}
    assignments = sorted((item for item in _assignments(ship) if item["validFrom"] <= day), key=lambda item: item["validFrom"])
    if not assignments:
        actuals = [(key, voyage) for key, voyage in ship["voyages"].items() if key <= day and max(parse(stop["departure"]).date().isoformat() for stop in voyage["stops"]) >= day]
        if actuals:
            key, actual = max(actuals, key=lambda item: item[0])
            return {"key": key, "proformaId": actual["proformaId"], "source": "actual", "stops": deepcopy(actual["stops"])}
        return None
    assignment = assignments[-1]
    proforma = _proforma_for(ship, assignment, services)
    if proforma is None:
        return None
    anchor = parse(proforma["stops"][0]["arrival"]) + timedelta(weeks=assignment.get("offsetWeeks", 0))
    period = timedelta(weeks=proforma["repeatWeeks"])
    cycle = (parse(day) - anchor.replace(hour=0, minute=0, second=0, microsecond=0)) // period
    start = anchor + cycle * period
    if start.date().isoformat() < assignment["validFrom"]:
        start += period
        cycle += 1
    key = start.date().isoformat()
    if any(item["validFrom"] > assignment["validFrom"] and item["validFrom"] <= key for item in _assignments(ship)):
        return None
    actual = ship["voyages"].get(key)
    if actual is not None:
        return {"key": key, "proformaId": actual["proformaId"], "source": "actual", "stops": deepcopy(actual["stops"])}
    stops = deepcopy(proforma["stops"])
    for stop in stops:
        for field in ("arrival", "departure"):
            stop[field] = (parse(stop[field]) + cycle * period + timedelta(weeks=assignment.get("offsetWeeks", 0))).isoformat(timespec="minutes")
    return {"key": key, "proformaId": proforma["id"], "source": "proforma", "stops": stops}


def voyages_in_range(ship, start, end, services=None):
    result = {}
    for assignment in sorted(_assignments(ship), key=lambda item: item["validFrom"]):
        version = _proforma_for(ship, assignment, services)
        if version is None:
            continue
        anchor = parse(version["stops"][0]["arrival"]) + timedelta(weeks=assignment.get("offsetWeeks", 0))
        period = timedelta(weeks=version["repeatWeeks"])
        cycle = (parse(start) - anchor) // period - 1
        while anchor + cycle * period < parse(end):
            date = (anchor + cycle * period).date().isoformat()
            if date >= assignment["validFrom"]:
                voyage = resolve_voyage(ship, date, services)
                if voyage and voyage["key"] == date:
                    result[date] = voyage
            cycle += 1
    for key, actual in ship["voyages"].items():
        result[key] = {"key": key, "proformaId": actual["proformaId"], "source": "actual", "stops": deepcopy(actual["stops"])}
    return [voyage for _, voyage in sorted(result.items()) if min(parse(stop["arrival"]) for stop in voyage["stops"]) < parse(end) and max(parse(stop["departure"]) for stop in voyage["stops"]) >= parse(start)]


def validate_ship(ship, original, ports, allow_rotation_conflicts=False, services=None):
    if any(ship.get(field) != original[field] for field in ("id", "name", "serviceId")):
        raise ValueError("Schiff und Dienst d\u00fcrfen nicht ver\u00e4ndert werden.")
    if ship.get("vesselName") != original.get("vesselName"):
        raise ValueError("Der eindeutige Schiffsname darf nicht durch eine Plan\u00e4nderung ver\u00e4ndert werden.")
    if not isinstance(ship.get("voyages"), dict):
        raise ValueError("Reisen fehlen.")
    minimum_transit_hours(ship, "", "", ports)
    port_map = {port["id"]: port for port in ports}
    if "proformaAssignments" in ship:
        assignments = ship["proformaAssignments"]
        if not isinstance(assignments, list):
            raise ValueError("Proforma-Zuordnungen fehlen.")
        service = next((item for item in services or [] if item["id"] == ship["serviceId"]), {})
        ids = {item["id"] for item in service.get("proformas", [])}
        dates = set()
        for assignment in assignments:
            if assignment.get("proformaId") not in ids or assignment.get("validFrom") in dates:
                raise ValueError("Proforma-Zuordnung oder Startdatum ist ungueltig.")
            dates.add(assignment["validFrom"])
            if parse(assignment["validFrom"]).date().isoformat() != assignment["validFrom"]:
                raise ValueError("Ungueltiges Zuordnungs-Startdatum.")
            if type(assignment.get("offsetWeeks")) is not int or not -104 <= assignment["offsetWeeks"] <= 104:
                raise ValueError("Der Wochenversatz muss zwischen -104 und 104 Wochen liegen.")
        has_assignments = bool(assignments)
    else:
        versions = ship.get("proformas", [])
        if not isinstance(versions, list):
            raise ValueError("Proformas fehlen.")
        ids, dates = set(), set()
        for version in versions:
            if not isinstance(version["id"], str) or version["id"] in ids or version["validFrom"] in dates:
                raise ValueError("Proforma-IDs und Startdaten m\u00fcssen eindeutig sein.")
            ids.add(version["id"])
            dates.add(version["validFrom"])
            if parse(version["validFrom"]).date().isoformat() != version["validFrom"]:
                raise ValueError("Ung\u00fcltiges Proforma-Startdatum.")
            if type(version["repeatWeeks"]) is not int or not 1 <= version["repeatWeeks"] <= 104:
                raise ValueError("Der Zyklus muss zwischen 1 und 104 Wochen liegen.")
            validate_stations(version["stops"], port_map)
            if parse(version["stops"][-1]["departure"]) >= parse(version["stops"][0]["arrival"]) + timedelta(weeks=version["repeatWeeks"]):
                raise ValueError("Die Proforma-Reise ist l\u00e4nger als ihr Zyklus.")
        has_assignments = bool(versions)
    for key, voyage in ship["voyages"].items():
        if parse(key).date().isoformat() != key or (voyage["proformaId"] not in ids and not (not has_assignments and voyage["proformaId"] is None)):
            raise ValueError("Ung\u00fcltiger Reiseabschnitt.")
        validate_stations(voyage["stops"], port_map, require_order=not allow_rotation_conflicts)
    routes = [voyage["stops"] for voyage in ship["voyages"].values()]
    routes.extend(_proforma_for(ship, assignment, services)["stops"] for assignment in _assignments(ship))
    for stops in routes:
        for previous, stop in zip(stops, stops[1:]):
            minimum_transit_hours(ship, previous["portId"], stop["portId"], ports)


def validate_service_proforma(proforma, ports):
    if not isinstance(proforma.get("id"), str) or not proforma["id"] or not isinstance(proforma.get("name"), str) or not proforma["name"].strip():
        raise ValueError("Proforma-ID und Name sind erforderlich.")
    if parse(proforma["validFrom"]).date().isoformat() != proforma["validFrom"]:
        raise ValueError("Ungueltiges Proforma-Startdatum.")
    if type(proforma["repeatWeeks"]) is not int or not 1 <= proforma["repeatWeeks"] <= 104:
        raise ValueError("Der Zyklus muss zwischen 1 und 104 Wochen liegen.")
    validate_stations(proforma["stops"], {port["id"]: port for port in ports})
    if parse(proforma["stops"][-1]["departure"]) >= parse(proforma["stops"][0]["arrival"]) + timedelta(weeks=proforma["repeatWeeks"]):
        raise ValueError("Die Proforma-Reise ist laenger als ihr Zyklus.")


def validate_stations(stops, ports, require_order=True):
    if not isinstance(stops, list) or not stops:
        raise ValueError("Die Hafenfolge darf nicht leer sein.")
    seen = set()
    previous = None
    for stop in stops:
        if stop["id"] in seen or stop["portId"] not in ports:
            raise ValueError("Ung\u00fcltige Hafenstation.")
        seen.add(stop["id"])
        if type(stop["berth"]) is not int or not 1 <= stop["berth"] <= ports[stop["portId"]]["berths"]:
            raise ValueError("Ung\u00fcltiger Liegeplatz.")
        if type(stop["transitMinutes"]) is not int or (require_order and stop["transitMinutes"] < 0):
            raise ValueError("Ung\u00fcltige Transitzeit.")
        arrival, departure = parse(stop["arrival"]), parse(stop["departure"])
        if departure <= arrival:
            raise ValueError("Abfahrt muss nach Ankunft liegen.")
        if require_order and previous and arrival < previous:
            raise ValueError("Hafenaufenthalte desselben Schiffs \u00fcberlappen sich.")
        previous = departure


def conflicts(ships, start, end, ports=None, services=None):
    occupied, issues = {}, {}
    for ship in ships:
        voyages = voyages_in_range(ship, start, end, services)
        for index, voyage in enumerate(voyages):
            if index and parse(voyages[index - 1]["stops"][-1]["departure"]) > parse(voyage["stops"][0]["arrival"]):
                overlap = (parse(voyages[index - 1]["stops"][-1]["departure"]) - parse(voyage["stops"][0]["arrival"])).total_seconds()
                issues[f"return:{ship['id']}:{voyage['key']}"] = {"severity": overlap, "message": "Folgereise beginnt vor Ende der vorherigen Reise."}
            for position, stop in enumerate(voyage["stops"]):
                start_time, end_time = parse(stop["arrival"]), parse(stop["departure"])
                identity = f"{ship['id']}:{voyage['key']}:{stop['id']}"
                if position:
                    previous = voyage["stops"][position - 1]
                    minimum = minimum_transit_hours(ship, previous["portId"], stop["portId"], ports)
                    actual = (start_time - parse(previous["departure"])).total_seconds() / 3600
                    deficit = minimum["hours"] - actual
                    if deficit > 1e-9:
                        issues[f"transit:{identity}"] = {"severity": deficit * 3600,
                            "message": f"{ship['name']}: Transit nach {stop['portId']} zu kurz: {actual:g} h verf\u00fcgbar, mindestens {minimum['hours']:g} h ({minimum['distanceNm']:g} sm / {minimum['maxSpeedKnots']:g} kn)."}
                key = (stop["portId"], stop["berth"])
                for other_start, other_end, other_id, other_name in occupied.get(key, []):
                    if start_time < other_end and end_time > other_start:
                        overlap = (min(end_time, other_end) - max(start_time, other_start)).total_seconds()
                        issues["berth:" + ":".join(sorted((identity, other_id)))] = {"severity": overlap, "message": f"Liegeplatzkonflikt: {ship['name']} / {other_name}, {stop['portId']}, LP {stop['berth']}."}
                occupied.setdefault(key, []).append((start_time, end_time, identity, ship["name"]))
    return issues