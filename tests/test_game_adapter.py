"""Reviewed profile integrity and the executable adapter/framework boundary."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from game_profiles_native import ROOT,CATALOG,HEADER,check,digest,generate,profiles
from check_game_adapter import time_scale_manifests


class GameAdapterChecks(unittest.TestCase):
    def test_time_scale_fixture_declares_no_unpublished_clock_services(self):
        hashes={'GameAssembly.dll':'a'*64,'MoonSweepers.exe':'b'*64,'UnityPlayer.dll':'c'*64}
        manifests=time_scale_manifests(hashes)
        self.assertEqual(list(manifests),['clock-framework','clock-feature'])
        for manifest in manifests.values():
            self.assertEqual(manifest['provides'],{})
            self.assertEqual(manifest['requires_apis'],[])
            self.assertEqual(manifest['claims'],[])
        self.assertEqual(manifests['clock-framework']['requires_game'],
                         {'unity.time-scale':{'abi':1,'min_size':16}})
        self.assertEqual(manifests['clock-feature']['requires_game'],{})
        self.assertEqual(manifests['clock-feature']['requires'],['clock-framework'])
        manifests['clock-framework']['game']['hashes']['GameAssembly.dll']='d'*64
        self.assertEqual(hashes['GameAssembly.dll'],'a'*64)
        self.assertEqual(manifests['clock-feature']['game']['hashes']['GameAssembly.dll'],'a'*64)

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

    def test_time_scale_candidate_requires_explicit_profile_promotion(self):
        document=json.loads((ROOT/CATALOG).read_text())
        original_digest=digest(document['profiles'][0])
        self.assertNotIn('unity.time-scale',document['profiles'][0]['capabilities'])
        self.assertRegex(generate(),r',1u\},\n\};')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,header=self.fixture(root,document)
            header.write_text(generate(root));check(root)
            document['profiles'][0]['capabilities']['unity.time-scale']={'abi':1,'size':16,'limits':{}}
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError,'Compiled native profiles'):check(root)
            candidate=generate(root);self.assertRegex(candidate,r',3u\},\n\};')
            header.write_text(candidate);result=check(root)
            self.assertNotEqual(original_digest,result['profiles'][document['profiles'][0]['id']]['digest'])
            self.assertEqual(document['profiles'][0]['hashes'],profiles()[0]['hashes'])
            for field,value in [('abi',2),('abi',True),('size',32),('size',True),('limits',{'max_reads':1})]:
                with self.subTest(field=field,value=value):
                    cap={'abi':1,'size':16,'limits':{}};cap[field]=value
                    document['profiles'][0]['capabilities']['unity.time-scale']=cap
                    path.write_text(json.dumps(document))
                    with self.assertRaisesRegex(ValueError,'capability differs'):generate(root)

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

    def test_legacy_profile_identity_cannot_be_reused_for_another_build(self):
        original=json.loads((ROOT/CATALOG).read_text())
        for field in ('GameAssembly.dll','MoonSweepers.exe','UnityPlayer.dll','version'):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temporary:
                document=copy.deepcopy(original);row=document['profiles'][0]
                if field=='version':row[field]='1.0.6'
                else:row['hashes'][field]='0'*64
                root=Path(temporary);self.fixture(root,document)
                with self.assertRaisesRegex(ValueError,'Legacy profile identity is frozen'):generate(root)

    def test_duplicate_catalog_keys_refuse_generation(self):
        document=json.loads((ROOT/CATALOG).read_text())
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,header=self.fixture(root,document)
            path.write_text(path.read_text().replace('"version": "1.0.5"','"version": "ignored", "version": "1.0.5"',1))
            with self.assertRaisesRegex(ValueError,'Duplicate profile catalog key: version'):generate(root)

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
            self.assertTrue(receipt['success']);self.assertEqual(len(receipt['cases']),23)
            self.assertEqual(set(receipt['immutable_binaries']),{'framework','consumer','time-scale-consumer'})
