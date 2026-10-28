import json
import os
import threading
import hashlib
import logging
import tempfile
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


from plugin_api import finite_number, validate_coordinates, plugin_locations

PAST_DAYS = 10
FORECAST_DAYS = 16

def fetch_open_meteo(latitude, longitude):
    api_key = os.environ.get('OPEN_METEO_API_KEY')
    host = 'customer-api.open-meteo.com' if api_key else 'api.open-meteo.com'
    parameters = {'latitude': latitude, 'longitude': longitude, 'hourly': 'wind_speed_10m,wind_direction_10m',
                  'wind_speed_unit': 'kn', 'timezone': 'GMT', 'past_days': PAST_DAYS, 'forecast_days': FORECAST_DAYS}
    if api_key:
        parameters['apikey'] = api_key
    request = Request(f'https://{host}/v1/forecast?{urlencode(parameters)}', headers={'User-Agent': 'PHOCA weather plugin'})
    with urlopen(request, timeout=12) as response:
        content = response.read(2_000_001)
    if len(content) > 2_000_000:
        raise ValueError('Wetterantwort ist zu gross.')
    return json.loads(content)


class WeatherPlugin:
    id = 'weather'
    label = 'Wind'
    presentation = 'directional'
    interval_minutes = 180
    source = {'name': 'Open-Meteo', 'url': 'https://open-meteo.com/', 'attribution': 'Weather data by Open-Meteo.com (CC BY 4.0)'}

    @staticmethod
    def validate_config(settings):
        threshold = settings.get('warningWindKnots')
        if threshold is not None and (not finite_number(threshold) or threshold <= 0):
            raise ValueError('Die Windwarnschwelle muss positiv sein oder leer bleiben.')

    def locations(self, port):
        return [location for location in plugin_locations(port) if location.get('plugin') == self.id or not location.get('plugin') and (
            location.get('plugins', {}).get(self.id, {}).get('enabled', True) or not any(
                settings.get('enabled', False) for identity, settings in location.get('plugins', {}).items() if identity != self.id))]

    def __init__(self, fetcher=None, clock=None, cache_dir=None):
        self.fetcher = fetcher or fetch_open_meteo
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.cache = {}
        self.lock = threading.Lock()
        self.fetch_lock = threading.Lock()
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None

    def cache_path(self, key):
        identity = hashlib.sha256(json.dumps(key, separators=(',', ':')).encode('utf-8')).hexdigest()
        return self.cache_dir / f'weather-{identity}.json'

    def read_cached(self, key):
        if self.cache_dir is None:
            return None
        try:
            with self.cache_path(key).open('rb') as source:
                content = source.read(2_000_001)
            if len(content) > 2_000_000:
                return None
            record = json.loads(content)
            if record.get('schemaVersion') != 1 or record.get('key') != list(key) or type(record.get('failed')) is not bool:
                return None
            expires = datetime.fromisoformat(record['expiresAt'])
            fetched_at = datetime.fromisoformat(record['fetchedAt']) if record.get('fetchedAt') else None
            now = self.clock().astimezone(timezone.utc)
            if expires.tzinfo is None or expires > now + timedelta(hours=1, minutes=1):
                return None
            if fetched_at is not None and (fetched_at.tzinfo is None or fetched_at > now + timedelta(minutes=1)):
                return None
            if not record['failed'] and (fetched_at is None or expires > fetched_at + timedelta(hours=1, minutes=1)):
                return None
            stored = record['samples']
            if not isinstance(stored, list) or any(not isinstance(sample, dict) for sample in stored):
                return None
            packet = {'utc_offset_seconds': 0, 'hourly_units': {'wind_speed_10m': 'kn'}, 'hourly': {
                'time': [sample['time'] for sample in stored], 'wind_speed_10m': [sample['value'] for sample in stored],
                'wind_direction_10m': [sample['directionDegrees'] for sample in stored]}}
            samples = self.decode(packet)
            if len(samples) != len(stored):
                return None
            return {'samples': samples, 'fetchedAt': record.get('fetchedAt'), 'expires': expires,
                    'failed': record['failed'], 'stale': record['failed']}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
            return None

    def write_cached(self, key, cached):
        if self.cache_dir is None:
            return
        temporary = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            record = {'schemaVersion': 1, 'key': list(key), 'fetchedAt': cached['fetchedAt'],
                      'expiresAt': cached['expires'].isoformat(timespec='seconds'),
                      'failed': cached['failed'], 'samples': cached['samples']}
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.cache_dir, suffix='.tmp', delete=False) as target:
                temporary = Path(target.name)
                json.dump(record, target, ensure_ascii=False, allow_nan=False)
            os.replace(temporary, self.cache_path(key))
        except (OSError, ValueError):
            logging.getLogger(__name__).warning('Wettercache konnte nicht gespeichert werden; Daten bleiben im Arbeitsspeicher.')
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def metadata(self):
        today = self.clock().astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        return {'id': self.id, 'label': self.label, 'presentation': self.presentation, 'unit': 'kn',
            'quickToggle': True, 'icon': 'wind',
            'intervalMinutes': self.interval_minutes, 'source': self.source,
                 'window': {'from': (today - timedelta(days=PAST_DAYS)).isoformat(timespec='minutes'),
                     'to': (today + timedelta(days=FORECAST_DAYS)).isoformat(timespec='minutes')}}

    def decode(self, packet):
        if packet.get('utc_offset_seconds') != 0 or packet.get('hourly_units', {}).get('wind_speed_10m') != 'kn':
            raise ValueError('Unerwartete Zeitzone oder Windeinheit.')
        hourly = packet.get('hourly', {})
        times, speeds, directions = (hourly.get(field) for field in ('time', 'wind_speed_10m', 'wind_direction_10m'))
        if any(not isinstance(values, list) for values in (times, speeds, directions)) or not len(times) == len(speeds) == len(directions):
            raise ValueError('Unvollstaendige Wetterantwort.')
        samples = []
        for stamp, speed, direction in zip(times, speeds, directions):
            time = datetime.fromisoformat(stamp)
            if time.tzinfo is not None or time.minute or time.second or time.hour % 3:
                continue
            if speed is None or direction is None:
                continue
            if not finite_number(speed) or not finite_number(direction) or speed < 0 or not 0 <= direction <= 360:
                continue
            samples.append({'time': time.isoformat(timespec='minutes'), 'value': round(speed, 1), 'unit': 'kn',
                            'directionDegrees': direction % 360, 'rotationDegrees': (direction + 180) % 360})
        return sorted(samples, key=lambda item: item['time'])

    def track(self, port, start, end):
        result = {**self.metadata(), 'status': 'ready', 'samples': [], 'periods': []}
        settings = port.get('plugins', {}).get(self.id, {})
        result['warningWindKnots'] = settings.get('warningWindKnots')
        if settings.get('enabled', True) is False:
            return {**result, 'status': 'disabled'}
        coordinates = port.get('coordinates')
        if coordinates is None:
            return {**result, 'status': 'unconfigured', 'message': 'Hafenkoordinaten fehlen.'}
        validate_coordinates(coordinates)
        self.validate_config(settings)
        now = self.clock().astimezone(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        window_start, window_end = today - timedelta(days=PAST_DAYS), today + timedelta(days=FORECAST_DAYS)
        result.update(requestedFrom=window_start.isoformat(timespec='minutes'), requestedTo=window_end.isoformat(timespec='minutes'))
        if end <= window_start or start >= window_end:
            return {**result, 'status': 'out-of-range', 'message': 'Ausserhalb des Wetterzeitraums.'}
        key = (float(coordinates['latitude']), float(coordinates['longitude']), PAST_DAYS, FORECAST_DAYS)
        with self.lock:
            cached = deepcopy(self.cache.get(key))
        if cached is None or now >= cached['expires']:
            with self.fetch_lock:
                now = self.clock().astimezone(timezone.utc)
                with self.lock:
                    cached = deepcopy(self.cache.get(key))
                if cached is None:
                    cached = self.read_cached(key)
                if cached is None or now >= cached['expires']:
                    try:
                        samples = self.decode(self.fetcher(coordinates['latitude'], coordinates['longitude']))
                        cached = {'samples': samples, 'fetchedAt': now.isoformat(timespec='seconds'),
                                  'expires': self.clock().astimezone(timezone.utc) + timedelta(hours=1), 'stale': False, 'failed': False}
                    except (OSError, ValueError, KeyError, TypeError, OverflowError):
                        cached = {**(cached or {'samples': [], 'fetchedAt': None}),
                                  'expires': self.clock().astimezone(timezone.utc) + timedelta(minutes=5), 'stale': True, 'failed': True}
                    self.write_cached(key, cached)
                with self.lock:
                    if key not in self.cache and len(self.cache) >= 128:
                        self.cache.pop(next(iter(self.cache)))
                    self.cache[key] = deepcopy(cached)
        samples = cached['samples']
        if samples:
            result.update(availableFrom=samples[0]['time'], availableTo=samples[-1]['time'])
        result['fetchedAt'] = cached['fetchedAt']
        result['refreshAfterSeconds'] = max(1, int((cached['expires'] - self.clock().astimezone(timezone.utc)).total_seconds()))
        if cached.get('failed'):
            result.update(status='stale' if samples else 'error', message='Wetterabruf fehlgeschlagen. Letzter Datenstand.' if samples else 'Wetterdaten derzeit nicht verfuegbar.')
        elif not samples:
            result.update(status='empty', message='Keine Windwerte geliefert.')
        threshold = settings.get('warningWindKnots')
        for sample in samples:
            time = datetime.fromisoformat(sample['time'])
            warning = threshold is not None and sample['value'] >= threshold
            period_start = max(time, start, window_start)
            period_end = min(time + timedelta(minutes=self.interval_minutes), end, window_end)
            if warning and period_start < period_end:
                first, last = period_start.isoformat(timespec='minutes'), period_end.isoformat(timespec='minutes')
                periods = result['periods']
                if periods and periods[-1]['end'] == first:
                    periods[-1]['end'] = last
                    periods[-1]['maxWindKnots'] = max(periods[-1]['maxWindKnots'], sample['value'])
                else:
                    periods.append({'start': first, 'end': last, 'state': 'warning', 'maxWindKnots': sample['value']})
            if not max(start, window_start) <= time < min(end, window_end):
                continue
            result['samples'].append({**sample, 'state': 'warning' if warning else 'normal', 'priority': sample['value'],
                'label': f"{sample['value']:g} kn, Wind aus {sample['directionDegrees']:g} Grad" + (f', Warnschwelle {threshold:g} kn' if warning else '')})
        for period in result['periods']:
            period['label'] = f"Kritischer Wind: maximal {period['maxWindKnots']:g} kn, Warnschwelle {threshold:g} kn (3-Stunden-Raster)"
        return result



Plugin = WeatherPlugin
