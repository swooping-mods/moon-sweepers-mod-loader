"""Pinned offline BepInEx deployment; packages never write host/core paths."""
import configparser
import hashlib
import json
from pathlib import Path
import re
from .storage import contained, load, write, is_alias

SCHEMA = 'moonlab-bepinex-build/v1'
VERSION = '6.0.0-be.791+b782da4'
STARTUP_FILES = frozenset(('winhttp.dll', 'doorstop_config.ini', 'dotnet/coreclr.dll',
    'BepInEx/core/BepInEx.Unity.IL2CPP.dll',
    'BepInEx/patchers/MoonLab.Adapter/MoonLab.BepInExAdapter.dll',
    'BepInEx/config/BepInEx.cfg'))


def descriptor(bundle):
    """Read declared host capability; preparation verifies every payload byte."""
    return artifact_descriptor(Path(bundle) / 'runtime/bepinex')


def artifact_descriptor(root):
    root = Path(root)
    receipt = load(contained(root, 'receipt.json'), {})
    files = receipt.get('files')
    if receipt.get('schema') != SCHEMA or not isinstance(files, dict) or not files:
        raise ValueError('The screened BepInEx bundle is missing; explicitly attach a checked runtime first')
    if receipt.get('version') != VERSION:
        raise ValueError('Unsupported BepInEx runtime version')
    if not STARTUP_FILES <= files.keys():
        raise ValueError('BepInEx bundle lacks required host/adapter inputs')
    folded = set()
    for name, expected in files.items():
        contained(root / 'files', name)
        if name.casefold() in folded or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('Invalid BepInEx file table')
        folded.add(name.casefold())
    return root, receipt


def available(bundle, runtime_receipt):
    if runtime_receipt.get('managed_profile_guard_abi') != 1:
        return False
    try:
        descriptor(bundle)
        return True
    except (ValueError, OSError):
        return False


def validate_runtime_receipt(receipt):
    if receipt.get('managed_profile_guard_abi') != 1:
        raise ValueError('Managed mods require the updated private-profile runtime; rebuild the loader')


def artifact_files(root):
    """Verify an attachment without executing its host, patcher or plugins."""
    root, receipt = artifact_descriptor(root)
    actual = set()
    for path in (root / 'files').rglob('*'):
        if is_alias(path): raise ValueError('Alias in BepInEx bundle: ' + str(path))
        if path.is_file(): actual.add(path.relative_to(root / 'files').as_posix())
    if actual != set(receipt['files']):
        raise ValueError('BepInEx bundle differs from its file table')
    result = {}
    for name, expected in receipt['files'].items():
        path = contained(root / 'files', name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected: raise ValueError('BepInEx bundle changed: ' + name)
        result[name] = data
    validate_config(contained(root / 'files', 'BepInEx/config/BepInEx.cfg'))
    return receipt, result


def runtime_files(bundle):
    _, result = artifact_files(Path(bundle) / 'runtime/bepinex')
    # BepInEx rewrites configuration. It is seeded separately, then checked
    # before every launch instead of pretending that it is immutable.
    return {name: data for name, data in result.items() if not name.startswith('BepInEx/config/')}


def plugin_files(manifest, folder):
    result = {}
    for member in manifest['files']:
        if member.startswith('data/'):
            target = 'BepInEx/' + manifest['bepinex']['data_root'] + '/' + member[5:]
        else:
            target = 'BepInEx/plugins/' + manifest['id'] + '/' + member
        result[target] = contained(folder, member).read_bytes()
    return result


def preflight(game, files):
    """Unknown executable inputs are never picked up by upstream discovery."""
    previous = load(Path(game).parent / 'deployment.json', {'files': {}})['files']
    allowed = set(files) | set(previous)
    for name in ('BepInEx/core', 'BepInEx/patchers', 'BepInEx/plugins', 'dotnet'):
        root = contained(game, name)
        if not root.exists(): continue
        for path in root.rglob('*'):
            if is_alias(path): raise ValueError('Alias in managed runtime: ' + str(path))
            if path.is_file() and path.relative_to(game).as_posix() not in allowed:
                raise ValueError('Unowned managed runtime/plugin input: ' + path.relative_to(game).as_posix())
    config = contained(game, 'BepInEx/config/BepInEx.cfg')
    if config.exists(): validate_config(config)


def validate_config(path):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(path, encoding='utf-8-sig')
    section = cfg['IL2CPP'] if 'IL2CPP' in cfg else {}
    if (any(str(section.get(name, '')).strip().lower() != 'false' for name in
            ('UpdateInteropAssemblies', 'PreloadIL2CPPInteropAssemblies', 'ScanMethodRefs'))
            or str(section.get('UnityBaseLibrariesSource', 'missing')).strip()):
        raise ValueError('BepInEx automatic downloads/generation must remain disabled')


def prepare_cache(game, bundle):
    for name in ('BepInEx/interop', 'BepInEx/unity-libs', 'BepInEx/config'):
        contained(game, name).mkdir(parents=True, exist_ok=True)
    config = contained(game, 'BepInEx/config/BepInEx.cfg')
    if not config.exists():
        source = Path(bundle) / 'runtime/bepinex/files/BepInEx/config/BepInEx.cfg'
        with config.open('xb') as output: output.write(source.read_bytes())
    validate_config(config)


def allowed_inputs(files):
    protected = ('BepInEx/core/', 'BepInEx/patchers/', 'BepInEx/plugins/', 'dotnet/')
    return {
        'schema': 'moonlab-managed-inputs/v1',
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()
                  if name.startswith(protected)}}


def allowlist(files):
    return (json.dumps(allowed_inputs(files), indent=2) + '\n').encode()


def write_allowlist(game, files):
    # Compatibility for existing private workshop callers; new deployments
    # journal allowlist(files) together with their immutable payloads.
    write(contained(game, 'BepInEx/MoonLab/allowed-inputs.json'), allowed_inputs(files))
