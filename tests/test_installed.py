"""Installed-mode filesystem/launch failures use disposable synthetic inputs."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import test_loader
from moonloader import discovery, launch, public
from moonloader.service import Service
from moonloader.storage import load, write, sha, locked
REAL_ASSERT_STOPPED = public.assert_stopped


class InstalledChecks(unittest.TestCase):
    def setUp(self):
        test_loader.LoaderChecks.setUp(self)
        # Filesystem fixtures never mutate a real installation or inspect/control
        # the user's game. Process detection is exercised separately.
        stopped = patch('moonloader.public.assert_stopped'); stopped.start(); self.addCleanup(stopped.stop)

    def fixture(self):
        service, installation = test_loader.LoaderChecks.prepared_fixture(self)
        service.set_mode(installation, 'installed')
        receipt = service.bundle / 'runtime/receipt.json'
        write(receipt, {**load(receipt), 'public_bootstrap_abi': 1, 'runtime_api_abi': 1})
        service.accept_normal_saves(installation, 'fresh')
        return service, installation

    def test_new_data_defaults_installed_legacy_data_stays_private(self):
        service = Service(self.root/'new', self.root/'bundle')
        installation = discovery.Installation(str(self.root/'source'))
        self.assertEqual(service.mode(installation), 'installed')
        state = dict(service.state); state.pop('default_mode'); state.pop('deployment_modes')
        write(self.root/'legacy/state.json', state)
        legacy = Service(self.root/'legacy', self.root/'bundle')
        self.assertEqual(legacy.mode(installation), 'private')

    def test_additive_prepare_keeps_originals_no_game_or_proton_copy(self):
        service, installation = self.fixture(); game = Path(installation.path)
        (game/'sentinel.txt').write_bytes(b'untouched')
        with patch('moonloader.service.copy_file', side_effect=AssertionError('No original copies')), patch('subprocess.Popen') as spawn:
            root = service.prepare(installation); service.prepare(installation)
        spawn.assert_not_called()
        self.assertFalse((root/'game').exists()); self.assertFalse((root/'proton').exists())
        self.assertFalse((game/'steam_appid.txt').exists())
        self.assertEqual({n:sha(game/n) for n in discovery.PIN}, discovery.PIN)
        self.assertEqual((game/'sentinel.txt').read_bytes(), b'untouched')
        deployed = load(root/'deployment.json')
        self.assertEqual(deployed['order'], ['test-mod'])
        self.assertEqual((game/public.CONFIG).read_bytes(), public.config(installation, deployed['generation'], ['test-mod'], True))

    def test_private_mode_switch_preserves_private_progress(self):
        service, installation = self.fixture(); service.set_mode(installation, 'private')
        private_root = service.prepare(installation)
        save = private_root/'profile/progress'; save.write_bytes(b'private progress')
        service.set_mode(installation, 'installed'); public_root = service.prepare(installation)
        self.assertNotEqual(private_root, public_root)
        service.uninstall(installation)
        self.assertEqual(save.read_bytes(), b'private progress')
        service.set_mode(installation, 'private'); service.prepare(installation)
        self.assertEqual(save.read_bytes(), b'private progress')

    def test_disable_empty_selection_uninstall_and_reinstall(self):
        service, installation = self.fixture(); root = service.prepare(installation); game = Path(installation.path)
        setting = game/'MoonLab/settings/user.ini'; setting.parent.mkdir(exist_ok=True); setting.write_bytes(b'user edit')
        log = game/'MoonLab/logs/user.log'; log.write_bytes(b'keep')
        service.set_enabled(installation, False); self.assertIn(b'enabled=0', (game/public.CONFIG).read_bytes())
        service.set_enabled(installation, True); self.assertIn(b'enabled=1', (game/public.CONFIG).read_bytes())
        service.state['selected'] = []; service.prepare(installation)
        self.assertIn(b'enabled=0\nmods=\n', (game/public.CONFIG).read_bytes())
        service.uninstall(installation); service.uninstall(installation)
        self.assertFalse((game/'version.dll').exists()); self.assertFalse((game/public.CONFIG).exists())
        self.assertEqual(setting.read_bytes(), b'user edit'); self.assertEqual(log.read_bytes(), b'keep')
        self.assertFalse(load(root/'deployment.json')['files'])
        service.state['selected'] = ['test-mod']; service.prepare(installation)

    def test_unknown_update_can_disable_uninstall_never_restore_old_game(self):
        service, installation = self.fixture(); service.prepare(installation); game = Path(installation.path)
        (game/'GameAssembly.dll').write_bytes(b'new Steam update')
        service.set_enabled(installation, False)
        with self.assertRaisesRegex(ValueError, 'changed'): service.set_enabled(installation, True)
        service.uninstall(installation)
        self.assertEqual((game/'GameAssembly.dll').read_bytes(), b'new Steam update')

    def test_collision_alias_and_other_data_owner_are_preserved(self):
        service, installation = self.fixture(); game = Path(installation.path)
        (game/'version.dll').write_bytes(b'another loader')
        with self.assertRaisesRegex(ValueError, 'Unowned'): service.prepare(installation)
        self.assertFalse((game/'MoonLab').exists())
        (game/'version.dll').unlink(); (game/'VERSION.DLL').write_bytes(b'case collision')
        with self.assertRaisesRegex(ValueError, 'Case alias'): service.prepare(installation)
        (game/'VERSION.DLL').unlink(); root = service.prepare(installation)
        other = Service(self.root/'other-data', service.bundle)
        with self.assertRaisesRegex(ValueError, 'another loader'):
            with public.operation(other.install_root(installation), game): pass
        self.assertEqual(load(root/'deployment.json')['order'], ['test-mod'])

    def test_competing_loader_is_reported_before_any_owned_game_writes(self):
        service, installation = self.fixture(); game = Path(installation.path)
        (game/'winhttp.dll').write_bytes(b'other bootstrap')
        preview = launch.plan(service, installation, platform='win32', check_client=False)['deployment']
        self.assertTrue(any('coexistence' in item for item in preview['conflicts']))
        with self.assertRaisesRegex(ValueError, 'coexistence'): service.prepare(installation)
        self.assertEqual((game/'winhttp.dll').read_bytes(), b'other bootstrap')
        self.assertFalse((game/'MoonLab').exists())

    def test_enable_refuses_new_competing_loader_but_disable_and_uninstall_work(self):
        service, installation = self.fixture(); service.prepare(installation); game = Path(installation.path)
        (game/'winhttp.dll').write_bytes(b'new competing loader')
        service.set_enabled(installation, False)
        disabled = (game/public.CONFIG).read_bytes()
        with self.assertRaisesRegex(ValueError, 'coexistence'): service.set_enabled(installation, True)
        self.assertEqual((game/public.CONFIG).read_bytes(), disabled)
        service.uninstall(installation)
        self.assertEqual((game/'winhttp.dll').read_bytes(), b'new competing loader')

    def test_case_alias_of_control_directory_is_rejected_before_ownership(self):
        service, installation = self.fixture(); game = Path(installation.path)
        alias = game/'moonlab'; alias.mkdir(); (alias/'user.txt').write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError, 'Case alias'): service.prepare(installation)
        self.assertEqual((alias/'user.txt').read_bytes(), b'preserve')
        self.assertFalse((alias/'owner.json').exists())
        self.assertFalse((game/'version.dll').exists())

    def test_package_destination_aliases_reject_before_transaction(self):
        service, installation = self.fixture(); game = Path(installation.path)
        for extra in ({'MOD.dll':b'alias'}, {'Assets/a':b'a', 'assets/b':b'b'}):
            with self.subTest(extra=list(extra)):
                manifest = test_loader.descriptor('alias-mod'); manifest['entry'] = 'entry.dll'
                manifest['game']['hashes'] = discovery.PIN
                files = {'entry.dll':b'inert DLL', 'icon.png':test_loader.PNG, **extra}
                manifest['files'] = {n:public.digest(data) for n,data in files.items()}
                package = self.root/'alias.msmod'
                with zipfile.ZipFile(package,'w') as archive:
                    archive.writestr('manifest.json',json.dumps(manifest))
                    for name,data in files.items(): archive.writestr(name,data)
                service.import_package(package, select=True); service.accept_normal_saves(installation, 'fresh')
                with self.assertRaisesRegex(ValueError, 'alias|collision'): service.prepare(installation)
                self.assertFalse((game/'version.dll').exists())
                self.assertFalse((service.install_root(installation)/'pending-installed.json').exists())

    def test_installed_api1_plan_is_hashed_and_unknown_edit_preserved(self):
        from moon_mod_api.runtime_plan import encode, PATH
        service, installation = self.fixture(); game = Path(installation.path)
        receipt_path = service.bundle/'runtime/receipt.json'
        write(receipt_path, {**load(receipt_path), 'runtime_api_abi':1})
        pins = service.library()[0]['test-mod'][0]['game']['hashes']
        for name, contracts in (
            ('test-provider', {'provides': {'test-provider.api': {'abi':2,'size':32}}}),
            ('test-consumer', {'requires':['test-provider'], 'requires_apis':[{'api':'test-provider.api','abi':2,'min_size':16}]})):
            manifest = test_loader.descriptor(name)
            manifest.update(abi='MoonLab_ModStart/v6', runtime_api_abi=1, **contracts)
            manifest['game']['hashes'] = pins
            files = {'mod.dll':b'inert provider/consumer fixture', 'icon.png':test_loader.PNG}
            manifest['files'] = {n:hashlib.sha256(data).hexdigest() for n,data in files.items()}
            package = self.root/(name+'.msmod')
            with zipfile.ZipFile(package,'w') as archive:
                archive.writestr('manifest.json',json.dumps(manifest))
                for n,data in files.items(): archive.writestr(n,data)
            service.import_package(package, select=True)
        service.accept_normal_saves(installation, 'fresh')
        order, library = service.selected(installation)
        root = service.prepare(installation); deployed = load(root/'deployment.json')
        expected = encode({name:pair[0] for name,pair in library.items()}, order)
        self.assertEqual((game/PATH).read_bytes(), expected)
        self.assertEqual(deployed['files'][PATH], hashlib.sha256(expected).hexdigest())
        inventory = game/f'MoonLab/deployments/{deployed["generation"]}/files.txt'
        self.assertIn(hashlib.sha256(expected).hexdigest()+' '+PATH, inventory.read_text())
        (game/PATH).write_bytes(b'unknown runtime plan edit')
        with self.assertRaisesRegex(ValueError, 'changed'): service.prepare(installation)
        self.assertEqual((game/PATH).read_bytes(), b'unknown runtime plan edit')

    def test_owned_changes_missing_files_symlinks_hardlinks_block_removal(self):
        service, installation = self.fixture(); root = service.prepare(installation); game = Path(installation.path)
        original = (game/'version.dll').read_bytes()
        (game/'version.dll').write_bytes(b'changed by someone else')
        with self.assertRaisesRegex(ValueError, 'changed'): service.uninstall(installation)
        self.assertEqual((game/'version.dll').read_bytes(), b'changed by someone else')
        (game/'version.dll').unlink()
        with self.assertRaisesRegex(ValueError, 'missing'): service.uninstall(installation)
        outside = self.root/'outside'; outside.write_bytes(original)
        (game/'version.dll').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Symlink'): service.uninstall(installation)
        (game/'version.dll').unlink(); os.link(outside, game/'version.dll')
        with self.assertRaisesRegex(ValueError, 'independent'): service.uninstall(installation)
        self.assertTrue((root/'deployment.json').exists())

    def test_running_game_and_target_lock_block_operations(self):
        service, installation = self.fixture(); service.prepare(installation); game = Path(installation.path)
        with patch('moonloader.public.assert_stopped', side_effect=ValueError('still running')):
            with self.assertRaisesRegex(ValueError, 'still running'): service.uninstall(installation)
        with locked(game/'MoonLab'):
            with self.assertRaisesRegex(ValueError, 'Another loader'): service.uninstall(installation)

    @unittest.skipIf(os.name == 'nt', 'Linux process boundary')
    def test_process_scan_recognizes_windows_and_unix_game_arguments(self):
        process = self.root/'123'; process.mkdir(); cmdline = process/'cmdline'
        original_iterdir = Path.iterdir
        def processes(path):
            return iter([process]) if path == Path('/proc') else original_iterdir(path)
        with patch.object(Path, 'iterdir', processes):
            for command in (b'/game/MoonSweepers.exe\0', b'wine64\0Z:\\game\\MoonSweepers.exe\0'):
                cmdline.write_bytes(command)
                with self.assertRaisesRegex(ValueError, 'still running'): REAL_ASSERT_STOPPED()
            cmdline.write_bytes(b'python3\0tools/test.py\0'); REAL_ASSERT_STOPPED()

    def test_public_launch_does_not_claim_steam_as_owned_game(self):
        from types import SimpleNamespace
        service, installation = self.fixture(); process = SimpleNamespace(pid=os.getpid())
        record = launch.plan(service, installation, platform='win32', check_client=False)
        with patch('moonloader.launch.plan', return_value=record), patch.object(service, 'prepare'), patch('subprocess.Popen', return_value=process):
            observed, _ = launch.start(service, installation)
        self.assertIs(observed, process); self.assertFalse((service.root/'active.json').exists())
        self.assertFalse(hasattr(process, '_moon_lease'))
        with locked(service.root, 'session.lock'): pass

    def test_failure_and_restart_restore_exact_prior_deployment(self):
        service, installation = self.fixture(); root = service.prepare(installation); game = Path(installation.path)
        before = load(root/'deployment.json'); replace_file = os.replace; failed = False
        def interrupt(source, target):
            nonlocal failed
            if str(target).endswith('/active.txt') and not failed:
                failed = True; raise OSError('injected selection commit failure')
            return replace_file(source, target)
        with patch('moonloader.public.os.replace', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'injected'): service.prepare(installation)
        self.assertEqual(load(root/'deployment.json'), before)
        self.assertTrue(all(public.current_hash(game, n) == h for n,h in before['files'].items()))
        self.assertFalse((root/'pending-installed.json').exists())
        # Actual process interruption after the active selection was renamed.
        def crash_after_switch(source, target):
            result = replace_file(source, target)
            if str(target).endswith('/active.txt'): raise KeyboardInterrupt()
            return result
        with patch('moonloader.public.os.replace', side_effect=crash_after_switch):
            with self.assertRaises(KeyboardInterrupt): service.prepare(installation)
        self.assertTrue((root/'pending-installed.json').exists())
        with public.operation(root, game): public.recover(root, installation)
        self.assertEqual(load(root/'deployment.json'), before)
        self.assertTrue(all(public.current_hash(game, n) == h for n,h in before['files'].items()))

    def test_unknown_edit_during_recovery_is_preserved(self):
        service, installation = self.fixture(); root = service.prepare(installation); game = Path(installation.path)
        old = load(root/'deployment.json'); stage = game/('.moonlab-stage-' + 'a'*32); stage.mkdir()
        for name in old['files']:
            path = stage/'old'/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes((game/name).read_bytes())
        write(root/'pending-installed.json', {'before':old,'after':old,'stage':stage.name})
        (game/'version.dll').write_bytes(b'unrecognized edit')
        with self.assertRaisesRegex(ValueError, 'Unknown edit'): service.uninstall(installation)
        self.assertEqual((game/'version.dll').read_bytes(), b'unrecognized edit')

    def test_game_start_during_apply_defers_rollback_until_closed(self):
        service, installation = self.fixture(); root = service.prepare(installation); game = Path(installation.path)
        before = load(root/'deployment.json'); replace_file = os.replace; running = False
        def stopped():
            if running: raise ValueError('Game is still running')
        def start_after_write(source, destination):
            nonlocal running
            result = replace_file(source, destination)
            if '/new/' in str(source): running = True
            elif running: self.fail('Rollback mutated files while the game was running')
            return result
        with patch('moonloader.public.assert_stopped', side_effect=stopped), patch('moonloader.public.os.replace', side_effect=start_after_write):
            with self.assertRaisesRegex(ValueError, 'still running'): service.prepare(installation)
            self.assertTrue((root/'pending-installed.json').exists())
            with self.assertRaisesRegex(ValueError, 'still running'): public.recover(root, installation)
        with public.operation(root, game): public.recover(root, installation)
        self.assertEqual(load(root/'deployment.json'), before)
        self.assertTrue(all(public.current_hash(game, n) == h for n,h in before['files'].items()))

    def test_edit_after_recovery_preflight_is_preserved(self):
        service, installation = self.fixture(); root = service.prepare(installation); game = Path(installation.path)
        old = load(root/'deployment.json'); stage = game/('.moonlab-stage-' + 'a'*32); stage.mkdir()
        for name in old['files']:
            path = stage/'old'/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes((game/name).read_bytes())
        write(root/'pending-installed.json', {'before':old,'after':old,'stage':stage.name})
        write_bytes = public.file_bytes
        def external_edit(path, data):
            write_bytes(path, data)
            if str(path).endswith('/restore/version.dll'): (game/'version.dll').write_bytes(b'edit during recovery')
        with patch('moonloader.public.file_bytes', side_effect=external_edit):
            with public.operation(root, game):
                with self.assertRaisesRegex(ValueError, 'Unknown edit'): public.recover(root, installation)
        self.assertEqual((game/'version.dll').read_bytes(), b'edit during recovery')
        self.assertTrue((root/'pending-installed.json').exists())

    def test_first_install_crash_can_recover_without_a_committed_receipt(self):
        service, installation = self.fixture(); game = Path(installation.path); root = service.install_root(installation)
        replace_file = os.replace
        def crash(source, target):
            result = replace_file(source, target)
            if str(target).endswith('/version.dll'): raise KeyboardInterrupt()
            return result
        with patch('moonloader.public.os.replace', side_effect=crash):
            with self.assertRaises(KeyboardInterrupt): service.prepare(installation)
        self.assertTrue((root/'pending-installed.json').exists()); self.assertFalse((root/'deployment.json').exists())
        service.prepare(installation)
        self.assertFalse((root/'pending-installed.json').exists()); self.assertTrue((game/public.CONFIG).exists())

    def test_first_install_failure_before_payload_writes_cleans_journal(self):
        service, installation = self.fixture(); root = service.install_root(installation)
        validate = public.validate_game; calls = 0
        def fail_after_staging(item, root=None):
            nonlocal calls
            calls += 1
            if calls == 2: raise ValueError('Game changed after staging')
            return validate(item, root)
        with patch('moonloader.public.validate_game', side_effect=fail_after_staging):
            with self.assertRaisesRegex(ValueError, 'after staging'): service.prepare(installation)
        self.assertFalse((root/'pending-installed.json').exists())
        self.assertFalse((Path(installation.path)/'version.dll').exists())
        service.prepare(installation)

    def test_disable_before_prepare_has_no_installed_side_effects(self):
        service, installation = self.fixture()
        with self.assertRaisesRegex(ValueError, 'Prepare'): service.set_enabled(installation, False)
        self.assertFalse((Path(installation.path)/'MoonLab').exists())

    def test_mid_apply_steam_change_aborts_without_overwriting_it(self):
        service, installation = self.fixture(); service.prepare(installation); game = Path(installation.path)
        original = public.validate_game; calls = 0
        def updating(item, root=None):
            nonlocal calls
            calls += 1
            if calls == 3: (game/'GameAssembly.dll').write_bytes(b'updated concurrently')
            return original(item, root)
        with patch('moonloader.public.validate_game', side_effect=updating):
            with self.assertRaisesRegex(ValueError, 'changed'): service.prepare(installation)
        self.assertEqual((game/'GameAssembly.dll').read_bytes(), b'updated concurrently')

    @unittest.skipIf(os.name == 'nt' or not Path('/dev/shm').is_dir(), 'Requires a separate Linux tmpfs volume')
    def test_data_and_game_on_different_volumes(self):
        service, installation = self.fixture()
        with tempfile.TemporaryDirectory(dir='/dev/shm', prefix='moon-loader-test-') as directory:
            game = Path(directory)/'game'; shutil.copytree(installation.path, game)
            if game.stat().st_dev == service.root.stat().st_dev: self.skipTest('Test paths are on the same volume')
            installation = replace(installation, path=str(game))
            service.accept_normal_saves(installation, 'fresh')
            service.prepare(installation); service.uninstall(installation)
            self.assertFalse((game/'version.dll').exists())

    def test_explicit_steam_save_backup_preserves_source_and_sidecars(self):
        service, installation = self.fixture(); saves = self.root/'chosen-steam-saves'; saves.mkdir()
        (saves/'slot.json').write_bytes(b'progress'); (saves/'slot.mod').write_bytes(b'sidecar')
        location = service.backup_saves(installation, saves)
        self.assertEqual((location/'files/slot.mod').read_bytes(), b'sidecar')
        self.assertEqual((saves/'slot.json').read_bytes(), b'progress')
        self.assertEqual(load(location/'receipt.json')['store'], 'steam')
        self.assertEqual(load(location/'receipt.json')['packages']['test-mod']['version'], '1.0.0')
        with self.assertRaisesRegex(ValueError, 'Steam-origin'): service.backup_saves(replace(installation, store='epic'), saves)
        nested = Path(installation.path)/'MoonSweepers_Data'; nested.mkdir()
        with self.assertRaisesRegex(ValueError, 'separate'): service.backup_saves(installation, nested)

    def test_save_choice_required_and_unknown_runtime_refused_before_writes(self):
        service, installation = self.fixture(); game = Path(installation.path)
        service.state.pop('save_policy')
        with self.assertRaisesRegex(ValueError, 'normal Steam saves'): service.prepare(installation)
        self.assertFalse((game/'MoonLab').exists())
        service.accept_normal_saves(installation, 'fresh')
        receipt_path = service.bundle/'runtime/receipt.json'; runtime = load(receipt_path); runtime.pop('public_bootstrap_abi'); write(receipt_path,runtime)
        with self.assertRaisesRegex(ValueError, 'startup'): service.prepare(installation)
        self.assertFalse((game/'MoonLab').exists())

    def test_save_choice_is_invalidated_by_changed_package_selection(self):
        service, installation = self.fixture()
        self.assertTrue(service.save_policy_ready(installation))
        order, library = service.selected(installation)
        changed = dict(library); manifest, folder = changed['test-mod']
        changed['test-mod'] = ({**manifest, 'version':'2.0.0'}, folder)
        self.assertFalse(service.save_policy_ready(installation, order, changed))

    def test_steam_plan_uses_no_private_prefix_environment_or_runtime(self):
        service, installation = self.fixture()
        for platform in ('win32','linux'):
            with patch('subprocess.Popen') as spawn:
                record = launch.plan(service, installation, platform=platform, check_client=False)
            spawn.assert_not_called(); self.assertEqual(record['env'], {})
            self.assertNotIn('private_proton', record); self.assertIn('-applaunch', record['command'])
            self.assertNotIn('MoonSweepers.exe', record['command']); self.assertEqual(record['mode'], 'installed')
            self.assertEqual(record['deployment']['original_game_replacements'], [])
        self.assertFalse((Path(installation.path)/'MoonLab').exists())

    def test_native_public_config_and_build_guard_ordering(self):
        binary = self.root/'public-check'
        subprocess.run(['clang','-std=c11','-fshort-wchar','-Wall','-Wextra','-Werror',
                        '-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all',
                        str(test_loader.ROOT/'tests/native_public_checks.c'),'-o',str(binary)],check=True)
        result = subprocess.run([str(binary)],check=True,capture_output=True,text=True)
        self.assertIn('guard ordering passed', result.stdout)

    def test_public_build_pins_and_settings_match_python_contract(self):
        # These are independent runtime/installer boundaries; drift can either
        # admit unsupported native reads or silently drop editable settings.
        from moonloader.settings import ENVIRONMENT
        source = (test_loader.ROOT/'runtime/loader/public.h').read_text()
        from game_profiles_native import check
        check(test_loader.ROOT)
        profiles = (test_loader.ROOT/'runtime/loader/game_profiles.generated.h').read_text()
        for value in discovery.PIN.values(): self.assertIn(value, profiles)
        for name, variable in ENVIRONMENT.items(): self.assertIn('{"'+name+'","'+variable+'"}', source)


if __name__ == '__main__': unittest.main()
