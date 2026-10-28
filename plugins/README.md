# PHOCA Plugin API 1

Lokale, vertrauenswuerdige Pakete werden beim Serverstart aus `plugins/*/plugin.toml` geladen. Keine Registrierung im PHOCA-Code, kein Hot-Reload. Paket hinzufuegen/entfernen oder Code aendern, Server neu starten und Browser neu laden. Gespeicherte Einstellungen entfernter Pakete bleiben erhalten. Fehlerhafte Pakete werden protokolliert; `/api/port-plugins` liefert Startdiagnosen.

## Paket

```text
plugins/example/
  plugin.toml
  backend.py
  frontend.js
  settings.html
  style.css
```

```toml
id = "example"
api_version = 1
order = 100
backend = "backend.py"
frontend = "frontend.js"
settings = "settings.html"
style = "style.css"
```

IDs: `[a-z0-9][a-z0-9_-]{0,63}`, eindeutig und dauerhaft. `order` ist optional, kleinere Werte zuerst. Dateipfade bleiben innerhalb des Pakets. Weitere Python-/JS-Module und Assets duerfen dort liegen; relative Imports werden unterstuetzt. Abhaengigkeiten gehoeren in eine optionale paketinterne `requirements.txt` und werden nicht automatisch installiert, z. B. `python -m pip install -r plugins/tide/requirements.txt`.

## Python

Das Backend exportiert `Plugin`, eine Klasse oder Klassenalias:

| Einstiegspunkt | Vertrag |
| --- | --- |
| `__init__(cache_dir=None, clock=None)` | Privater Cachepfad, ggf. `None`; `clock()` liefert die aktuelle zeitzonenbewusste Serverzeit in UTC. Konstruktor ohne Anbieterabruf. |
| `metadata()` | JSON-Objekt mit mindestens `id` und `label`. Optional `unit`, `source`, `window: {from, to}`, `locationOptIn`, `quickToggle`, `icon` (Lucide-Name), weitere eigene Felder. |
| `track(port, start, end)` | JSON-Objekt mit `status` und `samples: []`, optional `message`, `fetchedAt`, `refreshAfterSeconds` und eigenen Daten. PHOCA ergaenzt Identitaet, Standortname und Link. |
| `validate_config(settings)` | Optional; prueft globale und lokale eigene Konfigurationen. `ValueError` mit lesbarer Meldung bei ungueltigen Werten. Kein Schreiben. |
| `locations(port)` | Optional; eigene Altformat-/Standortauswahl. Standard: PHOCA-Standorte, gefiltert nach Plugin-ID. Fuer neue Pakete das kanonische Format unten verwenden. |

`port` ist eine lokale Kopie: Koordinaten und `port.plugins[id]` enthalten bereits die globale Konfiguration mit lokalen Ueberschreibungen. `start`/`end` sind naive Python-`datetime` in **UTC**, Ende exklusiv. `metadata.window` verwendet ebenfalls UTC-ISO ohne Offset. Anbieterzeitstempel selbst korrekt nach UTC umrechnen.

Statuswerte: `ready`, `stale`, `error`, `empty`, `unconfigured`, `disabled`, `out-of-range`. Eigene Sample-/Periodenformate vereinbaren Backend und Frontend innerhalb des Pakets; der Host interpretiert diese nicht. JSON muss endlich/serialisierbar sein. Abrufe, Cacheinhalt, Ablaufzeiten und fachliche Warnregeln gehoeren zum Plugin. `refreshAfterSeconds` steuert das Nachladen im Browser, ohne Hintergrundjob bei inaktiver Anwendung.

Allgemeine Helfer stehen in `plugin_api.py`: `finite_number`, `validate_coordinates`, `valid_plugin_url`, `plugin_locations`. Keine Imports aus einem anderen Plugin. Cache: `instance/plugin-cache/<id>/`; alte `<id>-*.json` aus `instance/weather-cache/` werden beim Start kopiert, ohne vorhandene private Dateien zu ueberschreiben.

## JavaScript / HTML

`frontend.js` ist ein ES-Modul mit synchronen Exporten:

| Export | Vertrag |
| --- | --- |
| `render({host, track, view, location, port, config, api})` | Zeichnet ausschliesslich innerhalb von `host`. PHOCA stellt je Standort eine feste, abgeschnittene 38-Pixel-Zeile bereit. Wird bei Scrollen, Zoom, Daten- oder Layoutaenderung erneut aufgerufen; vorheriger Inhalt wird entfernt. Auch Lade-/Fehlerstatus behandeln. |
| `mountSettings({host, port, template, api, metadata})` | Baut ausschliesslich innerhalb von `host` die eigenen Einstellungen auf. `template` ist der Inhalt von `settings.html`. Rueckgabe: `{read() { return {settings, locations}; }}`. |
| `locations(port)` | Optional; liefert die eigenen Standortobjekte fuer Kalender und Altformat-Unterstuetzung. Ohne Export werden kanonische Eintraege mit passender `plugin`-ID verwendet. |

`read()` liefert nur eigene globale `settings` und eigene vollstaendige `locations`. Neue/geaenderte Formulare loesen ein bubbelndes `input`- oder `change`-Ereignis aus. PHOCA uebernimmt Speichern, CSRF, Konfliktpruefung und Erhalt nicht verfuegbarer Konfigurationen. Solange Formulare laden, wird Speichern verhindert. Keine direkten Zugriffe auf interne PHOCA-Globals oder andere Plugins.

`api` stellt bereit:
- Zeit/Geometrie: `START`, `END`, `DAY`, `HOUR` (Millisekunden), `dayWidth`, `rowHeight`, `now` (UTC-ISO), `timeBasis: "UTC"`; `instant(iso)`, `iso(ms)`, `shortDate(ms)`.
- `view`: `left`, `right`, `labelWidth`, `labelLeft` in Pixeln; `from`, `to` als UTC-Epoch-Millisekunden. Pixelposition eines Zeitpunkts: `view.labelWidth + (api.instant(time) - api.START) / api.DAY * api.dayWidth`.
- Allgemeine Helfer: `finite`, `externalUrl`, `severity`, `icons()`, `statusElement(label, message, view, index=0, state='')`, `locationLabel(host, track, location, view, title='')`.
- Optional `locationSettings({host, port, template, id, locations, fill, readConfig, readGlobal})`: gemeinsame Standortbindung. Verwendet `data-location-template`, `data-locations`, `data-add`, `data-remove`, `data-enabled`, optional `data-global-enabled` und `data-field="name|url|latitude|longitude"`. Eigene Felder bleiben im Paket und werden mit `fill(row, location)`, `readConfig(row, previous)` und `readGlobal(settings)` verarbeitet. Siehe die beiden vorhandenen Pakete.

CSS-Regeln mit `[data-plugin-package="example"]` begrenzen. PHOCA stellt diesen Scope an Zeile und Formular sowie Designvariablen bereit. Keine globalen Selektoren oder eigenen dauerhaften Timer/Eventhandler ausserhalb des Hosts. Frontenddateien werden nur angemeldet unter `/plugin-assets/<id>/<Datei>` ausgeliefert; Python und Manifest sind nicht oeffentlich.

## Konfiguration

```json
{
  "id": "example-site-1",
  "plugin": "example",
  "name": "Freier Anzeigename",
  "url": "https://example.test/",
  "coordinates": {"latitude": 53.5, "longitude": 9.9},
  "plugins": {"example": {"enabled": true, "customValue": 42}}
}
```

Eintraege liegen am Hafen in `pluginLocations`, globale Einstellungen in `port.plugins[id]`. Standort-IDs eindeutig, Namen nicht leer, HTTPS-Links oder leer, endliche WGS84-Koordinaten. Bis 16 Standorte je Plugin, insgesamt bis 256. `ignoredPlugins` ist eine interne Altformat-Migrationsmarkierung; nicht selbst setzen. Kein Anbieter-API-Schluessel in Hafendaten; Umgebungsvariablen verwenden.

## Tests

Pakettests optional als `test_*.py` im Paket; `__init__.py` fuer rekursive Unittest-Erkennung hinzufuegen. Von PHOCA aus: `python -m unittest discover -p "test_*.py" -q`. Nur ein installiertes Paket: `python -m unittest plugins.weather.test_backend -q` bzw. `plugins.tide.test_backend`. Kern-/Entfernbarkeitstests: `python -m unittest test_port_plugins -q`.