"""Verify the pinned first-party distribution inputs without executing mods."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loader'))
from moonloader import packages
from moonloader.discovery import PIN


def payload(folder=None):
    lock = json.loads((ROOT / 'vendored/mod-bundle.json').read_text())
    if lock.get('schema') != 'moon-loader-mod-bundle/v1':
        raise ValueError('Unsupported bundled mod lock')
    if folder is None:
        folder = ROOT / 'vendored/mod-bundle/packages'
        # The source distribution retains these inputs in their runnable layout.
        if not folder.exists():
            folder = ROOT / 'loader/packages'
    folder = Path(folder)
    if folder.is_symlink():
        raise ValueError('Bundled package directory must not be an alias')
    files = {}; manifests = {}
    for item in lock['packages']:
        name = item['file']
        if Path(name).name != name or not name.endswith('.msmod') or '\\' in name:
            raise ValueError('Invalid bundled package filename')
        path = folder / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or aliased bundled package: ' + name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Bundled package checksum mismatch: ' + name)
        manifest = packages.examine(path)
        if (manifest['id'] != item['id'] or manifest['version'] != item['version']
                or manifest['kind'] != 'native' or manifest.get('default_selected') is not False):
            raise ValueError('Bundled package identity/default mismatch: ' + name)
        if manifest['id'] in manifests:
            raise ValueError('Duplicate bundled mod: ' + manifest['id'])
        manifests[manifest['id']] = manifest
        files['loader/packages/' + name] = data
    if set(p.name for p in folder.iterdir()) != {item['file'] for item in lock['packages']}:
        raise ValueError('Bundled package inventory differs from lock')
    if not set(lock['mods'] + [lock['test_mod']]) <= manifests.keys():
        raise ValueError('Missing handpicked mod or test mod')
    packages.resolve(manifests, list(manifests), PIN,
                     available_runtimes={('native', abi) for abi in packages.NATIVE_ABIS},
                     runtime_api_abi=1, runtime_readiness_abi=1,
                     host_capabilities={'interaction': 1})
    return files


if __name__ == '__main__':
    print('Verified', len(payload()), 'bundled mod packages; no game started.')
