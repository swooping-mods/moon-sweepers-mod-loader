#!/usr/bin/env python3
"""Offline portable Windows packaging from exact, previously reviewed publisher files."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile
import xml.etree.ElementTree as ET
import build

ROOT = build.ROOT


def put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True, help='Reviewed inert download directory; no downloads occur')
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'vendored/windows-runtime.lock.json').read_text())
    for item in lock['files']:
        path = args.inputs / item['name']
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Input hash mismatch: ' + item['name'])
    out = args.output.resolve()
    if not out.is_relative_to(ROOT/'artifacts'):
        raise ValueError('Build outputs belong under this project artifacts/')
    build.main(['--output', str(out)])
    work = out / 'build'
    tools = build.find_tools()
    cc, link, dlltool = (tools[name] for name in ('clang', 'lld-link', 'llvm-dlltool'))
    for name in ('kernel32', 'user32'):
        subprocess.run([dlltool, '-m', 'i386:x86-64', '-d', str(ROOT / f'runtime/loader/desktop-{name}.def'), '-l', str(work / f'desktop-{name}.lib')], check=True)
    subprocess.run([cc, '--target=x86_64-pc-windows-msvc', '-O2', '-Wall', '-Wextra', '-Werror', '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-c', str(ROOT / 'runtime/loader/desktop.c'), '-o', str(work / 'desktop.obj')], check=True)
    subprocess.run([link, '/entry:mainCRTStartup', '/subsystem:windows', '/nodefaultlib', '/machine:x64', '/timestamp:0', '/out:' + str(work / 'Mod Loader.exe'), str(work / 'desktop.obj'), str(work / 'desktop-kernel32.lib'), str(work / 'desktop-user32.lib')], check=True)
    dest = out / 'moon-sweepers-mod-loader-windows-x64'
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()
    (dest / 'LICENSES').mkdir()
    # Retain the source layout for SDK resolution and user-replaceable LGPL libraries.
    with zipfile.ZipFile(out / f'moon-sweepers-mod-loader-{build.VERSION}-source.zip') as z:
        for n in z.namelist():
            if n.startswith(('loader/', 'vendored/')):
                put(dest, n, z.read(n))
    shutil.copy2(work / 'Mod Loader.exe', dest / 'Mod Loader.exe')
    for item in lock['files']:
        path = args.inputs / item['name']
        if item['role'] == 'python':
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    put(dest, 'python/' + n, z.read(n))
                put(dest, 'LICENSES/Python/LICENSE.txt', z.read('LICENSE.txt'))
        elif item['role'] == 'wheel':
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    if n in lock['wheel_members']:
                        put(dest, 'python/' + n, z.read(n))
        elif item['role'] == 'source':
            # Ship source in the same ZIP, so recipients do not depend on a future offer.
            shutil.copy2(path, dest / 'LICENSES' / path.name)
            with tarfile.open(path) as t:
                for member in t.getmembers():
                    name = member.name
                    if member.isfile() and ('/LICENSES/' in name or 'LICENSE' in Path(name).name.upper() or Path(name).name in ('COPYING', 'COPYRIGHT', 'qt_attribution.json')):
                        put(dest, 'LICENSES/upstream/' + name, t.extractfile(member).read())
        elif item['role'] == 'license':
            shutil.copy2(path, dest / 'LICENSES' / path.name)
            with zipfile.ZipFile(path) as z:
                document = ET.fromstring(z.read('word/document.xml'))
                text = '\n'.join(''.join(t.itertext()) for t in document.iter(
                    '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
                put(dest, 'LICENSES/' + path.stem + '.txt', text.encode())
    python_tag = lock['python_tag']
    put(dest, f'python/{python_tag}._pth', (f'{python_tag}.zip\n.\n../loader\n../vendored/api/python\n').encode())
    put(dest, 'python/qt.conf', b'[Paths]\nPrefix=PySide6\nPlugins=plugins\n')
    put(dest, 'Start-Mod-Loader.cmd', b'@echo off\r\ncd /d "%~dp0"\r\n"Mod Loader.exe" %*\r\n')
    shutil.copy2(ROOT / 'vendored/THIRD_PARTY_NOTICES.md', dest / 'THIRD_PARTY_NOTICES.md')
    shutil.copy2(ROOT / 'vendored/windows-runtime.lock.json', dest / 'LICENSES/runtime-manifest.json')
    shutil.copy2(ROOT / 'vendored/WINDOWS-LICENSES.md', dest / 'LICENSES/README.md')
    put(dest, 'README.txt', b'Moon Sweepers Mod Loader - Windows x64\r\n\r\nExtract the entire ZIP, then double-click Mod Loader.exe. No Python install needed.\r\nImport .msmod packages, select your supported game installation, Prepare files, then Launch.\r\nThe game and mods are not included. Application data uses LOCALAPPDATA/MoonLab/Loader.\r\nFor UI inspection: "Mod Loader.exe" --no-launch\r\n\r\nBundled Python, PySide6/Shiboken and Qt notices, licenses and source: LICENSES/.\r\nQt/PySide use LGPLv3. You may replace these libraries and debug their modifications.\r\nSee THIRD_PARTY_NOTICES.md and LICENSES/README.md.\r\n')
    archive = out / f'moon-sweepers-mod-loader-{build.VERSION}-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(dest.rglob('*')):
            if p.is_file():
                info = zipfile.ZipInfo(p.relative_to(dest).as_posix(), (2026, 11, 10, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, p.read_bytes())
    receipt = {'version': build.VERSION, 'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'bytes': archive.stat().st_size, 'input_lock': lock, 'limits': ['Native Windows GUI/game execution not performed on Linux build host', 'Unsigned launcher; no signing certificate supplied']}
    (out / 'windows-build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (out / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in [out / f'moon-sweepers-mod-loader-{build.VERSION}-source.zip', archive]))
    print(archive)


if __name__ == '__main__':
    main()
