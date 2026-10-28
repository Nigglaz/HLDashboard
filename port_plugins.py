from plugin_runtime import discover_plugins
from plugin_api import finite_number, valid_plugin_url, validate_coordinates, plugin_locations
import json
import logging
import re
from copy import deepcopy


def validate_port_extensions(payload, original=None, validators=None):
    coordinates = deepcopy(payload.get('coordinates', (original or {}).get('coordinates')))
    validate_coordinates(coordinates)
    if validators is None:
        loaded, _ = discover_plugins()
        validators = {identity: getattr(item['instance'], 'validate_config', lambda settings: None) for identity, item in loaded.items()}
    settings = deepcopy(payload.get('plugins', (original or {}).get('plugins', {})))
    if not isinstance(settings, dict) or any(not isinstance(value, dict) for value in settings.values()):
        raise ValueError('Plugin-Einstellungen muessen als Objekt angegeben werden.')
    for identity, config in settings.items():
        if not isinstance(identity, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', identity) or type(config.get('enabled', True)) is not bool:
            raise ValueError('Plugin-ID und Aktivierung muessen gueltig sein.')
        if identity in validators:
            try:
                validators[identity](config)
            except ValueError:
                raise
            except Exception as error:
                raise ValueError(f'Plugin {identity}: Konfiguration kann derzeit nicht geprueft werden.') from error
    locations = payload.get('pluginLocations', (original or {}).get('pluginLocations'))
    if 'pluginLocations' in payload or 'pluginLocations' in (original or {}):
        if not isinstance(locations, list) or len(locations) > 256:
            raise ValueError('Maximal 16 Standorte je Plugin und Hafen sind erlaubt.')
        identities = set()
        counts = {}
        for location in locations:
            if not isinstance(location, dict) or not isinstance(location.get('id'), str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', location['id']) or location['id'] in identities:
                raise ValueError('Plugin-Standort-IDs muessen gueltig und eindeutig sein.')
            identities.add(location['id'])
            ignored = location.get('ignoredPlugins', [])
            if not isinstance(ignored, list) or any(not isinstance(identity, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', identity) for identity in ignored):
                raise ValueError('Ungueltige Plugin-Migrationszuordnung.')
            if not isinstance(location.get('name'), str) or not location['name'].strip() or len(location['name']) > 120:
                raise ValueError('Jeder Plugin-Standort benoetigt einen Namen (maximal 120 Zeichen).')
            if not valid_plugin_url(location.get('url', '')):
                raise ValueError('Standort-Link muss eine HTTPS-Adresse ohne Zugangsdaten sein oder leer bleiben.')
            if location.get('coordinates') is None:
                raise ValueError('Jeder Plugin-Standort benoetigt Koordinaten.')
            local_settings = location.get('plugins', {})
            if not isinstance(local_settings, dict) or any(not isinstance(value, dict) or type(value.get('enabled', True)) is not bool for value in local_settings.values()):
                raise ValueError('Die Standortauswahl je Plugin muss wahr oder falsch sein.')
            plugin = location.get('plugin')
            if plugin is not None and (not isinstance(plugin, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', plugin)):
                raise ValueError('Ungueltige Standort-Plugin-ID.')
            if plugin is not None:
                if any(config.get('enabled', False) for identity, config in local_settings.items() if identity != plugin):
                    raise ValueError('Ein getrennter Standort darf nur sein eigenes Plugin aktivieren.')
            for identity in ([plugin] if plugin is not None else set(local_settings) | set(validators)):
                counts[identity] = counts.get(identity, 0) + 1
            if any(count > 16 for count in counts.values()):
                raise ValueError('Maximal 16 Standorte je Plugin und Hafen sind erlaubt.')
            validate_port_extensions({'coordinates': location['coordinates'], 'plugins': local_settings}, validators=validators)
    return coordinates, settings


class PortPluginRegistry:
    def __init__(self, plugins=None, cache_dir=None, plugin_root=None, legacy_cache_dir=None):
        self.loaded, self.diagnostics = {}, []
        if plugins is None:
            self.loaded, self.diagnostics = discover_plugins(plugin_root, cache_dir=cache_dir, legacy_cache_dir=legacy_cache_dir)
            plugins = [item['instance'] for item in self.loaded.values()]
        self.plugins = {plugin.id: plugin for plugin in plugins}

    def metadata(self):
        metadata = []
        for identity, plugin in self.plugins.items():
            try:
                item = dict(plugin.metadata())
                if identity in self.loaded:
                    item['assets'] = {key: f'/plugin-assets/{identity}/{self.loaded[identity]["manifest"][key]}' for key in ('frontend', 'settings', 'style')}
                json.dumps(item, allow_nan=False)
                metadata.append(item)
            except Exception:
                logging.getLogger(__name__).warning('Metadaten von Plugin %s nicht verfuegbar.', identity)
        return {'schemaVersion': 1, 'plugins': metadata, 'diagnostics': self.diagnostics}

    def validators(self):
        return {identity: getattr(plugin, 'validate_config', lambda settings: None) for identity, plugin in self.plugins.items()}

    def series(self, port, start, end, plugin_ids):
        tracks = []
        for identity, plugin in self.plugins.items():
            if identity not in plugin_ids:
                continue
            try:
                metadata = dict(plugin.metadata())
                locations = plugin.locations(port) if callable(getattr(type(plugin), 'locations', None)) else plugin_locations(port)
            except Exception:
                continue
            default_location_enabled = not metadata.get('locationOptIn', False)
            for location in locations:
                if location.get('plugin') not in (None, identity) or identity in location.get('ignoredPlugins', []):
                    continue
                local_settings = location.get('plugins', {}).get(identity, {})
                if local_settings.get('enabled', default_location_enabled) is False:
                    continue
                settings = {**port.get('plugins', {}).get(identity, {}), **local_settings}
                settings['enabled'] = port.get('plugins', {}).get(identity, {}).get('enabled', True) and local_settings.get('enabled', default_location_enabled)
                local_port = {**port, 'coordinates': location.get('coordinates'),
                              'plugins': {**port.get('plugins', {}), identity: settings}}
                try:
                    track = plugin.track(local_port, start, end)
                    if not isinstance(track, dict) or track.get('id', identity) != identity or not isinstance(track.get('samples'), list):
                        raise ValueError('Ungueltiger Plugin-Track.')
                    json.dumps(track, allow_nan=False)
                except Exception:
                    track = {**metadata, 'status': 'error', 'message': 'Plugin-Daten nicht verfuegbar.', 'samples': []}
                link = local_settings.get('url') or location.get('url', '')
                tracks.append({**metadata, **track, 'locationId': location['id'], 'locationName': location['name'],
                               'url': link if valid_plugin_url(link) else ''})
        return {'schemaVersion': 1, 'portId': port['id'], 'timeBasis': 'UTC', 'tracks': tracks}