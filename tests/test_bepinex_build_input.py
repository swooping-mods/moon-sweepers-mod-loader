"""The source-only fallback preserves exact compiler inputs without a retired VM."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from build import ROOT, source_payload
from derive_bepinex_input import derive, UPSTREAM_SHA256
from managed_bundle import archive_files


class BepInExBuildInputChecks(unittest.TestCase):
    def test_pinned_vendor_archive_has_exact_manifest_and_no_native_clr(self):
        lock = json.loads((ROOT/'vendored/managed-runtime.lock.json').read_text())
        row = next(item for item in lock['files'] if item['role'] == 'bepinex')
        self.assertEqual(row['upstream_sha256'], UPSTREAM_SHA256)
        self.assertTrue(row['upstream_url'].startswith('https://builds.bepinex.dev/'))
        candidate = ROOT/row['local_path']
        self.assertEqual(hashlib.sha256(candidate.read_bytes()).hexdigest(), row['sha256'])
        manifest = json.loads((ROOT/row['derivation_manifest']).read_text())
        files = archive_files(candidate)
        self.assertEqual({name:hashlib.sha256(data).hexdigest() for name,data in files.items()}, manifest['retained_members'])
        self.assertEqual(len(manifest['compiler_reference_members']), 172)
        self.assertEqual(len(manifest['reference_provenance']['matching_members']), 165)
        for name in ('coreclr.dll','clrjit.dll','hostpolicy.dll','dbgshim.dll','mscordbi.dll',
                     'mscordaccore.dll','Microsoft.NETCore.App.runtimeconfig.json','Microsoft.NETCore.App.deps.json'):
            self.assertNotIn('dotnet/'+name, files)
        self.assertFalse(set(files) & set(manifest['excluded_members']))
        for name,digest in manifest['notice_files'].items():
            self.assertEqual(hashlib.sha256((candidate.parent/name).read_bytes()).hexdigest(),digest)

    def test_source_bundle_keeps_build_input_and_matching_reference_rights(self):
        files = source_payload()
        prefix = 'vendored/managed-build-inputs/'
        self.assertIn(prefix+'BepInEx-be791-host-and-compile-refs.zip',files)
        self.assertIn(prefix+'compiler-refs-net6.0.7.LICENSE.TXT',files)
        self.assertIn(prefix+'compiler-refs-net6.0.7.THIRD-PARTY-NOTICES.TXT',files)
        self.assertNotIn(prefix+'BepInEx-Unity.IL2CPP-win-x64-be791.zip',files)

    def test_derivation_refuses_any_other_upstream_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'changed.zip';source.write_bytes(b'changed')
            output=root/'derived.zip'
            with self.assertRaisesRegex(ValueError,'exact reviewed'):derive(source,output)
            self.assertFalse(output.exists())
