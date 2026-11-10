"""Additive installed-game deployment. Original game files are never replaced."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from . import discovery
from .storage import contained, is_alias, load, locked, sha, write

CONFIG = 'MoonLab/active.txt'
SCHEMA = 'moon-loader-installed/v1'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sync_directory(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)


def file_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    sync_directory(path.parent)


def target(game, name):
    """Reject Windows aliases even when reviewing an installation on Linux."""
    path = contained(game, name)
    current = Path(game)
    for part in Path(name).parts:
        if current.is_dir():
            if any(p.name.casefold() == part.casefold() and p.name != part for p in current.iterdir()):
                raise ValueError('Case alias in installed path: ' + name)
        current /= part
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError('Installed destination is not an independent file: ' + name)
    return path


def current_hash(game, name):
    path = target(game, name)
    return sha(path) if path.exists() else None


def assert_stopped():
    """Steam can launch without our GUI. Conservatively block any matching game."""
    if os.name != 'nt':
        for process in Path('/proc').iterdir():
            if not process.name.isdigit(): continue
            try:
                args = (process / 'cmdline').read_bytes().replace(b'\\', b'/').split(b'\0')
            except FileNotFoundError: continue
            except PermissionError as error:
                raise ValueError('Cannot verify running processes before deployment') from error
            if any(arg.rsplit(b'/', 1)[-1].lower() == b'moonsweepers.exe' for arg in args):
                raise ValueError('Moon Sweepers is still running; close it before changing installed files')
        return
    import ctypes
    from ctypes import wintypes as w
    class Entry(ctypes.Structure):
        _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD), ('heap', ctypes.c_size_t),
                    ('module', w.DWORD), ('threads', w.DWORD), ('parent', w.DWORD),
                    ('priority', w.LONG), ('flags', w.DWORD), ('exe', w.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    for name in ('Process32FirstW', 'Process32NextW'):
        fn = getattr(kernel, name); fn.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]; fn.restype = w.BOOL
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value: raise ValueError('Cannot enumerate game processes')
    try:
        entry = Entry(); entry.size = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            if entry.exe.casefold() == 'moonsweepers.exe':
                raise ValueError('Moon Sweepers is still running; close it before changing installed files')
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18: raise ValueError('Cannot finish enumerating game processes')
    finally: kernel.CloseHandle(handle)


def validate_game(installation):
    if installation.store != 'steam': raise ValueError('Installed-game mode requires a Steam installation')
    game = Path(installation.path)
    if not str(game).isascii() or len(str(game)) > 170:
        raise ValueError('This native mod ABI requires a short ASCII game installation path')
    for name, expected in discovery.PIN.items():
        if current_hash(game, name) != expected:
            raise ValueError('Installed game changed; update the adapter before applying mods')
    # A mounted/staged Steam update is not coordinated by our operation lock.
    if game.parent.name == 'common':
        manifest = game.parent.parent / f'appmanifest_{discovery.APP_ID}.acf'
        if manifest.exists():
            app = discovery.vdf(manifest.read_text('utf-8-sig')).get('AppState', {})
            if app.get('StateFlags') != '4': raise ValueError('Steam is updating or has not finished installing this game')


def competing_loaders(game):
    names = {'winhttp.dll', 'winmm.dll', 'doorstop_config.ini', 'bepinex', 'melonloader'}
    return sorted(path.name for path in Path(game).iterdir() if path.name.casefold() in names)


@contextmanager
def operation(root, game):
    """One on-target lock serializes managers even with different data folders."""
    game = Path(game)
    # Do not create game-root lock files that another data directory cannot own.
    root.mkdir(parents=True, exist_ok=True)
    with locked(root):
        assert_stopped()
        if (game / 'MoonLab').exists():
            owner = load(contained(game, 'MoonLab/owner.json'), {})
            if owner != {'schema': SCHEMA, 'data': str(root)}:
                raise ValueError('Unowned MoonLab folder or another loader data directory owns this installation')
            with locked(game / 'MoonLab', 'operation.lock'): yield
        else:
            # Initial ownership publication uses exclusive creation, not overwrite.
            if is_alias(game / 'MoonLab'): raise ValueError('Symlink in installed path')
            (game / 'MoonLab').mkdir()
            try:
                file_bytes(game / 'MoonLab/owner.json',
                           (json.dumps({'schema': SCHEMA, 'data': str(root)}) + '\n').encode())
                with locked(game / 'MoonLab', 'operation.lock'): yield
            except BaseException:
                # Preserve any interrupted or unknown content for inspection.
                raise


def empty(installation):
    return {'schema': SCHEMA, 'installation': installation.record(), 'files': {}, 'order': [],
            'enabled': False, 'generation': '', 'game_pins': dict(discovery.PIN)}


def receipt(root, installation):
    result = load(contained(root, 'deployment.json'), empty(installation))
    if result.get('schema') != SCHEMA or result.get('installation') != installation.record():
        raise ValueError('Foreign installed-game receipt')
    for name, value in result['files'].items():
        if (name not in ('version.dll', CONFIG, 'MoonLab/runtime-plan.bin') and
                not re.fullmatch(r'MoonLab/deployments/[a-f0-9]{32}/files.txt|MoonLab/mods/.+', name)):
            raise ValueError('Invalid owned payload path')
        if not re.fullmatch('[a-f0-9]{64}', value): raise ValueError('Invalid owned payload hash')
    return result


def config(installation, generation, order, enabled):
    if not re.fullmatch('[a-f0-9]{32}', generation): raise ValueError('Invalid deployment generation')
    from .storage import key
    for name in order: key(name)
    return (f'MOONLAB-PUBLIC-1\ninstallation={installation.identity}\ngeneration={generation}\n'
            f'enabled={int(enabled)}\nmods={";".join(order)}\n').encode('ascii')


def recover(root, installation):
    journal_path = contained(root, 'pending-installed.json')
    journal = load(journal_path)
    if not journal: return
    game = Path(installation.path)
    before, after = journal['before'], journal['after']
    if (before.get('schema') != SCHEMA or after.get('schema') != SCHEMA or
            before.get('installation') != installation.record() or after.get('installation') != installation.record()):
        raise ValueError('Foreign interrupted installed-game transaction')
    # Validate the path allowlist with the same receipt parser before using journal paths.
    for state in (before, after):
        for name in state['files']:
            if name not in ('version.dll', CONFIG, 'MoonLab/runtime-plan.bin') and not re.fullmatch(r'MoonLab/deployments/[a-f0-9]{32}/files.txt|MoonLab/mods/.+', name):
                raise ValueError('Invalid journal payload path')
    stage_name = journal['stage']
    if not re.fullmatch(r'\.moonlab-stage-[a-f0-9]{32}', stage_name): raise ValueError('Invalid transaction stage')
    stage = contained(game, stage_name)
    for name in set(before['files']) | set(after['files']):
        actual = current_hash(game, name)
        if actual is not None and actual not in (before['files'].get(name), after['files'].get(name)):
            raise ValueError('Unknown edit blocks installed recovery: ' + name)
    for name, expected in before['files'].items():
        if sha(contained(stage, 'old/' + name)) != expected: raise ValueError('Changed recovery backup')
    # Remove the selection before restoring a partially updated payload.
    target(game, CONFIG).unlink(missing_ok=True)
    for name, expected in before['files'].items():
        if name == CONFIG: continue
        destination = target(game, name); destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = contained(stage, 'restore/' + name)
        temporary.parent.mkdir(parents=True, exist_ok=True)
        if temporary.exists(): temporary.unlink()
        file_bytes(temporary, contained(stage, 'old/' + name).read_bytes())
        os.replace(temporary, destination); sync_directory(destination.parent)
    for name in set(after['files']) - set(before['files']): target(game, name).unlink(missing_ok=True)
    if CONFIG in before['files']:
        contained(stage, 'restore-active').unlink(missing_ok=True)
        file_bytes(contained(stage, 'restore-active'), contained(stage, 'old/' + CONFIG).read_bytes())
        os.replace(contained(stage, 'restore-active'), target(game, CONFIG)); sync_directory(game / 'MoonLab')
    if any(current_hash(game, n) != h for n, h in before['files'].items()): raise ValueError('Recovery read-back failed')
    write(root / 'deployment.json', before); sync_directory(root)
    journal_path.unlink(); sync_directory(root)
    cleanup_stage(stage)


def cleanup_stage(stage):
    # Only transaction-generated files may be discarded. Unknown contents survive.
    manifest = load(contained(stage, 'contents.json'), [])
    for name, expected in manifest:
        path = contained(stage, name)
        if path.exists() and sha(path) == expected: path.unlink()
    for directory in sorted((p for p in stage.rglob('*') if p.is_dir() and not is_alias(p)), key=lambda p: len(p.parts), reverse=True):
        try: directory.rmdir()
        except OSError: pass
    try:
        (stage / 'contents.json').unlink(); stage.rmdir()
    except OSError: pass


def transact(root, installation, files, order, generation, enabled):
    """Recheck external writes at each mutation, then publish selection last."""
    game = Path(installation.path); before = receipt(root, installation)
    after = {**empty(installation), 'files': {n: digest(b) for n, b in files.items()},
             'order': order, 'generation': generation, 'enabled': enabled}
    for name, expected in before['files'].items():
        if current_hash(game, name) != expected: raise ValueError('Owned installed file changed or missing: ' + name)
    for name in files:
        if name not in before['files'] and current_hash(game, name) is not None:
            raise ValueError('Unowned deployment file: ' + name)
    stage_name = '.moonlab-stage-' + uuid.uuid4().hex; stage = contained(game, stage_name)
    stage.mkdir()
    contents = []
    for name in before['files']:
        data = target(game, name).read_bytes()
        if digest(data) != before['files'][name]: raise ValueError('File changed while backing up: ' + name)
        file_bytes(contained(stage, 'old/' + name), data); contents.append(('old/' + name, digest(data)))
    for name, data in files.items():
        file_bytes(contained(stage, 'new/' + name), data); contents.append(('new/' + name, digest(data)))
    write(stage / 'contents.json', contents); sync_directory(stage)
    pending = contained(root, 'pending-installed.json')
    if pending.exists(): raise ValueError('Recover pending deployment first')
    write(pending, {'before': before, 'after': after, 'stage': stage_name}); sync_directory(root)
    try:
        assert_stopped()
        if enabled: validate_game(installation)
        baseline = {n: (game / n).stat() for n in discovery.PIN} if enabled else {}
        def unchanged_inputs():
            for name, previous in baseline.items():
                current = target(game, name).stat()
                if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (previous.st_dev, previous.st_ino, previous.st_size, previous.st_mtime_ns):
                    raise ValueError('Installed game changed during deployment')
        names = (set(before['files']) | set(files)) - {CONFIG}
        # Existing package ABIs resolve dependencies/assets under MoonLab/mods.
        # Disconnect selection while replacing that stable path surface.
        if current_hash(game, CONFIG) != before['files'].get(CONFIG): raise ValueError('Configuration changed')
        target(game, CONFIG).unlink(missing_ok=True); sync_directory(game / 'MoonLab')
        for name in sorted(names & set(files)):
            assert_stopped()
            unchanged_inputs()
            if current_hash(game, name) != before['files'].get(name): raise ValueError('File changed during deployment: ' + name)
            path = target(game, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(contained(stage, 'new/' + name), path)
            sync_directory(path.parent)
        if CONFIG in files:
            assert_stopped()
            if enabled: validate_game(installation)
            if current_hash(game, CONFIG) is not None: raise ValueError('Configuration changed')
            os.replace(contained(stage, 'new/' + CONFIG), target(game, CONFIG)); sync_directory(game / 'MoonLab')
        for name in sorted(names - set(files)):
            assert_stopped()
            if current_hash(game, name) != before['files'].get(name): raise ValueError('File changed during removal: ' + name)
            path = target(game, name); path.unlink(missing_ok=True); sync_directory(path.parent)
        if any(current_hash(game, n) != h for n, h in after['files'].items()): raise ValueError('Installed read-back failed')
        write(root / 'deployment.json', after); sync_directory(root)
        pending.unlink(); sync_directory(root)
    except Exception:
        recover(root, installation)
        raise
    cleanup_stage(stage)


def prepare(service, installation, order, library, runtime):
    root = service.install_root(installation); game = Path(installation.path)
    if order and not service.save_policy_ready(installation, order, library):
        raise ValueError('Installed mods use normal Steam saves. Back up saves or explicitly confirm a fresh Steam profile first.')
    competitors = competing_loaders(game)
    if competitors: raise ValueError('Unqualified loader coexistence: ' + ', '.join(competitors))
    # Reject bootstrap collisions before publishing any ownership metadata.
    if not (root / 'deployment.json').exists() and not (root / 'pending-installed.json').exists() and current_hash(game, 'version.dll') is not None:
        raise ValueError('Unowned deployment file: version.dll (another loader may be installed)')
    validate_game(installation)
    with operation(root, game):
        recover(root, installation)
        generation = uuid.uuid4().hex
        files = {'version.dll': runtime.read_bytes()}
        runtime_receipt = load(service.bundle / 'runtime/receipt.json', {})
        if digest(files['version.dll']) != runtime_receipt.get('sha256'): raise ValueError('Runtime changed during preparation')
        if runtime_receipt.get('runtime_api_abi') == 1 and order:
            from moon_mod_api.runtime_plan import encode, PATH
            files[PATH] = encode({name: library[name][0] for name in order}, order)
        for name in order:
            manifest, folder = library[name]
            for member in manifest['files']:
                destination = f'MoonLab/mods/{name}/' + ('mod.dll' if member == manifest['entry'] else member)
                if destination in files: raise ValueError('Package entry alias collision')
                data = contained(folder, member).read_bytes()
                if digest(data) != manifest['files'][member]: raise ValueError('Package changed during preparation: ' + name)
                files[destination] = data
        for destination in files:
            if not destination.isascii() or len(str(game / destination)) > 240:
                raise ValueError('Selected package needs a shorter ASCII installed payload path: ' + destination)
        # A payload inventory is checked inside the process before loading any mod.
        inventory = ''.join(f'{digest(data)} {name}\n' for name, data in sorted(files.items()) if name != 'version.dll')
        if len(inventory) > 1048576: raise ValueError('Selected payload inventory exceeds this bootstrap capacity')
        files[f'MoonLab/deployments/{generation}/files.txt'] = inventory.encode('ascii')
        files[CONFIG] = config(installation, generation, order, bool(order))
        from .settings import seed
        seed(game / 'MoonLab', order, library)
        contained(game, 'MoonLab/logs').mkdir(exist_ok=True)
        transact(root, installation, files, order, generation, bool(order))
    return root


def preview(service, installation, order, library):
    """Read-only destinations/conflicts; generation inventory allocated on apply."""
    game = Path(installation.path); root = service.install_root(installation)
    old = receipt(root, installation)
    destinations = {'version.dll', CONFIG}
    if load(service.bundle / 'runtime/receipt.json', {}).get('runtime_api_abi') == 1 and order:
        destinations.add('MoonLab/runtime-plan.bin')
    for name in order:
        manifest, _ = library[name]
        for member in manifest['files']:
            destinations.add(f'MoonLab/mods/{name}/' + ('mod.dll' if member == manifest['entry'] else member))
    conflicts = []
    conflicts.extend('Unqualified loader coexistence: ' + name for name in competing_loaders(game))
    for name in sorted(set(old['files']) | destinations):
        actual = current_hash(game, name)
        if name in old['files'] and actual != old['files'][name]: conflicts.append('Changed/missing owned file: ' + name)
        elif name not in old['files'] and actual is not None: conflicts.append('Unowned destination: ' + name)
    owner = load(contained(game, 'MoonLab/owner.json'), {})
    if (game / 'MoonLab').exists() and owner != {'schema': SCHEMA, 'data': str(root)}:
        conflicts.append('Foreign MoonLab directory or data owner')
    return {'target':str(game), 'destinations':sorted(destinations),
            'remove_owned':sorted(set(old['files']) - destinations),
            'selection_inventory':'MoonLab/deployments/<new-generation>/files.txt',
            'conflicts':conflicts, 'original_game_replacements':[],
            'backup_scope':'Previous owned additions for transaction recovery; no original DLL replacements',
            'save_policy':'Normal Steam saves; explicit backup/fresh-profile choice required',
            'steam_options':'Never edited automatically'}


def set_enabled(service, installation, enabled):
    root = service.install_root(installation); game = Path(installation.path)
    if not (root / 'deployment.json').exists() and not (root / 'pending-installed.json').exists():
        raise ValueError('Prepare this installation first')
    with operation(root, game):
        recover(root, installation); old = receipt(root, installation)
        if CONFIG not in old['files']: raise ValueError('Prepare this installation first')
        files = {n: target(game, n).read_bytes() for n in old['files']}
        files[CONFIG] = config(installation, old['generation'], old['order'], bool(enabled and old['order']))
        transact(root, installation, files, old['order'], old['generation'], bool(enabled and old['order']))


def uninstall(service, installation):
    root = service.install_root(installation); game = Path(installation.path)
    if not (root / 'deployment.json').exists() and not (root / 'pending-installed.json').exists(): return
    with operation(root, game):
        recover(root, installation)
        transact(root, installation, {}, [], '', False)
    # Ownership/control metadata remains so settings and logs cannot be mistaken
    # for somebody else's loader on a later reinstall. It loads no game code.
