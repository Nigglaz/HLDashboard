from math import isfinite
from urllib.parse import urlsplit


def finite_number(value):
    return type(value) in (int, float) and isfinite(value)


def validate_coordinates(coordinates):
    if coordinates is None:
        return
    if not isinstance(coordinates, dict) or not finite_number(coordinates.get('latitude')) or not finite_number(coordinates.get('longitude')):
        raise ValueError('Breiten- und Laengengrad muessen gemeinsam als endliche Zahlen angegeben werden.')
    if not -90 <= coordinates['latitude'] <= 90 or not -180 <= coordinates['longitude'] <= 180:
        raise ValueError('Koordinaten liegen ausserhalb des gueltigen Bereichs.')


def valid_plugin_url(value):
    if value == '':
        return True
    if not isinstance(value, str) or len(value) > 2048 or any(character.isspace() or ord(character) < 32 for character in value):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme == 'https' and bool(parsed.hostname) and parsed.username is None and parsed.password is None
    except ValueError:
        return False


def plugin_locations(port):
    if 'pluginLocations' in port:
        return port['pluginLocations']
    return [{'id': 'terminal', 'name': port.get('name', port['id']),
             'coordinates': port.get('coordinates'), 'url': '', 'plugins': {}}]