#!/usr/bin/env python3
"""Verify the Linux archive and launch its actual script using temporary data."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile

import build
from mod_bundle import payload as bundled_payload


def check(out, gui=False):
    receipt=json.loads((out/'linux-build-receipt.json').read_text())
    path=out/receipt['archive']
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if receipt['version']!=build.VERSION or digest!=receipt['sha256']:
        raise ValueError('Linux archive identity mismatch')
    with tempfile.TemporaryDirectory(prefix='Moon loader Linux check ') as temporary:
        root=Path(temporary)
        seen=set()
        with tarfile.open(path) as archive:
            for entry in archive:
                name=PurePosixPath(entry.name)
                if (not entry.isfile() or name.is_absolute() or '..' in name.parts
                        or entry.name in seen or '\\' in entry.name):
                    raise ValueError('Unsupported Linux archive member: '+entry.name)
                seen.add(entry.name)
                data=archive.extractfile(entry).read()
                if hashlib.sha256(data).hexdigest()!=receipt['files'].get(entry.name):
                    raise ValueError('Linux archive file mismatch: '+entry.name)
                target=root/entry.name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data);target.chmod(entry.mode)
        if seen!=set(receipt['files']):
            raise ValueError('Linux archive inventory mismatch')
        if any(name.startswith('vendored/managed-build-inputs/') for name in seen):
            raise ValueError('Upstream build input leaked into desktop bundle')
        required={'Moon Sweepers Mod Loader','loader/main.py','loader/runtime/receipt.json',
                  'loader/runtime/windows-x64/version.dll','vendored/api/snapshot.json','README.md'}
        linux_lock=json.loads((root/'vendored/linux-runtime.lock.json').read_text())
        required.update('.runtime/desktop-libs/'+name for name in linux_lock['desktop_libraries'])
        if not required<=seen:
            raise ValueError('Missing Linux loader files')
        bundled = bundled_payload(root / 'loader/packages')
        from managed_bundle import verify_bundle
        managed_receipt = verify_bundle(root/'loader')
        env={**os.environ,
             'XDG_DATA_HOME':str(root/'temporary-user-data'),'QT_QPA_PLATFORM':'offscreen'}
        env.pop('MOON_LOADER_PYTHON', None)
        command=[str(root/'Moon Sweepers Mod Loader')]
        subprocess.run(command+['--help'],env=env,check=True,timeout=30)
        desktop_env={**env,'QT_QPA_PLATFORM':'xcb'}
        subprocess.run([str(root/'.runtime/python/bin/python3.13'),'-I','-c',
            'import sys; sys.path.insert(0, sys.argv[1]); from moonloader.linux_desktop import prepare; prepare()',
            str(root/'loader')],env=desktop_env,check=True,timeout=30)
        if gui:
            subprocess.run(command+['--smoke-test'],env=env,check=True,timeout=30)
    result={'success':True,'version':build.VERSION,'sha256':digest,
            'bundled_mods_checked':len(bundled),
            'managed_coreclr_version':managed_receipt['coreclr_version'],
            'files_checked':len(seen),'actual_launcher_cli_passed':True,
            'portable_desktop_libraries_passed':True,
            'gui_smoke_passed':gui,'game_started':False,
            'limits':[] if gui else ['Linux GUI smoke requires installed PySide6; CLI launcher checked here.']}
    (out/'linux-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=build.ROOT/'artifacts')
    parser.add_argument('--gui',action='store_true',help='Also exercise installed PySide6 with temporary data and no game')
    args=parser.parse_args()
    print(json.dumps(check(args.output.resolve(),args.gui),indent=2))
