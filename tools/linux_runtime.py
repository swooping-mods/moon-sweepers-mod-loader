"""Materialize only the reviewed portable Python/Qt runtime; never install packages."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def locked_inputs(folder):
    lock = json.loads((ROOT/'vendored/linux-runtime.lock.json').read_text())
    for item in lock['files']:
        path = folder/item['name']
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or aliased Linux input: '+item['name'])
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != item['sha256']:
            raise ValueError('Linux input hash mismatch: '+item['name'])
    return lock


def safe(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or not p.parts:
        raise ValueError('Unsafe runtime member: '+name)
    return p.as_posix()


def python_member(name, version):
    prefix = f'python/lib/python{version}/'
    if name in (f'python/bin/python{version}', f'python/lib/libpython{version}.so.1.0'):
        return True
    if not name.startswith(prefix):
        return False
    relative = name[len(prefix):]
    if relative.split('/')[0] in ('site-packages', 'ensurepip', 'test', 'idlelib', 'tkinter', 'turtledemo'):
        return False
    return '__pycache__' not in name and not Path(relative).name.startswith(('_test', '_tkinter', 'xx', '_xx'))


def payload(folder):
    lock = locked_inputs(folder)
    files = {}
    version = lock['python_minor']
    for item in lock['files']:
        path = folder/item['name']
        if item['role'] == 'python':
            with tarfile.open(path) as archive:
                for member in archive:
                    name = safe(member.name)
                    if member.isfile() and python_member(name, version):
                        files['.runtime/'+name] = archive.extractfile(member).read()
        elif item['role'] == 'wheel':
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name in lock['wheel_members']:
                        safe(name)
                        files[f'.runtime/python/lib/python{version}/site-packages/'+name] = archive.read(name)
        elif item['role'] in ('source', 'appimage-source'):
            files['LICENSES/sources/'+path.name] = path.read_bytes()
            with tarfile.open(path) as archive:
                for member in archive:
                    base = Path(member.name).name.upper()
                    if member.isfile() and (base.startswith(('LICENSE', 'COPYING', 'COPYRIGHT')) or '/LICENSES/' in member.name):
                        name = safe(member.name)
                        files['LICENSES/upstream/'+path.name+'/'+name] = archive.extractfile(member).read()
        elif item['role'] == 'python-notices':
            # The matching full distribution owns the third-party license texts
            # omitted from its install-only derivative. No second runtime ships.
            raw = subprocess.check_output(['zstd', '-dc', str(path)])
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                for member in archive:
                    name = safe(member.name)
                    if member.isfile() and (name.startswith('python/licenses/') or name == 'python/PYTHON.json'):
                        files['LICENSES/standalone-python/'+name] = archive.extractfile(member).read()
        elif item['role'] == 'license':
            files['LICENSES/'+path.name] = path.read_bytes()
        elif item['role'] == 'desktop-library':
            raw = subprocess.check_output(['ar', 'p', str(path), 'data.tar.zst'])
            raw = subprocess.check_output(['zstd', '-dc'], input=raw)
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                members = {safe(m.name): m for m in archive if not m.isdir()}
                for name, member in members.items():
                    if name.startswith('usr/lib/x86_64-linux-gnu/') and '.so' in name:
                        source = member
                        if member.issym():
                            source = members[safe(str(Path(name).parent/member.linkname))]
                        if not source.isfile():
                            raise ValueError('Unsupported desktop library member')
                        files['.runtime/desktop-libs/'+Path(name).name] = archive.extractfile(source).read()
                    elif name.startswith('usr/share/doc/') and name.endswith('/copyright'):
                        files['LICENSES/desktop/'+path.name+'/copyright'] = archive.extractfile(member).read()
    expected = {f'.runtime/python/lib/python{version}/site-packages/'+n for n in lock['wheel_members']}
    expected.update('.runtime/desktop-libs/'+name for name in lock.get('desktop_libraries', ()))
    if not expected <= files.keys() or f'.runtime/python/bin/python{version}' not in files:
        raise ValueError('Incomplete portable Linux runtime')
    files['LICENSES/linux-runtime-manifest.json'] = (json.dumps(lock, indent=2)+'\n').encode()
    return files


def materialize(root, files):
    for name, data in files.items():
        safe(name)
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o755 if name in ('Moon Sweepers Mod Loader', 'AppRun') or name.startswith('.runtime/python/bin/') else 0o644)
