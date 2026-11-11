"""Reviewed profile integrity and the executable adapter/framework boundary."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from game_profiles_native import ROOT,CATALOG,HEADER,check,digest,generate,profiles


class GameAdapterChecks(unittest.TestCase):
    def test_compiled_catalog_is_current_and_complete(self):
        result=check();rows=profiles()
        self.assertEqual(len(rows),1)
        self.assertEqual(result['profiles'][rows[0]['id']]['digest'],digest(rows[0]))
        self.assertEqual(result['profiles'][rows[0]['id']]['capabilities'],{'unity.clock':{'abi':1,'size':16,'limits':{}}})

    def fixture(self,root,document):
        path=root/CATALOG;path.parent.mkdir(parents=True);path.write_text(json.dumps(document))
        header=root/HEADER;header.parent.mkdir(parents=True)
        return path,header

    def test_catalog_changes_cannot_reuse_stale_compiled_identity(self):
        document=json.loads((ROOT/CATALOG).read_text())
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,header=self.fixture(root,document);header.write_text(generate(root));check(root)
            document['profiles'][0]['native']['domain_rva']+=8;path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError,'Compiled native profiles'):check(root)
            header.write_text(generate(root));check(root)
            self.assertNotEqual(digest(document['profiles'][0]),digest(profiles()[0]))

    def test_unknown_layout_and_false_capabilities_refuse_generation(self):
        original=json.loads((ROOT/CATALOG).read_text())
        mutations=[lambda r:r['adapter'].update(layout='unknown/v1'),
                   lambda r:r['capabilities'].update({'unity.physics':{'abi':1,'size':16}}),
                   lambda r:r['adapter'].update(abi=True),
                   lambda r:r['capabilities']['unity.clock'].update(abi=True),
                   lambda r:r['native'].update(domain_ready_offset=32)]
        for mutate in mutations:
            with self.subTest(mutation=mutate),tempfile.TemporaryDirectory() as temporary:
                document=copy.deepcopy(original);mutate(document['profiles'][0]);root=Path(temporary);self.fixture(root,document)
                with self.assertRaises(ValueError):generate(root)

    def test_duplicate_identity_and_alias_refuse_generation(self):
        document=json.loads((ROOT/CATALOG).read_text());other=copy.deepcopy(document['profiles'][0]);other['id']='unqualified.second-build';document['profiles'].append(other)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,header=self.fixture(root,document)
            with self.assertRaisesRegex(ValueError,'Ambiguous'):generate(root)
            saved=root/'original.json';path.rename(saved);path.symlink_to(saved)
            with self.assertRaisesRegex(ValueError,'alias'):generate(root)

    def test_independent_immutable_binaries_on_relocated_adapters(self):
        with tempfile.TemporaryDirectory(prefix='native-game-adapter-',dir=ROOT/'artifacts') as temporary:
            output=Path(temporary)/'proof'
            result=subprocess.run([sys.executable,str(ROOT/'tools/check_game_adapter.py'),'--output',str(output)],capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            receipt=json.loads((output/'result.json').read_text())
            self.assertTrue(receipt['success']);self.assertEqual(len(receipt['cases']),15)
            self.assertEqual(set(receipt['immutable_binaries']),{'framework','consumer'})
