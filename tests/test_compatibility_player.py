"""Player admission uses inert fixtures, never an installed game or executable mod."""
import copy
import hashlib
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

import test_loader
from moonloader import compatibility, discovery, game_profiles, public
from moonloader.storage import load, write

ROOT = Path(__file__).resolve().parents[1]


class CompatibilityPlayerChecks(unittest.TestCase):
    setUp = test_loader.LoaderChecks.setUp
    prepared_fixture = test_loader.LoaderChecks.prepared_fixture

    def add_mod(self, service, name='portable-feature', **fields):
        manifest = test_loader.descriptor(name)
        if fields.get('abi', 'MoonLab_ModStart/v8') == 'MoonLab_ModStart/v8':
            manifest.update(abi='MoonLab_ModStart/v8', runtime_api_abi=1,
                            game_access='adapter', game_api_abi=1,
                            requires_game={'unity.clock': {'abi': 1, 'min_size': 16}},
                            game={'id': 'moon-sweepers', 'appid': '5335510'})
        manifest.update(fields)
        payload = {'mod.dll': b'Original immutable inert feature bytes', 'icon.png': test_loader.PNG}
        manifest['files'] = {n: hashlib.sha256(data).hexdigest() for n, data in payload.items()}
        path = self.root/(name+'.msmod')
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            for n, data in payload.items(): archive.writestr(n, data)
        service.import_package(path)
        return manifest

    def fixture(self):
        service, installation = self.prepared_fixture()
        service.set_mode(installation, 'installed')
        self.add_mod(service)
        service.state['selected'] = ['portable-feature']; service.save()
        profile = service.inspect(installation)['profile']
        path = service.bundle/'runtime/receipt.json'
        receipt = {**load(path), 'runtime_api_abi': 1, 'runtime_readiness_abi': 1,
                   'public_bootstrap_abi': 1, 'native_package_abis': list(range(1, 9)),
                   'game_adapter': {'abi': 1, 'profiles': {
                       profile['id']: {'digest': profile['digest'], 'capabilities': profile['capabilities']}}}}
        write(path, receipt)
        stopped = patch('moonloader.public.assert_stopped'); stopped.start(); self.addCleanup(stopped.stop)
        return service, installation

    def add_profile(self, service, *, same_game_assembly=False, advertise=True):
        catalog = copy.deepcopy(game_profiles.load()); second = copy.deepcopy(catalog['profiles'][0])
        second.update(id='moon-sweepers.fixture.second.win-x64', version='2.fixture')
        source = self.root/'second-source'; source.mkdir()
        for name in game_profiles.GAME_FILES:
            data = (self.root/'source'/name).read_bytes() if same_game_assembly and name == 'GameAssembly.dll' else ('second fixture '+name).encode()
            (source/name).write_bytes(data)
        second['hashes'] = {name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in game_profiles.GAME_FILES}
        second['native']['domain_rva'] += 16
        catalog['profiles'].append(second); service.profile_catalog = catalog
        profile = game_profiles.identify(second['hashes'], catalog)
        if advertise:
            path = service.bundle/'runtime/receipt.json'; receipt = load(path)
            receipt['game_adapter']['profiles'][profile['id']] = {'digest': profile['digest'], 'capabilities': profile['capabilities']}
            write(path, receipt)
        return discovery.Installation(str(source), 'steam', str(self.root/'Steam'))

    def test_same_immutable_feature_prepares_two_reviewed_synthetic_profiles(self):
        service, first = self.fixture(); second = self.add_profile(service)
        library = service.library()[0]; folder = library['portable-feature'][1]
        before = (folder/'mod.dll').read_bytes(); outputs = []
        with patch('subprocess.Popen') as spawn:
            for installation in (first, second):
                report = service.compatibility(installation)
                self.assertTrue(report['allowed'], report)
                self.assertEqual(report['status'], 'requirements-matched')
                service.accept_normal_saves(installation, 'fresh')
                root = service.prepare(installation)
                plan = (Path(installation.path)/'MoonLab/runtime-plan.bin').read_bytes()
                self.assertTrue(plan.startswith(b'MSAPI\x02\0\0'))
                self.assertIn(report['profile']['digest'].encode(), plan)
                receipt = load(root/'deployment.json')
                self.assertEqual(receipt['game_profile'], report['profile'])
                self.assertFalse(any((root/n).exists() for n in ('game', 'proton', 'profile')))
                outputs.append((Path(installation.path)/'MoonLab/mods/portable-feature/mod.dll').read_bytes())
        spawn.assert_not_called(); self.assertEqual(outputs, [before, before])

    def test_catalog_only_and_stale_physical_profile_cannot_grant_admission(self):
        service, installation = self.fixture(); second = self.add_profile(service, advertise=False)
        self.assertFalse(service.compatibility(second)['allowed'])
        profile = service.profile_catalog['profiles'][0]
        profile['native']['domain_rva'] += 16
        report = service.compatibility(installation)
        self.assertFalse(report['allowed'])
        self.assertIn('runtime-profile-unavailable', [r['code'] for r in report['reasons']])
        with self.assertRaises(ValueError): service.prepare(installation)
        self.assertFalse((Path(installation.path)/'MoonLab').exists())

    def test_legacy_subset_pin_stays_pinned_to_legacy_runtime_profile(self):
        service, installation = self.fixture(); second = self.add_profile(service, same_game_assembly=True)
        legacy = test_loader.descriptor('legacy-feature')
        legacy['game']['hashes'] = {'GameAssembly.dll': service.inspect(installation)['hashes']['GameAssembly.dll']}
        self.add_mod(service, 'legacy-feature', abi='MoonLab_ModStart/v1', game=legacy['game'])
        service.state['selected'] = ['legacy-feature']
        result = service.compatibility(second)
        self.assertFalse(result['allowed'])
        self.assertIn('legacy-runtime-profile-unavailable', [r['code'] for r in result['mods']['legacy-feature']['reasons']])

    def test_global_pin_override_does_not_change_reviewed_profile_admission(self):
        service, installation = self.fixture()
        real_catalog = json.loads(game_profiles.PATH.read_text())
        self.assertEqual(discovery.PIN, service.inspect(installation)['hashes'])
        self.assertFalse(discovery.inspect(installation, real_catalog)['compatible'])

    def test_game_change_between_selection_and_prepare_refuses_before_writes(self):
        service, installation = self.fixture(); service.accept_normal_saves(installation, 'fresh')
        inspect = service.inspect; calls = 0
        def changing(item):
            nonlocal calls
            calls += 1
            if calls == 2: (Path(item.path)/'GameAssembly.dll').write_bytes(b'concurrent Steam update')
            return inspect(item)
        with patch.object(service, 'inspect', side_effect=changing), patch('subprocess.Popen') as spawn:
            with self.assertRaises(ValueError): service.prepare(installation)
        spawn.assert_not_called(); self.assertFalse((Path(installation.path)/'MoonLab').exists())

    def test_private_payload_change_after_assessment_cannot_be_deployed(self):
        service, installation = self.fixture(); service.set_mode(installation, 'private')
        manifest, folder = service.library()[0]['portable-feature']; payload = folder/manifest['entry']
        read_bytes = Path.read_bytes
        def changing(path):
            if path == payload: path.write_bytes(b'changed after assessment')
            return read_bytes(path)
        with patch.object(Path, 'read_bytes', changing), patch('subprocess.Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'Package changed'): service.prepare(installation)
        spawn.assert_not_called()
        self.assertFalse((service.install_root(installation)/'game/version.dll').exists())

    def test_v8_abi_runtime_tampering_and_legacy_fallback_are_explicit(self):
        service, installation = self.fixture(); path = service.bundle/'runtime/receipt.json'; receipt = load(path)
        receipt.pop('native_package_abis'); write(path, receipt)
        report = service.compatibility(installation)
        self.assertFalse(report['allowed'])
        self.assertIn('native-package-abi-unavailable', [r['code'] for r in report['mods']['portable-feature']['reasons']])
        service.state['selected'] = ['test-mod']; receipt.pop('game_adapter'); write(path, receipt)
        self.assertTrue(service.compatibility(installation)['allowed'])
        receipt.pop('game_pins'); write(path, receipt)
        self.assertFalse(service.compatibility(installation)['allowed'])
        (service.bundle/'runtime/windows-x64/version.dll').write_bytes(b'tampered')
        self.assertIn('runtime-integrity', [r['code'] for r in service.compatibility(installation)['reasons']])

    def test_individual_mod_assessment_adds_required_frameworks_without_selecting(self):
        service, installation = self.fixture()
        self.add_mod(service, 'some-framework', requires_game={}, provides={'some-framework.demo': {'abi': 3, 'size': 24}})
        self.add_mod(service, requires=['some-framework'], requires_apis=[{'api': 'some-framework.demo', 'abi': 3, 'min_size': 16}])
        service.state['selected'] = []; service.save(); before = (service.root/'state.json').read_bytes()
        report = service.mod_compatibility(installation, 'portable-feature')
        self.assertTrue(report['allowed'], report)
        requirement = next(r for r in report['mods']['portable-feature']['requirements'] if r.get('kind') == 'framework-api')
        self.assertEqual(requirement['provider'], 'some-framework'); self.assertTrue(requirement['available'])
        self.assertEqual((service.root/'state.json').read_bytes(), before)
        self.assertFalse((Path(installation.path)/'MoonLab').exists())

    def test_cli_unknown_report_does_not_import_select_prepare_or_launch(self):
        service, installation = self.fixture(); (Path(installation.path)/'GameAssembly.dll').write_bytes(b'unknown game update')
        before = (service.root/'state.json').read_bytes(); library = sorted(service.state['library'])
        spec = importlib.util.spec_from_file_location('compatibility_cli', ROOT/'loader/main.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        args = ['loader', '--data', str(service.root), '--bundle', str(service.bundle), '--game', installation.path, '--compatibility']
        with patch.object(sys, 'argv', args), patch.object(discovery, 'manual', return_value=installation), \
                patch.object(discovery, 'discover', return_value=([installation], [])), \
                patch('subprocess.Popen') as spawn, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(module.main(), 0)
        result = json.loads(output.getvalue()); self.assertEqual(result['status'], 'unknown'); self.assertFalse(result['allowed'])
        spawn.assert_not_called(); self.assertEqual((service.root/'state.json').read_bytes(), before)
        self.assertEqual(sorted(service.state['library']), library); self.assertFalse((Path(installation.path)/'MoonLab').exists())

    def test_ui_unknown_build_still_explains_compatibility_without_starting(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        from moonloader.ui import Window
        app = QApplication.instance() or QApplication([])
        service, installation = self.fixture(); (Path(installation.path)/'GameAssembly.dll').write_bytes(b'unknown update')
        with patch.object(service, 'installations', return_value=([installation], [])), patch('moonloader.launch.start') as start:
            window = Window(service, no_launch=True); self.addCleanup(window.close); window.show(); app.processEvents()
            self.assertTrue(window.compatibility_button.isEnabled()); self.assertFalse(window.prepare_button.isEnabled())
            state = (service.root/'state.json').read_bytes()
            with patch.object(window, 'text_dialog') as dialog:
                window.compatibility_button.click(); self.assertIn('Unknown game build', dialog.call_args.args[1])
            self.assertEqual((service.root/'state.json').read_bytes(), state); start.assert_not_called()
