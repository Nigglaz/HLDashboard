from copy import deepcopy
from datetime import datetime, timedelta
from math import isfinite


def parse(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo:
        raise ValueError("Gemeinsame UTC-Planzeit ohne Zeitzonenoffset erwartet.")
    return result


def minimum_transit_hours(ship, origin, destination, ports=None):
    port_map = {port["id"]: port for port in ports or []}
    distance = port_map.get(origin, {}).get("distancesNm", {}).get(destination, port_map.get(destination, {}).get("distancesNm", {}).get(origin, 100))
    speed = ship.get("maxSpeedKnots", 20)
    if type(distance) not in (int, float) or not isfinite(distance) or distance < 0:
        raise ValueError("Die Entfernung muss eine endliche, nichtnegative Zahl in Seemeilen sein.")
    if type(speed) not in (int, float) or not isfinite(speed) or speed <= 0:
        raise ValueError("Die Maximalgeschwindigkeit muss eine positive Zahl in Knoten sein.")
    return {"distanceNm": distance, "maxSpeedKnots": speed, "hours": distance / speed}


def resolve_voyage(ship, date):
    day = parse(date).date().isoformat()
    if day in ship["voyages"]:
        actual = ship["voyages"][day]
        return {"key": day, "proformaId": actual["proformaId"], "source": "actual", "stops": deepcopy(actual["stops"])}
    versions = sorted((item for item in ship["proformas"] if item["validFrom"] <= day), key=lambda item: item["validFrom"])
    if not versions:
        return None
    proforma = versions[-1]
    anchor = parse(proforma["stops"][0]["arrival"])
    period = timedelta(weeks=proforma["repeatWeeks"])
    cycle = (parse(day) - anchor.replace(hour=0, minute=0, second=0, microsecond=0)) // period
    start = anchor + cycle * period
    if start.date().isoformat() < proforma["validFrom"]:
        start += period
        cycle += 1
    key = start.date().isoformat()
    if any(item["validFrom"] > proforma["validFrom"] and item["validFrom"] <= key for item in ship["proformas"]):
        return None
    actual = ship["voyages"].get(key)
    if actual is not None:
        return {"key": key, "proformaId": actual["proformaId"], "source": "actual", "stops": deepcopy(actual["stops"])}
    stops = deepcopy(proforma["stops"])
    for stop in stops:
        for field in ("arrival", "departure"):
            stop[field] = (parse(stop[field]) + cycle * period).isoformat(timespec="minutes")
    return {"key": key, "proformaId": proforma["id"], "source": "proforma", "stops": stops}


def voyages_in_range(ship, start, end):
    result = {}
    for version in sorted(ship["proformas"], key=lambda item: item["validFrom"]):
        anchor = parse(version["stops"][0]["arrival"])
        period = timedelta(weeks=version["repeatWeeks"])
        cycle = (parse(start) - anchor) // period - 1
        while anchor + cycle * period < parse(end):
            date = (anchor + cycle * period).date().isoformat()
            if date >= version["validFrom"]:
                voyage = resolve_voyage(ship, date)
                if voyage and voyage["key"] == date:
                    result[date] = voyage
            cycle += 1
    for key, actual in ship["voyages"].items():
        result[key] = {"key": key, "proformaId": actual["proformaId"], "source": "actual", "stops": deepcopy(actual["stops"])}
    return [voyage for _, voyage in sorted(result.items()) if parse(voyage["stops"][0]["arrival"]) < parse(end) and parse(voyage["stops"][-1]["departure"]) >= parse(start)]


def migrate_ship(ship):
    if "proformas" in ship:
        return deepcopy(ship)
    pattern = deepcopy(ship.get("recurrenceStops", ship["stops"]))
    for stops in [pattern, ship["stops"], *ship.get("voyageOverrides", {}).values()]:
        if ship["id"] == "mathilde":
            for stop in stops:
                if stop["portId"] == "rotterdam" and stop["arrival"] == "2027-01-16T11:00":
                    stop["arrival"] = "2027-01-26T11:00"
                    stop["transitMinutes"] = 2460
    version = {"id": "initial", "name": "Proforma 2027", "validFrom": "2027-01-01", "repeatWeeks": 14, "stops": pattern}
    voyages = {}
    if ship["stops"] != pattern:
        voyages[pattern[0]["arrival"][:10]] = {"proformaId": "initial", "stops": deepcopy(ship["stops"])}
    for cycle, stops in ship.get("voyageOverrides", {}).items():
        key = (parse(pattern[0]["arrival"]) + timedelta(weeks=15 * int(cycle))).date().isoformat()
        voyages[key] = {"proformaId": "initial", "stops": deepcopy(stops)}
    return {"id": ship["id"], "name": ship["name"], "serviceId": ship["serviceId"], "proformas": [version], "voyages": voyages}


def validate_ship(ship, original, ports):
    if any(ship.get(field) != original[field] for field in ("id", "name", "serviceId")):
        raise ValueError("Schiff und Dienst d\u00fcrfen nicht ver\u00e4ndert werden.")
    if not isinstance(ship.get("proformas"), list) or not ship["proformas"] or not isinstance(ship.get("voyages"), dict):
        raise ValueError("Proformas und Reisen fehlen.")
    minimum_transit_hours(ship, "", "", ports)
    ids, dates = set(), set()
    port_map = {port["id"]: port for port in ports}
    for version in ship["proformas"]:
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
    for key, voyage in ship["voyages"].items():
        if parse(key).date().isoformat() != key or voyage["proformaId"] not in ids:
            raise ValueError("Ung\u00fcltiger Reiseabschnitt.")
        validate_stations(voyage["stops"], port_map)


def validate_stations(stops, ports):
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
        if type(stop["transitMinutes"]) is not int or stop["transitMinutes"] < 0:
            raise ValueError("Ung\u00fcltige Transitzeit.")
        arrival, departure = parse(stop["arrival"]), parse(stop["departure"])
        if departure <= arrival:
            raise ValueError("Abfahrt muss nach Ankunft liegen.")
        if previous and arrival < previous:
            raise ValueError("Hafenaufenthalte desselben Schiffs \u00fcberlappen sich.")
        previous = departure


def conflicts(ships, start, end, ports=None):
    occupied, issues = {}, {}
    for ship in ships:
        voyages = voyages_in_range(ship, start, end)
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