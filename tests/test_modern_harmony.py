"""The modern detour overlay admits only locked archive members and notices."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import modern_harmony as modern


class ModernHarmonyChecks(unittest.TestCase):
    def fixture(self, root):
        inputs = root/'inputs'; inputs.mkdir()
        path = inputs/'fixture.nupkg'
        source = 'lib/net6.0/Fixture.dll'; data = b'original inert synthetic payload'
        with zipfile.ZipFile(path,'w') as archive: archive.writestr(source,data)
        notices = root/'vendored/modern-harmony-notices'; notices.mkdir(parents=True)
        notice = b'fixture notice'; (notices/'LICENSE').write_bytes(notice)
        lock = {'schema':'moon-loader-modern-harmony/v1','files':[
            {'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
             'members':{source:'BepInEx/core/Fixture.dll'},
             'member_sha256':{source:hashlib.sha256(data).hexdigest()}}],
             'notice_files':{'LICENSE':hashlib.sha256(notice).hexdigest()}}
        table = root/'vendored/modern-harmony.lock.json'; table.write_text(json.dumps(lock))
        return inputs,path,table,lock

    def test_overlay_returns_exact_selected_bytes_and_notices(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); inputs,_,table,_=self.fixture(root)
            with patch.object(modern,'ROOT',root),patch.object(modern,'LOCK',table):
                result=modern.payload(inputs)
                self.assertEqual(result['BepInEx/core/Fixture.dll'],b'original inert synthetic payload')
                self.assertEqual(result['BepInEx/third-party-sources/modern-detours/LICENSE'],b'fixture notice')
                self.assertEqual(modern.runtime_hashes()['BepInEx/core/Fixture.dll'],hashlib.sha256(result['BepInEx/core/Fixture.dll']).hexdigest())

    def test_changed_archive_or_aliased_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); inputs,path,table,_=self.fixture(root)
            with patch.object(modern,'ROOT',root),patch.object(modern,'LOCK',table):
                path.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'changed'):modern.payload(inputs)
                path.unlink(); other=root/'other';other.write_bytes(b'changed');path.symlink_to(other)
                with self.assertRaisesRegex(ValueError,'Missing reviewed'):modern.payload(inputs)

    def test_member_hash_and_notice_tamper_cannot_pass_outer_archive_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); inputs,_,table,lock=self.fixture(root)
            with patch.object(modern,'ROOT',root),patch.object(modern,'LOCK',table):
                member=next(iter(lock['files'][0]['member_sha256']))
                lock['files'][0]['member_sha256'][member]='0'*64;table.write_text(json.dumps(lock))
                with self.assertRaisesRegex(ValueError,'Changed modern Harmony member'):modern.payload(inputs)
                lock['files'][0]['member_sha256'][member]=hashlib.sha256(b'original inert synthetic payload').hexdigest();table.write_text(json.dumps(lock))
                (root/'vendored/modern-harmony-notices/LICENSE').write_bytes(b'changed notice')
                with self.assertRaisesRegex(ValueError,'notice changed'):modern.payload(inputs)

    def test_shipped_hashes_cover_modern_core_and_iced_dependency(self):
        hashes=modern.runtime_hashes()
        self.assertIn('BepInEx/core/0Harmony.dll',hashes)
        self.assertIn('BepInEx/core/MonoMod.Core.dll',hashes)
        self.assertIn('BepInEx/core/MonoMod.Iced.dll',hashes)
        self.assertEqual(len(hashes),11)
