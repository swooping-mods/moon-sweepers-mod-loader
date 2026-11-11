"""Verified modern Harmony/MonoMod overlay. No downloads or assembly activation."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT/'vendored/modern-harmony.lock.json'


def payload(inputs):
    lock = json.loads(LOCK.read_text())
    if lock.get('schema') != 'moon-loader-modern-harmony/v1':
        raise ValueError('Unsupported modern Harmony lock')
    files = {}; seen = set()
    for item in lock['files']:
        name = item['name']
        path = Path(inputs)/name
        if Path(name).name != name or path.is_symlink() or not path.is_file():
            raise ValueError('Missing reviewed modern Harmony input: '+name)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Modern Harmony input changed: '+name)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(n.casefold() for n in names)):
                raise ValueError('Aliased modern Harmony archive')
            for source, target in item['members'].items():
                if (target in seen or not target.startswith('BepInEx/core/')
                        or Path(target).name != source.rsplit('/',1)[-1]):
                    raise ValueError('Invalid modern Harmony target')
                seen.add(target)
                data = archive.read(source)
                if hashlib.sha256(data).hexdigest() != item['member_sha256'][source]:
                    raise ValueError('Changed modern Harmony member: '+source)
                files[target] = data
    folder = ROOT/'vendored/modern-harmony-notices'
    if folder.is_symlink() or {p.name for p in folder.iterdir()} != set(lock['notice_files']):
        raise ValueError('Modern Harmony notice inventory changed')
    for name, expected in lock['notice_files'].items():
        path = folder/name
        if Path(name).name != name or path.is_symlink() or not path.is_file():
            raise ValueError('Aliased modern Harmony notice')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Modern Harmony notice changed: '+name)
        files['BepInEx/third-party-sources/modern-detours/'+name] = data
    files['BepInEx/third-party-sources/modern-detours/components.json'] = LOCK.read_bytes()
    return files


def runtime_hashes():
    """Authoritative packaged-byte expectations without acquiring build inputs."""
    lock = json.loads(LOCK.read_text())
    return {target: item['member_sha256'][source]
            for item in lock['files'] for source, target in item['members'].items()}
