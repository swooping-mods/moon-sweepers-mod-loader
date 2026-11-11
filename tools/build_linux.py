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
from linux_runtime import payload as runtime_payload

LAUNCHER = b'''#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
exec "${MOON_LOADER_PYTHON:-$root/.runtime/python/bin/python3.13}" -I "$root/loader/main.py" "$@"
'''


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=build.ROOT/'artifacts')
    parser.add_argument('--inputs',type=Path,required=True,help='Previously reviewed hash-locked Linux inputs')
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
               if name.startswith(('loader/','vendored/')) and name!='vendored/appimage/runtime-x86_64'}
    files['Moon Sweepers Mod Loader']=LAUNCHER
    files.update(runtime_payload(args.inputs.resolve()))
    files['LICENSES/README.md']=(build.ROOT/'vendored/LINUX-LICENSES.md').read_bytes()
    files['THIRD_PARTY_NOTICES.md']=(build.ROOT/'vendored/THIRD_PARTY_NOTICES.md').read_bytes()
    files['requirements.txt']=(build.ROOT/'loader/requirements.txt').read_bytes()
    files['README.md']=('''# Moon Sweepers Mod Loader for Linux x64

Extract the archive and run `./Moon\\ Sweepers\\ Mod\\ Loader`.
Python and Qt are included. No Python environment setup or installer is needed.
Requires a modern Linux x64 desktop (glibc 2.38+, such as Ubuntu 24.04) and Steam Proton for the game.
The .run download extracts the same payload to your user cache and opens it.
The AppImage provides the same application; --appimage-extract-and-run works without FUSE.
Use `MOON_LOADER_PYTHON=/path/to/python` only to deliberately replace the runtime.

Squishy Plushie, Futuristic Courier, Power Poles, Debug Menu (F4), and their five
dependencies are included in the library, initially unchecked. Select the mods
and required frameworks, choose the supported Steam game, prepare files, then launch.
Use Add mods... for files, Add folder... for extracted mods, or drop files/folders
onto the window. Supports .msmod, packaged ZIPs and MarsSweepers 0.6.1 downloads.
MarsSweepers needs the supported BepInEx runtime and Private game copy mode.
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
                    info.mode=0o755 if path=='Moon Sweepers Mod Loader' or path.startswith('.runtime/python/bin/') else 0o644
                    archive.addfile(info,io.BytesIO(data))
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    (out/'linux-build-receipt.json').write_text(json.dumps({
        'version':build.VERSION,'platform':'linux-x64','archive':name,'sha256':digest,
        'source_archive_sha256':receipt['sha256'],
        'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
        'requires':['Linux x64 desktop; glibc 2.38+','Steam Proton for the game'],
        'python_qt_bundled':True,'game_started':False},indent=2)+'\n')
    sums=out/'SHA256SUMS'
    lines=[line for line in sums.read_text().splitlines() if not line.endswith('  '+name)]
    sums.write_text('\n'.join(lines+[digest+'  '+name])+'\n')
    print(destination)


if __name__=='__main__':
    main()
