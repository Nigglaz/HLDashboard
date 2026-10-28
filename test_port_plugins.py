import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from flask.testing import FlaskClient
from port_plugins import PortPluginRegistry, validate_port_extensions
from plugin_runtime import discover_plugins
from test_support import create_test_app

class PluginLoaderTests(unittest.TestCase):
    def test_empty_missing_and_broken_plugin_directories_do_not_break_startup(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(discover_plugins(root), ({}, []))
            folder = Path(root) / 'broken'
            folder.mkdir()
            for version in ('999', 'true'):
                (folder / 'plugin.toml').write_text(f'id = "broken"\napi_version = {version}\n', encoding='utf-8')
                loaded, diagnostics = discover_plugins(root)
                self.assertEqual(loaded, {})
                self.assertEqual(diagnostics[0], {'plugin': 'broken', 'error': 'ValueError'})
            (folder / 'plugin.toml').unlink()
            self.assertEqual(discover_plugins(root), ({}, []))

    def test_manifest_discovers_backend_without_fixed_imports(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'example'
            folder.mkdir()
            (folder / 'plugin.toml').write_text('id = "example"\napi_version = 1\nbackend = "backend.py"\nfrontend = "frontend.js"\nsettings = "settings.html"\nstyle = "style.css"\n', encoding='utf-8')
            (folder / 'backend.py').write_text('class Plugin:\n    def __init__(self, cache_dir=None, clock=None): self.cache_dir, self.clock = cache_dir, clock\n    def metadata(self): return {"id": "example", "label": "Example"}\n    def track(self, port, start, end): return {"status": "empty", "samples": []}\n', encoding='utf-8')
            for name in ('frontend.js', 'settings.html', 'style.css'):
                (folder / name).write_text('', encoding='utf-8')
            legacy = Path(root) / 'legacy-cache'
            legacy.mkdir()
            (legacy / 'example-old.json').write_text('{"saved":42}', encoding='utf-8')
            loaded, diagnostics = discover_plugins(root, cache_dir=Path(root) / 'cache', legacy_cache_dir=legacy)
            self.assertEqual(list(loaded), ['example'])
            self.assertEqual(diagnostics, [])
            self.assertEqual(loaded['example']['instance'].metadata()['label'], 'Example')
            self.assertEqual(loaded['example']['instance'].cache_dir, Path(root) / 'cache' / 'example')
            self.assertEqual(loaded['example']['instance'].clock().utcoffset().total_seconds(), 0)
            self.assertEqual((Path(root) / 'cache' / 'example' / 'example-old.json').read_text(encoding='utf-8'), '{"saved":42}')


class PluginIntegrationTests(unittest.TestCase):
    def test_application_works_without_plugins_or_with_either_builtin_package(self):
        source = Path(__file__).parent / 'plugins'
        for installed in ((), ('weather',), ('tide',), ('weather', 'tide')):
            if any(not (source / identity).is_dir() for identity in installed):
                continue
            with self.subTest(installed=installed), tempfile.TemporaryDirectory() as root:
                root = Path(root)
                packages = root / 'packages'
                packages.mkdir()
                data = root / 'data'
                data.mkdir()
                for identity in installed:
                    shutil.copytree(source / identity, packages / identity)
                app = create_test_app(data, plugin_root=packages)
                client = app.test_client()
                metadata = client.get('/api/port-plugins').get_json()
                self.assertEqual({plugin['id'] for plugin in metadata['plugins']}, set(installed))
                self.assertEqual(client.get('/').status_code, 200)
                plan = client.get('/api/plan').get_json()
                port = plan['ports'][0]
                response = client.get(f"/api/ports/{port['id']}/plugins?start=2030-01-01&end=2030-01-02&plugins=weather,tide,removed")
                self.assertEqual(response.status_code, 200)
                for plugin in metadata['plugins']:
                    for asset in plugin['assets'].values():
                        with client.get(asset) as response:
                            self.assertEqual(response.status_code, 200)
                    self.assertEqual(client.get(f"/plugin-assets/{plugin['id']}/backend.py").status_code, 404)
                    self.assertEqual(client.get(f"/plugin-assets/{plugin['id']}/plugin.toml").status_code, 404)
                    self.assertEqual(client.get(f"/plugin-assets/{plugin['id']}/../../static/app.js").status_code, 404)
                    self.assertEqual(FlaskClient(app).get(plugin['assets']['frontend']).status_code, 302)

    def test_removing_package_preserves_orphan_configuration_and_does_not_import_it(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            packages = root / 'packages'
            packages.mkdir()
            data = root / 'data'
            data.mkdir()
            app = create_test_app(data, plugin_root=packages)
            client = app.test_client()
            plan = client.get('/api/plan').get_json()
            port = plan['ports'][0]
            location = {'id': 'removed-site', 'plugin': 'removed', 'name': 'Still saved', 'url': 'https://example.test/',
                        'coordinates': {'latitude': 53, 'longitude': 9}, 'plugins': {'removed': {'enabled': True, 'custom': {'value': 42}}}}
            response = client.put(f"/api/ports/{port['id']}", json={**port, 'dataSignature': plan['dataSignature'], 'pluginLocations': [location], 'plugins': {'removed': {'enabled': True, 'custom': 7}}})
            self.assertEqual(response.status_code, 200)
            restored = client.get('/api/plan').get_json()
            saved_port = next(item for item in restored['ports'] if item['id'] == port['id'])
            self.assertEqual(saved_port['pluginLocations'], [location])
            self.assertEqual(saved_port['plugins']['removed']['custom'], 7)
            self.assertEqual(restored['ships'], plan['ships'])
            self.assertEqual(client.get('/api/port-plugins').get_json()['plugins'], [])
            self.assertEqual(client.get('/plugin-assets/removed/frontend.js').status_code, 404)

    def test_backend_and_metadata_errors_are_isolated_and_validator_errors_are_reported(self):
        broken = Mock()
        broken.id = 'broken'
        broken.metadata.side_effect = RuntimeError('broken metadata')
        registry = PortPluginRegistry([broken])
        self.assertEqual(registry.metadata()['plugins'], [])
        self.assertEqual(registry.series({'id': 'test'}, datetime(2026, 1, 1), datetime(2026, 1, 2), {'broken'})['tracks'], [])
        with self.assertRaisesRegex(ValueError, 'broken'):
            validate_port_extensions({'plugins': {'broken': {}}}, validators={'broken': Mock(side_effect=RuntimeError('broken validation'))})


if __name__ == '__main__':
    unittest.main()