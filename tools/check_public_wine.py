#!/usr/bin/env python3
"""Run the built DLL on a synthetic EXE in a new private Wine prefix, offline."""
import argparse
from audio_policy import audio_environment
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import build

ROOT = build.ROOT
sys.path.insert(0, str(ROOT/'loader'))
from moonloader.discovery import Installation
from moonloader.public import config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wine',type=Path,required=True,help='Previously installed/reviewed Wine executable')
    parser.add_argument('--portable',type=Path,help='Also smoke-check this built portable folder and actual launcher')
    parser.add_argument('--build-dir',type=Path,default=ROOT/'artifacts/build')
    args = parser.parse_args()
    if not os.environ.get('GAMESCOPE_WAYLAND_DISPLAY'):
        raise ValueError('Use private headless Gamescope for Wine initialization')
    tools = build.find_tools(); native = args.build_dir.resolve()
    if not native.is_relative_to(ROOT/'artifacts'):
        raise ValueError('Native diagnostic inputs must belong to this project artifacts/')
    if not (native/'version.dll').is_file(): raise ValueError('Run tools/build.py first')
    root = ROOT/'artifacts'/('public-wine-'+str(time.time_ns())); root.mkdir()
    subprocess.run([tools['clang'],'--target=x86_64-pc-windows-msvc','-O2','-Wall','-Wextra','-Werror',
                    '-ffreestanding','-fno-builtin','-fno-stack-protector','-c',str(ROOT/'tests/public_wine_probe.c'),
                    '-o',str(root/'probe.obj')],check=True)
    subprocess.run([tools['lld-link'],'/entry:mainCRTStartup','/subsystem:console','/nodefaultlib','/machine:x64',
                    '/out:'+str(root/'probe.exe'),str(root/'probe.obj'),str(native/'kernel32.lib')],check=True)
    env = {k:v for k,v in os.environ.items() if not k.startswith('MOONLAB_')}
    env.update(WINEPREFIX=str(root/'pfx'),WINEDLLOVERRIDES='version=n,b;mscoree,mshtml=',WINEDEBUG='+debugstr',
               WINEFSYNC='0',WINENTSYNC='0',MOONLAB_PROFILE_ROOT='C:\\must-not-be-used')
    env = audio_environment(env)
    cases = {}
    for name in ('missing','disabled','malformed','unknown-build'):
        folder = root/name; folder.mkdir(); (folder/'MoonLab').mkdir()
        (folder/'MoonLab/owner.json').write_text('{}\n')
        shutil.copy2(root/'probe.exe',folder/'MoonSweepers.exe'); shutil.copy2(native/'version.dll',folder/'version.dll')
        (folder/'GameAssembly.dll').write_bytes(b'unknown synthetic game input')
        if name != 'missing':
            value = config(Installation(str(folder),'steam'),'a'*32,['test-mod'],name!='disabled')
            if name == 'malformed': value=b'bad-schema\n'
            (folder/'MoonLab/active.txt').write_bytes(value)
        result = subprocess.run([str(args.wine),str(folder/'MoonSweepers.exe')],cwd=folder,env=env,
                                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        (folder/'probe.log').write_bytes(result.stdout)
        success = result.returncode == 0 and b'synthetic public DLL survived' in result.stdout and b'MoonLab: mods disabled' in result.stdout
        cases[name]={'success':success,'exit':result.returncode}
    if args.portable:
        folder = args.portable.resolve()
        commands = {'portable-runtime': [folder/'python/python.exe', folder/'loader/check_portable_windows.py'],
                    'portable-launcher': [folder/'Mod Loader.exe', '--smoke-test']}
        for name, command in commands.items():
            log = root/(name+'.log')
            with log.open('wb') as output:
                result = subprocess.run([str(args.wine),*map(str,command)],cwd=folder,env=env,
                                        stdout=output,stderr=subprocess.STDOUT,timeout=60)
            success = result.returncode == 0
            if name == 'portable-runtime': success = success and b'no game started' in log.read_bytes()
            cases[name] = {'success':success,'exit':result.returncode}
    server = args.wine.with_name('wineserver')
    cleanup = False
    if server.is_file():
        stop = subprocess.run([str(server), '-k'], env=env, timeout=10)
        wait = subprocess.run([str(server), '-w'], env=env, timeout=10)
        cleanup = stop.returncode == 0 and wait.returncode == 0
    record={'success':all(row['success'] for row in cases.values()),'cases':cases,'game_started':False,
            'owned_prefix_cleanup':cleanup,
            'runtime_sha256':hashlib.sha256((native/'version.dll').read_bytes()).hexdigest(),
            'runtime':'Existing Wine; fresh private prefix; actual built Windows DLL and BCrypt',
            'limits':['Synthetic EXE only; no supported-game successful mod startup','No native Windows, Steam, Cloud or co-op qualification']}
    (root/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(root/'result.json')
    return 0 if record['success'] else 1


if __name__ == '__main__': raise SystemExit(main())
