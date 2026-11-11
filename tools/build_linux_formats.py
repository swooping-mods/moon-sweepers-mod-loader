#!/usr/bin/env python3
"""Wrap the checked Linux payload in a self-extracting launcher and AppImage."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile

import build
from linux_runtime import locked_inputs, materialize

RUN_HEADER = '''#!/bin/sh
set -eu
umask 077
loader_cache="${XDG_CACHE_HOME:-$HOME/.cache}/moon-sweepers-mod-loader/@VERSION@-@HASH@"
if [ ! -x "$loader_cache/Moon Sweepers Mod Loader" ]; then
 mkdir -p -- "$(dirname -- "$loader_cache")"
 loader_temp=$(mktemp -d "${loader_cache}.XXXXXX")
 trap 'rm -rf -- "$loader_temp"' EXIT HUP INT TERM
 tail -n +@OFFSET@ "$0" | tar -xz -C "$loader_temp"
 mv -T -n -- "$loader_temp" "$loader_cache"
 rm -rf -- "$loader_temp"
 trap - EXIT HUP INT TERM
fi
exec "$loader_cache/Moon Sweepers Mod Loader" "$@"
'''


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build_formats(out, inputs, squashfs):
    lock = locked_inputs(inputs)
    receipt = json.loads((out/'linux-build-receipt.json').read_text())
    archive = out/receipt['archive']
    if receipt['version'] != build.VERSION or digest(archive) != receipt['sha256'] or not receipt.get('python_qt_bundled'):
        raise ValueError('Formats require this version’s sealed portable Linux archive')
    prefix = f'moon-sweepers-mod-loader-{build.VERSION}-linux-x64'
    run = out/(prefix+'.run')
    header = RUN_HEADER.replace('@VERSION@', build.VERSION).replace('@HASH@', digest(archive))
    header = header.replace('@OFFSET@', str(len(header.splitlines())+1))
    with run.open('wb') as stream, archive.open('rb') as payload:
        stream.write(header.encode())
        shutil.copyfileobj(payload, stream)
    run.chmod(0o755)
    runtime = next(item for item in lock['files'] if item['role'] == 'appimage-runtime')
    with tempfile.TemporaryDirectory(prefix='Linux formats ', dir=out) as temporary:
        root = Path(temporary)
        appdir = root/'AppDir'
        appdir.mkdir()
        with tarfile.open(archive) as bundle:
            files = {}
            for member in bundle:
                name = PurePosixPath(member.name)
                if not member.isfile() or name.is_absolute() or '..' in name.parts or member.name in files:
                    raise ValueError('Invalid Linux payload member')
                data = bundle.extractfile(member).read()
                if hashlib.sha256(data).hexdigest() != receipt['files'].get(member.name):
                    raise ValueError('Linux payload inventory differs')
                files[member.name] = data
        if set(files) != set(receipt['files']):
            raise ValueError('Incomplete Linux payload inventory')
        files['AppRun'] = b'#!/bin/sh\nset -eu\nloader_root=${APPDIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}\nexec "$loader_root/Moon Sweepers Mod Loader" "$@"\n'
        files['io.github.swooping_mods.Loader.desktop'] = b'[Desktop Entry]\nType=Application\nName=Moon Sweepers Mod Loader\nExec=AppRun\nIcon=io.github.swooping_mods.Loader\nCategories=Game;Utility;\nTerminal=false\n'
        files['io.github.swooping_mods.Loader.svg'] = (build.ROOT/'loader/assets/electricity-toggle.svg').read_bytes()
        files['.DirIcon'] = files['io.github.swooping_mods.Loader.svg']
        materialize(appdir, files)
        squash = root/'payload.squashfs'
        subprocess.run([str(squashfs), str(appdir), str(squash), '-noappend', '-all-root',
                        '-comp', 'gzip', '-processors', '2', '-no-progress', '-mkfs-time', '0', '-all-time', '0'], check=True)
        image = out/(prefix+'.AppImage')
        with image.open('wb') as stream:
            for part in (inputs/runtime['name'], squash):
                with part.open('rb') as source:
                    shutil.copyfileobj(source, stream)
        image.chmod(0o755)
    result = {'version': build.VERSION, 'source_archive_sha256': digest(archive),
              'appimage_runtime_sha256': runtime['sha256'], 'python_qt_bundled': True,
              'files': {path.name: digest(path) for path in (run, image)}}
    (out/'linux-formats-receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    sums = out/'SHA256SUMS'
    lines = [line for line in sums.read_text().splitlines() if line.split('  ', 1)[-1] not in result['files']]
    sums.write_text('\n'.join(lines+[sha+'  '+name for name, sha in result['files'].items()])+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=build.ROOT/'artifacts')
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--mksquashfs', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(build.ROOT/'artifacts'):
        raise ValueError('Build outputs belong under artifacts/')
    print(json.dumps(build_formats(out, args.inputs.resolve(), args.mksquashfs.resolve()), indent=2))
