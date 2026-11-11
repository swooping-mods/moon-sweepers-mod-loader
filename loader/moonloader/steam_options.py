"""Bounded Steam launch-option repair. Never edits a running client's config."""
import hashlib
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tempfile
import uuid
from .discovery import APP_ID
from .storage import contained, locked, write

_LIMIT = 16 * 1024 * 1024
_TOKEN = re.compile(r'\s+|//[^\n]*|"(?:\\.|[^"\\])*"|[{}]|[^\s{}"]+')


def _quoted(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _tree(text):
    """Retain scalar/brace offsets; reject duplicate keys rather than edit guesses."""
    tokens = []
    position = 0
    for match in _TOKEN.finditer(text):
        if match.start() != position: raise ValueError('Unsupported Steam configuration syntax')
        position = match.end()
        raw = match.group()
        if raw.isspace() or raw.startswith('//'): continue
        value = re.sub(r'\\([\\"])', r'\1', raw[1:-1]) if raw.startswith('"') else raw
        tokens.append((value, match.start(), match.end()))
    if position != len(text): raise ValueError('Unsupported Steam configuration syntax')
    def group(index, nested):
        result = {}
        while index < len(tokens):
            key, _, _ = tokens[index]
            if key == '}':
                if not nested: raise ValueError('Unexpected Steam configuration brace')
                return result, index + 1, tokens[index][1]
            if key == '{' or index + 1 >= len(tokens): raise ValueError('Incomplete Steam configuration')
            key = key.casefold()
            if key in result: raise ValueError('Ambiguous duplicate Steam configuration key')
            index += 1; value, start, end = tokens[index]
            if value == '{':
                children, index, close = group(index + 1, True)
                result[key] = {'children': children, 'close': close}
            elif value == '}': raise ValueError('Missing Steam configuration value')
            else:
                result[key] = {'value': value, 'start': start, 'end': end}; index += 1
        if nested: raise ValueError('Incomplete Steam configuration')
        return result, index, len(text)
    return group(0, False)[0]


def _walk(tree, *keys):
    for key in keys:
        node = tree.get(key.casefold())
        if not node or 'children' not in node: raise ValueError('Steam game configuration is missing; launch the game once from Steam, then retry')
        tree = node['children']
    return tree


def _merge_one(current, dll):
    """Change only the required assignment; preserve other command bytes verbatim."""
    if any(c in current for c in '\r\n\0'):
        raise ValueError('Multiline Steam options need manual setup')
    # Shell control/expansion makes assignment scope uncertain. Leave it untouched.
    if re.search(r'[|&<>`$]', current):
        raise ValueError('Shell expressions in Steam options need manual setup')
    quote = ''; escaped = False
    for char in current:
        if escaped: escaped = False; continue
        if char == '\\' and quote != "'": escaped = True; continue
        if quote:
            if char == quote: quote = ''
        elif char in ("'", '"'): quote = char
        elif char == ';': raise ValueError('Shell command separators need manual setup')
    raw_tokens = list(re.finditer(r'''(?:[^\s'"\\]|\\.|"(?:\\.|[^"\\])*"|'[^']*')+''', current))
    tokens = []
    end = 0
    for match in raw_tokens:
        if current[end:match.start()].strip(): raise ValueError('Unsupported quoting in Steam options; merge the override manually')
        try: parsed = shlex.split(match.group())
        except ValueError as error: raise ValueError('Unsupported quoting in Steam options') from error
        if len(parsed) != 1: raise ValueError('Unsupported Steam launch options')
        tokens.append((parsed[0], match.start(), match.end())); end = match.end()
    if current[end:].strip(): raise ValueError('Unsupported quoting in Steam options')
    commands = [i for i, (value, _, _) in enumerate(tokens) if value == '%command%']
    if len(commands) > 1 or any('%command%' in value and value != '%command%' for value, _, _ in tokens):
        raise ValueError('Steam options need exactly one standalone %command%; merge the override manually')
    if not commands:
        if not tokens: return 'WINEDLLOVERRIDES="'+dll+'=n,b" %command%'
        if not tokens[0][0].startswith('-'): raise ValueError('Wrapper options without %command% need manual setup')
        return 'WINEDLLOVERRIDES="'+dll+'=n,b" %command% ' + current
    command = commands[0]
    prefix_values = [value for value, _, _ in tokens[:command]]
    # A leading assignment cannot survive an environment-clearing wrapper.
    # Unknown env flags and shell/elevation scopes are deliberately manual.
    for index, token in enumerate(prefix_values):
        name = Path(token).name
        if name in ('sh', 'bash', 'dash', 'zsh', 'fish', 'csh', 'tcsh', 'sudo', 'doas') or token == '--clearenv':
            raise ValueError('Environment-changing wrappers need manual Steam setup')
        if name == 'env' and index + 1 < len(prefix_values) and prefix_values[index + 1].startswith('-'):
            raise ValueError('env options need manual Steam setup; preserve the required override inside its environment')
    assignments = [(i, value, start, end) for i, (value, start, end) in enumerate(tokens) if value.startswith('WINEDLLOVERRIDES=')]
    if len(assignments) > 1: raise ValueError('Multiple WINEDLLOVERRIDES assignments need manual setup')
    if not assignments: return 'WINEDLLOVERRIDES="'+dll+'=n,b" ' + current
    index, assignment, start, end = assignments[0]
    if not current[start:end].startswith('WINEDLLOVERRIDES='):
        raise ValueError('Quoted assignment names need manual Steam setup')
    # Only leading assignments or env's assignment prefix have unambiguous scope.
    prefix = [value for value, _, _ in tokens[:index]]
    if prefix and prefix[0] == 'env': prefix = prefix[1:]
    if index >= command or any(not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*=.*', value) for value in prefix):
        raise ValueError('WINEDLLOVERRIDES inside a wrapper needs manual setup')
    value = assignment.split('=', 1)[1]
    clauses = []; found = 0
    for clause in value.split(';'):
        if not clause: continue
        if '=' not in clause: raise ValueError('Unsupported DLL override syntax; merge version=n,b manually')
        names, modes = clause.split('=', 1)
        names = names.split(',')
        if not all(re.fullmatch(r'[A-Za-z0-9_.-]+', name) for name in names) or not re.fullmatch(r'[nb,]*', modes):
            raise ValueError('Unsupported DLL override syntax; merge version=n,b manually')
        remaining = [name for name in names if name.casefold() != dll]
        count = len(names) - len(remaining); found += count
        if count and modes == 'n,b' and len(names) == 1:
            clauses.append(clause)
        else:
            if remaining: clauses.append(','.join(remaining) + '=' + modes)
            if count: clauses.append(dll+'=n,b')
    if found > 1: raise ValueError('Conflicting repeated version overrides need manual setup')
    if not found: clauses.append(dll+'=n,b')
    proposed = ';'.join(clauses)
    if proposed == value: return current
    return current[:start] + 'WINEDLLOVERRIDES=' + _quoted(proposed) + current[end:]


def merge(current, dlls=('version',)):
    if tuple(dlls) not in (('version',), ('version', 'winhttp')):
        raise ValueError('Unsupported required Steam override set')
    for dll in dlls: current = _merge_one(current, dll)
    return current


def _read(path, root):
    path = Path(path); root = Path(root).resolve()
    try: relative = path.relative_to(root)
    except ValueError as error: raise ValueError('Steam configuration is outside its installation') from error
    here = root
    for part in relative.parts:
        here = here / part
        if here.is_symlink(): raise ValueError('Steam configuration symlinks need manual setup')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > _LIMIT:
        raise ValueError('Unsupported Steam configuration file')
    data = path.read_bytes()
    if len(data) > _LIMIT: raise ValueError('Steam configuration is too large')
    after = path.stat()
    signature = lambda item: (item.st_dev, item.st_ino, item.st_mtime_ns, item.st_size)
    if signature(info) != signature(after): raise ValueError('Steam configuration changed; refresh the preview')
    return data, [*signature(info), hashlib.sha256(data).hexdigest()]


def _snapshot(installation, dlls=('version',)):
    if installation.store != 'steam' or not installation.steam_root: raise ValueError('Choose a Steam-discovered installation')
    root = Path(installation.steam_root).resolve()
    login = root / 'config/loginusers.vdf'
    login_data, login_signature = _read(login, root)
    users = _walk(_tree(login_data.decode('utf-8-sig')), 'users')
    recent = []; accounts = []; marked = False
    for steam_id, user in users.items():
        if 'children' not in user or not steam_id.isdigit(): continue
        accounts.append(steam_id)
        marker = user['children'].get('mostrecent')
        if marker is not None:
            marked = True
            if marker.get('value') not in ('0', '1'): raise ValueError('Unsupported Steam account selection marker')
            if marker['value'] == '1': recent.append(steam_id)
    # Some current Steam clients omit MostRecent entirely for a sole account.
    # That shape is unambiguous; never guess among multiple stored accounts.
    if not marked and len(accounts) == 1: recent = accounts
    if len(recent) != 1: raise ValueError('Cannot identify one recent Steam account; sign in to the intended account and retry')
    account = str(int(recent[0]) & 0xffffffff)
    path = root / 'userdata' / account / 'config/localconfig.vdf'
    data, signature = _read(path, root); text = data.decode('utf-8-sig')
    apps = _walk(_tree(text), 'UserLocalConfigStore', 'Software', 'Valve', 'Steam', 'apps')
    node = apps.get(APP_ID)
    if not node or 'children' not in node:
        raise ValueError('Moon Sweepers has no Steam account settings; launch it once from Steam, then retry')
    options = node['children'].get('launchoptions')
    if options and 'value' not in options: raise ValueError('Invalid Steam launch options')
    current = options['value'] if options else ''
    proposed = merge(current, dlls)
    if options: modified = text[:options['start']] + _quoted(proposed) + text[options['end']:]
    else:
        newline = '\r\n' if '\r\n' in text else '\n'
        modified = text[:node['close']] + newline + '\t\t\t\t\t"LaunchOptions"\t\t' + _quoted(proposed) + newline + '\t\t\t\t' + text[node['close']:]
    if data.startswith(b'\xef\xbb\xbf'): modified = '\ufeff' + modified
    return {'path': str(path), 'account': account, 'current': current, 'proposed': proposed,
            'signature': signature, 'login_signature': login_signature, 'required_dlls': list(dlls)}, data, modified.encode('utf-8')


def inspect(installation, platform=None, managed=False):
    platform = platform or sys.platform
    if platform == 'win32': return {'status': 'not-required', 'message': 'Windows loads the installed bootstrap directly; no Proton launch options are needed.'}
    if platform != 'linux': return {'status': 'unsupported', 'message': 'Steam setup is supported on Windows and Linux.'}
    try:
        result, _, _ = _snapshot(installation, ('version', 'winhttp') if managed else ('version',))
        ready = result['current'] == result['proposed']
        result.update(status='ready' if ready else 'required', message='Steam Proton launch options are ready.' if ready else 'Steam setup required: apply the version and winhttp DLL overrides before launching managed mods.' if managed else 'Steam setup required: apply the version DLL override before launching mods.')
        return result
    except (OSError, ValueError, UnicodeError) as error:
        required = 'version=n,b;winhttp=n,b' if managed else 'version=n,b'
        return {'status': 'unsupported', 'message': str(error) + '. Set WINEDLLOVERRIDES="'+required+'" in Steam Properties → Launch Options, preserving existing options.'}


def assert_steam_stopped():
    """Conservative client scan, including Flatpak helpers; unreadable peers reject."""
    for process in Path('/proc').iterdir():
        if not process.name.isdigit(): continue
        try: command = (process / 'cmdline').read_bytes().split(b'\0')[0].decode('utf-8')
        except (FileNotFoundError, ProcessLookupError): continue
        except (OSError, UnicodeError) as error: raise ValueError('Cannot verify that Steam is closed; use manual setup') from error
        if Path(command).name.casefold() in ('steam', 'steam.exe', 'steamwebhelper'):
            raise ValueError('Quit Steam completely, then apply these options. Reopen Steam before launching the game.')


def apply(installation, data_root, preview):
    """Explicit user action only: compare snapshots, back up, replace, read back."""
    if sys.platform != 'linux': raise ValueError('Automatic Proton setup is only needed on Linux')
    with locked(data_root, 'steam-options.lock'):
        assert_steam_stopped()
        dlls = tuple(preview.get('required_dlls', ['version']))
        current, before, after = _snapshot(installation, dlls)
        for key in ('path', 'account', 'signature', 'login_signature', 'current', 'proposed', 'required_dlls'):
            if current.get(key) != preview.get(key): raise ValueError('Steam settings changed; refresh the setup preview before applying')
        if before == after or current['current'] == current['proposed']: return {'changed': False}
        backup = contained(Path(data_root), 'steam-options-backups/' + uuid.uuid4().hex)
        backup.mkdir(parents=True)
        (backup / 'localconfig.vdf').write_bytes(before)
        write(backup / 'receipt.json', {'schema': 'moon-loader-steam-options/v1', **current})
        path = Path(current['path']); temporary = None
        try:
            handle, temporary = tempfile.mkstemp(prefix='.moon-launch-options-', dir=path.parent)
            with os.fdopen(handle, 'wb') as stream:
                stream.write(after); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            assert_steam_stopped()
            checked, _, _ = _snapshot(installation, dlls)
            if checked != current: raise ValueError('Steam settings changed during setup; nothing was replaced')
            os.replace(temporary, path); temporary = None
            verified, _ = _read(path, Path(installation.steam_root).resolve())
            if verified != after: raise ValueError('Steam settings verification failed; inspect backup: ' + str(backup))
        finally:
            if temporary is not None: Path(temporary).unlink(missing_ok=True)
        return {'changed': True, 'backup': str(backup), 'message': 'Steam launch options applied and verified. Reopen Steam, then launch the game.'}


def require_ready(installation, platform=None, managed=False):
    result = inspect(installation, platform, managed)
    if result['status'] not in ('ready', 'not-required'): raise ValueError(result['message'] + ' Open Steam setup in the loader.')
    return result
