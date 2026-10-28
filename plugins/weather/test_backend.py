import unittest
import tempfile
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse
from pathlib import Path
from copy import deepcopy
from port_plugins import PortPluginRegistry, validate_port_extensions
from .backend import WeatherPlugin, fetch_open_meteo
from test_support import create_test_app

class WeatherTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
        self.start = datetime(2026, 10, 27)
        self.end = datetime(2026, 10, 28)
        self.port = {'id': 'test', 'coordinates': {'latitude': 53.5, 'longitude': 9.9},
                     'plugins': {'weather': {'enabled': True, 'warningWindKnots': 20}}}
        self.packet = {'utc_offset_seconds': 0, 'hourly_units': {'wind_speed_10m': 'kn'}, 'hourly': {
            'time': ['2026-10-27T00:00', '2026-10-27T01:00', '2026-10-27T03:00', '2026-10-27T06:00'],
            'wind_speed_10m': [10, 11, 25, None], 'wind_direction_10m': [0, 90, 225, None]}}
        self.fetcher = Mock(return_value=self.packet)
        self.plugin = WeatherPlugin(self.fetcher, lambda: self.now)

    def test_three_hour_values_units_direction_and_warning_are_plugin_output(self):
        result = self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(result['intervalMinutes'], 180)
        self.assertEqual([item['value'] for item in result['samples']], [10, 25])
        self.assertEqual([item['state'] for item in result['samples']], ['normal', 'warning'])
        self.assertEqual([item['rotationDegrees'] for item in result['samples']], [180, 45])
        self.assertTrue(all(item['unit'] == 'kn' for item in result['samples']))

    def test_cache_avoids_refetch_and_retains_last_values_after_failure(self):
        self.plugin.track(self.port, self.start, self.end)
        self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(self.fetcher.call_count, 1)
        self.now += timedelta(minutes=61)
        self.fetcher.side_effect = OSError('offline')
        result = self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(result['status'], 'stale')
        self.assertEqual(len(result['samples']), 2)

    def test_weather_is_cached_for_one_hour_and_new_server_instance_refetches(self):
        first = self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(first['refreshAfterSeconds'], 3600)
        self.now += timedelta(minutes=59, seconds=59)
        remaining = self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(remaining['refreshAfterSeconds'], 1)
        self.assertEqual(self.fetcher.call_count, 1)
        self.now += timedelta(seconds=1)
        self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(self.fetcher.call_count, 2)
        restarted = WeatherPlugin(self.fetcher, lambda: self.now)
        restarted.track(self.port, self.start, self.end)
        self.assertEqual(self.fetcher.call_count, 3)

    def test_fetch_failure_waits_five_minutes_before_retrying(self):
        self.fetcher.side_effect = OSError('offline')
        self.plugin.track(self.port, self.start, self.end)
        self.now += timedelta(minutes=4, seconds=59)
        self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(self.fetcher.call_count, 1)
        self.now += timedelta(seconds=1)
        self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(self.fetcher.call_count, 2)

    def test_simultaneous_requests_share_one_external_fetch(self):
        entered, release = threading.Event(), threading.Event()

        def fetch(latitude, longitude):
            entered.set()
            if not release.wait(5):
                raise OSError('test release timeout')
            return self.packet

        self.fetcher.side_effect = fetch
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.plugin.track, self.port, self.start, self.end)
            try:
                self.assertTrue(entered.wait(5))
                second = pool.submit(self.plugin.track, self.port, self.start, self.end)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)['status'], 'ready')
            self.assertEqual(second.result(timeout=5)['status'], 'ready')
        self.assertEqual(self.fetcher.call_count, 1)

    def test_warning_periods_merge_adjacent_slots_but_not_missing_data(self):
        self.packet['hourly'] = {
            'time': ['2026-10-27T00:00', '2026-10-27T03:00', '2026-10-27T06:00', '2026-10-27T09:00', '2026-10-27T12:00', '2026-10-27T15:00'],
            'wind_speed_10m': [8, 25, 30, None, 26, 8],
            'wind_direction_10m': [90, 90, 90, None, 90, 90]}
        result = self.plugin.track(self.port, self.start, self.end)
        self.assertEqual([(period['start'], period['end']) for period in result['periods']],
                         [('2026-10-27T03:00', '2026-10-27T09:00'), ('2026-10-27T12:00', '2026-10-27T15:00')])
        self.assertEqual(result['periods'][0]['maxWindKnots'], 30)

    def test_warning_period_intersects_requested_window_even_if_sample_precedes_it(self):
        result = self.plugin.track(self.port, datetime(2026, 10, 27, 4), datetime(2026, 10, 27, 5))
        self.assertEqual(result['samples'], [])
        self.assertEqual([(period['start'], period['end']) for period in result['periods']],
                         [('2026-10-27T04:00', '2026-10-27T05:00')])

    def test_disabled_missing_coordinates_and_outside_window_do_not_fetch(self):
        self.port['plugins']['weather']['enabled'] = False
        self.assertEqual(self.plugin.track(self.port, self.start, self.end)['status'], 'disabled')
        self.assertEqual(self.plugin.track({'id': 'missing'}, self.start, self.end)['status'], 'unconfigured')
        self.port['plugins']['weather']['enabled'] = True
        result = self.plugin.track(self.port, datetime(2027, 1, 1), datetime(2027, 2, 1))
        self.assertEqual(result['status'], 'out-of-range')
        self.fetcher.assert_not_called()

    def test_invalid_units_and_network_failure_are_isolated(self):
        self.packet['hourly_units']['wind_speed_10m'] = 'km/h'
        result = self.plugin.track(self.port, self.start, self.end)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['samples'], [])

    def test_coordinate_validation_accepts_zero_and_rejects_invalid_values(self):
        validate_port_extensions({'coordinates': {'latitude': 0, 'longitude': 0}})
        for coordinates in ({'latitude': 91, 'longitude': 0}, {'latitude': 0}, {'latitude': True, 'longitude': 2}):
            with self.assertRaises(ValueError):
                validate_port_extensions({'coordinates': coordinates})

    def test_registry_supports_additional_value_plugins(self):
        tide = Mock()
        tide.id = 'tide'
        tide.metadata.return_value = {'id': 'tide', 'label': 'Tide', 'presentation': 'value', 'unit': 'm'}
        tide.track.return_value = {**tide.metadata(), 'status': 'ready', 'samples': []}
        registry = PortPluginRegistry([self.plugin, tide])
        result = registry.series(self.port, self.start, self.end, {'weather', 'tide'})
        self.assertEqual([item['id'] for item in result['tracks']], ['weather', 'tide'])
        self.assertEqual(registry.series(self.port, self.start, self.end, {'unknown'})['tracks'], [])

        tide.track.side_effect = RuntimeError('plugin bug')
        result = registry.series(self.port, self.start, self.end, {'weather', 'tide'})
        self.assertEqual([item['status'] for item in result['tracks']], ['ready', 'error'])

    def test_multiple_locations_keep_individual_links_and_disabled_locations_do_not_fetch(self):
        self.port['pluginLocations'] = [
            {'id': 'terminal', 'name': 'Hamburg', 'coordinates': {'latitude': 53.5264, 'longitude': 9.9175},
             'url': 'https://www.windy.com/?53.777,9.181,10', 'plugins': {'weather': {'enabled': True}}},
            {'id': 'river', 'name': 'Cuxhaven', 'coordinates': {'latitude': 53.873, 'longitude': 8.709},
             'url': 'https://www.windy.com/?53.873,8.709,10', 'plugins': {'weather': {'enabled': True}}}]
        registry = PortPluginRegistry([self.plugin])
        result = registry.series(self.port, self.start, self.end, {'weather'})
        self.assertEqual([track['locationName'] for track in result['tracks']], ['Hamburg', 'Cuxhaven'])
        self.assertEqual(result['tracks'][0]['url'], self.port['pluginLocations'][0]['url'])
        self.assertEqual(self.fetcher.call_count, 2)
        self.fetcher.reset_mock()
        self.port['pluginLocations'][1]['plugins']['weather']['enabled'] = False
        fresh = WeatherPlugin(self.fetcher, lambda: self.now)
        result = PortPluginRegistry([fresh]).series(self.port, self.start, self.end, {'weather'})
        self.assertEqual([track['locationId'] for track in result['tracks']], ['terminal'])
        self.assertEqual(self.fetcher.call_count, 1)

    def test_location_selection_is_independent_for_tide_and_weather(self):
        self.port['pluginLocations'] = [
            {'id': 'wind', 'name': 'Wind location', 'coordinates': self.port['coordinates'],
             'plugins': {'weather': {'enabled': True}, 'tide': {'enabled': False}}},
            {'id': 'tide', 'name': 'Tide location', 'coordinates': self.port['coordinates'],
             'plugins': {'weather': {'enabled': False}, 'tide': {'enabled': True}}}]
        tide = Mock()
        tide.id = 'tide'
        tide.track.return_value = {'id': 'tide', 'status': 'ready', 'samples': []}
        tide.metadata.return_value = {'id': 'tide', 'label': 'Tide', 'locationOptIn': True}
        result = PortPluginRegistry([self.plugin, tide]).series(self.port, self.start, self.end, {'weather', 'tide'})
        self.assertEqual([(track['id'], track['locationId']) for track in result['tracks']], [('weather', 'wind'), ('tide', 'tide')])

    def test_location_thresholds_produce_independent_warning_bands_with_shared_weather_cache(self):
        self.port['pluginLocations'] = [
            {'id': 'terminal', 'name': 'Hamburg', 'coordinates': self.port['coordinates'],
             'plugins': {'weather': {'enabled': True, 'warningWindKnots': 20}}},
            {'id': 'river', 'name': 'Cuxhaven', 'coordinates': self.port['coordinates'],
             'plugins': {'weather': {'enabled': True, 'warningWindKnots': 30}}}]
        registry = PortPluginRegistry([self.plugin])
        tracks = registry.series(self.port, self.start, self.end, {'weather'})['tracks']
        self.assertEqual([track['warningWindKnots'] for track in tracks], [20, 30])
        self.assertEqual([len(track['periods']) for track in tracks], [1, 0])
        self.assertEqual([track['samples'][1]['state'] for track in tracks], ['warning', 'normal'])
        self.assertEqual(self.fetcher.call_count, 1)
        self.port['pluginLocations'][0]['plugins']['weather']['warningWindKnots'] = None
        tracks = registry.series(self.port, self.start, self.end, {'weather'})['tracks']
        self.assertIsNone(tracks[0]['warningWindKnots'])
        self.assertEqual(tracks[0]['periods'], [])
        self.assertEqual(len(tracks[0]['samples']), 2)
        self.assertEqual(self.fetcher.call_count, 1)

    def test_location_validation_rejects_bad_links_duplicates_and_missing_coordinates(self):
        location = {'id': 'terminal', 'name': 'Test', 'coordinates': self.port['coordinates'], 'url': 'https://www.windy.com/?53.777,9.181,10'}
        validate_port_extensions({'pluginLocations': [location]})
        for bad_url in ['javascript:alert(1)', 'http://example.test/', 'https://user:password@example.test', '//example.test']:
            with self.subTest(url=bad_url), self.assertRaises(ValueError):
                validate_port_extensions({'pluginLocations': [{**location, 'url': bad_url}]})
        for locations in [None, [location, deepcopy(location)], [{**location, 'coordinates': None}]]:
            with self.assertRaises(ValueError):
                validate_port_extensions({'pluginLocations': locations})

    def test_separate_locations_allow_sixteen_per_plugin_and_reject_mixed_assignment(self):
        locations = [{'id': f'{plugin}-{index}', 'plugin': plugin, 'name': f'{plugin} {index}',
                      'coordinates': self.port['coordinates'],
                      'plugins': {'weather': {'enabled': plugin == 'weather'}, 'tide': {'enabled': plugin == 'tide'}}}
                     for plugin in ('weather', 'tide') for index in range(16)]
        validate_port_extensions({'pluginLocations': locations})
        with self.assertRaises(ValueError):
            validate_port_extensions({'pluginLocations': locations[:16] + [{**locations[0], 'id': 'weather-extra'}]})
        with self.assertRaises(ValueError):
            validate_port_extensions({'pluginLocations': [{**locations[0], 'plugin': '../invalid'}]})
        with self.assertRaises(ValueError):
            validate_port_extensions({'pluginLocations': [{**locations[0], 'plugins': {'weather': {'enabled': True}, 'tide': {'enabled': True}}}]})

    def test_api_keeps_unequal_separate_location_lists_and_disabled_tide_assignment(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_test_app(root)
            client = app.test_client()
            plan = client.get('/api/plan').get_json()
            port = plan['ports'][0]
            locations = [{'id': identity, 'plugin': plugin, 'name': name, 'url': url,
                          'coordinates': {'latitude': latitude, 'longitude': longitude},
                          'plugins': {'weather': {'enabled': plugin == 'weather', 'warningWindKnots': 25 if plugin == 'weather' else None},
                                      'tide': {'enabled': False}}}
                         for identity, plugin, name, url, latitude, longitude in [
                             ('wind-one', 'weather', 'Terminal', 'https://wind.example.test/', 53.5, 9.9),
                             ('wind-two', 'weather', 'Aussenelbe', '', 54, 8),
                             ('tide-one', 'tide', 'Pegel', 'https://tide.example.test/', 53.8, 8.7)]]
            response = client.put(f"/api/ports/{port['id']}", json={**port, 'dataSignature': plan['dataSignature'], 'pluginLocations': locations})
            self.assertEqual(response.status_code, 200)
            reloaded = client.get('/api/plan').get_json()
            self.assertEqual(next(item for item in reloaded['ports'] if item['id'] == port['id'])['pluginLocations'], locations)
            self.assertEqual(reloaded['ships'], plan['ships'])

    def test_api_persists_location_choices_and_preserves_ship_plans(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_test_app(root)
            client = app.test_client()
            plan = client.get('/api/plan').get_json()
            port = plan['ports'][0]
            locations = [
                {'id': 'terminal', 'name': 'Terminal', 'coordinates': self.port['coordinates'],
                 'url': 'https://www.windy.com/?53.5,9.9,10', 'plugins': {'weather': {'enabled': True}, 'tide': {'enabled': False}}},
                {'id': 'river', 'name': 'River', 'coordinates': {'latitude': 53.873, 'longitude': 8.709},
                 'url': 'https://www.windy.com/?53.873,8.709,10', 'plugins': {'weather': {'enabled': False}, 'tide': {'enabled': True}}}]
            response = client.put(f"/api/ports/{port['id']}", json={**port, 'dataSignature': plan['dataSignature'], 'pluginLocations': locations})
            self.assertEqual(response.status_code, 200)
            saved = response.get_json()
            updated = next(item for item in saved['ports'] if item['id'] == port['id'])
            self.assertEqual(updated['pluginLocations'], locations)
            self.assertEqual(saved['ships'], plan['ships'])
            app.extensions['port_plugins'].plugins['weather'] = self.plugin
            data = client.get(f"/api/ports/{port['id']}/plugins?start=2026-10-27&end=2026-10-28&plugins=weather").get_json()
            self.assertEqual([track['locationId'] for track in data['tracks']], ['terminal'])
            self.assertEqual(data['tracks'][0]['url'], locations[0]['url'])

    def test_commercial_api_uses_customer_endpoint_and_requested_units(self):
        with patch.dict('os.environ', {'OPEN_METEO_API_KEY': 'test-only-key'}), patch(f'{WeatherPlugin.__module__}.urlopen') as opener:
            opener.return_value.__enter__.return_value.read.return_value = json.dumps(self.packet).encode('utf-8')
            self.assertEqual(fetch_open_meteo(0, 0), self.packet)
        url = urlparse(opener.call_args.args[0].full_url)
        parameters = parse_qs(url.query)
        self.assertEqual(url.hostname, 'customer-api.open-meteo.com')
        self.assertEqual(parameters['wind_speed_unit'], ['kn'])
        self.assertEqual(parameters['past_days'], ['10'])
        self.assertEqual(parameters['forecast_days'], ['16'])
        self.assertEqual(parameters['apikey'], ['test-only-key'])

    def test_persistent_cache_survives_restart_until_original_expiry(self):
        with tempfile.TemporaryDirectory() as root:
            first = WeatherPlugin(self.fetcher, lambda: self.now, cache_dir=root)
            first.track(self.port, self.start, self.end)
            self.now += timedelta(minutes=30)
            restarted = WeatherPlugin(self.fetcher, lambda: self.now, cache_dir=root)
            result = restarted.track(self.port, self.start, self.end)
            self.assertEqual(self.fetcher.call_count, 1)
            self.assertEqual(result['refreshAfterSeconds'], 1800)
            self.assertEqual(result['status'], 'ready')
            record = json.loads(next(Path(root).glob('weather-*.json')).read_text(encoding='utf-8'))
            self.assertEqual(record['fetchedAt'], '2026-10-27T12:00:00+00:00')
            self.assertEqual(record['expiresAt'], '2026-10-27T13:00:00+00:00')
            self.now += timedelta(minutes=30)
            after_expiry = WeatherPlugin(self.fetcher, lambda: self.now, cache_dir=root)
            after_expiry.track(self.port, self.start, self.end)
            self.assertEqual(self.fetcher.call_count, 2)

    def test_corrupt_file_cache_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            first = WeatherPlugin(self.fetcher, lambda: self.now, cache_dir=root)
            first.track(self.port, self.start, self.end)
            next(Path(root).glob('weather-*.json')).write_text('{broken', encoding='utf-8')
            restarted = WeatherPlugin(self.fetcher, lambda: self.now, cache_dir=root)
            self.assertEqual(restarted.track(self.port, self.start, self.end)['status'], 'ready')
            self.assertEqual(self.fetcher.call_count, 2)

    def test_expired_disk_cache_remains_available_as_stale_when_provider_is_offline(self):
        with tempfile.TemporaryDirectory() as root:
            first = WeatherPlugin(self.fetcher, lambda: self.now, cache_dir=root)
            first.track(self.port, self.start, self.end)
            self.now += timedelta(minutes=61)
            self.fetcher.side_effect = OSError('offline')
            restarted = WeatherPlugin(self.fetcher, lambda: self.now, cache_dir=root)
            result = restarted.track(self.port, self.start, self.end)
            self.assertEqual(result['status'], 'stale')
            self.assertEqual(len(result['samples']), 2)
            self.assertEqual(result['refreshAfterSeconds'], 300)

    def test_midnight_and_restart_do_not_expire_a_fresh_cache_early(self):
        with tempfile.TemporaryDirectory() as root:
            self.now = datetime(2026, 10, 27, 23, 50, tzinfo=timezone.utc)
            first = WeatherPlugin(self.fetcher, lambda: self.now, cache_dir=root)
            first.track(self.port, self.start, self.end)
            self.now += timedelta(minutes=20)
            restarted = WeatherPlugin(self.fetcher, lambda: self.now, cache_dir=root)
            result = restarted.track(self.port, self.start, self.end)
            self.assertEqual(result['status'], 'ready')
            self.assertEqual(result['refreshAfterSeconds'], 2400)
            self.assertEqual(self.fetcher.call_count, 1)

    def test_forecast_window_reaches_provider_maximum_without_eager_fetch(self):
        metadata = self.plugin.metadata()
        self.assertEqual(metadata['window']['from'], '2026-10-17T00:00')
        self.assertEqual(metadata['window']['to'], '2026-11-12T00:00')
        self.fetcher.assert_not_called()

    def test_api_settings_and_series_do_not_mutate_planning_data(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_test_app(root)
            client = app.test_client()
            plan = client.get('/api/plan').get_json()
            port = plan['ports'][0]
            payload = {**port, 'dataSignature': plan['dataSignature'], 'coordinates': self.port['coordinates'],
                       'plugins': self.port['plugins']}
            updated = client.put(f"/api/ports/{port['id']}", json=payload)
            self.assertEqual(updated.status_code, 200)
            saved = updated.get_json()
            app.extensions['port_plugins'].plugins['weather'] = self.plugin
            response = client.get(f"/api/ports/{port['id']}/plugins?start=2026-10-27&end=2026-10-28&plugins=weather")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.get_json()['tracks'][0]['samples']), 2)
            self.assertEqual(client.get('/api/plan').get_json(), saved)
            self.assertEqual(client.get('/api/port-plugins').get_json()['schemaVersion'], 1)
            self.assertEqual(client.get(f"/api/ports/{port['id']}/plugins?start=bad&end=2026-10-28").status_code, 400)
            self.assertEqual(client.get(f"/api/ports/{port['id']}/plugins?start=2026-10-27&end=2026-10-28&plugins=unknown").get_json()['tracks'], [])


if __name__ == '__main__':
    unittest.main()