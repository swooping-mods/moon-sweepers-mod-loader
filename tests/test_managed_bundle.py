"""Managed distribution inputs remain offline, closed and free of game payloads."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import managed_bundle as bundle


class ManagedBundleChecks(unittest.TestCase):
    def test_reviewed_lock_is_complete_supported_and_has_no_plugin(self):
        lock = json.loads(bundle.LOCK.read_text())
        self.assertEqual(lock['coreclr_version'], '10.0.15')
        self.assertEqual(lock['bepinex_version'], '6.0.0-be.791+b782da4')
        self.assertEqual(sorted(row['role'] for row in lock['files']), ['bepinex', 'coreclr', 'source', 'source'])
        for row in lock['files']:
            self.assertTrue(row['url'].startswith('https://'))
            self.assertRegex(row['sha256'], '^[a-f0-9]{64}$')
            self.assertNotIn('MarsSweepers', row['name'])

    def test_archive_reader_refuses_traversal_alias_and_case_collision(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'input.zip'
            for names in (['../bad'], ['/absolute'], ['a\\b'], ['a:drive'], ['A.dll', 'a.dll']):
                with zipfile.ZipFile(path, 'w') as archive:
                    for name in names: archive.writestr(name, b'payload')
                with self.subTest(names=names), self.assertRaises(ValueError): bundle.archive_files(path)
            with zipfile.ZipFile(path, 'w') as archive:
                info = zipfile.ZipInfo('alias'); info.external_attr = 0o120777 << 16
                archive.writestr(info, 'target')
            with self.assertRaises(ValueError): bundle.archive_files(path)

    def test_offline_inputs_reject_missing_and_changed_before_compilation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = []
            for role, name in [('bepinex','host.zip'), ('coreclr','runtime.zip'), ('source','source.zip')]:
                data = role.encode(); (root/name).write_bytes(data)
                rows.append({'role':role,'name':name,'sha256':hashlib.sha256(data).hexdigest()})
            lock = root/'lock.json'; lock.write_text(json.dumps({'files': rows}))
            with patch.object(bundle, 'LOCK', lock):
                self.assertEqual(set(bundle.read_inputs(root)[1]), {'bepinex','coreclr','source'})
                (root/'runtime.zip').write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError, 'changed'): bundle.read_inputs(root)
                (root/'runtime.zip').unlink()
                with self.assertRaisesRegex(ValueError, 'Missing'): bundle.read_inputs(root)

    def test_config_disables_automatic_downloads_generation_and_scan(self):
        import configparser
        config = configparser.ConfigParser(); config.read_string(bundle.CONFIG.decode())
        self.assertEqual(config['IL2CPP']['UnityBaseLibrariesSource'], '')
        for name in ('UpdateInteropAssemblies', 'PreloadIL2CPPInteropAssemblies', 'ScanMethodRefs'):
            self.assertFalse(config.getboolean('IL2CPP', name))

    def test_package_gate_rejects_development_only_runtime_even_with_valid_file_table(self):
        from moonloader import managed
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); target = root/'runtime/bepinex'; files = target/'files'
            payload = {name:b'original synthetic inert bytes' for name in managed.STARTUP_FILES}
            payload['BepInEx/config/BepInEx.cfg'] = bundle.CONFIG
            payload['BepInEx/core/MoonLab.ManagedHostCompat.dll'] = b'original synthetic inert helper'
            payload['BepInEx/core/MoonLab.LegacyMonoMod.Utils.dll'] = b'original synthetic inert legacy utilities'
            for name, data in payload.items():
                path = files/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
            receipt = {'schema': managed.SCHEMA, 'version': managed.VERSION,
                       'files': {n:hashlib.sha256(v).hexdigest() for n,v in payload.items()}}
            (target/'receipt.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'maintained CoreCLR'): bundle.verify_bundle(root)
            receipt['coreclr_version'] = json.loads(bundle.LOCK.read_text())['coreclr_version']
            receipt['host_compatibility'] = 'be791-modern-detours/v3'
            (target/'receipt.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'CoreCLR bytes'): bundle.verify_bundle(root)
            lock = root/'lock.json'; lock.write_text(json.dumps({'coreclr_version':receipt['coreclr_version'],
                'coreclr_files':{'coreclr.dll':receipt['files']['dotnet/coreclr.dll']}, 'application_libraries':{}}))
            with patch.object(bundle, 'LOCK', lock), patch('modern_harmony.runtime_hashes', return_value={}):
                self.assertEqual(bundle.verify_bundle(root)['coreclr_version'], receipt['coreclr_version'])
                data=json.loads(lock.read_text());data['application_libraries']={'Microsoft.Extensions.Logging.Abstractions.dll':{'sha256':'0'*64}}
                lock.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, 'application library closure'): bundle.verify_bundle(root)
            (files/'dotnet/coreclr.dll').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'): bundle.verify_bundle(root)
