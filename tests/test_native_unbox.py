"""Production-header fault fixture; compilation/execution is a deferred gate."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeUnboxHostChecks(unittest.TestCase):
    def test_payload_failures_defaults_checked_status_and_caller_numeric_policy(self):
        for compiler in ('clang', 'gcc'):
            if not shutil.which(compiler):
                self.skipTest('existing host compiler unavailable; no acquisition')
            with self.subTest(compiler=compiler), tempfile.TemporaryDirectory(prefix='moon-unbox-') as folder:
                binary = Path(folder) / 'unbox'
                command = [compiler, '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
                           '-Wno-unused-function', '-Wno-unused-variable', '-Wno-misleading-indentation',
                           '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                           '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                           str(ROOT / 'tests/native_unbox_checks.c'), '-o', str(binary)]
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('payload failure/default/status checks passed', result.stdout)
