"""State, package selection and read-only source/private deployment ownership."""
import os
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import discovery, packages
from .storage import contained, locked, load, sha, write, assert_inactive, is_alias


def copy_file(source, target):
    """Independent writable files; Linux reflinks avoid a second full disk copy."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        try:
            import fcntl
            with source.open('rb') as incoming, target.open('xb') as outgoing:
                fcntl.ioctl(outgoing.fileno(), 0x40049409, incoming.fileno())
            shutil.copystat(source, target)
            return
        except OSError: target.unlink(missing_ok=True)
    shutil.copy2(source, target)


def tree(root):
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in dirs + files:
            if is_alias(base / name): raise ValueError('Source contains a symlink: ' + str(base / name))
        for name in files:
            path = base / name
            result[path.relative_to(root).as_posix()] = sha(path)
    return result


class Service:
    def __init__(self, root, bundle):
        self.root = Path(root).expanduser().absolute()
        contained(self.root, 'state.json')
        self.bundle = Path(bundle).absolute()
        self.root.mkdir(parents=True, exist_ok=True)
        self.state = load(self.root / 'state.json', {'schema': 'moon-loader-state/v1', 'library': {}, 'selected': [], 'view': 'grid', 'installations': [], 'installation': '', 'default_mode': 'installed', 'deployment_modes': {}})
        if self.state.get('schema') != 'moon-loader-state/v1': raise ValueError('Unsupported loader state')

    def save(self):
        with locked(self.root): write(self.root / 'state.json', self.state)

    def import_package(self, path, select=False):
        with locked(self.root):
            location, manifest = packages.install(path, self.root)
            if select and not packages.game_mod(manifest):
                raise ValueError('Companion tools cannot be selected for a game launch')
            self.state['library'][manifest['id']] = location
            if select and manifest['id'] not in self.state['selected']: self.state['selected'].append(manifest['id'])
            write(self.root / 'state.json', self.state)
        return manifest

    def seed(self):
        package_dir = self.bundle / 'packages'
        if not package_dir.exists():
            package_dir = self.bundle.parent / 'vendored/mod-bundle/packages'
        for path in sorted(package_dir.glob('*.msmod')):
            manifest = packages.examine(path)
            if manifest['id'] not in self.state['library']:
                self.import_package(path, select=packages.game_mod(manifest) and manifest.get('default_selected', True))

    def library(self):
        result = {}; errors = {}
        for name, location in self.state['library'].items():
            try:
                folder = contained(self.root / 'library', location)
                manifest = packages.installed(folder)
                if name != manifest['id']: raise ValueError('Library identity mismatch')
                result[name] = (manifest, folder)
            except (ValueError, OSError) as error: errors[name] = str(error)
        return result, errors

    def remove(self, name):
        # Forget only; immutable package versions remain available for recovery.
        with locked(self.root):
            self.state['library'].pop(name)
            self.state['selected'] = [x for x in self.state['selected'] if x != name]
            write(self.root / 'state.json', self.state)

    def installations(self):
        found, errors = discovery.discover()
        merged = {x.path: x for x in found}
        for record in self.state['installations']:
            item = discovery.Installation(**record)
            merged.setdefault(item.path, item)
        return list(merged.values()), errors

    def add_installation(self, path, store='manual'):
        installation = discovery.manual(path, store)
        records = {record['path']: record for record in self.state['installations']}
        records[installation.path] = installation.record()
        self.state['installations'] = list(records.values())
        self.state['installation'] = installation.path
        self.save()
        return installation

    def available_runtimes(self, installation=None):
        result = {('native', abi) for abi in packages.NATIVE_ABIS}
        if installation is not None and self.mode(installation) == 'private':
            from . import managed
            if managed.available(self.bundle, load(self.bundle / 'runtime/receipt.json', {})):
                result.add((packages.MANAGED_KIND, packages.MANAGED_ABI))
        return result

    def runtime_api_abi(self):
        return load(self.bundle / 'runtime/receipt.json', {}).get('runtime_api_abi', 0)

    def selected(self, installation):
        result = discovery.inspect(installation)
        if not result['compatible']: raise ValueError(result['reason'])
        library, errors = self.library()
        for name in self.state['selected']:
            if name in errors: raise ValueError(errors[name])
        if not self.state['selected'] and self.mode(installation) == 'installed': return [], library
        order = packages.resolve({name: pair[0] for name, pair in library.items()}, self.state['selected'], result['hashes'],
                                 available_runtimes=self.available_runtimes(installation), runtime_api_abi=self.runtime_api_abi(),
                                 runtime_readiness_abi=load(self.bundle / 'runtime/receipt.json', {}).get('runtime_readiness_abi', 0),
                                 host_capabilities=load(self.bundle / 'runtime/receipt.json', {}).get('host_capabilities') or {})
        return order, library

    def install_root(self, installation):
        suffix = '-installed' if self.mode(installation) == 'installed' else ''
        return contained(self.root / 'installs', installation.store + '-' + installation.identity + suffix)

    def mode(self, installation):
        # Missing fields are legacy private installations, never write consent.
        mode = self.state.get('deployment_modes', {}).get(installation.identity, self.state.get('default_mode', 'private'))
        if mode not in ('private', 'installed'): raise ValueError('Unknown deployment mode')
        return mode

    def set_mode(self, installation, mode):
        if mode not in ('private', 'installed'): raise ValueError('Unknown deployment mode')
        self.state.setdefault('deployment_modes', {})[installation.identity] = mode
        self.save()

    def accept_normal_saves(self, installation, basis):
        if basis not in ('backed-up', 'fresh'):
            raise ValueError('Confirm backed-up Steam saves or a fresh Steam profile')
        order, library = self.selected(installation)
        self.state.setdefault('save_policy', {})[installation.identity] = {'basis': basis, 'selection': self.save_selection(order, library)}
        self.save()

    @staticmethod
    def save_selection(order, library):
        return hashlib.sha256(json.dumps([(name, library[name][0]) for name in order], sort_keys=True).encode()).hexdigest()

    def save_policy_ready(self, installation, order=None, library=None):
        if order is None: order, library = self.selected(installation)
        policy = self.state.get('save_policy', {}).get(installation.identity, {})
        return isinstance(policy, dict) and policy.get('basis') in ('backed-up', 'fresh') and policy.get('selection') == self.save_selection(order, library)

    def backup_saves(self, installation, source):
        """An explicit user-chosen Steam folder; never discover or seed profiles."""
        from . import public
        if installation.store != 'steam': raise ValueError('Only Steam-origin saves are accepted here')
        source = Path(source).expanduser().absolute()
        contained(source, 'save-backup-probe')
        if not source.is_dir(): raise ValueError('Choose the existing Steam save directory, including its sidecars')
        game = Path(installation.path)
        if source.is_relative_to(game) or game.is_relative_to(source) or self.root.is_relative_to(source) or source.is_relative_to(self.root):
            raise ValueError('Save backups must be separate from game and loader storage')
        with locked(self.root, 'session.lock'), locked(self.root):
            public.assert_stopped(); assert_inactive(self.root)
            before = tree(source)
            if not before: raise ValueError('Save directory is empty; confirm a fresh profile instead')
            location = contained(self.install_root(installation), 'save-backups/' + uuid.uuid4().hex)
            for name in before: copy_file(contained(source, name), contained(location / 'files', name))
            if tree(location / 'files') != before or tree(source) != before:
                raise ValueError('Save files changed while backing up; backup is not qualified')
            for name in before:
                with contained(location / 'files', name).open('rb') as stream: os.fsync(stream.fileno())
            for directory, _, _ in os.walk(location / 'files', topdown=False): public.sync_directory(directory)
            order, library = self.selected(installation)
            write(location / 'receipt.json', {'store': 'steam', 'source': str(source), 'files': before,
                  'game_hashes': discovery.inspect(installation)['hashes'], 'mods': order,
                  'packages': {name: {'version': library[name][0]['version'], 'files': library[name][0]['files']} for name in order},
                  'created_at': datetime.now(timezone.utc).isoformat(),
                  'policy': 'Manual Steam-only backup; never automatically restore over newer progress'})
            public.sync_directory(location)
            self.state.setdefault('save_policy', {})[installation.identity] = {'basis': 'backed-up', 'selection': self.save_selection(order, library)}
            write(self.root / 'state.json', self.state)
            return location

    def set_enabled(self, installation, enabled):
        if self.mode(installation) != 'installed': raise ValueError('Enable/disable applies to installed-game mode')
        from . import public
        with locked(self.root, 'session.lock'):
            assert_inactive(self.root)
            public.set_enabled(self, installation, enabled)

    def uninstall(self, installation):
        if self.mode(installation) != 'installed': raise ValueError('Uninstall applies to installed-game mode; private copies are retained')
        from . import public
        with locked(self.root, 'session.lock'):
            assert_inactive(self.root)
            public.uninstall(self, installation)

    def prepare(self, installation, _session_owner=False):
        """Copy/verify/deploy only. This never starts Steam, Wine or a game."""
        if not _session_owner:
            with locked(self.root, 'session.lock'):
                return self.prepare(installation, _session_owner=True)
        with locked(self.root):
            assert_inactive(self.root)
            order, library = self.selected(installation)
            root = self.install_root(installation)
            source = Path(installation.path).resolve()
            if root.resolve().is_relative_to(source) or source.is_relative_to(root.resolve()):
                raise ValueError('Loader storage and the installed game must be separate folders')
            runtime = self.bundle / 'runtime/windows-x64/version.dll'
            runtime_receipt = load(self.bundle / 'runtime/receipt.json', {})
            if not runtime.is_file() or sha(runtime) != runtime_receipt.get('sha256'):
                raise ValueError('Loader runtime is missing or changed; rebuild the distribution')
            for name in order:
                packages.require_available(library[name][0], self.available_runtimes(installation),
                                           runtime_receipt.get('runtime_api_abi', 0), runtime_receipt.get('runtime_readiness_abi', 0),
                                           runtime_receipt.get('host_capabilities') or {})
            if any(library[name][0].get('shared_claims') for name in order) and runtime_receipt.get('shared_update_abi') != 1:
                raise ValueError('Selected mods require the shared Update runtime; rebuild the distribution')
            if any(library[name][0].get('vehicle_hook') for name in order) and runtime_receipt.get('vehicle_dispatch_abi') != 1:
                raise ValueError('Selected mods require the vehicle adapter runtime; rebuild the distribution')
            if any(library[name][0].get('late_update_hook') for name in order) and runtime_receipt.get('late_update_abi') != 1:
                raise ValueError('Selected mods require the shared LateUpdate runtime; rebuild the distribution')
            if any(library[name][0].get('hook_framework_abi') for name in order) and runtime_receipt.get('hook_framework_abi') != 1:
                raise ValueError('Selected mods require hook framework ABI 1; rebuild the distribution')
            capacity = runtime_receipt.get('max_native_mods', 32)
            if not isinstance(capacity, int) or sum(library[name][0]['kind'] == 'native' for name in order) > capacity:
                raise ValueError('Selected mods exceed this loader runtime capacity; rebuild the distribution')
            if self.mode(installation) == 'installed':
                if runtime_receipt.get('public_bootstrap_abi') != 1:
                    raise ValueError('Runtime does not support installed-game startup; rebuild the distribution')
                from . import public
                return public.prepare(self, installation, order, library, runtime)
            managed_selected = any(library[name][0]['kind'] == packages.MANAGED_KIND for name in order)
            managed_files = {}
            if managed_selected:
                from . import managed
                managed.validate_runtime_receipt(runtime_receipt)
                managed_files = managed.runtime_files(self.bundle)
            root.mkdir(parents=True, exist_ok=True)
            game = contained(root, 'game'); baseline_file = root / 'baseline.json'
            if not baseline_file.exists():
                if game.exists(): raise ValueError('Unowned private game folder; move it aside before preparing')
                if any((source / name).exists() for name in ('version.dll', 'MoonLab', 'winhttp.dll', 'BepInEx', 'doorstop_config.ini')):
                    raise ValueError('Source already has a loader; choose a clean game installation')
                before = tree(source)
                stage = contained(root, 'copy-' + uuid.uuid4().hex)
                stage.mkdir()
                try:
                    for name in before: copy_file(source / name, contained(stage, name))
                    if tree(stage) != before or tree(source) != before: raise ValueError('Source changed during private game copy')
                    write(baseline_file, {'schema': 'moon-loader-copy/v1', 'source': installation.record(), 'files': before, 'state': 'copying'})
                    stage.rename(game)
                    write(baseline_file, {'schema': 'moon-loader-copy/v1', 'source': installation.record(), 'files': before, 'state': 'ready'})
                finally:
                    if stage.exists(): shutil.rmtree(stage)
            baseline = load(baseline_file)
            if baseline['source'] != installation.record() or baseline['state'] != 'ready': raise ValueError('Incomplete or foreign game copy; preserve it and prepare a new data folder')
            # All original assets are verified, not just the three executable pins.
            for name, expected in baseline['files'].items():
                if sha(contained(game, name)) != expected: raise ValueError('Private original file changed: ' + name)
            for name, expected in discovery.PIN.items():
                if sha(source / name) != expected: raise ValueError('Installed game changed; reselect a supported installation')
            self.recover(root)
            files = {'version.dll': runtime.read_bytes()}
            if runtime_receipt.get('runtime_api_abi') == 1:
                from moon_mod_api.runtime_plan import encode, PATH
                files[PATH] = encode({name: library[name][0] for name in order}, order)
            if installation.store == 'steam':
                # Valve documents this public ID file for a directly started
                # executable. It prevents RestartAppIfNecessary from replacing
                # the private launch with the original Steam installation.
                if 'steam_appid.txt' not in baseline['files']:
                    files['steam_appid.txt'] = (discovery.APP_ID + '\n').encode('ascii')
                elif (game / 'steam_appid.txt').read_text().strip() != discovery.APP_ID:
                    raise ValueError('Source Steam application ID differs')
            files.update(managed_files)
            for name in order:
                manifest, folder = library[name]
                if manifest['kind'] == packages.MANAGED_KIND:
                    payload = managed.plugin_files(manifest, folder)
                    if set(payload) & files.keys(): raise ValueError('Managed package destination collision')
                    files.update(payload)
                    continue
                for member in manifest['files']:
                    target = 'MoonLab/mods/' + name + '/' + ('mod.dll' if member == manifest['entry'] else member)
                    if target in files: raise ValueError('Package entry alias collision')
                    files[target] = contained(folder, member).read_bytes()
            if managed_selected:
                managed.preflight(game, files)
                # Keep the executable-input allowlist inside the same deployment
                # transaction as the bytes it authorizes.
                files['BepInEx/MoonLab/allowed-inputs.json'] = managed.allowlist(files)
            self.deploy(root, files, order)
            if managed_selected:
                managed.prepare_cache(game, self.bundle)
            from .settings import seed
            seed(root, order, library)
            profile = contained(root, 'profile')
            for folder in ('AppData/Local', 'AppData/LocalLow', 'AppData/Roaming'):
                contained(profile, folder).mkdir(parents=True, exist_ok=True)
            write(root / 'save-origin.json', {'store': installation.store, 'installation': installation.path,
                  'profile': str(profile), 'policy': 'Fresh private profile. Never seed or merge personal saves.'})
            return root


    def recover(self, root):
        """Restore an interrupted/caught deployment only from checked owned bytes."""
        root = Path(root); pending = contained(root, 'pending-deployment.json')
        if not pending.exists(): return
        journal = load(pending); game = root / 'game'; backup = contained(root, journal['backup'])
        old = journal['before']; new = journal['after']
        for name in set(old['files']) | set(new['files']):
            target = contained(game, name)
            if target.exists() and sha(target) not in {old['files'].get(name),new['files'].get(name)}:
                raise ValueError('Unknown edit blocks deployment recovery: ' + name)
        for name, expected in old['files'].items():
            if sha(contained(backup / 'old',name)) != expected: raise ValueError('Changed deployment backup')
        for name, expected in old['files'].items():
            target = contained(game,name); temporary = contained(backup / 'restore',name)
            temporary.parent.mkdir(parents=True,exist_ok=True); temporary.write_bytes(contained(backup / 'old',name).read_bytes())
            target.parent.mkdir(parents=True,exist_ok=True); os.replace(temporary,target)
        for name in set(new['files']) - set(old['files']): contained(game,name).unlink(missing_ok=True)
        for name, expected in old['files'].items():
            if sha(contained(game,name)) != expected: raise ValueError('Recovery read-back failed')
        write(root / 'deployment.json',old); pending.unlink(); shutil.rmtree(backup)

    def deploy(self, root, files, order):
        root = Path(root); game = root / 'game'; old = load(root / 'deployment.json',{'files':{},'order':[]})
        import hashlib
        new = {'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}, 'order':order}
        for name, expected in old['files'].items():
            if sha(contained(game,name)) != expected: raise ValueError('Owned mod file changed: ' + name)
        for name in files:
            if contained(game,name).exists() and name not in old['files']: raise ValueError('Unowned deployment file: ' + name)
        backup_name = 'backups/' + uuid.uuid4().hex; backup = contained(root,backup_name)
        for name in old['files']: copy_file(contained(game,name),contained(backup / 'old',name))
        for name, data in files.items():
            path = contained(backup / 'new',name); path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        pending = contained(root, 'pending-deployment.json')
        if pending.exists(): raise ValueError('A pending deployment must be recovered first')
        write(pending,{'before':old,'after':new,'backup':backup_name})
        try:
            for name in files:
                target=contained(game,name);target.parent.mkdir(parents=True,exist_ok=True)
                os.replace(contained(backup / 'new',name),target)
            for name in set(old['files']) - set(files): contained(game,name).unlink()
            if any(sha(contained(game,name)) != expected for name,expected in new['files'].items()): raise ValueError('Deployment read-back failed')
            write(root / 'deployment.json',new)
            pending.unlink();shutil.rmtree(backup)
        except Exception:
            self.recover(root)
            raise
