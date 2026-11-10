"""Strict local package intake. Hashes establish integrity, not author identity."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import struct
import tempfile
import zipfile
from .storage import contained, key, relative, sha, load, write
from .build_items import validate_manifest as validate_build_items, validate_selection as validate_build_selection
from .runtimes import (MANAGED_KIND, MANAGED_ABI, game_mod, validate as validate_runtime,
                       selection as validate_runtime_selection, require_available)
from .interfaces import validate_manifest as validate_interfaces, selection as interface_selection

SCHEMA = 'moon-mod-package/v1'
MAX_FILES = 128
MAX_BYTES = 64 * 1024 * 1024
MAX_GAME_MODS = 64
MAX_NATIVE_MODS = MAX_GAME_MODS  # Retained import name for existing loaders.


def validate(manifest):
    if manifest.get('schema') != SCHEMA: raise ValueError('Unsupported mod package format')
    key(manifest.get('id'))
    version = manifest.get('version', '')
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-z0-9.]+)?', version): raise ValueError('Invalid package version')
    for field in ('name', 'summary', 'description', 'author'):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip() or len(manifest[field]) > 8000: raise ValueError('Missing package ' + field)
    runtime = (manifest.get('kind'), manifest.get('abi'))
    files = manifest.get('files', {})
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES: raise ValueError('Invalid package file table')
    folded = set()
    for name, digest in files.items():
        relative(name)
        if name.casefold() in folded or name.casefold() == 'manifest.json': raise ValueError('Duplicate or reserved package path')
        folded.add(name.casefold())
        if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest): raise ValueError('Invalid file digest')
    entry = manifest.get('entry', '')
    extension = '.dll' if game_mod(manifest) else '.pyz'
    if entry not in files or not entry.lower().endswith(extension):
        raise ValueError('Missing native entry DLL' if extension == '.dll' else 'Missing companion Python ZIP application')
    if manifest.get('icon') not in files: raise ValueError('Missing package icon')
    # Only PNG artwork is decoded by Qt; package SVG/XML or HTML is never executed.
    if not manifest['icon'].endswith('.png'): raise ValueError('Package icons must be PNG')
    for field in ('conflicts', 'requires', 'claims'):
        values = manifest.get(field)
        if not isinstance(values, list) or len(values) > 64 or any(not isinstance(v, str) or len(v) > 160 for v in values): raise ValueError('Invalid ' + field)
    if manifest['kind'] == 'companion' and any(manifest[field] for field in ('requires', 'conflicts', 'claims')):
        raise ValueError('Companion tools cannot declare native dependencies or hook claims')
    shared = manifest.get('shared_claims', [])
    if not isinstance(shared, list) or any(v not in ('MoonWalker.Update','MoonWalker.LateUpdate') for v in shared) or len(shared) != len(set(shared)) or len(shared) > 2:
        raise ValueError('Unsupported shared hook claim')
    if shared and (runtime not in (('native', 'MoonLab_ModStart/v2'), ('native', 'MoonLab_ModStart/v3'), ('native', 'MoonLab_ModStart/v4'), ('native', 'MoonLab_ModStart/v5'), ('native', 'MoonLab_ModStart/v6')) or set(shared) & set(manifest['claims'])):
        raise ValueError('Shared Update requires v2 and cannot also be exclusive')
    vehicle = manifest.get('vehicle_hook')
    if 'vehicle_hook' in manifest and (vehicle not in ('input', 'physics') or runtime not in (('native', 'MoonLab_ModStart/v3'),('native', 'MoonLab_ModStart/v4'),('native', 'MoonLab_ModStart/v5'),('native', 'MoonLab_ModStart/v6'))):
        raise ValueError('Vehicle adapter requires v3 and input or physics role')
    if vehicle and 'MoonPrototypeVehicle.FixedUpdate' in manifest['claims']:
        raise ValueError('Vehicle adapter cannot also claim exclusive FixedUpdate')
    late = manifest.get('late_update_hook')
    if 'late_update_hook' in manifest or 'MoonWalker.LateUpdate' in shared:
        if runtime not in (('native','MoonLab_ModStart/v4'),('native','MoonLab_ModStart/v5'),('native','MoonLab_ModStart/v6')) or late not in ('observer','override') or 'MoonWalker.LateUpdate' not in shared:
            raise ValueError('Shared LateUpdate requires v4, a shared claim and observer or override role')
    if ('hook_framework_abi' in manifest or runtime == ('native','MoonLab_ModStart/v5')
            or runtime == ('native','MoonLab_ModStart/v6') and (shared or vehicle)):
        if runtime not in (('native','MoonLab_ModStart/v5'),('native','MoonLab_ModStart/v6')) or type(manifest.get('hook_framework_abi')) is not int or manifest['hook_framework_abi'] != 1 or not (shared or vehicle):
            raise ValueError('Hook framework requires v5, ABI 1 and a declared shared hook role')
    if 'default_selected' in manifest and type(manifest['default_selected']) is not bool:
        raise ValueError('default_selected must be a boolean')
    game = manifest.get('game', {})
    if game.get('id') != 'moon-sweepers' or game.get('appid') != '5335510' or not game.get('hashes'): raise ValueError('Missing game compatibility pins')
    for name, digest in game['hashes'].items():
        if name not in ('GameAssembly.dll', 'MoonSweepers.exe', 'UnityPlayer.dll') or not re.fullmatch('[a-f0-9]{64}', digest): raise ValueError('Invalid game pin')
    validate_runtime(manifest)
    validate_interfaces(manifest)
    validate_build_items(manifest)
    return manifest


def png_icon(data):
    if len(data)<24 or data[:8]!=b'\x89PNG\r\n\x1a\n' or data[12:16]!=b'IHDR':
        raise ValueError('Package icon must contain PNG data')
    width,height=struct.unpack('>II',data[16:24])
    if not 0<width<=1024 or not 0<height<=1024: raise ValueError('Package icon must be at most 1024 by 1024 pixels')


def examine(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES: raise ValueError('Package exceeds 64 MiB')
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES + 1: raise ValueError('Too many package files')
        names = set(); total = 0
        for info in infos:
            relative(info.filename)
            if info.filename.casefold() in names: raise ValueError('Duplicate package member')
            names.add(info.filename.casefold())
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or info.is_dir() or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)) or info.flag_bits & 1:
                raise ValueError('Only unencrypted regular package files are accepted')
            total += info.file_size
            if total > MAX_BYTES: raise ValueError('Unpacked package exceeds 64 MiB')
        if 'manifest.json' not in {info.filename for info in infos}: raise ValueError('Package has no manifest')
        if archive.getinfo('manifest.json').file_size > 32 * 1024: raise ValueError('Manifest exceeds 32 KiB')
        manifest = validate(json.loads(archive.read('manifest.json')))
        if set(x.filename for x in infos) != set(manifest['files']) | {'manifest.json'}: raise ValueError('Unlisted or missing package files')
        png_icon(archive.read(manifest['icon']))
        for name, expected in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected: raise ValueError('Package checksum mismatch: ' + name)
    return manifest


def install(path, root):
    root = Path(root); manifest = examine(path); archive_hash = sha(path)
    name = manifest['id'] + '/' + manifest['version'] + '-' + archive_hash[:16]
    target = contained(root / 'library', name)
    if target.exists():
        installed(target)
        return name, manifest
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.intake-', dir=target.parent))
    try:
        with zipfile.ZipFile(path) as archive:
            # Recheck the package actually read during extraction, not only a prior pathname.
            if sha(path) != archive_hash: raise ValueError('Package changed during intake')
            for info in archive.infolist():
                output = contained(temporary, info.filename)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(archive.read(info))
        installed(temporary)
        temporary.rename(target)
    finally:
        if temporary.exists(): shutil.rmtree(temporary)
    return name, manifest


def installed(folder):
    folder = Path(folder); manifest = validate(load(contained(folder, 'manifest.json'), {}))
    expected = set(manifest['files']) | {'manifest.json'}
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != expected: raise ValueError('Installed package file set changed')
    for name, digest in manifest['files'].items():
        if sha(contained(folder, name)) != digest: raise ValueError('Installed package was changed: ' + name)
    png_icon(contained(folder,manifest['icon']).read_bytes())
    return manifest


def resolve(manifests, selected, game_hashes, *, available_runtimes=None, runtime_api_abi=None):
    """Order selected game mods and reject conflicting runtime/API contracts."""
    chosen = set(selected); ordered = []; visiting = set(); done = set(); claims = {}; shared_claims = {}; vehicle_roles = {}; late_override = []
    if not chosen: raise ValueError('Select at least one mod')
    if len(chosen) > MAX_GAME_MODS: raise ValueError('At most ' + str(MAX_GAME_MODS) + ' game mods can be loaded')
    validate_runtime_selection(manifests, chosen)
    api_dependencies = interface_selection(manifests, chosen)
    validate_build_selection(manifests, chosen)
    def visit(name):
        if name in visiting: raise ValueError('Circular mod dependency: ' + name)
        if name in done: return
        if name not in manifests: raise ValueError('Missing installed mod: ' + name)
        mod = manifests[name]
        if not game_mod(mod): raise ValueError(mod['name'] + ' is a companion tool; open its folder instead of selecting it for a game launch')
        require_available(mod, available_runtimes, runtime_api_abi)
        for file, digest in mod['game']['hashes'].items():
            if game_hashes.get(file) != digest: raise ValueError(mod['name'] + ' does not support this game build')
        for other in mod['conflicts']:
            if other in chosen: raise ValueError(mod['name'] + ' conflicts with ' + other)
        for claim in mod['claims']:
            if claim == 'MoonPrototypeVehicle.FixedUpdate' and vehicle_roles: raise ValueError('Exclusive vehicle hook conflicts with vehicle adapter')
            if claim in shared_claims: raise ValueError(mod['name'] + ' exclusively owns shared hook ' + claim)
            if claim in claims: raise ValueError(mod['name'] + ' and ' + claims[claim] + ' both own ' + claim)
            claims[claim] = mod['name']
        for claim in mod.get('shared_claims', []):
            if claim in claims: raise ValueError(claim + ' is exclusively owned by ' + claims[claim])
            shared_claims[claim] = mod['name']
        role = mod.get('vehicle_hook')
        if role:
            if 'MoonPrototypeVehicle.FixedUpdate' in claims: raise ValueError('Vehicle adapter conflicts with exclusive FixedUpdate')
            if role in vehicle_roles: raise ValueError('Multiple vehicle ' + role + ' providers')
            vehicle_roles[role] = name
        if mod.get('late_update_hook') == 'override':
            if late_override: raise ValueError('Multiple LateUpdate override providers')
            late_override.append(name)
        visiting.add(name)
        for dependency in mod['requires']:
            if dependency not in chosen: raise ValueError('Also select required mod: ' + dependency)
            visit(dependency)
        for dependency in api_dependencies.get(name, []):
            visit(dependency)
        visiting.remove(name); done.add(name); ordered.append(name)
    for name in sorted(chosen): visit(name)
    return ordered
