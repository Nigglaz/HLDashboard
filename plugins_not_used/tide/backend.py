import hashlib
import json
import logging
import os
import re
import ssl
import sys
import tempfile
import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from plugin_api import plugin_locations, valid_plugin_url

TIDE_PAST_DAYS = 10
TIDE_FORECAST_DAYS = 8


def fetch_bsh_levels(station_id):
    if not isinstance(station_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,119}', station_id):
        raise ValueError('Ungueltige BSH-Pegelkennung.')
    request = Request(f'https://gdi.bsh.de/ldproxy/rest/services/WaterLevelForecast/collections/waterlevelforecastdata/items/{station_id}?f=json',
                      headers={'User-Agent': 'PHOCA tide plugin', 'Accept': 'application/geo+json'})
    context = ssl.create_default_context()
    if sys.platform == 'win32':
        from truststore import SSLContext
        context = SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with urlopen(request, timeout=12, context=context) as response:
        content = response.read(2_000_001)
    if len(content) > 2_000_000:
        raise ValueError('Tide-Antwort ist zu gross.')
    return json.loads(content)


class TidePlugin:
    id = 'tide'
    label = 'Tide (BSH)'
    presentation = 'tide'
    source = {'name': 'BSH', 'url': 'https://gdi.bsh.de/ldproxy/rest/services/WaterLevelForecast',
              'attribution': 'Bundesamt fuer Seeschifffahrt und Hydrographie (BSH), CC BY 4.0',
              'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/'}
    accuracy_note = 'BSH-Hoch-/Niedrigwasserereignisse; relative Darstellung durch PHOCA ohne Hoehenmassstab. Keine sicherheitsverbindliche Freigabe. Wetterbedingte Zeitverschiebungen werden nicht eigenstaendig berechnet.'

    @staticmethod
    def validate_config(settings):
        station = settings.get('stationId', '')
        if not isinstance(station, str) or station and not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,119}', station):
            raise ValueError('BSH-Pegelkennung muss eine gueltige Kennung oder leer sein.')
        if not valid_plugin_url(settings.get('url', '')):
            raise ValueError('Tide-Link muss eine HTTPS-Adresse oder leer sein.')

    def locations(self, port):
        return [location for location in plugin_locations(port) if location.get('plugin') == self.id or not location.get('plugin') and (
            location.get('plugins', {}).get(self.id, {}).get('enabled', False) or location.get('plugins', {}).get(self.id, {}).get('url'))]

    def __init__(self, fetcher=None, clock=None, cache_dir=None):
        self.fetcher = fetcher or fetch_bsh_levels
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.cache = {}
        self.lock = threading.Lock()

    def metadata(self):
        today = self.clock().astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        return {'id': self.id, 'label': self.label, 'presentation': self.presentation, 'unit': '',
                'locationOptIn': True, 'stationRequired': True, 'source': self.source, 'accuracyNote': self.accuracy_note,
                'window': {'from': (today - timedelta(days=TIDE_PAST_DAYS)).isoformat(timespec='minutes'),
                           'to': (today + timedelta(days=TIDE_FORECAST_DAYS)).isoformat(timespec='minutes')}}

    def decode(self, packet):
        if not isinstance(packet, dict) or packet.get('type') != 'Feature':
            raise ValueError('Unerwartete BSH-Antwort.')
        properties = packet.get('properties')
        points = properties.get('high_water_low_water') if isinstance(properties, dict) else None
        if not isinstance(points, list):
            raise ValueError('BSH liefert keine Hoch-/Niedrigwasserereignisse fuer diesen Pegel.')
        events, previous, segment_id = [], None, 0
        for point in points:
            if not isinstance(point, dict) or point.get('event') not in ('HW', 'NW'):
                raise ValueError('Ungueltiges BSH-Tideereignis.')
            time = datetime.fromisoformat(point['event_timestamp'])
            if time.tzinfo is None:
                raise ValueError('BSH-Zeitpunkt ohne Zeitzone.')
            time = time.astimezone(timezone.utc).replace(tzinfo=None)
            if previous is not None:
                if time <= previous:
                    raise ValueError('BSH-Zeitpunkte muessen aufsteigend vorliegen.')
                if time - previous > timedelta(hours=18) or events[-1]['kind'] == ('high' if point['event'] == 'HW' else 'low'):
                    segment_id += 1
            events.append({'time': time.isoformat(timespec='minutes'), 'kind': 'high' if point['event'] == 'HW' else 'low',
                           'value': 1 if point['event'] == 'HW' else -1, 'segmentId': segment_id})
            previous = time
        return events

    def cache_path(self, key):
        identity = hashlib.sha256(json.dumps(key, separators=(',', ':')).encode('utf-8')).hexdigest()
        return self.cache_dir / f'tide-{identity}.json'

    def read_cached(self, key):
        if self.cache_dir is None:
            return None
        try:
            with self.cache_path(key).open('rb') as source:
                content = source.read(2_000_001)
            if len(content) > 2_000_000:
                return None
            data = json.loads(content)
            if data.get('schemaVersion') != 1 or data.get('key') != list(key) or type(data.get('failed')) is not bool:
                return None
            expires = datetime.fromisoformat(data['expiresAt'])
            fetched = datetime.fromisoformat(data['fetchedAt']) if data.get('fetchedAt') else None
            now = self.clock().astimezone(timezone.utc)
            if expires.tzinfo is None or expires > now + timedelta(hours=1, minutes=1):
                return None
            if fetched is not None and (fetched.tzinfo is None or fetched > now + timedelta(minutes=1)):
                return None
            if not data['failed'] and (fetched is None or expires > fetched + timedelta(hours=1, minutes=1)):
                return None
            events, previous = data['events'], None
            if not isinstance(events, list):
                return None
            for event in events:
                time = datetime.fromisoformat(event['time'])
                if time.tzinfo is not None or previous is not None and time <= previous or event['kind'] not in ('high', 'low'):
                    return None
                if event['value'] != (1 if event['kind'] == 'high' else -1) or type(event['segmentId']) is not int:
                    return None
                previous = time
            return {'events': events, 'fetchedAt': data.get('fetchedAt'), 'expires': expires, 'failed': data['failed']}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def write_cached(self, key, cached):
        if self.cache_dir is None:
            return
        temporary = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            data = {'schemaVersion': 1, 'key': list(key), 'fetchedAt': cached['fetchedAt'],
                    'expiresAt': cached['expires'].isoformat(timespec='seconds'), 'failed': cached['failed'], 'events': cached['events']}
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.cache_dir, suffix='.tmp', delete=False) as target:
                temporary = Path(target.name)
                json.dump(data, target, allow_nan=False)
            os.replace(temporary, self.cache_path(key))
        except (OSError, ValueError):
            logging.getLogger(__name__).warning('Tidecache konnte nicht gespeichert werden; Daten bleiben im Arbeitsspeicher.')
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def track(self, port, start, end):
        result = {**self.metadata(), 'status': 'ready', 'samples': [], 'relative': True}
        if port.get('plugins', {}).get(self.id, {}).get('enabled', False) is False:
            return {**result, 'status': 'disabled'}
        station_id = port.get('plugins', {}).get(self.id, {}).get('stationId')
        if not isinstance(station_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,119}', station_id):
            return {**result, 'status': 'unconfigured', 'message': 'BSH-Pegel am Tide-Standort auswaehlen.'}
        result['stationId'] = station_id
        window_start = datetime.fromisoformat(result['window']['from'])
        window_end = datetime.fromisoformat(result['window']['to'])
        if end <= window_start or start >= window_end:
            return {**result, 'status': 'out-of-range', 'message': 'Ausserhalb des Tide-Datenzeitraums.'}
        key = (station_id, 'bsh-events-v1')
        with self.lock:
            now = self.clock().astimezone(timezone.utc)
            cached = self.cache.get(key) or self.read_cached(key)
            if cached is None or now >= cached['expires']:
                try:
                    packet = self.fetcher(station_id)
                    if not isinstance(packet, dict) or packet.get('id') != station_id:
                        raise ValueError('BSH-Antwort gehoert zu einem anderen Pegel.')
                    events = self.decode(packet)
                    cached = {'events': events, 'fetchedAt': now.isoformat(timespec='seconds'),
                              'expires': self.clock().astimezone(timezone.utc) + timedelta(hours=1), 'failed': False}
                except (OSError, ValueError, KeyError, TypeError, OverflowError):
                    cached = {**(cached or {'events': [], 'fetchedAt': None}),
                              'expires': self.clock().astimezone(timezone.utc) + timedelta(minutes=5), 'failed': True}
                self.write_cached(key, cached)
            if key not in self.cache and len(self.cache) >= 128:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = cached
            cached = deepcopy(cached)
        events = cached['events']
        result.update(fetchedAt=cached['fetchedAt'], refreshAfterSeconds=max(1, int((cached['expires'] - self.clock().astimezone(timezone.utc)).total_seconds())))
        if cached['failed']:
            result.update(status='stale' if events else 'error', message='Tideabruf fehlgeschlagen; letzter Datenstand.' if events else 'Tide-Daten derzeit nicht verfuegbar.')
        elif not events:
            result.update(status='empty', message='Keine BSH-Hoch-/Niedrigwasserereignisse verfuegbar.')
        if events:
            result.update(availableFrom=events[0]['time'], availableTo=events[-1]['time'])
        result['samples'] = [event for event in events if max(window_start, start - timedelta(days=2)) <= datetime.fromisoformat(event['time']) < min(window_end, end + timedelta(days=2))]
        return result
Plugin = TidePlugin
