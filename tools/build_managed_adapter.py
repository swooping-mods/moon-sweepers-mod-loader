#!/usr/bin/env python3
"""Compile the original managed adapter from an explicit verified host attachment."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'loader'))
from moonloader.managed import artifact_files
from bepinex_sources import sources
from bepinex_support import managed, compile_atomic


def build(attachment, dotnet, output, target='adapter'):
    from check_managed_sources import check
    check()
    if output.absolute() != output.resolve() or not output.resolve().is_relative_to(ROOT/'artifacts'):
        raise ValueError('Output must be an unaliased new directory under artifacts/')
    if output.exists():
        raise ValueError('Output already exists')
    old, payload = artifact_files(attachment)
    dotnet = dotnet.resolve()
    compilers = sorted((dotnet.parent/'sdk').glob('*/Roslyn/bincore/csc.dll'),
        key=lambda p: tuple(int(x) for x in p.parents[2].name.split('-')[0].split('.')))
    if not dotnet.is_file() or not compilers:
        raise ValueError('An existing .NET SDK is required; no download attempted')
    input_sources = sources(ROOT, target)
    identity = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in input_sources}
    references = [p for folder in ('dotnet', 'BepInEx/core')
                  for p in sorted((attachment/'files'/folder).glob('*.dll')) if managed(p)]
    if not references:
        raise ValueError('No checked managed reference closure')
    output.mkdir(parents=True)
    name = 'MoonLab.BepInExAdapter.dll' if target == 'adapter' else 'MoonLab.Generate.dll'
    binary = output/name
    command = [str(dotnet), str(compilers[-1]), '/nologo', '/noconfig', '/nostdlib+',
               '/target:'+('library' if target == 'adapter' else 'exe'), '/unsafe+', '/nullable:enable',
               '/langversion:latest', '/deterministic+', '/optimize+', '/out:'+str(binary),
               *['/reference:'+str(p) for p in references], *map(str, input_sources)]
    if compile_atomic(command, binary, identity, output/'compile.log'):
        raise ValueError('Managed compilation failed; inspect '+str(output/'compile.log'))
    # Re-read the complete host after compilation; input replacement cannot
    # silently produce an attachment from a different reference closure.
    current, current_payload = artifact_files(attachment)
    if current['files'] != old['files'] or current_payload != payload:
        raise ValueError('Host attachment changed during compilation')
    receipt = {'schema': 'moon-managed-source-build/v1', 'target': target,
               'sources': {p.relative_to(ROOT).as_posix(): sha for p, sha in identity.items()},
               'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
               'host_files': old['files'], 'game_or_plugin_executed': False}
    if target == 'adapter':
        payload['BepInEx/patchers/MoonLab.Adapter/'+name] = binary.read_bytes()
        root = output/'attachment'
        for member, data in payload.items():
            path = root/'files'/member
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        public = {key: value for key, value in old.items() if key in ('schema', 'version', 'limits')}
        public.update(inputs=receipt['sources'], adapter_sha256=receipt['binary_sha256'],
                      builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      files={n: hashlib.sha256(data).hexdigest() for n, data in payload.items()})
        (root/'receipt.json').write_text(json.dumps(public, indent=2)+'\n')
        artifact_files(root)
    else:
        runtimes = sorted((dotnet.parent/'shared/Microsoft.NETCore.App').iterdir(),
            key=lambda p: tuple(int(x) for x in p.name.split('-')[0].split('.')))
        version = runtimes[-1].name
        (output/'MoonLab.Generate.runtimeconfig.json').write_text(json.dumps({
            'runtimeOptions': {'tfm': 'net'+version.split('.')[0]+'.0',
                              'framework': {'name': 'Microsoft.NETCore.App', 'version': version}}}, indent=2)+'\n')
    (output/'source-build.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attachment', type=Path, required=True)
    parser.add_argument('--dotnet', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', choices=('adapter', 'diagnostic'), default='adapter')
    args = parser.parse_args()
    result = build(args.attachment, args.dotnet, args.output, args.target)
    print(json.dumps({'target': result['target'], 'sources': len(result['sources']),
                      'game_or_plugin_executed': False}, indent=2))


if __name__ == '__main__':
    main()
