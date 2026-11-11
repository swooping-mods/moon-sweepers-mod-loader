"""Reviewed game identities; version labels never authorize executable bytes."""
import hashlib
import json
from pathlib import Path
import re

PATH = Path(__file__).with_name('game_profiles.json')
SCHEMA = 'moon-game-profiles/v1'
CURRENT_PROFILE_ID = 'moon-sweepers.steam.1.0.5.il2cpp108.win-x64'
GAME_FILES = ('GameAssembly.dll', 'MoonSweepers.exe', 'UnityPlayer.dll')
_ID = re.compile(r'[a-z][a-z0-9_.-]{0,63}')
_HEX = re.compile(r'[a-f0-9]{64}')


def digest(profile):
    """Bind labels, logical contracts and physical bindings in one identity."""
    value = {k: v for k, v in profile.items() if k != 'digest'}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode('ascii')).hexdigest()


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result: raise ValueError('Duplicate game profile field: ' + key)
        result[key] = value
    return result


def validate(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'profiles'} or value['schema'] != SCHEMA:
        raise ValueError('Unsupported game profile catalog')
    rows = value['profiles']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 64:
        raise ValueError('Game profile catalog must contain one to 64 reviewed profiles')
    identities = set(); binaries = set()
    for row in rows:
        required = {'id', 'version', 'backend', 'architecture', 'metadata_version',
                    'hashes', 'adapter', 'capabilities', 'native'}
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError('Invalid game profile fields')
        if not isinstance(row['id'], str) or not _ID.fullmatch(row['id']) or row['id'] in identities:
            raise ValueError('Invalid or duplicate game profile identity')
        identities.add(row['id'])
        if (not isinstance(row['version'], str) or not 1 <= len(row['version']) <= 64
                or any(ord(c) < 32 or ord(c) > 126 for c in row['version'])):
            raise ValueError('Invalid game profile version label')
        if row['backend'] != 'il2cpp' or row['architecture'] != 'win-x64':
            raise ValueError('Unsupported game profile backend or architecture')
        if type(row['metadata_version']) is not int or not 1 <= row['metadata_version'] <= 0xffffffff:
            raise ValueError('Invalid game metadata version')
        hashes = row['hashes']
        if (not isinstance(hashes, dict) or set(hashes) != set(GAME_FILES)
                or any(not isinstance(v, str) or not _HEX.fullmatch(v) for v in hashes.values())):
            raise ValueError('Game profiles require the exact three executable hashes')
        key = tuple(sorted(hashes.items()))
        if key in binaries: raise ValueError('Ambiguous executable hashes in game profile catalog')
        binaries.add(key)
        adapter = row['adapter']
        if (not isinstance(adapter, dict) or set(adapter) != {'id', 'abi', 'layout'}
                or type(adapter['abi']) is not int or not 1 <= adapter['abi'] <= 0xffffffff
                or any(not isinstance(adapter[n], str) or not 1 <= len(adapter[n]) <= 128
                       or any(ord(c) < 32 or ord(c) > 126 for c in adapter[n]) for n in ('id', 'layout'))):
            raise ValueError('Invalid game adapter identity')
        caps = row['capabilities']
        if not isinstance(caps, dict) or len(caps) > 64:
            raise ValueError('Invalid game capability inventory')
        for name, cap in caps.items():
            if not isinstance(name, str) or len(name) > 160 or not re.fullmatch(r'[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)*', name):
                raise ValueError('Invalid game capability name')
            if (not isinstance(cap, dict) or set(cap) != {'abi', 'size', 'limits'}
                    or type(cap['abi']) is not int or not 1 <= cap['abi'] <= 0xffffffff
                    or type(cap['size']) is not int or not 1 <= cap['size'] <= 65536
                    or not isinstance(cap['limits'], dict) or len(cap['limits']) > 32):
                raise ValueError('Invalid game capability contract')
            if any(not isinstance(k, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', k)
                   or type(v) is not int or not 0 <= v <= 0xffffffff for k, v in cap['limits'].items()):
                raise ValueError('Invalid game capability limits')
        native = row['native']
        if (not isinstance(native, dict) or not native or len(native) > 64
                or any(not isinstance(k, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', k)
                       or type(v) is not int or not 0 <= v <= 0xffffffff for k, v in native.items())):
            raise ValueError('Invalid native game profile data')
    return value


def load(path=None):
    path = Path(path) if path is not None else PATH
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > 262144:
        raise ValueError('Game profile catalog is missing, aliased or too large')
    return validate(json.loads(path.read_text('utf-8'), object_pairs_hook=_pairs))


def identify(hashes, catalog=None):
    catalog = validate(catalog) if catalog is not None else load()
    for profile in catalog['profiles']:
        if profile['hashes'] == hashes:
            return {**profile, 'digest': digest(profile)}
    return None
