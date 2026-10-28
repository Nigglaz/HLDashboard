import hashlib
import importlib.util
import json
import logging
import re
import sys
import tomllib
import shutil
from pathlib import Path
from datetime import datetime, timezone


API_VERSION = 1
PLUGIN_ROOT = Path(__file__).parent / 'plugins'


def plugin_file(folder, name):
    if not isinstance(name, str) or not name:
        raise ValueError('Plugin-Dateiname fehlt.')
    path = (folder / name).resolve()
    if not path.is_relative_to(folder.resolve()) or not path.is_file():
        raise ValueError('Plugin-Datei fehlt oder liegt ausserhalb des Pakets.')
    return path


def discover_plugins(root=None, cache_dir=None, legacy_cache_dir=None):
    loaded, diagnostics = {}, []
    root = Path(root) if root is not None else PLUGIN_ROOT
    for manifest_path in sorted(root.glob('*/plugin.toml')):
        identity = manifest_path.parent.name
        try:
            manifest = tomllib.loads(manifest_path.read_text(encoding='utf-8'))
            identity = manifest['id']
            if not isinstance(identity, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', identity):
                raise ValueError('Ungueltige Plugin-ID.')
            if type(manifest.get('api_version')) is not int or manifest.get('api_version') != API_VERSION or identity in loaded:
                raise ValueError('Schnittstellenversion oder doppelte Plugin-ID.')
            if type(manifest.get('order', 100)) is not int:
                raise ValueError('Plugin-Reihenfolge muss ganzzahlig sein.')
            folder = manifest_path.parent
            files = {key: plugin_file(folder, manifest[key]) for key in ('backend', 'frontend', 'settings', 'style')}
            suffix = hashlib.sha256(str(folder.resolve()).encode()).hexdigest()[:16]
            name = f'_phoca_plugin_{identity}_{suffix}'
            spec = importlib.util.spec_from_file_location(name, files['backend'], submodule_search_locations=[str(folder)])
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            try:
                spec.loader.exec_module(module)
                private_cache = Path(cache_dir) / identity if cache_dir is not None else None
                if private_cache is not None and legacy_cache_dir is not None:
                    try:
                        for previous in Path(legacy_cache_dir).glob(f'{identity}-*.json'):
                            private_cache.mkdir(parents=True, exist_ok=True)
                            target = private_cache / previous.name
                            if not target.exists():
                                shutil.copy2(previous, target)
                    except OSError:
                        logging.getLogger(__name__).warning('Alter Cache von Plugin %s konnte nicht uebernommen werden.', identity)
                instance = module.Plugin(cache_dir=private_cache, clock=lambda: datetime.now(timezone.utc))
                if getattr(instance, 'id', identity) != identity:
                    raise ValueError('Plugin-ID stimmt nicht mit Manifest ueberein.')
                if not hasattr(instance, 'id'):
                    instance.id = identity
                metadata = instance.metadata()
                if metadata.get('id') != identity or not isinstance(metadata.get('label'), str) or not callable(instance.track):
                    raise ValueError('Ungueltiger Plugin-Vertrag.')
                json.dumps(metadata, allow_nan=False)
            except Exception:
                sys.modules.pop(name, None)
                raise
            loaded[identity] = {'instance': instance, 'files': files, 'manifest': manifest, 'folder': folder}
        except Exception as error:
            diagnostics.append({'plugin': identity, 'error': type(error).__name__})
            logging.getLogger(__name__).warning('Plugin %s deaktiviert: %s', identity, type(error).__name__)
    return dict(sorted(loaded.items(), key=lambda item: (item[1]['manifest'].get('order', 100), item[0]))), diagnostics