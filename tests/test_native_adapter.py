"""The public native adapter compiles after relocation without a workshop."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from check_native_sdk import check


class NativeAdapterChecks(unittest.TestCase):
    def test_inventory_and_core_contracts_match_their_pins(self):
        self.assertGreater(check()['headers'], 20)

    def test_relocated_game_binding_and_scene_sdk_compile_without_siblings(self):
        with tempfile.TemporaryDirectory(prefix='moon-public-adapter-') as folder:
            root = Path(folder)
            shutil.copytree(ROOT/'sdk/native', root/'sdk')
            samples = {
                'scene': '#include "sdk/runtime/native/gameplay.h"\n#include "sdk/runtime/sdk/scene/static_model.h"\nint consumer(const SMModel *m,SMResources *r){return sm_attach(m,r,0,0,"prop")!=0;}\n',
                'interaction': '#include "sdk/runtime/native/gameplay.h"\n#include "sdk/runtime/native/interaction_client.h"\nunsigned consumer(void){return moon_interactions()!=0;}\n',
            }
            for name, code in samples.items():
                with self.subTest(consumer=name):
                    source = root/(name+'.c')
                    source.write_text(code)
                    result = subprocess.run(['clang', '--target=x86_64-pc-windows-msvc',
                        '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                        '-ffreestanding', '-fno-builtin', '-c', str(source), '-o', str(root/(name+'.obj'))],
                        cwd=root, capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
