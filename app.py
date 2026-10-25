import json
import os
import threading
import hashlib
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from planning import conflicts, migrate_ship, validate_ship


PORTS = [
    {"id": "rotterdam", "name": "Rotterdam MV2", "berths": 2},
    {"id": "hamburg", "name": "Hamburg Eurogate", "berths": 6},
    {"id": "antwerp", "name": "Antwerpen", "berths": 1},
    {"id": "london", "name": "London", "berths": 4},
    {"id": "tangier", "name": "Tangier TC3", "berths": 2},
    {"id": "bremerhaven", "name": "Bremerhaven", "berths": 2},
    {"id": "algeciras", "name": "Algeciras", "berths": 2},
]

SERVICES = [
    {"id": "NE2", "repeatWeeks": 14, "defaultBerths": {port: 1 for port in ("rotterdam", "hamburg", "antwerp", "london", "tangier")}},
    {"id": "NE4", "repeatWeeks": 14, "defaultBerths": {"london": 3, "bremerhaven": 1, "hamburg": 2, "rotterdam": 2, "algeciras": 1}},
]


def mathilde_schedule():
    dates = [("london", "2027-01-16T14:00", "2027-01-18T04:00"),
             ("bremerhaven", "2027-01-20T06:00", "2027-01-21T22:00"),
             ("hamburg", "2027-01-22T15:00", "2027-01-24T18:00"),
             ("rotterdam", "2027-01-26T11:00", "2027-01-27T12:00"),
             ("algeciras", "2027-02-01T20:00", "2027-02-02T14:00")]
    stops = []
    for port, arrival, departure in dates:
        transit = max(0, int((datetime.fromisoformat(arrival) - datetime.fromisoformat(stops[-1]["departure"])).total_seconds() / 60)) if stops else 0
        stops.append({"id": f"mathilde-{port}", "portId": port, "berth": SERVICES[1]["defaultBerths"][port],
                      "arrival": arrival, "departure": departure, "transitMinutes": transit})
    return {"id": "mathilde", "name": "Mathilde Maersk", "serviceId": "NE4", "stops": stops}


def example_schedule():
    dates = [
        ("2027-01-16T11:00", "2027-01-18T00:00"),
        ("2027-01-19T13:00", "2027-01-21T10:00"),
        ("2027-01-23T06:00", "2027-01-25T23:00"),
        ("2027-01-26T12:00", "2027-01-28T23:00"),
        ("2027-02-02T03:00", "2027-02-03T01:00"),
    ]
    ships = []
    for index, name in enumerate(["Busan", "Berlin", "Gdansk", "Rotterdam", "Hamburg", "Genova"]):
        stops = []
        for position, (port, dates_pair) in enumerate(zip(PORTS, dates)):
            arrival, departure = [datetime.fromisoformat(value) + timedelta(days=7 * index) for value in dates_pair]
            transit = 0 if not position else int((arrival - datetime.fromisoformat(stops[-1]["departure"])).total_seconds() / 60)
            stops.append({"id": f"{name.lower()}-{port['id']}", "portId": port["id"],
                          "berth": index % port["berths"] + 1,
                          "arrival": arrival.isoformat(timespec="minutes"),
                          "departure": departure.isoformat(timespec="minutes"), "transitMinutes": transit})
        for stop in stops:
            stop["berth"] = 1
        ships.append({"id": name.lower(), "name": f"{name} Express", "serviceId": "NE2", "stops": stops})
    ships.append(mathilde_schedule())
    for ship in ships:
        ship["recurrenceStops"] = deepcopy(ship["stops"])
        ship["voyageOverrides"] = {}
    return {"revision": 1, "ships": ships}


def create_app(data_root=None):
    app = Flask(__name__)
    root = Path(data_root) if data_root else Path(__file__).parent / "data"
    root.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    def write(path, value):
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) == value:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)

    if not (root / "ports.json").exists():
        write(root / "ports.json", PORTS)
    if not (root / "schedules.json").exists():
        write(root / "schedules.json", example_schedule())

    def load(name):
        return json.loads((root / name).read_text(encoding="utf-8"))

    ports = load("ports.json")
    for port in PORTS:
        if not any(existing["id"] == port["id"] for existing in ports):
            ports.append(port)
    write(root / "ports.json", ports)
    if not (root / "services.json").exists():
        write(root / "services.json", SERVICES)
    if not (root / "views.json").exists():
        write(root / "views.json", {})
    schedule = load("schedules.json")
    if any("serviceId" not in ship for ship in schedule.get("ships", [])):
        for index, ship in enumerate(schedule["ships"]):
            ship.setdefault("serviceId", "NE2")
            for stop in ship["stops"]:
                port = next(port for port in ports if port["id"] == stop["portId"])
                if stop["berth"] == index % port["berths"] + 1:
                    stop["berth"] = SERVICES[0]["defaultBerths"].get(port["id"], stop["berth"])
    if "shipFiles" not in schedule and not any(ship["id"] == "mathilde" for ship in schedule["ships"]):
        schedule["ships"].append(mathilde_schedule())
    for ship in schedule.get("ships", []):
        ship.setdefault("recurrenceStops", deepcopy(ship["stops"]))
        ship.setdefault("voyageOverrides", {})
    if schedule != load("schedules.json"):
        schedule["revision"] += 1
        write(root / "schedules.json", schedule)

    def read_schedule():
        manifest = load("schedules.json")
        if any(path != f"ships/{ship_id}.json" for ship_id, path in manifest["shipFiles"].items()):
            ships = [load(path) for path in manifest["shipFiles"].values()]
        else:
            paths = {path.stem: path for path in (root / "ships").glob("*.json")}
            ordered = [ship_id for ship_id in manifest["shipFiles"] if ship_id in paths]
            ordered += sorted(set(paths) - set(ordered))
            ships = [json.loads(paths[ship_id].read_text(encoding="utf-8")) for ship_id in ordered]
            for ship_id, ship in zip(ordered, ships):
                if ship.get("id") != ship_id:
                    raise ValueError(f"Schiffs-ID muss zum Dateinamen {ship_id}.json passen.")
        for ship in ships:
            ship.setdefault("maxSpeedKnots", 20)
            try:
                validate_ship(ship, ship, load("ports.json"))
            except (ValueError, KeyError, TypeError, OverflowError) as error:
                raise ValueError(f"Ung\u00fcltige Schiffsdatei {ship.get('id', '?')}: {error}") from error
        return {"revision": manifest["revision"], "ships": ships}

    def data_signature(plan):
        value = {"ships": plan["ships"], "ports": load("ports.json"), "services": load("services.json")}
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def store_schedule(plan):
        manifest = {"schemaVersion": 2, "revision": plan["revision"], "shipFiles": {}}
        previous = load("schedules.json")
        for ship in plan["ships"]:
            old_path = previous.get("shipFiles", {}).get(ship["id"])
            path = f"ships/{ship['id']}.json"
            if old_path == path and load(old_path) == ship:
                manifest["shipFiles"][ship["id"]] = old_path
            else:
                write(root / path, ship)
                manifest["shipFiles"][ship["id"]] = path
        write(root / "schedules.json", manifest)

    if "shipFiles" not in schedule:
        write(root / "schedules.legacy.json", schedule)
        store_schedule({"revision": schedule["revision"] + 1, "ships": [migrate_ship(ship) for ship in schedule["ships"]]})
    elif any(path != f"ships/{ship_id}.json" for ship_id, path in schedule["shipFiles"].items()):
        store_schedule(read_schedule())
    legacy_path = root / "navigation.json"
    legacy = load("navigation.json") if legacy_path.exists() else {}
    for index, port in enumerate(ports):
        distances = port.setdefault("distancesNm", {})
        for destination in ports[index + 1:]:
            distances.setdefault(destination["id"], 100)
    write(root / "ports.json", ports)
    current = read_schedule()
    for ship in current["ships"]:
        path = f"ships/{ship['id']}.json"
        existing = load(path)
        if "maxSpeedKnots" not in existing:
            ship["maxSpeedKnots"] = legacy.get("maxSpeedKnotsByShip", {}).get(ship["id"], legacy.get("defaultMaxSpeedKnots", 20))
            write(root / path, ship)
    if legacy_path.exists():
        legacy_path.unlink()
    services = load("services.json")
    for service in services:
        if service["repeatWeeks"] == 15:
            service["repeatWeeks"] = 14
    write(root / "services.json", services)

    def response_plan(schedule):
        services = load("services.json")
        for service_id in sorted({ship["serviceId"] for ship in schedule["ships"]} - {service["id"] for service in services}):
            services.append({"id": service_id, "repeatWeeks": 14, "defaultBerths": {}})
        return {**schedule, "ports": load("ports.json"), "services": services, "dataSignature": data_signature(schedule)}

    @app.errorhandler(ValueError)
    @app.errorhandler(OSError)
    def data_error(error):
        return jsonify(error=f"JSON-Daten konnten nicht geladen werden: {error}"), 503

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/plan")
    def get_plan():
        with lock:
            return jsonify(response_plan(read_schedule()))

    @app.put("/api/ships/<ship_id>/plan")
    def save_plan(ship_id):
        if not request.is_json:
            return jsonify(error="JSON erwartet."), 400
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Ung\u00fcltiger Plan."), 400
        with lock:
            current = read_schedule()
            if payload.get("revision") != current["revision"]:
                return jsonify(error="Der aktuelle Plan wurde inzwischen ge\u00e4ndert. Bitte neu laden."), 409
            if payload.get("dataSignature") is not None and payload["dataSignature"] != data_signature(current):
                return jsonify(error="Die JSON-Dateien wurden extern ge\u00e4ndert. Bitte zuerst die aktuellen Daten laden; der Entwurf bleibt erhalten."), 409
            try:
                ships = deepcopy(current["ships"])
                originals = {ship["id"]: ship for ship in current["ships"]}
                if ship_id not in originals:
                    return jsonify(error="Unbekanntes Schiff."), 404
                ship = deepcopy(payload["ship"])
                original = originals[ship_id]
                validate_ship(ship, original, load("ports.json"))
                if ship.get("maxSpeedKnots", 20) != original["maxSpeedKnots"]:
                    raise ValueError("Die Maximalgeschwindigkeit bitte in der Schiffs-JSON bearbeiten.")
                if ship["proformas"] != original["proformas"] or payload.get("mode", "planning") != "planning":
                    raise ValueError("Proformas sind schreibgeschützt.")
                ships = [ship if item["id"] == ship_id else item for item in ships]
                dates = [stop[field] for ship in [*ships, *current["ships"]] for version in ship["proformas"] for stop in version["stops"] for field in ("arrival", "departure")]
                dates += [stop[field] for ship in [*ships, *current["ships"]] for voyage in ship["voyages"].values() for stop in voyage["stops"] for field in ("arrival", "departure")]
                dates += [version["validFrom"] for ship in [*ships, *current["ships"]] for version in ship["proformas"]]
                start = (datetime.fromisoformat(min(dates)) - timedelta(weeks=104)).isoformat()
                end = (datetime.fromisoformat(max(dates)) + timedelta(weeks=104)).isoformat()
                current_ports = load("ports.json")
                previous_issues = conflicts(current["ships"], start, end, current_ports)
                for identity, issue in conflicts(ships, start, end, current_ports).items():
                    if issue["severity"] > previous_issues.get(identity, {}).get("severity", 0) + 1e-6:
                        raise ValueError(issue["message"])
            except (ValueError, KeyError, TypeError, OverflowError) as error:
                return jsonify(error=str(error)), 400
            updated = {"revision": current["revision"] + 1, "ships": ships}
            store_schedule(updated)
            return jsonify(response_plan(updated))

    @app.get("/api/views")
    def get_views():
        with lock:
            return jsonify(load("views.json"))

    @app.put("/api/views")
    def save_view():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("name"), str) or not 1 <= len(payload["name"].strip()) <= 80:
            return jsonify(error="Bitte einen Ansichtsnamen mit maximal 80 Zeichen eingeben."), 400
        config = payload.get("config")
        if not isinstance(config, dict):
            return jsonify(error="Ung\u00fcltige Ansicht."), 400
        try:
            port_ids = {port["id"] for port in load("ports.json")}
            berth_ids = {f"{port['id']}:{berth}" for port in load("ports.json") for berth in range(1, port["berths"] + 1)}
            if not set(config["collapsed"]) <= port_ids or not set(config["hiddenBerths"]) <= berth_ids:
                raise ValueError()
            if type(config["dayWidth"]) is not int or not 16 <= config["dayWidth"] <= 1200:
                raise ValueError()
            datetime.fromisoformat(config["start"])
            if config.get("end"):
                if datetime.fromisoformat(config["end"]) < datetime.fromisoformat(config["start"]):
                    raise ValueError()
            if "compareProforma" in config and type(config["compareProforma"]) is not bool:
                raise ValueError()
            if config["selected"] not in {ship["id"] for ship in read_schedule()["ships"]}:
                raise ValueError()
            if any(not isinstance(config[field], (int, float)) or not 0 <= config[field] <= 1000000 for field in ("scrollLeft", "scrollTop")):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            return jsonify(error="Ung\u00fcltige Ansicht."), 400
        with lock:
            views = load("views.json")
            views[payload["name"].strip()] = {key: config[key] for key in ("collapsed", "hiddenBerths", "dayWidth", "start", "selected", "scrollLeft", "scrollTop")}
            views[payload["name"].strip()]["voyageDate"] = config.get("voyageDate", config["start"][:10])
            if config.get("end"):
                views[payload["name"].strip()]["end"] = config["end"]
            if "compareProforma" in config:
                views[payload["name"].strip()]["compareProforma"] = config["compareProforma"]
            write(root / "views.json", views)
            return jsonify(views)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "5055")), debug=False)