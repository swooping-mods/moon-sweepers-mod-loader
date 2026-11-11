"""Bounded, inert import of local downloads into ordinary checked mod packages."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import zipfile
import zlib

from . import packages
from .storage import contained, is_alias, relative

PROFILES = Path(__file__).resolve().parents[2] / 'vendored/import-profiles'
MAX_ENTRIES = 2048
MAX_DEPTH = 8
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
MAX_PACKAGES = 32
FORMAT_ERRORS = (ValueError, OSError, zipfile.BadZipFile, EOFError, zlib.error,
                 NotImplementedError, RecursionError, KeyError, TypeError, AttributeError)


class Download:
    def __init__(self, entries, reader):
        self.entries = entries
        self.reader = reader
        self.bytes_read = 0

    def read(self, name, limit=packages.MAX_BYTES):
        if name not in self.entries:
            raise ValueError('Missing mod file: ' + name)
        if self.entries[name] > limit:
            raise ValueError('Mod file exceeds import size limit: ' + name)
        data = self.reader(name, limit)
        self.bytes_read += len(data)
        if len(data) > limit or self.bytes_read > MAX_DOWNLOAD_BYTES:
            raise ValueError('Download exceeds import size limit')
        return data


def _inventory(items):
    result = {}; folded = set()
    for name, size in items:
        relative(name)
        if len(name.split('/')) > MAX_DEPTH or len(result) >= MAX_ENTRIES:
            raise ValueError('Choose a smaller mod folder or archive')
        if name.casefold() in folded:
            raise ValueError('Duplicate download path: ' + name)
        result[name] = size; folded.add(name.casefold())
    if sum(result.values()) > MAX_DOWNLOAD_BYTES:
        raise ValueError('Download exceeds 256 MiB expanded size limit')
    return result


@contextmanager
def open_download(path):
    path = contained(path.parent, path.name)
    if path.is_dir():
        items = []; count = 0
        for directory, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                child = Path(directory) / name
                count += 1
                if count > MAX_ENTRIES or len(child.relative_to(path).parts) > MAX_DEPTH:
                    raise ValueError('Choose a smaller mod folder')
                if is_alias(child):
                    raise ValueError('Links are not imported: ' + str(child))
                if not child.is_dir():
                    if not stat.S_ISREG(child.stat().st_mode):
                        raise ValueError('Only regular mod files can be imported')
                    items.append((child.relative_to(path).as_posix(), child.stat().st_size))
        def read(name, limit):
            with contained(path, name).open('rb') as stream:
                return stream.read(limit + 1)
        yield Download(_inventory(items), read)
    else:
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError('Only regular mod files can be imported')
        if path.stat().st_size > MAX_DOWNLOAD_BYTES:
            raise ValueError('Download exceeds 256 MiB size limit')
        with zipfile.ZipFile(path) as archive:
            items = []; seen = set()
            if len(archive.infolist()) > MAX_ENTRIES:
                raise ValueError('Too many files in download')
            for info in archive.infolist():
                name = info.filename.rstrip('/') if info.is_dir() else info.filename
                relative(name)
                if name.casefold() in seen:
                    raise ValueError('Duplicate download path: ' + name)
                seen.add(name.casefold())
                mode = stat.S_IFMT(info.external_attr >> 16)
                if info.flag_bits & 1 or mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError('Only unencrypted regular mod files can be imported')
                if not info.is_dir():
                    if mode == stat.S_IFDIR:
                        raise ValueError('Invalid download member type')
                    items.append((info.filename, info.file_size))
            def read(name, limit):
                with archive.open(name) as stream:
                    return stream.read(limit + 1)
            yield Download(_inventory(items), read)


def profiles():
    result = []
    for path in sorted(PROFILES.glob('*.json')):
        profile = json.loads(contained(PROFILES, path.name).read_text('utf-8'))
        if profile.get('schema') != 'moon-loader-download-profile/v1':
            raise ValueError('Unsupported download recognition profile')
        manifest = packages.validate(profile['manifest'])
        sources, assets = profile['sources'], profile['assets']
        if set(sources) & set(assets) or set(sources) | set(assets) != set(manifest['files']):
            raise ValueError('Incomplete download recognition profile')
        for name in [*sources.values(), *assets.values()]: relative(name)
        for name, location in assets.items():
            if hashlib.sha256(contained(PROFILES, location).read_bytes()).hexdigest() != manifest['files'][name]:
                raise ValueError('Changed download support file: ' + location)
        result.append(profile)
    return result


def _pack(manifest, files):
    # Existing manifests retain their expected hashes. Never "repair" a changed
    # download by recomputing its advertised integrity table.
    for name, data in files.items():
        if hashlib.sha256(data).hexdigest() != manifest['files'][name]:
            raise ValueError('Downloaded mod checksum mismatch: ' + name)
    import io
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted({**files, 'manifest.json': (json.dumps(manifest, indent=2) + '\n').encode()}.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return output.getvalue()


def candidates(download):
    found = False
    for name in sorted(download.entries):
        if name.lower().endswith('.msmod'):
            found = True
            yield name, download.read(name)
        elif name.rsplit('/', 1)[-1] == 'manifest.json':
            manifest = json.loads(download.read(name, 32 * 1024))
            if not isinstance(manifest, dict) or manifest.get('schema') != packages.SCHEMA: continue
            packages.validate(manifest)
            prefix = name[:-len('manifest.json')]
            if sum(download.entries.get(prefix + item, 0) for item in manifest['files']) > packages.MAX_BYTES:
                raise ValueError('Unpacked mod package exceeds 64 MiB')
            files = {item: download.read(prefix + item) for item in manifest['files']}
            if sum(map(len, files.values())) > packages.MAX_BYTES:
                raise ValueError('Unpacked mod package exceeds 64 MiB')
            found = True
            yield name, _pack(manifest, files)
    folded = {name.casefold(): name for name in download.entries}
    for profile in profiles():
        manifest = profile['manifest']
        entry = profile['sources'][manifest['entry']]
        matches = [name for name in download.entries
                   if name.casefold() == entry.casefold() or name.casefold().endswith('/' + entry.casefold())]
        if len(matches) > 1:
            raise ValueError('Multiple copies of ' + manifest['name'] + '; choose one mod folder')
        if not matches: continue
        prefix = matches[0][:-len(entry)]
        files = {name: download.read(folded.get((prefix + source).casefold(), prefix + source))
                 for name, source in profile['sources'].items()}
        files.update({name: contained(PROFILES, source).read_bytes() for name, source in profile['assets'].items()})
        found = True
        yield manifest['name'], _pack(manifest, files)
    if not found:
        raise ValueError('No supported mod found. Choose a .msmod package, a folder with its package manifest, '
                         'or the complete MarsSweepers 0.6.1 folder/ZIP. Loose DLLs need a compatible mod package.')


def add(service, paths):
    """Import successes independently, report failures, and preserve checkmarks."""
    if len(paths) > MAX_PACKAGES:
        raise ValueError('Add at most 32 downloads at a time')
    result = {'installed': [], 'errors': []}
    seen = {}; count = 0
    with tempfile.TemporaryDirectory(prefix='MoonLoader-import-') as temporary:
        for incoming in paths:
            path = Path(incoming).expanduser().absolute()
            try:
                if path.suffix.lower() == '.dll':
                    raise ValueError('Choose the complete mod folder or ZIP, including its package metadata and assets.')
                if not path.is_dir() and path.suffix.lower() not in ('.msmod', '.zip'):
                    raise ValueError('Choose a mod folder, .msmod package or .zip download')
                if path.suffix.lower() == '.msmod' and not path.is_dir():
                    source = contained(path.parent, path.name)
                    if not stat.S_ISREG(source.stat().st_mode):
                        raise ValueError('Only regular mod files can be imported')
                    with source.open('rb') as stream: data = stream.read(packages.MAX_BYTES + 1)
                    entries = [(path.name, data)]
                else:
                    entries = None
                with _entries(path, entries) as entries:
                    for name, data in entries:
                        count += 1
                        if count > MAX_PACKAGES:
                            raise ValueError('Add at most 32 packages at a time')
                        staged = Path(temporary) / (str(count) + '.msmod')
                        staged.write_bytes(data)
                        try:
                            manifest = packages.examine(staged)
                            digest = hashlib.sha256(data).hexdigest()
                            previous = seen.get(manifest['id'])
                            if previous == digest: continue
                            if previous:
                                raise ValueError('Multiple versions of ' + manifest['name'] + '; add only the version you want')
                            service.import_package(staged, select=False)
                            seen[manifest['id']] = digest
                            result['installed'].append(manifest)
                        except FORMAT_ERRORS as error:
                            result['errors'].append({'path': str(path) + ' / ' + name, 'error': str(error)})
            except FORMAT_ERRORS as error:
                result['errors'].append({'path': str(path), 'error': str(error)})
    return result


@contextmanager
def _entries(path, direct):
    if direct is not None:
        yield direct
    else:
        with open_download(path) as download:
            yield candidates(download)
