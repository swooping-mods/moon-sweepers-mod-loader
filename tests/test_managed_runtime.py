"""Optional managed hosting uses inert original packages and disposable games."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import zipfile

import test_loader
from moonloader import launch, managed, packages
from moonloader.storage import load, write
from moonloader.service import tree
from moon_mod_api.runtime_plan import MAGIC

CONFIG = b'''[IL2CPP]
UpdateInteropAssemblies = false
UnityBaseLibrariesSource =
PreloadIL2CPPInteropAssemblies = false
ScanMethodRefs = false
'''


class ManagedRuntimeChecks(unittest.TestCase):
    setUp = test_loader.LoaderChecks.setUp
    prepared_fixture = test_loader.LoaderChecks.prepared_fixture

    def fixture(self, external=False, mixed=False):
        service, installation = self.prepared_fixture()
        receipt_path = service.bundle / 'runtime/receipt.json'
        write(receipt_path, {**load(receipt_path), 'managed_profile_guard_abi': 1, 'runtime_api_abi': 1})
        runtime = service.bundle / 'runtime/bepinex'
        host = {name: ('Inert host: ' + name).encode() for name in managed.STARTUP_FILES}
        host['BepInEx/config/BepInEx.cfg'] = CONFIG
        for name, data in host.items():
            path = runtime / 'files' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        write(runtime / 'receipt.json', {'schema': managed.SCHEMA, 'version': managed.VERSION,
            'files': {name: hashlib.sha256(data).hexdigest() for name, data in host.items()}})
        manifest = test_loader.descriptor('other-managed')
        manifest.update(kind=packages.MANAGED_KIND, abi=packages.MANAGED_ABI,
            bepinex={'guid': 'another.author.plugin', 'data_root': 'OtherAuthor'})
        manifest['game']['hashes'] = service.library()[0]['test-mod'][0]['game']['hashes']
        if external:
            manifest.update(mode='external', external={'adapter': packages.MANAGED_KIND,
                'repository': 'https://example.com/author/independent-plugin', 'revision': '1.0.0'})
        if mixed: manifest['requires'] = ['test-mod']
        payload = {'mod.dll': b'Original inert plugin v1', 'icon.png': test_loader.PNG,
                   'data/voice/example.wav': b'Original inert audio'}
        self.package(service, manifest, payload)
        service.state['selected'] = ['test-mod', manifest['id']] if mixed else [manifest['id']]
        service.save()
        return service, installation, manifest, payload

    def package(self, service, manifest, payload):
        manifest['files'] = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
        source = self.root / (manifest['id'] + '-' + manifest['version'] + '.msmod')
        with zipfile.ZipFile(source, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            for name, data in payload.items(): archive.writestr(name, data)
        service.import_package(source, select=True)

    def test_managed_only_deploys_plugins_data_empty_native_plan_and_profile(self):
        service, installation, _, payload = self.fixture()
        before = tree(Path(installation.path))
        with patch('subprocess.Popen') as spawn:
            root = service.prepare(installation)
            service.prepare(installation)
            record = launch.plan(service, installation, platform='win32')
        spawn.assert_not_called()
        self.assertEqual((root / 'game/BepInEx/plugins/other-managed/mod.dll').read_bytes(), payload['mod.dll'])
        self.assertEqual((root / 'game/BepInEx/OtherAuthor/voice/example.wav').read_bytes(), payload['data/voice/example.wav'])
        self.assertFalse((root / 'game/MoonLab/mods/other-managed').exists())
        self.assertEqual((root / 'game/MoonLab/runtime-plan.bin').read_bytes(), MAGIC + b'\0\0\0\0')
        self.assertEqual(record['env']['MOONLAB_MODS'], '')
        self.assertEqual(record['env']['MOONLAB_BEPINEX'], '1')
        self.assertEqual(Path(record['profile']), root / 'profile')
        self.assertTrue((root / 'profile/AppData/LocalLow').is_dir())
        self.assertFalse((Path(installation.path) / 'winhttp.dll').exists())
        self.assertEqual(tree(Path(installation.path)), before)
        allowlist = load(root / 'game/BepInEx/MoonLab/allowed-inputs.json')
        self.assertIn('BepInEx/plugins/other-managed/mod.dll', allowlist['files'])
        self.assertNotIn('BepInEx/OtherAuthor/voice/example.wav', allowlist['files'])

    def test_external_plugin_and_native_dependency_use_separate_backends(self):
        service, installation, _, _ = self.fixture(external=True, mixed=True)
        receipt = service.bundle / 'runtime/receipt.json'
        write(receipt, {**load(receipt), 'max_native_mods': 1})
        root = service.prepare(installation)
        record = launch.plan(service, installation, platform='win32')
        self.assertEqual(record['env']['MOONLAB_MODS'], 'test-mod')
        self.assertEqual(record['external_mods'], {'other-managed': packages.MANAGED_KIND})
        self.assertTrue((root / 'game/MoonLab/mods/test-mod/mod.dll').is_file())
        self.assertTrue((root / 'game/BepInEx/plugins/other-managed/mod.dll').is_file())
        self.assertEqual(service.state['selected'], ['test-mod', 'other-managed'])

    def test_optional_host_unavailable_in_installed_mode_and_without_attachment(self):
        service, installation, _, _ = self.fixture()
        service.set_mode(installation, 'installed')
        with self.assertRaisesRegex(ValueError, 'Runtime is unavailable'): service.prepare(installation)
        self.assertFalse(service.install_root(installation).exists())
        self.assertFalse((Path(installation.path) / 'MoonLab').exists())
        service.set_mode(installation, 'private')
        shutil.rmtree(service.bundle / 'runtime/bepinex')
        with self.assertRaisesRegex(ValueError, 'Runtime is unavailable'): service.prepare(installation)
        self.assertFalse(service.install_root(installation).exists())

    def test_host_version_profile_guard_and_required_files_gate_selection(self):
        service, installation, _, _ = self.fixture()
        core_receipt = service.bundle / 'runtime/receipt.json'
        saved = load(core_receipt); write(core_receipt, {**saved, 'managed_profile_guard_abi': 0})
        with self.assertRaisesRegex(ValueError, 'Runtime is unavailable'): service.prepare(installation)
        write(core_receipt, saved)
        host_receipt = service.bundle / 'runtime/bepinex/receipt.json'
        host = load(host_receipt); write(host_receipt, {**host, 'version': 'unknown'})
        with self.assertRaisesRegex(ValueError, 'Runtime is unavailable'): service.prepare(installation)
        del host['files']['winhttp.dll']; write(host_receipt, host)
        with self.assertRaisesRegex(ValueError, 'Runtime is unavailable'): service.prepare(installation)
        self.assertFalse(service.install_root(installation).exists())

    def test_tampered_host_and_unlisted_bundle_inputs_reject_before_game_copy(self):
        service, installation, _, _ = self.fixture()
        extra = service.bundle / 'runtime/bepinex/files/unlisted.dll'; extra.write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'file table'): service.prepare(installation)
        extra.unlink()
        (service.bundle / 'runtime/bepinex/files/winhttp.dll').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'bundle changed'): service.prepare(installation)
        self.assertFalse(service.install_root(installation).exists())

    def test_unowned_plugins_and_download_configuration_preserve_existing_state(self):
        service, installation, _, _ = self.fixture(); root = service.prepare(installation)
        extra = root / 'game/BepInEx/plugins/unknown.dll'; extra.write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'Unowned managed'): service.prepare(installation)
        self.assertEqual(extra.read_bytes(), b'unknown'); extra.unlink()
        config = root / 'game/BepInEx/config/BepInEx.cfg'
        config.write_bytes(CONFIG.replace(b'UpdateInteropAssemblies = false', b'UpdateInteropAssemblies = true'))
        with self.assertRaisesRegex(ValueError, 'automatic downloads'): service.prepare(installation)
        self.assertIn(b'UpdateInteropAssemblies = true', config.read_bytes())

    def test_failed_allowlist_commit_restores_plugin_and_allowlist_together(self):
        service, installation, manifest, payload = self.fixture(); root = service.prepare(installation)
        game = root / 'game'; old_allowlist = (game / 'BepInEx/MoonLab/allowed-inputs.json').read_bytes()
        updated = copy.deepcopy(manifest); updated['version'] = '2.0.0'
        self.package(service, updated, {**payload, 'mod.dll': b'Original inert plugin v2'})
        import os
        replace = os.replace; failed = False
        def fail_allowlist(source, destination):
            nonlocal failed
            if Path(destination) == game / 'BepInEx/MoonLab/allowed-inputs.json' and not failed:
                failed = True; raise OSError('injected allowlist interruption')
            return replace(source, destination)
        with patch('moonloader.service.os.replace', side_effect=fail_allowlist):
            with self.assertRaisesRegex(OSError, 'injected'): service.prepare(installation)
        self.assertTrue(failed)
        self.assertEqual((game / 'BepInEx/plugins/other-managed/mod.dll').read_bytes(), payload['mod.dll'])
        self.assertEqual((game / 'BepInEx/MoonLab/allowed-inputs.json').read_bytes(), old_allowlist)
        self.assertFalse((root / 'pending-deployment.json').exists())
