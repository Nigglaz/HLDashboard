import json
import os
import threading
import hashlib
import re
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory, abort
from planning import change_rotation, conflicts, insert_adhoc_stop, migrate_service_proformas, resolve_voyage, validate_service_proforma, validate_ship, validate_stations
from schedule_import import parse_maersk_text, prepare_import, prepare_service_import, vessel_identifier, vessel_key
from master_data import rename_port_references, update_port_metadata, update_ship_metadata
from auth import register_auth
from port_plugins import PortPluginRegistry
from plugin_runtime import plugin_file


def create_app(data_root=None, auth_root=None, plugin_root=None):
    app = Flask(__name__)
    root = Path(data_root) if data_root else Path(__file__).parent / "data"
    lock = threading.Lock()
    live_import_lock = threading.Lock()
    runtime_root = Path(auth_root) if auth_root is not None else (root / '.runtime' if data_root is not None else Path(app.instance_path))
    port_plugins = PortPluginRegistry(cache_dir=runtime_root / 'plugin-cache', plugin_root=plugin_root, legacy_cache_dir=runtime_root / 'weather-cache')
    app.extensions['port_plugins'] = port_plugins

    def write(path, value):
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) == value:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)

    def load(name):
        return json.loads((root / name).read_text(encoding="utf-8"))

    load("ports.json")
    service_data = load("services.json")
    ship_paths = sorted((root / "ships").glob("*.json"))
    ship_data = [json.loads(path.read_text(encoding="utf-8")) for path in ship_paths]
    migrated_ships, migrated_services = migrate_service_proformas(ship_data, service_data)
    if migrated_ships != ship_data or migrated_services != service_data:
        before = {root / "services.json": service_data, **{path: ship for path, ship in zip(ship_paths, ship_data)}}
        changes = {root / "services.json": migrated_services, **{path: ship for path, ship in zip(ship_paths, migrated_ships)}}
        written = []
        try:
            for path, value in changes.items():
                write(path, value)
                written.append(path)
        except OSError:
            for path in reversed(written):
                write(path, before[path])
            raise

    def read_schedule():
        paths = sorted((root / "ships").glob("*.json"))
        ships = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        services = load("services.json")
        vessel_names = set()
        for path, ship in zip(paths, ships):
            if ship.get("id") != path.stem:
                raise ValueError(f"Schiffs-ID muss zum Dateinamen {path.stem}.json passen.")
            unique_name = vessel_key(ship.get("vesselName", ship.get("name", "")))
            if not unique_name or unique_name in vessel_names:
                raise ValueError(f"Ung\u00fcltige Schiffsdatei {path.name}: Der Schiffsname muss vorhanden und eindeutig sein: {unique_name}")
            vessel_names.add(unique_name)
        for ship in ships:
            try:
                validate_ship(ship, ship, load("ports.json"), allow_rotation_conflicts=True, services=services)
            except (ValueError, KeyError, TypeError, OverflowError) as error:
                raise ValueError(f"Ung\u00fcltige Schiffsdatei {ship.get('id', '?')}: {error}") from error
        ships.sort(key=lambda ship: (ship["serviceId"], min([voyage["stops"][0]["arrival"] for voyage in ship["voyages"].values()] + [resolve_voyage(ship, assignment["validFrom"], services)["stops"][0]["arrival"] for assignment in ship.get("proformaAssignments", []) if resolve_voyage(ship, assignment["validFrom"], services)], default="9999"), ship["id"]))
        return {"ships": ships}

    def data_signature(plan):
        value = {"ships": plan["ships"], "ports": load("ports.json"), "services": load("services.json")}
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    legacy_path = root / "navigation.json"
    legacy = load("navigation.json") if legacy_path.exists() else {}
    for ship_path in (root / "ships").glob("*.json"):
        existing = json.loads(ship_path.read_text(encoding="utf-8"))
        speed = legacy.get("maxSpeedKnotsByShip", {}).get(existing["id"], legacy.get("defaultMaxSpeedKnots"))
        if "maxSpeedKnots" not in existing and speed is not None:
            existing["maxSpeedKnots"] = speed
            write(ship_path, existing)
    if legacy_path.exists():
        legacy_path.unlink()

    def response_plan(schedule):
        services = load("services.json")
        for service in services:
            service.setdefault("proformas", [])
            color = service.get("color")
            if color is not None and (not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color)):
                raise ValueError(f"Ung\u00fcltige Farbe f\u00fcr Dienst {service['id']}: Hexfarbe (#RRGGBB) erwartet.")
        for service_id in sorted({ship["serviceId"] for ship in schedule["ships"]} - {service["id"] for service in services}):
            services.append({"id": service_id, "proformas": []})
        return {**schedule, "ports": load("ports.json"), "services": services, "dataSignature": data_signature(schedule)}

    @app.errorhandler(ValueError)
    @app.errorhandler(OSError)
    def data_error(error):
        return jsonify(error=f"JSON-Daten konnten nicht geladen werden: {error}"), 503

    register_auth(app, auth_root if auth_root is not None else app.instance_path)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/assets/phoca_logo.png")
    def phoca_logo():
        return send_from_directory(Path(__file__).parent, "phoca_logo.png", mimetype="image/png")

    @app.get("/assets/phoca_font.svg")
    def phoca_font():
        return send_from_directory(Path(__file__).parent, "phoca_font.svg", mimetype="image/svg+xml")

    @app.get("/api/plan")
    def get_plan():
        with lock:
            return jsonify(response_plan(read_schedule()))

    @app.get('/api/port-plugins')
    def get_port_plugins():
        return jsonify(port_plugins.metadata())

    @app.get('/plugin-assets/<identity>/<path:name>')
    def get_plugin_asset(identity, name):
        package = port_plugins.loaded.get(identity)
        if package is None or Path(name).suffix.lower() not in {'.js', '.css', '.html', '.svg', '.png', '.jpg', '.webp', '.woff2'}:
            abort(404)
        try:
            path = plugin_file(package['folder'], name)
        except ValueError:
            abort(404)
        response = send_from_directory(path.parent, path.name)
        response.cache_control.no_cache = True
        return response

    @app.get('/api/ports/<port_id>/plugins')
    def get_port_plugin_series(port_id):
        try:
            start = datetime.fromisoformat(request.args['start'])
            end = datetime.fromisoformat(request.args['end'])
            if start.tzinfo is not None or end.tzinfo is not None or start >= end:
                raise ValueError('Gueltigen UTC-Planzeitraum ohne Zeitzonenoffset angeben.')
            plugin_ids = set(request.args['plugins'].split(',')) if 'plugins' in request.args else set(port_plugins.plugins)
            with lock:
                port = next((item for item in load('ports.json') if item['id'] == port_id), None)
            if port is None:
                return jsonify(error='Hafen nicht gefunden.'), 404
            return jsonify(port_plugins.series(port, start, end, plugin_ids))
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            return jsonify(error=str(error)), 400

    @app.post("/api/fleet")
    @app.put("/api/fleet/<ship_id>")
    def edit_fleet(ship_id=None):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="JSON erwartet."), 400
        with lock:
            plan = read_schedule()
            if payload.get("dataSignature") != data_signature(plan):
                return jsonify(error="Daten wurden geaendert. Bitte zuerst aktualisieren."), 409
            original = next((ship for ship in plan["ships"] if ship["id"] == ship_id), None)
            if ship_id is not None and original is None:
                return jsonify(error="Schiff nicht gefunden."), 404
            try:
                candidate = update_ship_metadata(payload, original, plan["ships"])
                if original and candidate["serviceId"] != original["serviceId"] and "proformaAssignments" not in payload:
                    candidate["proformaAssignments"] = []
                else:
                    candidate["proformaAssignments"] = payload.get("proformaAssignments", candidate.get("proformaAssignments", []))
                validate_ship(candidate, candidate, load("ports.json"), allow_rotation_conflicts=True, services=load("services.json"))
                write(root / "ships" / f"{candidate['id']}.json", candidate)
            except (ValueError, KeyError, TypeError) as error:
                return jsonify(error=str(error)), 400
            return jsonify(response_plan(read_schedule()))

    @app.post("/api/services/<service_id>/proformas")
    @app.put("/api/services/<service_id>/proformas/<proforma_id>")
    def edit_service_proforma(service_id, proforma_id=None):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("proforma"), dict):
            return jsonify(error="Proforma-JSON erwartet."), 400
        with lock:
            plan = read_schedule()
            if payload.get("dataSignature") != data_signature(plan):
                return jsonify(error="Daten wurden geaendert. Bitte zuerst aktualisieren."), 409
            services = load("services.json")
            service = next((item for item in services if item["id"] == service_id), None)
            if service is None:
                return jsonify(error="Dienst nicht gefunden."), 404
            proformas = service.setdefault("proformas", [])
            original = next((item for item in proformas if item["id"] == proforma_id), None)
            if proforma_id is not None and original is None:
                return jsonify(error="Proforma nicht gefunden."), 404
            candidate = deepcopy(payload["proforma"])
            if original and candidate.get("id") != proforma_id:
                return jsonify(error="Die Proforma-ID kann nach dem Verknuepfen nicht geaendert werden."), 400
            if any(item["id"] == candidate.get("id") and item is not original for item in proformas):
                return jsonify(error="Diese Proforma-ID existiert bereits."), 400
            try:
                validate_service_proforma(candidate, load("ports.json"))
                if original:
                    proformas[proformas.index(original)] = candidate
                else:
                    proformas.append(candidate)
                write(root / "services.json", services)
            except (ValueError, KeyError, TypeError, OverflowError) as error:
                return jsonify(error=str(error)), 400
            return jsonify(response_plan(read_schedule()))

    @app.post("/api/ports")
    @app.put("/api/ports/<port_id>")
    def edit_ports(port_id=None):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="JSON erwartet."), 400
        with lock:
            plan = read_schedule()
            if payload.get("dataSignature") != data_signature(plan):
                return jsonify(error="Daten wurden geaendert. Bitte zuerst aktualisieren."), 409
            ports = load("ports.json")
            original = next((port for port in ports if port["id"] == port_id), None)
            if port_id is not None and original is None:
                return jsonify(error="Hafen nicht gefunden."), 404
            try:
                candidate, updated = update_port_metadata(payload, original, ports, plugin_validators=port_plugins.validators())
                services = load("services.json")
                changed_ships, changed_services = rename_port_references(plan["ships"], services, port_id, candidate["id"]) if original else (plan["ships"], services)
                for service in changed_services:
                    for proforma in service.get("proformas", []):
                        validate_service_proforma(proforma, updated)
                for ship in changed_ships:
                    validate_ship(ship, ship, updated, allow_rotation_conflicts=True, services=changed_services)
                before = {root / "ports.json": ports, root / "services.json": services}
                changes = {root / "ports.json": updated, root / "services.json": changed_services}
                for old_ship, ship in zip(plan["ships"], changed_ships):
                    if old_ship != ship:
                        path = root / "ships" / f"{ship['id']}.json"
                        before[path] = old_ship
                        changes[path] = ship
                written = []
                try:
                    for path, value in changes.items():
                        write(path, value)
                        written.append(path)
                except OSError:
                    for path in reversed(written):
                        write(path, before[path])
                    raise
            except (ValueError, KeyError, TypeError) as error:
                return jsonify(error=str(error)), 400
            result = response_plan(read_schedule())
            if original and candidate["id"] != port_id:
                result["portIdChange"] = {"from": port_id, "to": candidate["id"]}
            return jsonify(result)

    @app.put("/api/ships/<ship_id>/plan")
    def save_plan(ship_id):
        if not request.is_json:
            return jsonify(error="JSON erwartet."), 400
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Ung\u00fcltiger Plan."), 400
        with lock:
            current = read_schedule()
            if payload.get("dataSignature") != data_signature(current):
                return jsonify(error="Die JSON-Dateien wurden extern ge\u00e4ndert. Bitte zuerst die aktuellen Daten laden; der Entwurf bleibt erhalten."), 409
            try:
                ships = deepcopy(current["ships"])
                services = load("services.json")
                originals = {ship["id"]: ship for ship in current["ships"]}
                if ship_id not in originals:
                    return jsonify(error="Unbekanntes Schiff."), 404
                ship = deepcopy(payload["ship"])
                original = originals[ship_id]
                validate_ship(ship, original, load("ports.json"), services=services)
                if ship.get("maxSpeedKnots") != original["maxSpeedKnots"]:
                    raise ValueError("Die Maximalgeschwindigkeit bitte in der Schiffs-JSON bearbeiten.")
                if ship.get("proformaAssignments") != original.get("proformaAssignments") or payload.get("mode", "planning") != "planning":
                    raise ValueError("Proforma-Zuordnungen werden im Flotten-Tab bearbeitet.")
                ships = [ship if item["id"] == ship_id else item for item in ships]
                dates = [stop[field] for service in services for version in service.get("proformas", []) for stop in version["stops"] for field in ("arrival", "departure")]
                dates += [assignment["validFrom"] for item in [*ships, *current["ships"]] for assignment in item.get("proformaAssignments", [])]
                dates += [stop[field] for item in [*ships, *current["ships"]] for voyage in item["voyages"].values() for stop in voyage["stops"] for field in ("arrival", "departure")]
                start = (datetime.fromisoformat(min(dates)) - timedelta(weeks=104)).isoformat()
                end = (datetime.fromisoformat(max(dates)) + timedelta(weeks=104)).isoformat()
                current_ports = load("ports.json")
                previous_issues = conflicts(current["ships"], start, end, current_ports, services)
                for identity, issue in conflicts(ships, start, end, current_ports, services).items():
                    if issue["severity"] > previous_issues.get(identity, {}).get("severity", 0) + 1e-6:
                        raise ValueError(issue["message"])
            except (ValueError, KeyError, TypeError, OverflowError) as error:
                return jsonify(error=str(error)), 400
            write(root / "ships" / f"{ship_id}.json", ship)
            return jsonify(response_plan(read_schedule()))

    @app.post("/api/import/<source>/live")
    def import_live(source):
        sources = {"maersk": "Maersk", "hapag": "Hapag-Lloyd"}
        if source not in sources:
            return jsonify(error="Unbekannte Importquelle."), 404
        label = sources[source]
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="JSON erwartet."), 400
        try:
            name = vessel_identifier(payload.get("vesselName", ""))
            start, end = payload["fromDate"], payload["toDate"]
            if datetime.fromisoformat(start).date().isoformat() != start or datetime.fromisoformat(end).date().isoformat() != end or end < start:
                raise ValueError("Ung\u00fcltiger Importzeitraum.")
            with lock:
                known = [ship for ship in read_schedule()["ships"] if vessel_key(ship.get("vesselName", ship["name"])) == vessel_key(name)]
            if len(known) != 1:
                raise ValueError("Der Schiffsname muss genau einem vorhandenen Schiff entsprechen.")
        except (KeyError, TypeError, ValueError) as error:
            return jsonify(error=str(error)), 400
        if not live_import_lock.acquire(blocking=False):
            return jsonify(error="Ein Live-Import l\u00e4uft bereits."), 409
        try:
            command = [sys.executable, str(Path(__file__).parent / f"import_{source}.py"), "--vessel", name, "--from", start, "--to", end]
            command.append("--headed")
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=180, cwd=Path(__file__).parent)
            if result.returncode:
                return jsonify(error=result.stderr.strip()[-5000:] or f"{label}-Live-Abruf fehlgeschlagen."), 502
            packet = json.loads(result.stdout)
            if packet.get("source") != source or packet.get("vesselName") != name or not packet.get("calls"):
                raise ValueError("Das Skript hat kein passendes Importergebnis geliefert.")
            return jsonify(packet=packet)
        except subprocess.TimeoutExpired:
            return jsonify(error=f"Der {label}-Abruf hat das Zeitlimit von drei Minuten \u00fcberschritten."), 504
        except (OSError, ValueError) as error:
            return jsonify(error=str(error)), 502
        finally:
            live_import_lock.release()

    def import_preview(payload, plan):
        packet = payload.get("packet")
        if packet is None:
            if not all(payload.get(field) for field in ("vesselName", "fromDate", "toDate")):
                raise ValueError("Schiffsname und Importzeitraum sind erforderlich.")
            packet = parse_maersk_text(payload.get("text", ""), payload["vesselName"], payload["fromDate"], payload["toDate"])
        if isinstance(packet, dict) and "packets" in packet:
            if payload.get("serviceId") and payload["serviceId"] != packet.get("serviceId"):
                raise ValueError("Importdaten gehoeren nicht zum ausgewaehlten Dienst.")
            preview = prepare_service_import(plan, packet, payload.get("choices"), payload.get("excludedShips"), payload.get("voyageDate") or None, payload.get("fromDate"), payload.get("toDate"))
        else:
            if payload.get("scope") == "service":
                raise ValueError("Fuer einen Dienst werden gebuendelte Schiffsergebnisse benoetigt.")
            preview = prepare_import(plan, packet, payload.get("choices"), payload.get("voyageDate") or None, payload.get("fromDate"), payload.get("toDate"))
        single_candidate = preview.get("candidate") or {}
        if preview.get("candidates") or single_candidate.get("id"):
            replacements = {ship["id"]: ship for ship in preview.get("candidates", [])}
            if single_candidate.get("id"):
                replacements[single_candidate["id"]] = single_candidate
            proposed = [replacements.get(ship["id"], ship) for ship in plan["ships"]]
            dates = [stop[field] for service in plan["services"] for version in service.get("proformas", []) for stop in version["stops"] for field in ("arrival", "departure")]
            dates += [stop[field] for ship in [*proposed, *plan["ships"]] for voyage in ship["voyages"].values() for stop in voyage["stops"] for field in ("arrival", "departure")]
            if dates:
                start = (datetime.fromisoformat(min(dates)) - timedelta(weeks=104)).isoformat()
                end = (datetime.fromisoformat(max(dates)) + timedelta(weeks=104)).isoformat()
                existing = conflicts(plan["ships"], start, end, plan["ports"], plan["services"])
                current = conflicts(proposed, start, end, plan["ports"], plan["services"])
                preview["warnings"] = [issue["message"] for key, issue in current.items() if issue["severity"] > existing.get(key, {}).get("severity", 0) + 1e-6]
            else:
                preview["warnings"] = []
        else:
            preview["warnings"] = []
        return {**preview, "packet": packet, "dataSignature": plan["dataSignature"]}

    @app.post("/api/import/preview")
    def preview_import():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="JSON erwartet."), 400
        with lock:
            try:
                return jsonify(import_preview(payload, response_plan(read_schedule())))
            except (ValueError, KeyError, TypeError, OverflowError) as error:
                return jsonify(error=str(error)), 400

    @app.post("/api/import/apply")
    def apply_import():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="JSON erwartet."), 400
        with lock:
            plan = response_plan(read_schedule())
            if payload.get("dataSignature") != plan["dataSignature"]:
                return jsonify(error="Die Daten wurden inzwischen ge\u00e4ndert. Bitte die Importvorschau neu berechnen."), 409
            try:
                preview = import_preview(payload, plan)
                if preview["unresolved"] or preview["candidate"] is None:
                    raise ValueError("Alle eingeschlossenen Haefen muessen eindeutig zugeordnet sein.")
                if preview.get("errors"):
                    raise ValueError("Mindestens ein eingeschlossenes Schiff hat kein gueltiges Importergebnis.")
                if payload.get("confirmTimeBasis") is not True:
                    raise ValueError("Bitte die Zeitbasis vor der Uebernahme bestaetigen.")
                if any(change["status"] == "removed" for change in preview["changes"]) and payload.get("confirmRemovals") is not True:
                    raise ValueError("Bitte entfernte Aufenthalte ausdruecklich bestaetigen.")
                candidates = preview.get("candidates", [preview["candidate"]])
                originals = {ship["id"]: ship for ship in plan["ships"]}
                replacements = {ship["id"]: ship for ship in candidates}
                for candidate in candidates:
                    original = originals[candidate["id"]]
                    validate_ship(candidate, original, plan["ports"], services=plan["services"])
                    if candidate.get("proformaAssignments") != original.get("proformaAssignments"):
                        raise ValueError("Proforma-Zuordnungen duerfen beim Fahrplanimport nicht veraendert werden.")
                proposed = [replacements.get(ship["id"], ship) for ship in plan["ships"]]
                services = plan["services"]
                dates = [stop[field] for service in services for version in service.get("proformas", []) for stop in version["stops"] for field in ("arrival", "departure")]
                dates += [assignment["validFrom"] for ship in [*proposed, *plan["ships"]] for assignment in ship.get("proformaAssignments", [])]
                dates += [stop[field] for ship in [*proposed, *plan["ships"]] for voyage in ship["voyages"].values() for stop in voyage["stops"] for field in ("arrival", "departure")]
                start = (datetime.fromisoformat(min(dates)) - timedelta(weeks=104)).isoformat()
                end = (datetime.fromisoformat(max(dates)) + timedelta(weeks=104)).isoformat()
                warnings = preview.get("warnings", [])
                written = []
                try:
                    for candidate in candidates:
                        write(root / "ships" / f"{candidate['id']}.json", candidate)
                        written.append(candidate["id"])
                except OSError:
                    for ship_id in written:
                        write(root / "ships" / f"{ship_id}.json", originals[ship_id])
                    raise
            except (ValueError, KeyError, TypeError, OverflowError) as error:
                return jsonify(error=str(error)), 400
            result = response_plan(read_schedule())
            result["importWarnings"] = warnings
            return jsonify(result)

    @app.post("/api/ships/<ship_id>/rotation")
    def preview_rotation(ship_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="JSON erwartet."), 400
        with lock:
            current = read_schedule()
            if payload.get("dataSignature") != data_signature(current):
                return jsonify(error="Die Daten wurden inzwischen ge\u00e4ndert. Bitte zuerst aktualisieren."), 409
            ship = next((item for item in current["ships"] if item["id"] == ship_id), None)
            if ship is None:
                return jsonify(error="Unbekanntes Schiff."), 404
            try:
                key = payload["voyageDate"]
                if datetime.fromisoformat(key).date().isoformat() != key:
                    raise ValueError("Ung\u00fcltiges Reisedatum.")
                voyage = resolve_voyage(ship, key, load("services.json"))
                if voyage is None or voyage["key"] != key:
                    raise ValueError("Keine Reise f\u00fcr dieses Datum vorhanden.")
                stops = payload["stops"]
                original = {(stop["id"], stop["portId"]) for stop in voyage["stops"]}
                provided = {(stop["id"], stop["portId"]) for stop in stops}
                if not original <= provided or any((stop["id"], stop["portId"]) not in original and not stop.get("adhoc") for stop in stops):
                    raise ValueError("Change Rotation darf nur vorhandene Hafenaufenthalte umordnen.")
                reordered = change_rotation(ship, stops, load("ports.json"))
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                return jsonify(error=str(error)), 400
            return jsonify(stops=reordered, voyageDate=key, proformaId=voyage["proformaId"])

    @app.post("/api/ships/<ship_id>/adhoc-stop")
    def preview_adhoc_stop(ship_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="JSON erwartet."), 400
        with lock:
            current = read_schedule()
            if payload.get("dataSignature") != data_signature(current):
                return jsonify(error="Die Daten wurden inzwischen ge\u00e4ndert. Bitte zuerst aktualisieren."), 409
            ship = next((item for item in current["ships"] if item["id"] == ship_id), None)
            if ship is None:
                return jsonify(error="Unbekanntes Schiff."), 404
            try:
                key = payload["voyageDate"]
                if datetime.fromisoformat(key).date().isoformat() != key:
                    raise ValueError("Ung\u00fcltiges Reisedatum.")
                voyage = resolve_voyage(ship, key, load("services.json"))
                if voyage is None or voyage["key"] != key:
                    raise ValueError("Keine Reise f\u00fcr dieses Datum vorhanden.")
                stops = payload["stops"]
                current_ports = load("ports.json")
                validate_stations(stops, {port["id"]: port for port in current_ports}, require_order=False)
                service = next((service for service in load("services.json") if service["id"] == ship["serviceId"]), {})
                port_id = payload["portId"]
                berth = service.get("defaultBerths", {}).get(port_id, 1)
                if ("beforeStopId" in payload) == ("afterStopId" in payload):
                    raise ValueError("Genau eine Einf\u00fcgeposition angeben.")
                if "beforeStopId" in payload and not isinstance(payload["beforeStopId"], str):
                    raise ValueError("Ung\u00fcltiger folgender Aufenthalt.")
                reordered = insert_adhoc_stop(stops, payload.get("afterStopId"), port_id, current_ports, berth,
                                              before_stop_id=payload.get("beforeStopId"))
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                return jsonify(error=str(error)), 400
            return jsonify(stops=reordered, voyageDate=key, proformaId=voyage["proformaId"])

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "5055")), debug=False)