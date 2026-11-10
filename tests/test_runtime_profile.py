"""The optional timing fixture must prove outputs/counts and reject a bad cache."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from profile_runtime import compile_fixture, run_fixture, checked_result


class RuntimeProfileChecks(unittest.TestCase):
    def test_actual_core_parity_counts_and_wrong_owner_negative_control(self):
        with tempfile.TemporaryDirectory() as directory:
            for compiler in ("clang", "gcc"):
                with self.subTest(compiler=compiler):
                    binary, _ = compile_fixture(directory, compiler, verify=True)
                    for services in (4, 64, 256):
                        value = checked_result(run_fixture(binary, services, 128, 1))
                        self.assertEqual(len(value["samples"]), 4)
                        self.assertEqual(value["callbacks"], services // 4)
                    result = run_fixture(binary, 4, 128, 1, wrong_cache=True)
                    self.assertEqual(result.returncode, 3)
                    self.assertIn("wrong cached owner", result.stderr)
