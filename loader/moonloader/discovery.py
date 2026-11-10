"""Read Steam VDF manifests; manual install discovery uses the same validator."""
from dataclasses import dataclass, asdict
import hashlib
import os
from pathlib import Path
import re
import sys
from .storage import sha

APP_ID = '5335510'
PIN = {'GameAssembly.dll': '14f711a6a3b1b7cd803a03f85cc6c6201c5b546ab9b90329533f5cb8ae2e7f13',
       'MoonSweepers.exe': '0e780f8e8d4bf26ed6bdd8a4068ac42a18846a66a80da7ba5c78f1917a093901',
       'UnityPlayer.dll': 'bfafc49b185eb8427ad75e3648bcba3bf5b07455567ca05ae2b2e23bc1646c0c'}


def vdf(text):
    tokens = [t for t in re.findall(r'"(?:\\.|[^"\\])*"|//[^\n]*|[{}]|[^\s{}"]+', text) if not t.startswith('//')]
    def atom(token):
        return re.sub(r'\\([\\"])', r'\1', token[1:-1]) if token.startswith('"') else token
    def group(index, nested=False):
        result = {}
        while index < len(tokens):
            token = tokens[index]
            if token == '}':
                if not nested: raise ValueError('Unexpected VDF closing brace')
                return result, index + 1
            if token == '{' or index + 1 == len(tokens): raise ValueError('Invalid VDF')
            name = atom(token); index += 1
            if tokens[index] == '{': value, index = group(index + 1, True)
            else: value = atom(tokens[index]); index += 1
            result[name] = value
        if nested: raise ValueError('Incomplete VDF')
        return result, index
    return group(0)[0]


@dataclass(frozen=True)
class Installation:
    path: str
    store: str = 'manual'
    steam_root: str = ''
    detected: bool = False

    @property
    def identity(self):
        return hashlib.sha256((self.store + '\0' + str(Path(self.path).resolve())).encode()).hexdigest()[:16]

    def record(self): return asdict(self)


def steam_roots(home=None, platform=None, env=None):
    home = Path(home or Path.home()); platform = platform or sys.platform; env = env or os.environ
    if platform == 'win32':
        roots = [Path(env.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Steam',
                 Path(env.get('PROGRAMFILES', 'C:/Program Files')) / 'Steam']
        if sys.platform == 'win32':
            import winreg
            for hive, path, value in [(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                                      (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')]:
                try:
                    with winreg.OpenKey(hive, path) as handle: roots.insert(0, Path(winreg.QueryValueEx(handle, value)[0]))
                except OSError: pass
        return roots
    return [home / '.steam/steam', home / '.local/share/Steam',
            home / '.var/app/com.valvesoftware.Steam/.local/share/Steam',
            Path(env.get('XDG_DATA_HOME', str(home / '.local/share'))) / 'Steam']


def library_roots(root):
    root=Path(root).resolve();result={root};folders=root/'steamapps/libraryfolders.vdf'
    if folders.is_file():
        for value in vdf(folders.read_text('utf-8-sig')).get('libraryfolders',{}).values():
            path=value.get('path') if isinstance(value,dict) else value
            if isinstance(path,str):result.add(Path(path).expanduser().resolve())
    return result


def discover(roots=None):
    found = {}; errors = []
    for root in roots if roots is not None else steam_roots():
        root = Path(root).expanduser().resolve()
        libraries = {root}
        folders = root / 'steamapps/libraryfolders.vdf'
        if folders.is_file():
            try:
                for value in vdf(folders.read_text('utf-8-sig')).get('libraryfolders', {}).values():
                    path = value.get('path') if isinstance(value, dict) else value
                    if isinstance(path, str): libraries.add(Path(path).expanduser().resolve())
            except (ValueError, OSError) as error: errors.append(str(folders) + ': ' + str(error))
        for library in libraries:
            manifest = library / f'steamapps/appmanifest_{APP_ID}.acf'
            if not manifest.is_file(): continue
            try:
                app = vdf(manifest.read_text('utf-8-sig'))['AppState']
                folder = app['installdir']
                if app.get('appid') != APP_ID or not folder or Path(folder).name != folder or folder in ('.', '..') or '\\' in folder:
                    raise ValueError('Invalid Steam application manifest')
                game = (library / 'steamapps/common' / folder).resolve()
                if not (game / 'MoonSweepers.exe').is_file(): continue
                found[str(game)] = Installation(str(game), 'steam', str(root), True)
            except (ValueError, KeyError, OSError) as error: errors.append(str(manifest) + ': ' + str(error))
    return sorted(found.values(), key=lambda x: x.path), errors


def manual(path, store='manual'):
    game = Path(path).expanduser()
    if game.is_file(): game = game.parent
    game = game.resolve()
    if not (game / 'MoonSweepers.exe').is_file():
        raise ValueError('Choose the Moon Sweepers folder containing MoonSweepers.exe')
    for installed in discover()[0]:
        if Path(installed.path) == game: return installed
    if store == 'manual' and (game / '.egstore').is_dir(): store = 'epic'
    return Installation(str(game), store)


def inspect(installation):
    game = Path(installation.path)
    if not (game / 'MoonSweepers.exe').is_file(): return {'compatible': False, 'reason': 'Game executable is missing', 'hashes': {}}
    if (game / 'MoonSweepers_Data/Managed/Assembly-CSharp.dll').is_file():
        return {'compatible': False, 'reason': 'Older Mono build. These packages require Steam IL2CPP 1.0.5.', 'hashes': {}}
    hashes = {name: sha(game / name) for name in PIN if (game / name).is_file()}
    ok = hashes == PIN
    return {'compatible': ok, 'reason': 'Steam 1.0.5 · IL2CPP · x64' if ok else 'Unqualified game build; update the adapter before loading mods.', 'hashes': hashes}
