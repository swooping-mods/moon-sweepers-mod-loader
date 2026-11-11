"""Download import uses inert fixtures; no mod or installer code is executed."""
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import test_loader
from moonloader import downloads, packages
from moonloader.service import Service


class DownloadChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = Service(self.root / 'data', self.root / 'bundle')

    def package(self, name):
        path = self.root / (name + '.msmod')
        test_loader.package(path, name)
        return path

    def unpack(self, package, folder):
        folder.mkdir(parents=True)
        with zipfile.ZipFile(package) as archive:
            for name in archive.namelist():
                path = folder / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(name))
        return folder

    def assert_imported(self, sources, expected):
        result = self.service.import_downloads(sources)
        self.assertFalse(result['errors'], result['errors'])
        self.assertEqual({m['id'] for m in result['installed']}, set(expected))
        self.assertFalse(self.service.state['selected'])
        return result

    def test_multi_file_folder_and_nested_zip_import(self):
        one, two, three = [self.package(n) for n in ('first', 'second', 'third')]
        folder = self.root / 'My downloaded mods'; folder.mkdir()
        (folder / two.name).write_bytes(two.read_bytes())
        self.unpack(three, folder / 'Third mod')
        self.assert_imported([one, folder], ['first', 'second', 'third'])
        archive = self.root / 'downloads.zip'
        with zipfile.ZipFile(archive, 'w') as target:
            target.writestr('Release folder/' + one.name, one.read_bytes())
            for path in (folder / 'Third mod').rglob('*'):
                if path.is_file(): target.write(path, 'Release folder/' + path.relative_to(folder).as_posix())
        self.assert_imported([archive], ['first', 'third'])

    def test_import_preserves_selections_and_does_not_copy_unlisted_scripts(self):
        package = self.package('existing'); self.service.import_package(package, select=True)
        folder = self.unpack(self.package('new-mod'), self.root / 'Unpacked')
        (folder / 'install.py').write_text('raise RuntimeError("must never execute")')
        result = self.service.import_downloads([folder])
        self.assertFalse(result['errors'])
        self.assertEqual(self.service.state['selected'], ['existing'])
        _, installed = self.service.library()[0]['new-mod']
        self.assertFalse((installed / 'install.py').exists())
        self.assertEqual((folder / 'install.py').read_text(), 'raise RuntimeError("must never execute")')

    def test_package_manifest_hashes_are_not_recomputed(self):
        folder = self.unpack(self.package('changed'), self.root / 'Changed')
        (folder / 'mod.dll').write_bytes(b'changed after download')
        result = self.service.import_downloads([folder])
        self.assertIn('checksum', result['errors'][0]['error'])
        self.assertFalse(self.service.library()[0])

    def test_mixed_batch_reports_failure_and_keeps_success(self):
        bad = self.root / 'bad.msmod'; bad.write_bytes(b'not a zip')
        good = self.package('good')
        result = self.service.import_downloads([bad, good])
        self.assertEqual([m['id'] for m in result['installed']], ['good'])
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('bad.msmod', result['errors'][0]['path'])

    def test_duplicate_and_multiple_versions_are_explicit(self):
        one = self.package('same')
        two = self.root / 'other-version.msmod'
        with zipfile.ZipFile(one) as source, zipfile.ZipFile(two, 'w') as target:
            for name in source.namelist():
                data = source.read(name)
                if name == 'manifest.json':
                    m = json.loads(data); m['version'] = '2.0.0'; data = json.dumps(m).encode()
                target.writestr(name, data)
        result = self.service.import_downloads([one, one, two])
        self.assertEqual(len(result['installed']), 1)
        self.assertIn('Multiple versions', result['errors'][0]['error'])
        self.assertEqual(self.service.library()[0]['same'][0]['version'], '1.0.0')

    def test_unsafe_zip_paths_aliases_duplicates_and_encryption_reject(self):
        archive = self.root / 'unsafe.zip'
        for name in ('../escape.msmod', '/absolute.msmod', 'C:/stream.msmod', 'a\\b.msmod'):
            with zipfile.ZipFile(archive, 'w') as target: target.writestr(name, b'x')
            result = self.service.import_downloads([archive])
            self.assertTrue(result['errors'], name)
        info = zipfile.ZipInfo('link.msmod'); info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, 'w') as target: target.writestr(info, 'target')
        self.assertTrue(self.service.import_downloads([archive])['errors'])
        with zipfile.ZipFile(archive, 'w') as target:
            target.writestr('mod.msmod', b'x'); target.writestr('MOD.msmod', b'y')
        self.assertIn('Duplicate', self.service.import_downloads([archive])['errors'][0]['error'])
        with zipfile.ZipFile(archive, 'w') as target: target.writestr('mod.msmod', b'x')
        data = bytearray(archive.read_bytes())
        data[6] |= 1
        data[data.index(b'PK\x01\x02') + 8] |= 1
        archive.write_bytes(data)
        self.assertIn('unencrypted', self.service.import_downloads([archive])['errors'][0]['error'])
        self.assertFalse((self.root / 'escape.msmod').exists())

    def test_folder_links_and_source_aliases_reject(self):
        original = self.package('outside')
        folder = self.root / 'linked'; folder.mkdir()
        (folder / 'outside.msmod').symlink_to(original)
        self.assertIn('Links', self.service.import_downloads([folder])['errors'][0]['error'])
        alias = self.root / 'alias.msmod'; alias.symlink_to(original)
        self.assertIn('Symlink', self.service.import_downloads([alias])['errors'][0]['error'])
        self.assertFalse(self.service.library()[0])

    def test_download_budgets_and_loose_dll_guidance(self):
        with self.assertRaisesRegex(ValueError, '32'):
            self.service.import_downloads([self.root / 'a'] * 33)
        archive = self.root / 'large.zip'
        with zipfile.ZipFile(archive, 'w') as target: target.writestr('readme.txt', 'too much')
        with patch.object(downloads, 'MAX_DOWNLOAD_BYTES', 3):
            self.assertIn('size limit', self.service.import_downloads([archive])['errors'][0]['error'])
        dll = self.root / 'unknown.dll'; dll.write_bytes(b'MZ inert')
        self.assertIn('complete mod folder', self.service.import_downloads([dll])['errors'][0]['error'])

    def profile_fixture(self):
        root = self.root / 'profile'; root.mkdir()
        files = {'mod.dll': b'original inert plugin', 'data/voice/intro.wav': b'RIFF inert audio', 'icon.png': test_loader.PNG}
        (root / 'icon.png').write_bytes(files['icon.png'])
        m = test_loader.descriptor('profiled-mod')
        m['files'] = {n: hashlib.sha256(data).hexdigest() for n, data in files.items()}
        profile = {'schema': 'moon-loader-download-profile/v1', 'manifest': m,
                   'sources': {'mod.dll': 'BepInEx/plugins/Example/mod.dll', 'data/voice/intro.wav': 'BepInEx/Example/voice/intro.wav'},
                   'assets': {'icon.png': 'icon.png'}}
        (root / 'example.json').write_text(json.dumps(profile))
        download = self.root / 'Example release'
        for target, source in profile['sources'].items():
            path = download / source; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(files[target])
        return root, download, profile

    def test_recognized_external_layout_folder_and_zip(self):
        profile_root, folder, _ = self.profile_fixture()
        archive = self.root / 'original-release.zip'
        with zipfile.ZipFile(archive, 'w') as target:
            for path in folder.rglob('*'):
                if path.is_file(): target.write(path, 'Release/' + path.relative_to(folder).as_posix())
        with patch.object(downloads, 'PROFILES', profile_root):
            self.assert_imported([folder], ['profiled-mod'])
            self.assert_imported([archive], ['profiled-mod'])
        manifest, location = self.service.library()[0]['profiled-mod']
        self.assertEqual((location / 'mod.dll').read_bytes(), b'original inert plugin')
        self.assertFalse(manifest.get('default_selected', False))

    def test_recognized_layout_changed_missing_and_support_asset_reject(self):
        profile_root, folder, profile = self.profile_fixture()
        dll = folder / profile['sources']['mod.dll']
        with patch.object(downloads, 'PROFILES', profile_root):
            dll.write_bytes(b'new unreviewed version')
            self.assertIn('checksum', self.service.import_downloads([folder])['errors'][0]['error'])
            dll.write_bytes(b'original inert plugin')
            (folder / profile['sources']['data/voice/intro.wav']).unlink()
            self.assertIn('Missing mod file', self.service.import_downloads([folder])['errors'][0]['error'])
            (profile_root / 'icon.png').write_bytes(b'changed support input')
            self.assertIn('support file', self.service.import_downloads([folder])['errors'][0]['error'])
        self.assertFalse(self.service.library()[0])

    def test_shipped_mars_profile_contains_no_upstream_payload(self):
        profiles = downloads.profiles()
        self.assertEqual([p['manifest']['id'] for p in profiles], ['marssweepers'])
        profile = profiles[0]
        self.assertEqual(profile['manifest']['kind'], packages.MANAGED_KIND)
        self.assertEqual(profile['manifest']['mode'], 'external')
        self.assertFalse(profile['manifest']['default_selected'])
        self.assertNotIn('MarsMod.dll', profile['assets'])
        self.assertEqual(len(profile['sources']), 8)
