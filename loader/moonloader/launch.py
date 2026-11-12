"""Explicit launch boundary. Planning and GUI inspection never spawn processes."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from . import packages, steam_options, diagnostics
from .discovery import APP_ID, library_roots
from .storage import contained, load, write, sha, locked, assert_inactive, process_birth
from .settings import environment as settings_environment


def failure_detail(record):
    """Read a bounded bootstrap tail, even when a runner masks its exit code."""
    try:
        with (Path(record['run'])/'loader.jsonl').open('rb') as stream:
            stream.seek(0,2);stream.seek(max(0,stream.tell()-65536));tail=stream.read(65536)
    except (OSError,KeyError):return ''
    failures={
        'mod-library-load-failed':'Could not load mod DLL',
        'mod-entry-missing':'Mod entry point is missing',
        'mod-start-failed':'Mod startup failed',
        'runtime-registration-scope':'Required mod interface is unavailable',
        'mod-interface-contract-failed':'Mod did not publish its declared interfaces',
        'runtime-api-marker':'Mod runtime API version does not match its package',
        'runtime-plan-missing':'Mod deployment plan is missing; prepare files again',
        'runtime-plan-invalid':'Mod deployment plan is invalid; prepare files again',
        'runtime-plan-mod-list':'Selected mods do not match the prepared deployment plan',
        'shared-update-install-failed':'Could not install shared game update',
    }
    for line in reversed(tail.splitlines()):
        try:row=json.loads(line)
        except (ValueError,UnicodeDecodeError):continue
        if not isinstance(row,dict) or row.get('success') is not False:continue
        detail=failures.get(row.get('case'),'Loader startup failed')
        name=row.get('mod')
        if name in record.get('order',[]) and isinstance(name,str):detail+=': '+name
        return detail
    return ''


def host_pid(steam):
    expected = str(Path(steam) / 'ubuntu12_32/steam')
    matches = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit(): continue
        try:
            if (path / 'cmdline').read_bytes().split(b'\0')[0].decode() == expected: matches.append(int(path.name))
        except (OSError, UnicodeError): pass
    if len(matches) != 1: raise ValueError('Open Steam and sign in before launching the modded game')
    return matches[0]


def plan(service, installation, platform=None, check_client=True):
    """Deterministic preflight with no runtime initialization or directory writes."""
    platform = platform or sys.platform
    order, library = service.selected(installation)
    assessment = getattr(service, '_last_compatibility', None)
    native_order = [name for name in order if library[name][0]['kind'] == 'native']
    managed_selected = any(library[name][0]['kind'] == packages.MANAGED_KIND for name in order)
    external_mods = {name: library[name][0]['external']['adapter'] for name in order
                     if library[name][0].get('mode') == 'external'}
    root = service.install_root(installation)
    if service.mode(installation) == 'installed':
        from .public import preview
        if installation.store != 'steam' or not installation.steam_root:
            raise ValueError('Installed-game launch requires the Steam-discovered installation; rescan Steam')
        if platform not in ('win32', 'linux'): raise ValueError('Supported hosts are Linux and Windows')
        if platform == 'win32':
            command = [str(Path(installation.steam_root) / 'steam.exe'), '-applaunch', APP_ID]
        elif str(installation.steam_root).startswith(str(Path.home() / '.var/app/com.valvesoftware.Steam/')):
            command = ['flatpak', 'run', 'com.valvesoftware.Steam', '-applaunch', APP_ID]
        else:
            command = ['steam', '-applaunch', APP_ID]
        return {'mode': 'installed', 'platform': platform, 'command': command, 'env': {}, 'managed': managed_selected,
                'compatibility': assessment,
                'deployment': preview(service, installation, order, library),
                'cwd': installation.path, 'run': str(root / 'runs' / uuid.uuid4().hex),
                'store': 'steam', 'profile': 'Normal Steam saves (not isolated)', 'order': order,
                'runtime': 'Steam selected compatibility runtime' if platform == 'linux' else 'Steam / Windows',
                'launch_options': ('WINEDLLOVERRIDES="version=n,b;winhttp=n,b" %command%' if managed_selected else 'WINEDLLOVERRIDES="version=n,b" %command%') if platform == 'linux' else '',
                'steam_setup': steam_options.inspect(installation, platform, managed_selected),
                'limits': ['Steam launch request is not game-process ownership or startup confirmation',
                           'Proton requires verified launch options; use Steam setup before launching mods',
                           'Back up saves before save-affecting mods; binary uninstall does not restore saves',
                           'Native Windows gameplay, Cloud and two-account co-op require separate qualification']}
    game = root / 'game'
    run = root / 'runs' / uuid.uuid4().hex
    profile = root / 'profile'
    # The existing v1 feature ABI opens its evidence file with CreateFileA.
    # Reject lossy ANSI conversion rather than silently losing startup evidence.
    if not str(root).isascii() or len(str(root)) > 170:
        raise ValueError('This v1 mod needs a short ASCII data folder. Start the loader with --data PATH.')
    if platform == 'win32':
        environment = {'MOONLAB_MODS': ';'.join(native_order), 'MOONLAB_EVIDENCE': str(run),
                       'MOONLAB_RUN_ID': run.name, 'MOONLAB_PROFILE_ROOT': str(profile)}
        if managed_selected: environment.update(MOONLAB_BEPINEX='1', MOONLAB_BEPINEX_EVIDENCE=str(run))
        environment.update(settings_environment(root, order, platform))
        if installation.store == 'steam': environment.update(SteamAppId=APP_ID, SteamGameId=APP_ID)
        command = [str(game / 'MoonSweepers.exe'), '-logFile', str(run / 'Player.log')]
        return {'platform': platform, 'command': command, 'env': environment, 'cwd': str(game), 'run': str(run), 'compatibility': assessment,
                'store': installation.store, 'profile': str(profile), 'order': order, 'external_mods': external_mods, 'runtime': 'Windows native',
                'limits': ['Native Windows game replay pending', 'Process-local known-folder isolation requires rendered qualification']}
    if platform != 'linux': raise ValueError('Supported hosts are Linux and Windows')
    if installation.store != 'steam' or not installation.steam_root:
        raise ValueError('Linux currently launches Steam installations. Manual folders are detected, but another storefront needs its own runner adapter.')
    steam = Path(installation.steam_root)
    installed = next((root / 'steamapps/common/Proton - Experimental' for root in sorted(library_roots(steam)) if (root / 'steamapps/common/Proton - Experimental/proton').is_file()), None)
    if installed is None: raise ValueError('Install Proton Experimental through Steam, then rescan')
    proton = root / 'proton/runtime'
    prefix = root / 'proton/pfx'
    windows = lambda p: 'Z:' + str(p).replace('/', '\\')
    environment = {'STEAM_COMPAT_CLIENT_INSTALL_PATH': str(steam), 'STEAM_COMPAT_DATA_PATH': str(prefix.parent),
                   'WINEPREFIX': str(prefix), 'SteamAppId': APP_ID, 'SteamGameId': APP_ID,
                   'WINEDLLOVERRIDES': 'version=n,b;winhttp=n,b' if managed_selected else 'version=n,b',
                   'WINEDEBUG': '-all,err+eventlog' if managed_selected else '-all', 'PROTON_NO_NTSYNC': '1',
                   'WINEFSYNC': '0', 'WINENTSYNC': '0', 'MOONLAB_MODS': ';'.join(native_order),
                   'MOONLAB_EVIDENCE': windows(run), 'MOONLAB_RUN_ID': run.name,
                   'MOONLAB_PROFILE_ROOT': 'M:\\profile'}
    if managed_selected: environment.update(MOONLAB_BEPINEX='1', MOONLAB_BEPINEX_EVIDENCE=windows(run))
    environment.update(settings_environment(root, order, platform))
    flatpak = str(steam).startswith(str(Path.home() / '.var/app/com.valvesoftware.Steam/'))
    if flatpak:
        pid = host_pid(steam) if check_client else '<signed-in-Steam-PID>'
        command = ['flatpak', 'run', '--parent-pid=' + str(pid), '--parent-share-pids', '--share=network',
                   '--no-documents-portal', '--nofilesystem=home', '--filesystem=' + str(service.root),
                   '--filesystem=' + str(steam) + ':ro']
        command += ['--env=' + k + '=' + v for k, v in environment.items()]
        command += ['--command=/usr/bin/python3', 'com.valvesoftware.Steam', str(proton / 'proton'), 'run']
    else:
        if check_client: host_pid(steam)
        command = [sys.executable, str(proton / 'proton'), 'run']
    command += [str(game / 'MoonSweepers.exe'), '-logFile', windows(run / 'Player.log')]
    return {'platform': platform, 'command': command, 'env': environment, 'cwd': str(game), 'run': str(run), 'compatibility': assessment,
            'store': installation.store, 'profile': str(profile), 'order': order, 'external_mods': external_mods, 'runtime': 'Steam / Proton Experimental',
            'installed_proton': str(installed), 'private_proton': str(proton),
            'limits': ['Packaged loader replay pending', 'Native Steam host adapter is unqualified; existing evidence uses Flatpak Steam']}


def prepare_profile_drive(record):
    """Keep existing save bytes in place behind a short private Wine drive."""
    profile=Path(record['profile']);proton=Path(record['private_proton']).parent
    root=proton.parent
    if profile!=root/'profile':raise ValueError('Profile drive must target this private installation')
    contained(root,'profile')
    devices=contained(proton,'pfx/dosdevices');alias=devices/'m:';marker=proton/'profile-drive.json'
    ownership={'schema':'moon-loader-profile-drive/v1','drive':'m:','target':str(root)}
    present=alias.exists() or alias.is_symlink()
    if marker.exists():
        if load(marker)!=ownership or not alias.is_symlink() or os.readlink(alias)!=str(root):
            raise ValueError('Private profile drive changed; preserve it before retrying')
        return
    if present:raise ValueError('Refusing an existing unowned private M: drive')
    devices.mkdir(parents=True,exist_ok=True)
    alias.symlink_to(root,target_is_directory=True)
    write(marker,ownership)


def prepare_proton(record):
    """Copy mutable Proton bookkeeping privately; invoked only by explicit launch."""
    installed = Path(record['installed_proton']); target = Path(record['private_proton'])
    receipt = target.parent / 'runtime.json'
    identity = {name: sha(installed / name) for name in ('proton', 'version', 'files/bin/wine', 'files/bin/wineserver')}
    if receipt.exists():
        if load(receipt)['files'] != identity or any(sha(target / name) != value for name, value in identity.items()):
            raise ValueError('Proton changed; preserve the private runtime and prepare a fresh data folder')
        prepare_profile_drive(record)
        return
    if target.exists(): raise ValueError('Unowned or interrupted Proton copy; preserve it before retrying')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(installed, target, symlinks=True)
    write(receipt, {'files': identity})
    prepare_profile_drive(record)


def start(service, installation, progress=None):
    """Only a human Launch action should call this during the agent launch pause."""
    logger = diagnostics.start(service.root)
    logger.event('launch-request', 'Checking selected mods and launch setup')
    lease = locked(service.root, 'session.lock')
    acquired = False
    try:
        lease.__enter__(); acquired = True
        assert_inactive(service.root)
        return _start_locked(service, installation, lease, progress)
    except Exception as error:
        logger.exception('launch-error', error)
        if acquired: lease.__exit__(*sys.exc_info())
        raise


def _start_locked(service, installation, lease, progress=None):
    if progress: progress('Checking selected mods and Steam setup…')
    record = plan(service, installation)
    logger = diagnostics.start(service.root)
    if record.get('mode') == 'installed' and record['order']:
        steam_options.require_ready(installation, record['platform'], record.get('managed', False))
    if progress: progress('Applying selected mods automatically…')
    service.prepare(installation, _session_owner=True)
    previous, current = record.get('compatibility'), getattr(service, '_last_compatibility', None)
    if previous is not None and current is not None and any(previous.get(k) != current.get(k)
            for k in ('profile', 'selection_digest', 'runtime_receipt_digest')):
        raise ValueError('Compatibility changed during launch preparation; review the refreshed report before launching')
    if record.get('mode') == 'installed':
        diagnostics.prepare_installed(service, installation, record)
        run = Path(record['run']); run.mkdir(parents=True, exist_ok=True)
        write(run / 'launch.json', record)
        logger.event('steam-request-starting', 'Files prepared; requesting Steam launch. Game startup remains unconfirmed.', run=str(run), mods=record.get('order', []), platform=record.get('platform'))
        env = {k:v for k,v in os.environ.items() if not k.startswith('MOONLAB_')}
        # The request PID is not the game. Retain uncertainty across windows and
        # restarts until observed game exit or explicit user acknowledgement.
        active = service.root / 'active.json'
        write(active, {'state':'steam-starting', 'run':str(run)})
        if progress: progress('Files ready · handing launch to Steam…')
        try:
            with (run / 'process.log').open('wb') as output:
                process = subprocess.Popen(record['command'], cwd=record['cwd'], env=env,
                                           stdout=output, stderr=subprocess.STDOUT)
        except Exception:
            write(active, {'state':'failed', 'run':str(run)})
            raise
        try: write(active, {'state':'steam-unconfirmed', 'run':str(run)})
        except (ValueError, OSError) as error: record['diagnostic_error'] = str(error)
        # Steam owns the real game, whose lifetime is independent of this
        # short request process. Never record the client as our game PID.
        lease.__exit__(None, None, None)
        return process, record
    if progress: progress('Files ready · preparing the private launch…')
    if record['platform'] == 'linux': prepare_proton(record)
    run = Path(record['run']); contained(service.root, run.relative_to(service.root).as_posix()).mkdir(parents=True)
    diagnostics.prepare_run(service.root, record)
    write(run / 'launch.json', record)
    logger.event('private-game-starting', 'Files prepared; starting the private game process.', run=str(run), mods=record.get('order', []), platform=record.get('platform'))
    env = os.environ.copy()
    # A normal launch must never inherit automation/cheat switches from a shell.
    for name in list(env):
        if name.startswith('MOONLAB_'): env.pop(name)
    env.update(record['env'])
    active = service.root / 'active.json'
    write(active, {'state':'starting','launcher_pid':os.getpid(),'run':str(run)})
    try:
        with (run / 'process.log').open('wb') as output:
            process = subprocess.Popen(record['command'], cwd=record['cwd'], env=env, stdout=output, stderr=subprocess.STDOUT)
    except Exception:
        write(active, {'state':'failed','pid':0,'birth':None,'run':str(run)})
        raise
    # Once a process exists, preserve the lease/handle even if evidence writes
    # fail. The starting journal then blocks a later, untracked redeployment.
    process._moon_lease = lease
    try:
        birth = process_birth(process.pid)
        write(run / 'process.json', {'pid':process.pid,'birth':birth,'runtime':record['runtime']})
        write(active, {'state':'running','pid':process.pid,'birth':birth,'run':str(run)})
    except (ValueError,OSError) as error:
        record['diagnostic_error'] = str(error)
    return process, record
