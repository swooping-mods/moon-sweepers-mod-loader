#!/usr/bin/env python3
"""Audit managed metadata links without loading candidate assemblies as code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def negative_control(dotnet, cecil, output, image):
    """The auditor must reject a removed type/field, changed signature and getter."""
    output = Path(output).absolute()
    if output != output.resolve() or not output.is_relative_to(ROOT/'artifacts') or output.exists():
        raise ValueError('Use a new unaliased artifacts/ output directory')
    output.mkdir(parents=True)
    sdk = Path(dotnet).resolve().parent
    compiler = sorted((sdk/'sdk').glob('*/Roslyn/bincore/csc.dll'),
        key=lambda path: tuple(int(part) for part in path.parents[2].name.split('-')[0].split('.')))[-1]
    references = sorted((sdk/'packs/Microsoft.NETCore.App.Ref').glob('*/ref/net10.0'),
        key=lambda path: tuple(int(part) for part in path.parents[1].name.split('-')[0].split('.')))[-1]
    shutil.copyfile(ROOT/'tests/fixtures/static_managed_compat_negative.cs', output/'Fixture.cs')
    command = ['podman','run','--rm','--pull','never','--network','none','--userns','keep-id',
        '--user',str(os.getuid())+':'+str(os.getgid()),'--cap-drop','ALL','--security-opt','no-new-privileges',
        '--read-only','--tmpfs','/tmp','--memory','1G','--cpus','2','--pids-limit','128',
        '-e','HOME=/tmp','-e','DOTNET_CLI_TELEMETRY_OPTOUT=1','-e','DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1',
        '-v',str(sdk)+':/dotnet:ro','-v',str(output)+':/output:rw',
        '--entrypoint','/dotnet/dotnet',image,'/dotnet/'+compiler.relative_to(sdk).as_posix()]
    framework = ['/reference:/dotnet/'+path.relative_to(sdk).as_posix() for path in sorted(references.glob('*.dll'))]
    for name, define, target, additional in (
        ('legacy','LEGACY','old/MonoMod.Utils.dll',[]),
        ('modern','MODERN','new/MonoMod.Utils.dll',[]),
        ('consumer','CONSUMER','Consumer.dll',['/reference:/output/old/MonoMod.Utils.dll']),
    ):
        (output/target).parent.mkdir(parents=True,exist_ok=True)
        args=['/nologo','/nostdlib+','/target:library','/langversion:latest',
            '/define:'+define,'/out:/output/'+target,*framework,*additional,'/output/Fixture.cs']
        (output/(name+'.rsp')).write_text('\n'.join(args)+'\n')
        with (output/(name+'.log')).open('wb') as log:
            subprocess.run(command+['/noconfig','@/output/'+name+'.rsp'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    rejected=check(dotnet,cecil,output/'new',[output/'Consumer.dll'],output/'rejected',image)
    accepted=check(dotnet,cecil,output/'old',[output/'Consumer.dll'],output/'accepted',image)
    (output/'missing').mkdir()
    absent=check(dotnet,cecil,output/'missing',[output/'Consumer.dll'],output/'absent',image)
    row=rejected['modules'][0]
    categories=('missingTypes','missingMembers','signatureMismatches','missingImplementations')
    missing_assembly = not absent['success'] and any('MonoMod.Utils' in name for name in absent['modules'][0]['missingAssemblies'])
    success=not rejected['success'] and accepted['success'] and missing_assembly and all(len(row[name])==1 for name in categories)
    result={'success':success,'negative_counts':{name:len(row[name]) for name in categories},
            'unchanged_contract_accepted':accepted['success'],'changed_contract_rejected':not rejected['success'],
            'missing_assembly_rejected':missing_assembly}
    (output/'self-test.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def check(dotnet, cecil, dependencies, modules, output, image):
    output = Path(output).absolute()
    if output != output.resolve() or not output.is_relative_to(ROOT/'artifacts') or output.exists():
        raise ValueError('Use a new unaliased artifacts/ output directory')
    sdk = Path(dotnet).resolve().parent
    compiler = sorted((sdk/'sdk').glob('*/Roslyn/bincore/csc.dll'),
        key=lambda path: tuple(int(part) for part in path.parents[2].name.split('-')[0].split('.')))[-1]
    references = sorted((sdk/'packs/Microsoft.NETCore.App.Ref').glob('*/ref/net10.0'),
        key=lambda path: tuple(int(part) for part in path.parents[1].name.split('-')[0].split('.')))[-1]
    runtime = sorted((sdk/'shared/Microsoft.NETCore.App').iterdir(),
        key=lambda path: tuple(int(part) for part in path.name.split('-')[0].split('.')))[-1].name
    source = ROOT/'tests/fixtures/static_managed_compat_audit.cs'
    output.mkdir(parents=True)
    shutil.copyfile(source, output/'Audit.cs')
    shutil.copyfile(cecil, output/'Mono.Cecil.dll')
    (output/'Audit.runtimeconfig.json').write_text(json.dumps({'runtimeOptions': {
        'tfm':'net10.0', 'framework':{'name':'Microsoft.NETCore.App','version':runtime}}})+'\n')
    args = ['/nologo','/nostdlib+','/target:exe','/langversion:latest',
            '/out:/output/Audit.dll','/reference:/output/Mono.Cecil.dll']
    args += ['/reference:/dotnet/'+path.relative_to(sdk).as_posix() for path in sorted(references.glob('*.dll'))]
    args += ['/output/Audit.cs']
    (output/'compile.rsp').write_text('\n'.join(args)+'\n')
    supplied = Path(dependencies).resolve()
    dependencies = output/'dependencies'; dependencies.mkdir()
    for path in sorted(supplied.glob('*.dll')):
        if path.is_symlink(): raise ValueError('Alias in metadata dependencies')
        shutil.copyfile(path, dependencies/path.name)
    # A complete AssemblyRef check also needs platform metadata. Prefer actual
    # supplied runtime members, supplementing only absent platform names with
    # the explicitly selected installed SDK's shared runtime.
    for path in sorted((sdk/'shared/Microsoft.NETCore.App'/runtime).glob('*.dll')):
        if not (dependencies/path.name).exists(): shutil.copyfile(path, dependencies/path.name)
    modules = [Path(path).resolve() for path in modules]
    command = ['podman','run','--rm','--pull','never','--network','none','--userns','keep-id',
        '--user',str(os.getuid())+':'+str(os.getgid()),'--cap-drop','ALL','--security-opt','no-new-privileges',
        '--read-only','--tmpfs','/tmp','--memory','1G','--cpus','2','--pids-limit','128',
        '-e','HOME=/tmp','-e','DOTNET_CLI_TELEMETRY_OPTOUT=1','-e','DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1',
        '-v',str(sdk)+':/dotnet:ro','-v',str(output)+':/output:rw','-v',str(dependencies)+':/dependencies:ro']
    parents = list(dict.fromkeys(path.parent for path in modules))
    for index, parent in enumerate(parents): command += ['-v',str(parent)+':/modules'+str(index)+':ro']
    command += ['--entrypoint','/dotnet/dotnet',image]
    with (output/'audit.log').open('wb') as log:
        compiled = subprocess.run(command+['/dotnet/'+compiler.relative_to(sdk).as_posix(),
            '/noconfig','@/output/compile.rsp'],stdout=log,stderr=subprocess.STDOUT,timeout=90)
        module_args = ['/modules'+str(parents.index(path.parent))+'/'+path.name for path in modules]
        observed = subprocess.run(command+['/output/Audit.dll','/dependencies','/output/links.json',*module_args],
            stdout=log,stderr=subprocess.STDOUT,timeout=90) if compiled.returncode == 0 else compiled
    rows = json.loads((output/'links.json').read_text()) if (output/'links.json').is_file() else []
    result = {'success':observed.returncode==0 and len(rows)==len(modules), 'exit_code':observed.returncode,
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'inputs':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in modules},
        'modules':rows,'limits':['Metadata only; candidate assemblies are not loaded as code',
            'Checks named detour/compatibility dependency scopes, not dynamic string lookup or native ABI behavior',
            'Inherited generic-base argument remapping and custom modifier identity need separate qualification']}
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dotnet',type=Path,required=True)
    parser.add_argument('--cecil',type=Path,required=True)
    parser.add_argument('--dependencies',type=Path)
    parser.add_argument('--module',type=Path,action='append')
    parser.add_argument('--self-test',action='store_true',help='Run changed and unchanged synthetic metadata controls')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--image',required=True,help='Existing reviewed container image; never pulled')
    args=parser.parse_args()
    if args.self_test: result=negative_control(args.dotnet,args.cecil,args.output,args.image)
    else:
        if args.dependencies is None or not args.module: parser.error('--dependencies and --module are required without --self-test')
        result=check(args.dotnet,args.cecil,args.dependencies,args.module,args.output,args.image)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['success'] else 1)
