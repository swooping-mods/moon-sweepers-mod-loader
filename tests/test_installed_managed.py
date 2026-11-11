"""Managed installed mode uses only owned additive files and normal Steam launch."""
from pathlib import Path
import copy
import hashlib
import unittest
from unittest.mock import patch

import test_installed
import test_loader
import test_managed_runtime
from moonloader import discovery, launch, managed, public, steam_options
from moonloader.storage import load, write, sha


class InstalledManagedChecks(unittest.TestCase):
    setUp = test_installed.InstalledChecks.setUp
    prepared_fixture = test_loader.LoaderChecks.prepared_fixture
    package = test_managed_runtime.ManagedRuntimeChecks.package

    def fixture(self, mixed=False):
        service, installation, manifest, payload = test_managed_runtime.ManagedRuntimeChecks.fixture(self, external=True, mixed=mixed)
        receipt = service.bundle/'runtime/receipt.json'
        write(receipt, {**load(receipt), 'public_bootstrap_abi':1, 'installed_managed_abi':1})
        host = service.bundle/'runtime/bepinex'
        config = b'[General]\nenabled = true\ntarget_assembly = BepInEx/core/BepInEx.Unity.IL2CPP.dll\n[Il2Cpp]\ncoreclr_path = dotnet/coreclr.dll\n'
        (host/'files/doorstop_config.ini').write_bytes(config)
        value = load(host/'receipt.json'); value['files']['doorstop_config.ini'] = hashlib.sha256(config).hexdigest(); write(host/'receipt.json', value)
        service.set_mode(installation, 'installed'); service.accept_normal_saves(installation, 'fresh')
        return service, installation, manifest, payload

    def test_managed_only_installs_without_copy_or_private_save_redirect(self):
        service, installation, _, payload = self.fixture(); game=Path(installation.path)
        original={name:sha(game/name) for name in discovery.PIN}
        with patch('moonloader.service.copy_file', side_effect=AssertionError('No original game copy')), patch('subprocess.Popen') as spawn:
            root=service.prepare(installation); service.prepare(installation)
        spawn.assert_not_called()
        self.assertFalse((root/'game').exists()); self.assertFalse((root/'proton').exists()); self.assertFalse((root/'profile').exists())
        self.assertFalse((game/'steam_appid.txt').exists())
        self.assertEqual({name:sha(game/name) for name in discovery.PIN}, original)
        self.assertEqual((game/'BepInEx/plugins/other-managed/mod.dll').read_bytes(), payload['mod.dll'])
        self.assertTrue((game/'winhttp.dll').exists()); self.assertTrue((game/'dotnet/coreclr.dll').exists())
        self.assertFalse((game/'MoonLab/mods/other-managed').exists())
        receipt=load(root/'deployment.json')
        self.assertEqual(receipt['order'],['other-managed']); self.assertEqual(receipt['native_order'],[])
        config=(game/public.CONFIG).read_text(); self.assertIn('mods=\nmanaged=1\n',config)
        from moon_mod_api.runtime_plan import MAGIC
        self.assertEqual((game/'MoonLab/runtime-plan.bin').read_bytes(),MAGIC+b'\0\0\0\0')
        plan=launch.plan(service,installation,platform='linux',check_client=False)
        self.assertIn('-applaunch',plan['command']); self.assertEqual(plan['env'],{})
        self.assertNotIn('private_proton',plan); self.assertIn('winhttp=n,b',plan['launch_options'])

    def test_mixed_plan_contains_only_native_ids_and_claims(self):
        service, installation, _, _=self.fixture(mixed=True); root=service.prepare(installation)
        receipt=load(root/'deployment.json'); self.assertEqual(receipt['native_order'],['test-mod'])
        config=(Path(installation.path)/public.CONFIG).read_text()
        self.assertIn('mods=test-mod\nmanaged=1\n',config); self.assertNotIn('other-managed',config)
        self.assertTrue((Path(installation.path)/'MoonLab/mods/test-mod/mod.dll').exists())

    def test_disable_enable_and_uninstall_preserve_mutable_state(self):
        service, installation, _, _=self.fixture(); root=service.prepare(installation); game=Path(installation.path)
        cache=game/'BepInEx/interop/generated.dll'; cache.parent.mkdir(exist_ok=True); cache.write_bytes(b'generated binding')
        log=game/'BepInEx/LogOutput.log'; log.write_text('runtime log')
        cfg=game/'BepInEx/config/example.cfg'; cfg.write_text('user options')
        service.set_enabled(installation,False)
        self.assertIn('enabled = false',(game/'doorstop_config.ini').read_text())
        self.assertIn('enabled=0',(game/public.CONFIG).read_text())
        service.set_enabled(installation,True)
        self.assertIn('enabled = true',(game/'doorstop_config.ini').read_text())
        service.uninstall(installation)
        for name in ('winhttp.dll','doorstop_config.ini','dotnet/coreclr.dll','BepInEx/plugins/other-managed/mod.dll'):
            self.assertFalse((game/name).exists(),name)
        self.assertEqual(cache.read_bytes(),b'generated binding'); self.assertEqual(log.read_text(),'runtime log'); self.assertEqual(cfg.read_text(),'user options')
        service.prepare(installation)
        self.assertTrue((game/'winhttp.dll').exists()); self.assertEqual(cache.read_bytes(),b'generated binding')

    def test_foreign_runtime_and_unknown_plugin_refuse_before_admission(self):
        service, installation, _, _=self.fixture(); game=Path(installation.path)
        foreign=game/'BepInEx/plugins/foreign.dll'; foreign.parent.mkdir(parents=True); foreign.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError,'coexistence'): service.prepare(installation)
        self.assertEqual(foreign.read_bytes(),b'foreign'); self.assertFalse((game/'MoonLab').exists())
        foreign.unlink(); foreign.parent.rmdir(); foreign.parent.parent.rmdir()
        service.prepare(installation)
        foreign.parent.mkdir(exist_ok=True); foreign.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError,'Unowned managed'):service.prepare(installation)
        self.assertEqual(foreign.read_bytes(),b'foreign')

    def test_failed_update_restores_host_plugin_allowlist_and_selection(self):
        service, installation, manifest, payload=self.fixture(); root=service.prepare(installation); game=Path(installation.path)
        old=load(root/'deployment.json'); before={name:(game/name).read_bytes() for name in old['files']}
        manifest=copy.deepcopy(manifest);manifest['version']='2.0.0';self.package(service,manifest,{**payload,'mod.dll':b'changed plugin'})
        service.accept_normal_saves(installation,'fresh')
        import os
        replace=os.replace; failed=False
        def interrupt(source,destination):
            nonlocal failed
            if Path(destination)==game/'BepInEx/MoonLab/allowed-inputs.json' and not failed:
                failed=True;raise OSError('managed update interruption')
            return replace(source,destination)
        with patch('moonloader.public.os.replace',side_effect=interrupt):
            with self.assertRaisesRegex(OSError,'interruption'):service.prepare(installation)
        self.assertTrue(failed);self.assertEqual(load(root/'deployment.json'),old)
        self.assertEqual({name:(game/name).read_bytes() for name in old['files']},before)

    def test_managed_steam_override_preserves_other_overrides_and_is_idempotent(self):
        current='env WINEDLLOVERRIDES="dinput8=n;version=n,b;winhttp=b" gamemoderun %command% -x'
        proposed=steam_options.merge(current,('version','winhttp'))
        self.assertEqual(proposed,current.replace('winhttp=b','winhttp=n,b'))
        self.assertEqual(steam_options.merge(proposed,('version','winhttp')),proposed)
        self.assertEqual(steam_options.merge('WINEDLLOVERRIDES="version=n,b" %command%',('version','winhttp')),'WINEDLLOVERRIDES="version=n,b;winhttp=n,b" %command%')

    def test_managed_package_edit_after_library_validation_rejects_before_game_write(self):
        service, installation, _, _=self.fixture(); original=managed.plugin_files
        def changed(manifest, folder):
            (folder/manifest['entry']).write_bytes(b'changed after the library hash check')
            return original(manifest,folder)
        with patch('moonloader.managed.plugin_files',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'Managed package changed'):service.prepare(installation)
        game=Path(installation.path)
        self.assertFalse((game/'MoonLab').exists());self.assertFalse((game/'winhttp.dll').exists())

    def test_retained_installed_data_does_not_get_silently_deleted_for_private_copy(self):
        service, installation, _, _=self.fixture();service.prepare(installation);service.uninstall(installation)
        from moonloader.service import tree
        game=Path(installation.path);before=tree(game);service.set_mode(installation,'private')
        with patch('moonloader.service.copy_file',side_effect=AssertionError('No implicit source copy')):
            with self.assertRaisesRegex(ValueError,'retained loader data'):service.prepare(installation)
        self.assertEqual(tree(game),before)
