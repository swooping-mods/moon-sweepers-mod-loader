#!/usr/bin/env python3
"""Exercise the reviewed Harmony overlay in a bounded, networkless .NET host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from modern_harmony import ROOT, payload


def check(inputs, dotnet, output, image):
    output = Path(output).absolute()
    if output != output.resolve() or not output.is_relative_to(ROOT/'artifacts') or output.exists():
        raise ValueError('Use a new unaliased artifacts/ output directory')
    sdk = Path(dotnet).resolve().parent
    compiler = sorted((sdk/'sdk').glob('*/Roslyn/bincore/csc.dll'),
        key=lambda p: tuple(int(x) for x in p.parents[2].name.split('-')[0].split('.')))[-1]
    references = sorted((sdk/'packs/Microsoft.NETCore.App.Ref').glob('*/ref/net10.0'),
        key=lambda p: tuple(int(x) for x in p.parents[1].name.split('-')[0].split('.')))[-1]
    runtimes = sorted((sdk/'shared/Microsoft.NETCore.App').iterdir(),
        key=lambda p: tuple(int(x) for x in p.name.split('-')[0].split('.')))
    version = runtimes[-1].name
    if version.split('.')[0] != '10': raise ValueError('This qualification requires an installed .NET 10 runtime')
    files = payload(inputs)
    output.mkdir(parents=True)
    for name, data in files.items():
        if name.startswith('BepInEx/core/'): (output/Path(name).name).write_bytes(data)
    source = ROOT/'tests/fixtures/modern_harmony_probe.cs'
    shutil.copyfile(source, output/'Probe.cs')
    (output/'Probe.runtimeconfig.json').write_text(json.dumps({'runtimeOptions': {
        'tfm':'net10.0', 'framework':{'name':'Microsoft.NETCore.App','version':version}}})+'\n')
    arguments = ['/nologo', '/nostdlib+', '/target:exe', '/langversion:latest',
                 '/out:/output/Probe.dll', '/reference:/output/0Harmony.dll']
    arguments += ['/reference:/dotnet/' + p.relative_to(sdk).as_posix() for p in sorted(references.glob('*.dll'))]
    arguments += ['/output/Probe.cs']
    (output/'compile.rsp').write_text('\n'.join(arguments)+'\n')
    command = ['podman', 'run', '--rm', '--pull', 'never', '--network', 'none', '--userns', 'keep-id',
               '--user', str(os.getuid())+':'+str(os.getgid()),
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--read-only',
               '--tmpfs', '/tmp', '--memory', '1G', '--cpus', '2', '--pids-limit', '128',
               '-e', 'HOME=/tmp', '-e', 'DOTNET_CLI_TELEMETRY_OPTOUT=1',
               '-e', 'DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1',
               '-v', str(sdk)+':/dotnet:ro', '-v', str(output)+':/output:rw',
               '--entrypoint', '/dotnet/dotnet', image]
    with (output/'host.log').open('wb') as log:
        compiled = subprocess.run(command+['/dotnet/'+compiler.relative_to(sdk).as_posix(),
                                  '/noconfig', '@/output/compile.rsp'], stdout=log, stderr=subprocess.STDOUT, timeout=90)
        run = subprocess.run(command+['/output/Probe.dll'], stdout=log, stderr=subprocess.STDOUT,
                             timeout=60) if compiled.returncode == 0 else compiled
    text = (output/'host.log').read_text(errors='replace')
    success = run.returncode == 0 and 'patch-roundtrip-passed' in text
    record = {'success':success, 'runtime':version, 'exit_code':run.returncode,
              'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'inputs':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()},
              'scope':'Actual Harmony prefix/postfix, 1000 calls, GC and unpatch in original synthetic Linux host',
              'limits':['No Windows, Unity, multiplayer, or user-mod execution']}
    (output/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    if not success: raise ValueError('Modern Harmony host check failed; inspect '+str(output/'host.log'))
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--dotnet', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', required=True, help='Existing reviewed container image; no image is built or pulled')
    args = parser.parse_args()
    print(json.dumps(check(args.inputs,args.dotnet,args.output,args.image),indent=2))
