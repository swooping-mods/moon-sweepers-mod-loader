#!/usr/bin/env python3
"""Package the Linux desktop app and Proton bootstrap from a checked offline build."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

import build

LAUNCHER = b'''#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "${MOON_LOADER_PYTHON:-python3}" "$root/loader/main.py" "$@"
'''


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=build.ROOT/'artifacts')
    args=parser.parse_args(argv)
    out=args.output.resolve()
    if not out.is_relative_to(build.ROOT/'artifacts'):
        raise ValueError('Build output belongs under artifacts/')
    receipt=json.loads((out/'build-receipt.json').read_text())
    source=out/receipt['archive']
    if receipt['version']!=build.VERSION or hashlib.sha256(source.read_bytes()).hexdigest()!=receipt['sha256']:
        raise ValueError('Source archive differs from the checked build')
    with zipfile.ZipFile(source) as archive:
        files={name:archive.read(name) for name in archive.namelist()
               if name.startswith(('loader/','vendored/'))}
    files['Moon Sweepers Mod Loader']=LAUNCHER
    files['requirements.txt']=(build.ROOT/'loader/requirements.txt').read_bytes()
    files['README.md']=('''# Moon Sweepers Mod Loader for Linux x64

Requires Python 3.11+ and PySide6 6.8–6.x from your existing environment.
Extract the archive and run `./Moon\\ Sweepers\\ Mod\\ Loader`.
Use `MOON_LOADER_PYTHON=/path/to/python` to select an existing Python environment.

Squishy Plushie, Futuristic Courier, Power Poles, Debug Menu (F4), and their five
dependencies are included in the library, initially unchecked. Select the mods
and required frameworks, choose the supported Steam game, prepare files, then launch.
You can also import other .msmod packages.
Moon Sweepers uses Steam Proton; its native mod bootstrap is the included Windows DLL.
Merge `WINEDLLOVERRIDES="version=n,b" %command%` into the Steam launch options.
The desktop loader itself runs on Linux. See the repository README for save backups,
deployment recovery and compatibility.
''').encode()
    name=f'moon-sweepers-mod-loader-{build.VERSION}-linux-x64.tar.gz'
    destination=out/name
    with destination.open('wb') as stream:
        with gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for path,data in sorted(files.items()):
                    info=tarfile.TarInfo(path)
                    info.size=len(data);info.mtime=0;info.uid=info.gid=0
                    info.mode=0o755 if path=='Moon Sweepers Mod Loader' else 0o644
                    archive.addfile(info,io.BytesIO(data))
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    (out/'linux-build-receipt.json').write_text(json.dumps({
        'version':build.VERSION,'platform':'linux-x64','archive':name,'sha256':digest,
        'source_archive_sha256':receipt['sha256'],
        'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
        'requires':['Python 3.11+','PySide6 6.8–6.x','Steam Proton for the game'],
        'python_qt_bundled':False,'game_started':False},indent=2)+'\n')
    sums=out/'SHA256SUMS'
    lines=[line for line in sums.read_text().splitlines() if not line.endswith('  '+name)]
    sums.write_text('\n'.join(lines+[digest+'  '+name])+'\n')
    print(destination)


if __name__=='__main__':
    main()
