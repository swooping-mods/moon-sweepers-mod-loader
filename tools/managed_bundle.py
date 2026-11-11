"""Build the checked managed host offline; no plugin or game input is included."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import zipfile

from bepinex_sources import sources
from bepinex_support import compile_atomic, managed

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'vendored/managed-runtime.lock.json'
CONFIG = b'''[IL2CPP]
UpdateInteropAssemblies = false
UnityBaseLibrariesSource =
PreloadIL2CPPInteropAssemblies = false
ScanMethodRefs = false

[Logging]
UnityLogListening = false

[Logging.Console]
Enabled = false
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive_files(path):
    """Bounded portable ZIP reader; no archive-supplied code is executed."""
    files = {}; folded = set(); total = 0
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            name = member.filename; parts = PurePosixPath(name)
            if (parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name
                    or not parts.parts or name.casefold() in folded
                    or member.flag_bits & 1 or (member.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Unsupported managed input member: ' + name)
            folded.add(name.casefold()); total += member.file_size
            if len(folded) > 20000 or total > 512 * 1024 * 1024 or member.file_size > 128 * 1024 * 1024:
                raise ValueError('Managed archive exceeds bounded input size')
            if not member.is_dir(): files[name] = archive.read(member)
    return files


def read_inputs(folder):
    lock = json.loads(LOCK.read_text())
    result = {}
    for item in lock['files']:
        if Path(item['name']).name != item['name']: raise ValueError('Invalid managed input filename')
        path = Path(folder) / item['name']
        if path.is_symlink() or not path.is_file(): raise ValueError('Missing checked managed input: ' + item['name'])
        data = path.read_bytes()
        if digest(data) != item['sha256']: raise ValueError('Managed input changed: ' + item['name'])
        result[item['role']] = (item, data) if item['role'] != 'source' else result.get('source', []) + [(item, data)]
    if set(result) != {'bepinex', 'coreclr', 'source'}: raise ValueError('Incomplete managed runtime lock')
    return lock, result


def host_compatibility(dotnet, compiler, references, upstream, modern, work):
    """Preserve the be.791 host API while using the maintained detour backend."""
    source = ROOT/'runtime/managed-host'
    helper_sources = [source/'LegacyDetourCompatibility.cs', source/'ILegacyDetour.cs']
    patcher_source = source/'PatchLegacyHost.cs'
    checks_source = ROOT/'tests/ManagedHostCompatibilityChecks.cs'
    identities = {p: digest(p.read_bytes()) for p in [*helper_sources, patcher_source, checks_source]}
    common = [str(dotnet), str(compiler), '/nologo', '/noconfig', '/nostdlib+', '/nullable:enable',
              '/langversion:latest', '/deterministic+', '/optimize+', '/pathmap:' + str(ROOT) + '=/_/']
    common += ['/reference:' + str(p) for p in references]
    helper = work/'MoonLab.ManagedHostCompat.dll'
    patcher = work/'PatchLegacyHost.dll'
    if compile_atomic(common + ['/target:library', '/out:' + str(helper), *map(str, helper_sources)],
                      helper, identities, work/'compat-helper-compile.log'):
        raise ValueError('Managed host compatibility helper compilation failed')
    if compile_atomic(common + ['/target:exe', '/out:' + str(patcher), str(patcher_source)],
                      patcher, identities, work/'compat-patcher-compile.log'):
        raise ValueError('Managed host compatibility patcher compilation failed')
    # Only this original offline tool is executed; upstream libraries are read
    # as metadata, never initialized in the build process.
    (work/'Mono.Cecil.dll').write_bytes(upstream['BepInEx/core/Mono.Cecil.dll'])
    runtimes = sorted((dotnet.parent/'shared/Microsoft.NETCore.App').iterdir(),
                      key=lambda p: tuple(int(x) for x in p.name.split('-')[0].split('.')))
    version = runtimes[-1].name
    (work/'PatchLegacyHost.runtimeconfig.json').write_text(json.dumps({'runtimeOptions': {
        'tfm':'net' + version.split('.')[0] + '.0',
        'framework':{'name':'Microsoft.NETCore.App', 'version':version}}})+'\n')
    checks = work/'CompatibilityChecks.dll'
    if compile_atomic(common + ['/reference:' + str(helper), '/target:exe', '/out:' + str(checks), str(checks_source)],
                      checks, identities, work/'compat-checks-compile.log'):
        raise ValueError('Managed host compatibility checks did not compile')
    (work/'CompatibilityChecks.runtimeconfig.json').write_bytes((work/'PatchLegacyHost.runtimeconfig.json').read_bytes())
    with (work/'compat-checks.log').open('wb') as log:
        subprocess.run([str(dotnet), str(checks)], stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=30)
    if b'Managed native trampoline checks passed' not in (work/'compat-checks.log').read_bytes():
        raise ValueError('Managed native trampoline checks did not complete')
    legacy_utils = work/'original-MonoMod.Utils.dll'
    legacy_utils.write_bytes(upstream['BepInEx/core/MonoMod.Utils.dll'])
    patched = {'BepInEx/core/' + helper.name: helper.read_bytes()}
    names = ('BepInEx.Core.dll', 'BepInEx.Preloader.Core.dll', 'BepInEx.Unity.Common.dll',
             'BepInEx.Unity.IL2CPP.dll', 'MonoMod.Utils.dll')
    with (work/'compat-patch.log').open('wb') as log:
        for name in names:
            original = work/('original-' + name); original.write_bytes(upstream['BepInEx/core/' + name])
            target = 'MoonLab.LegacyMonoMod.Utils.dll' if name == 'MonoMod.Utils.dll' else name
            output = work/target
            subprocess.run([str(dotnet), str(patcher), str(original), str(legacy_utils), str(output)],
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30,
                           env={**__import__('os').environ, 'DOTNET_CLI_TELEMETRY_OPTOUT':'1'})
            patched['BepInEx/core/' + target] = output.read_bytes()
    if any(digest(p.read_bytes()) != value for p, value in identities.items()):
        raise ValueError('Managed compatibility sources changed during build')
    for path in [*helper_sources, patcher_source]:
        patched['BepInEx/third-party-sources/managed-host-compat/' + path.name] = path.read_bytes()
    return patched, {p.relative_to(ROOT).as_posix(): value for p, value in identities.items()}


def audit_host(files, dotnet, compiler, work):
    """Resolve scoped metadata links before any managed game startup is attempted."""
    audit_source = ROOT/'tests/fixtures/static_managed_compat_audit.cs'
    source_hash = digest(audit_source.read_bytes())
    core = work/'audit-core'; core.mkdir(exist_ok=True)
    for name, data in files.items():
        if name.startswith('BepInEx/core/') and name.endswith('.dll'):
            (core/Path(name).name).write_bytes(data)
    # The reviewed BCL implementation assemblies supply metadata references;
    # candidate dependencies themselves are never imported as executable code.
    references = []
    for name, data in files.items():
        if name.startswith('dotnet/') and name.endswith('.dll'):
            target = work/('audit-ref-' + Path(name).name); target.write_bytes(data)
            if managed(target):
                references.append(target)
                (core/Path(name).name).write_bytes(data)
    audit = work/'StaticManagedAudit.dll'
    command = [str(dotnet), str(compiler), '/nologo', '/noconfig', '/nostdlib+', '/target:exe',
               '/langversion:latest', '/deterministic+', '/optimize+', '/out:' + str(audit),
               '/reference:' + str(work/'Mono.Cecil.dll'),
               *['/reference:' + str(path) for path in references], str(audit_source)]
    if compile_atomic(command, audit, {audit_source: source_hash}, work/'static-audit-compile.log'):
        raise ValueError('Managed compatibility metadata audit did not compile')
    (work/'StaticManagedAudit.runtimeconfig.json').write_bytes((work/'PatchLegacyHost.runtimeconfig.json').read_bytes())
    names = tuple(sorted(Path(name).name for name in files
                         if name.startswith('BepInEx/core/') and name.endswith('.dll') and managed(core/Path(name).name)))
    with (work/'static-audit.log').open('wb') as log:
        subprocess.run([str(dotnet), str(audit), str(core), str(work/'static-links.json'),
                        *[str(core/name) for name in names]], stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=40)
    rows = json.loads((work/'static-links.json').read_text())
    if len(rows) != len(names): raise ValueError('Managed metadata audit omitted a module')
    return source_hash


def payload(inputs, dotnet, work):
    """Compile our adapter against reviewed references, replace the retired CLR."""
    from check_managed_sources import check
    check()
    lock, selected = read_inputs(inputs)
    dotnet = Path(dotnet or shutil.which('dotnet') or '').absolute()
    if not dotnet.is_file(): raise ValueError('Use an installed .NET SDK with --dotnet; no SDK is downloaded')
    # Standard SDK layouts place Roslyn beside dotnet. A PATH symlink is resolved
    # only for the compiler installation, never for acquired runtime payloads.
    dotnet = dotnet.resolve()
    compilers = sorted((dotnet.parent / 'sdk').glob('*/Roslyn/bincore/csc.dll'),
                       key=lambda p: tuple(int(x) for x in p.parents[2].name.split('-')[0].split('.')))
    if not compilers: raise ValueError('Installed .NET SDK compiler is missing')
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    upstream = archive_files(Path(inputs) / selected['bepinex'][0]['name'])
    framework = archive_files(Path(inputs) / selected['coreclr'][0]['name'])
    prefixes = ('runtimes/win-x64/native/', 'runtimes/win-x64/lib/net10.0/')
    runtime = {name.rsplit('/', 1)[-1]: data for name, data in framework.items() if name.startswith(prefixes)}
    if 'coreclr.dll' not in runtime or 'System.Private.CoreLib.dll' not in runtime:
        raise ValueError('Incomplete maintained CoreCLR runtime')
    runtime.update({name: framework[name] for name in ('LICENSE.TXT', 'THIRD-PARTY-NOTICES.TXT', 'Microsoft.NETCore.App.Runtime.win-x64.nuspec')})
    if {name: digest(data) for name, data in runtime.items()} != lock['coreclr_files']:
        raise ValueError('CoreCLR member inventory differs from the reviewed runtime')
    original_sources = sources(ROOT, 'adapter')
    identities = {p: digest(p.read_bytes()) for p in original_sources}
    from modern_harmony import payload as modern_payload
    modern = modern_payload(inputs)
    with tempfile.TemporaryDirectory(prefix='managed references ', dir=work) as temporary:
        refs = []
        for name, data in upstream.items():
            if name.endswith('.dll') and (name.startswith('dotnet/') or name.startswith('BepInEx/core/')):
                target = Path(temporary) / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
                if managed(target): refs.append(target)
        binary = work / 'MoonLab.BepInExAdapter.dll'
        command = [str(dotnet), str(compilers[-1]), '/nologo', '/noconfig', '/nostdlib+',
                   '/target:library', '/unsafe+', '/nullable:enable', '/langversion:latest',
                   '/deterministic+', '/optimize+', '/pathmap:' + str(ROOT) + '=/_/', '/out:' + str(binary),
                   *['/reference:' + str(p) for p in sorted(refs)], *map(str, original_sources)]
        if compile_atomic(command, binary, identities, work / 'managed-compile.log'):
            raise ValueError('Managed adapter compilation failed; inspect ' + str(work / 'managed-compile.log'))
        compatibility, compatibility_sources = host_compatibility(dotnet, compilers[-1], refs, upstream, modern, work)
    files = {name: data for name, data in upstream.items() if not name.startswith('dotnet/')}
    for name, item in lock['application_libraries'].items():
        data = upstream[item['source']]
        if digest(data) != item['sha256']: raise ValueError('Reviewed managed application library changed: ' + name)
        files['BepInEx/core/' + name] = data
    files.update({'dotnet/' + name: data for name, data in runtime.items()})
    files['BepInEx/config/BepInEx.cfg'] = CONFIG
    files['BepInEx/patchers/MoonLab.Adapter/MoonLab.BepInExAdapter.dll'] = binary.read_bytes()
    files.update(modern)
    files.update(compatibility)
    for item, data in selected['source']:
        files['BepInEx/third-party-sources/' + item['name']] = data
    from bepinex_notices import payload as notices
    files.update(notices())
    app_notices = ROOT/'vendored/managed-application-notices'
    if {path.name for path in app_notices.iterdir()} != set(lock['application_notice_files']):
        raise ValueError('Managed application notice inventory differs from the lock')
    for name, expected in lock['application_notice_files'].items():
        path = app_notices/name
        if path.is_symlink() or digest(path.read_bytes()) != expected:
            raise ValueError('Managed application notice changed: ' + name)
        files['BepInEx/third-party-sources/application-dependencies/' + name] = path.read_bytes()
    for forbidden in ('BepInEx/plugins/', 'BepInEx/interop/', 'BepInEx/unity-libs/'):
        if any(name.startswith(forbidden) for name in files): raise ValueError('Managed host unexpectedly includes game/plugin payload')
    # Verify acquired inputs once more after compilation before sealing output.
    if read_inputs(inputs) != (lock, selected): raise ValueError('Managed inputs changed during compilation')
    if modern_payload(inputs) != modern: raise ValueError('Modern detour inputs changed during compilation')
    audit_hash = audit_host(files, dotnet, compilers[-1], work)
    receipt = {'schema': 'moonlab-bepinex-build/v1', 'version': lock['bepinex_version'],
               'coreclr_version': lock['coreclr_version'], 'input_lock_sha256': digest(LOCK.read_bytes()),
               'compiler_sdk_version': compilers[-1].parents[2].name,
               'compiler_sha256': digest(compilers[-1].read_bytes()),
               'dotnet_host_sha256': digest(dotnet.read_bytes()),
               'inputs': {p.relative_to(ROOT).as_posix(): value for p, value in identities.items()},
               'compatibility_sources': compatibility_sources,
               'compatibility_audit_sha256': audit_hash,
               'host_compatibility': 'be791-modern-detours/v3',
               'adapter_sha256': digest(binary.read_bytes()), 'builder_sha256': digest(Path(__file__).read_bytes()),
               'files': {name: digest(data) for name, data in sorted(files.items())},
               'limits': ['Managed runtime supports the pinned Moon Sweepers Steam profile in Private game copy mode',
                          'No game/plugin execution by the offline builder; Windows gameplay and co-op require separate qualification']}
    output = {'loader/runtime/bepinex/files/' + name: data for name, data in files.items()}
    output['loader/runtime/bepinex/receipt.json'] = (json.dumps(receipt, indent=2) + '\n').encode()
    return output, receipt


def verify_bundle(bundle):
    """Package gates check the actual complete runtime instead of declared presence."""
    import sys
    sys.path.insert(0, str(ROOT / 'loader'))
    from moonloader.managed import artifact_files
    receipt, _ = artifact_files(Path(bundle) / 'runtime/bepinex')
    lock = json.loads(LOCK.read_text())
    if receipt.get('coreclr_version') != lock['coreclr_version']:
        raise ValueError('Package has no qualified maintained CoreCLR runtime')
    expected = {'dotnet/' + name: value for name, value in lock['coreclr_files'].items()}
    if {name: value for name, value in receipt['files'].items() if name.startswith('dotnet/')} != expected:
        raise ValueError('Package CoreCLR bytes differ from the maintained runtime lock')
    if any(receipt['files'].get('BepInEx/core/' + name) != item['sha256'] for name, item in lock['application_libraries'].items()):
        raise ValueError('Package omits the checked managed application library closure')
    if any(receipt['files'].get('BepInEx/third-party-sources/application-dependencies/' + name) != value for name, value in lock.get('application_notice_files', {}).items()):
        raise ValueError('Package omits managed application library notices')
    from modern_harmony import runtime_hashes
    if any(receipt['files'].get(name) != value for name, value in runtime_hashes().items()):
        raise ValueError('Package has no verified modern detour implementation')
    if receipt.get('host_compatibility') != 'be791-modern-detours/v3' or not {'BepInEx/core/MoonLab.ManagedHostCompat.dll', 'BepInEx/core/MoonLab.LegacyMonoMod.Utils.dll'} <= receipt['files'].keys():
        raise ValueError('Package lacks the matching BepInEx host compatibility layer')
    return receipt
