import re
from copy import deepcopy
from math import isfinite
from uuid import uuid4

from schedule_import import vessel_identifier, vessel_key


def record_id(value, prefix):
    value = value or f"{prefix}-{uuid4().hex[:12]}"
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value):
        raise ValueError("Die ID darf nur kleine Buchstaben, Zahlen, Bindestriche und Unterstriche enthalten.")
    return value


def update_ship_metadata(payload, original, ships):
    name = str(payload.get("name", "")).strip()
    unique_name = vessel_identifier(payload.get("vesselName", ""))
    service = str(payload.get("serviceId", "")).strip().upper()
    speed = payload.get("maxSpeedKnots", 20)
    if not name or len(name) > 120 or not unique_name or len(unique_name) > 120:
        raise ValueError("Anzeigename und eindeutiger Schiffsname sind erforderlich (maximal 120 Zeichen).")
    if not re.fullmatch(r"[A-Z0-9_-]{1,40}", service):
        raise ValueError("Ein gueltiger Dienst ist erforderlich.")
    if type(speed) not in (float, int) or not isfinite(speed) or speed <= 0:
        raise ValueError("Die Maximalgeschwindigkeit muss positiv sein.")
    identity = original["id"] if original else record_id(payload.get("id"), "ship")
    if original and payload.get("id", identity) != identity:
        raise ValueError("Die technische ID einer bestehenden Datei bleibt unveraendert.")
    if any(ship["id"] != identity and vessel_key(ship.get("vesselName", ship["name"])) == vessel_key(unique_name) for ship in ships):
        raise ValueError("Dieser eindeutige Schiffsname wird bereits verwendet.")
    if original is None and any(ship["id"] == identity for ship in ships):
        raise ValueError("Diese Schiffs-ID existiert bereits.")
    result = deepcopy(original) if original else {"id": identity, "proformaAssignments": [], "voyages": {}}
    result.update(name=name, vesselName=unique_name, serviceId=service, maxSpeedKnots=speed)
    return result


def update_port_metadata(payload, original, ports):
    name = str(payload.get("name", "")).strip()
    berths = payload.get("berths")
    old_identity = original["id"] if original else None
    if original and not payload.get("id", old_identity):
        raise ValueError("Die ID eines vorhandenen Hafens darf nicht leer sein.")
    identity = record_id(payload.get("id", old_identity), "port")
    if not name or len(name) > 160:
        raise ValueError("Ein Hafenname ist erforderlich (maximal 160 Zeichen).")
    if type(berths) is not int or not 1 <= berths <= 200:
        raise ValueError("Die Liegeplatzzahl muss zwischen 1 und 200 liegen.")
    if any(port["id"] == identity and port["id"] != old_identity for port in ports):
        raise ValueError("Diese Hafen-ID existiert bereits.")
    aliases = payload.get("aliases", {})
    if not isinstance(aliases, dict) or any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", source) or not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values) for source, values in aliases.items()):
        raise ValueError("Aliase muessen als Objekt aus Datenquelle und Namensliste angegeben werden.")
    distances = deepcopy(payload.get("distancesNm", original.get("distancesNm", {}) if original else {}))
    if original and isinstance(distances, dict):
        for port in ports:
            if port["id"] != old_identity and old_identity in port.get("distancesNm", {}):
                distances.setdefault(port["id"], port["distancesNm"][old_identity])
    known = {port["id"] for port in ports} - {identity, old_identity}
    if not isinstance(distances, dict) or not set(distances) <= known or any(type(distance) not in (float, int) or not isfinite(distance) or distance < 0 for distance in distances.values()):
        raise ValueError("Entfernungen muessen nichtnegative Zahlen zu vorhandenen Haefen sein.")
    result = deepcopy(original) if original else {"id": identity}
    result.update(id=identity, name=name, berths=berths, aliases={source: list(dict.fromkeys(value.strip() for value in values)) for source, values in aliases.items()}, distancesNm=distances)
    updated = [deepcopy(port) for port in ports if port["id"] != old_identity]
    for port in updated:
        if old_identity:
            port.setdefault("distancesNm", {}).pop(old_identity, None)
        port.setdefault("distancesNm", {}).pop(identity, None)
    updated.append(result)
    if original:
        positions = {port["id"]: index for index, port in enumerate(ports)}
        updated.sort(key=lambda port: positions[old_identity if port["id"] == identity else port["id"]])
    return result, updated


def rename_port_references(ships, services, old_id, new_id):
    updated_ships, updated_services = deepcopy(ships), deepcopy(services)
    if old_id == new_id:
        return updated_ships, updated_services
    for ship in updated_ships:
        for collection in ship["voyages"].values():
            for stop in collection["stops"]:
                if stop["portId"] == old_id:
                    stop["portId"] = new_id
    for service in updated_services:
        for proforma in service.get("proformas", []):
            for stop in proforma["stops"]:
                if stop["portId"] == old_id:
                    stop["portId"] = new_id
        defaults = service.get("defaultBerths", {})
        if old_id in defaults:
            defaults[new_id] = defaults.pop(old_id)
    return updated_ships, updated_services