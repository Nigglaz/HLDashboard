import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import json
import ssl
from urllib.parse import parse_qs, urlparse

from .backend import TidePlugin, fetch_bsh_levels
from port_plugins import validate_port_extensions
from test_support import create_test_app


class TideTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
        self.start, self.end = datetime(2026, 10, 28), datetime(2026, 10, 29)
        self.port = {'id': 'test', 'coordinates': {'latitude': 53.873, 'longitude': 8.709},
                     'plugins': {'tide': {'enabled': True, 'stationId': 'cuxhaven_steubenhoeft'}}}
        self.packet = {'type': 'Feature', 'id': 'cuxhaven_steubenhoeft', 'properties': {'high_water_low_water': [
            {'event_timestamp': '2026-10-28T03:00:00+01:00', 'event': 'HW', 'tidal_prediction_value': '680'},
            {'event_timestamp': '2026-10-28T07:00:00+01:00', 'event': 'NW', 'tidal_prediction_value': '350'},
            {'event_timestamp': '2026-10-28T11:00:00+01:00', 'event': 'HW', 'tidal_prediction_value': '670'}]}}
        self.fetcher = Mock(return_value=self.packet)
        self.plugin = TidePlugin(self.fetcher, lambda: self.now)

    def test_returns_high_and_low_times_without_absolute_heights(self):
        result = self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(result['presentation'], 'tide')
        self.assertEqual([(point['time'], point['kind'], point['value']) for point in result['samples']],
                         [('2026-10-28T02:00', 'high', 1), ('2026-10-28T06:00', 'low', -1), ('2026-10-28T10:00', 'high', 1)])
        self.assertTrue(result['relative'])

    def test_gaps_have_separate_segments_and_no_invented_end_extrema(self):
        self.packet['properties']['high_water_low_water'][1]['event_timestamp'] = '2026-10-29T07:00:00+01:00'
        self.packet['properties']['high_water_low_water'][2]['event_timestamp'] = '2026-10-29T11:00:00+01:00'
        events = self.plugin.decode(self.packet)
        self.assertNotEqual(events[0]['segmentId'], events[-1]['segmentId'])
        self.assertFalse(any(point['time'].endswith(('00:00', '12:00')) for point in events))

    def test_missing_timezone_and_wrong_station_are_rejected(self):
        self.packet['properties']['high_water_low_water'][0]['event_timestamp'] = '2026-10-28T03:00'
        with self.assertRaises(ValueError):
            self.plugin.decode(self.packet)
        self.packet['id'] = 'other_station'
        self.assertEqual(self.plugin.track(self.port, self.start, self.end)['status'], 'error')

    def test_restart_uses_valid_file_cache_and_failed_refresh_keeps_stale_events(self):
        with tempfile.TemporaryDirectory() as root:
            first = TidePlugin(self.fetcher, lambda: self.now, cache_dir=root)
            first.track(self.port, self.start, self.end)
            restarted = TidePlugin(self.fetcher, lambda: self.now, cache_dir=root)
            self.assertEqual(restarted.track(self.port, self.start, self.end)['status'], 'ready')
            self.assertEqual(self.fetcher.call_count, 1)
            self.now += timedelta(minutes=61)
            self.fetcher.side_effect = OSError('offline')
            self.assertEqual(restarted.track(self.port, self.start, self.end)['status'], 'stale')

    def test_disabled_and_outside_window_do_not_fetch(self):
        self.assertEqual(self.plugin.track({**self.port, 'plugins': {}}, self.start, self.end)['status'], 'disabled')
        self.assertEqual(self.plugin.track(self.port, datetime(2030, 1, 1), datetime(2030, 2, 1))['status'], 'out-of-range')
        self.fetcher.assert_not_called()

    def test_constant_or_missing_data_do_not_invent_extrema(self):
        self.packet['properties']['high_water_low_water'] = []
        self.assertEqual(self.plugin.track(self.port, self.start, self.end)['status'], 'empty')
        with self.assertRaises(ValueError):
            self.plugin.decode({**self.packet, 'properties': {}})

    def test_tide_link_is_validated_and_does_not_replace_weather_link(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_test_app(root)
            client = app.test_client()
            plan = client.get('/api/plan').get_json()
            port = plan['ports'][0]
            location = {'id': 'tide-only', 'name': 'Elbe entrance', 'coordinates': self.port['coordinates'],
                        'url': 'https://www.windy.com/', 'plugins': {'weather': {'enabled': False},
                        'tide': {'enabled': True, 'stationId': 'cuxhaven_steubenhoeft', 'url': 'https://www.bsh.de/'}}}
            response = client.put(f"/api/ports/{port['id']}", json={**port, 'dataSignature': plan['dataSignature'], 'pluginLocations': [location]})
            self.assertEqual(response.status_code, 200)
            app.extensions['port_plugins'].plugins['tide'] = self.plugin
            data = client.get(f"/api/ports/{port['id']}/plugins?start=2026-10-28&end=2026-10-29&plugins=weather,tide").get_json()
            self.assertEqual([(track['id'], track['locationName']) for track in data['tracks']], [('tide', 'Elbe entrance')])
            self.assertEqual(data['tracks'][0]['url'], 'https://www.bsh.de/')
            self.assertEqual(len(data['tracks'][0]['samples']), 3)
            self.assertEqual(data['tracks'][0]['stationId'], 'cuxhaven_steubenhoeft')
            reloaded = client.get('/api/plan').get_json()
            self.assertEqual(next(item for item in reloaded['ports'] if item['id'] == port['id'])['pluginLocations'][0]['plugins']['tide']['stationId'], 'cuxhaven_steubenhoeft')
            self.assertEqual(client.get('/api/plan').get_json()['ships'], plan['ships'])
        with self.assertRaises(ValueError):
            validate_port_extensions({'plugins': {'tide': {'url': 'javascript:alert(1)'}}})

    def test_provider_uses_bsh_without_commercial_key_or_coordinate_guessing(self):
        with patch.dict('os.environ', {'OPEN_METEO_API_KEY': 'test-only-key'}), patch(f'{TidePlugin.__module__}.urlopen') as opener:
            opener.return_value.__enter__.return_value.read.return_value = json.dumps(self.packet).encode('utf-8')
            self.assertEqual(fetch_bsh_levels('cuxhaven_steubenhoeft'), self.packet)
        url = urlparse(opener.call_args.args[0].full_url)
        parameters = parse_qs(url.query)
        self.assertEqual(url.hostname, 'gdi.bsh.de')
        self.assertTrue(url.path.endswith('/cuxhaven_steubenhoeft'))
        self.assertEqual(parameters, {'f': ['json']})
        self.assertEqual(opener.call_args.kwargs['context'].verify_mode, ssl.CERT_REQUIRED)
        with self.assertRaises(ValueError):
            fetch_bsh_levels('../other-host')

    def test_unassigned_station_does_not_fetch_and_shared_station_reuses_cache(self):
        self.assertEqual(self.plugin.track({**self.port, 'plugins': {'tide': {'enabled': True}}}, self.start, self.end)['status'], 'unconfigured')
        self.fetcher.assert_not_called()
        self.plugin.track(self.port, self.start, self.end)
        self.plugin.track({**self.port, 'coordinates': {'latitude': 54, 'longitude': 8}}, self.start, self.end)
        self.fetcher.assert_called_once_with('cuxhaven_steubenhoeft')

    def test_old_marine_cache_cannot_be_relabelled_as_bsh(self):
        with tempfile.TemporaryDirectory() as root:
            plugin = TidePlugin(self.fetcher, lambda: self.now, cache_dir=root)
            plugin.write_cached((53.873, 8.709, 10, 8, 'marine-hourly-extrema-v1'), {
                'events': [{'time': '2026-10-28T01:00', 'kind': 'high', 'value': 1, 'segmentId': 0}],
                'fetchedAt': self.now.isoformat(), 'expires': self.now + timedelta(hours=1), 'failed': False})
            result = plugin.track(self.port, self.start, self.end)
            self.fetcher.assert_called_once_with('cuxhaven_steubenhoeft')
            self.assertEqual(result['samples'][0]['time'], '2026-10-28T02:00')
            self.assertEqual(result['source']['name'], 'BSH')

    def test_station_validation_and_missing_tide_events(self):
        for invalid in [True, 123, '../cuxhaven', 'https://other.example.test/', 'Hamburg St. Pauli']:
            with self.subTest(station=invalid), self.assertRaises(ValueError):
                validate_port_extensions({'plugins': {'tide': {'stationId': invalid}}})
        self.packet['properties']['high_water_low_water'].pop(1)
        events = self.plugin.decode(self.packet)
        self.assertNotEqual(events[0]['segmentId'], events[1]['segmentId'])


if __name__ == '__main__':
    unittest.main()