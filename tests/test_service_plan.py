"""Exercise production C contracts with real SDK consumers and malformed bytes."""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "loader"))
import moonloader
from moon_mod_api.runtime_plan import encode, MAGIC


def fixtures():
    library = {"id": "other-authors-library", "kind": "native", "abi": "MoonLab_ModStart/v6",
               "runtime_api_abi": 1, "requires": [], "provides": {
                   "other-authors-library.building": {"abi": 7, "size": 64,
                       "limits": {"build_menu_max_kind": 384}}}}
    feature = {"id": "independent-feature", "kind": "native", "abi": "MoonLab_ModStart/v6",
               "runtime_api_abi": 1, "requires": [library["id"]], "requires_apis": [{
                   "api": "other-authors-library.building", "abi": 7, "min_size": 16,
                   "limits": {"build_menu_max_kind": 384}}]}
    return {value["id"]: value for value in (library, feature)}


class ServicePlanChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.binaries = []
        sources = [ROOT / "tests/native_service_plan_checks.c",
                   ROOT / "tests/fixtures/runtime_provider.c", ROOT / "tests/fixtures/runtime_consumer.c"]
        for compiler in ("clang", "gcc"):
            binary = cls.directory / compiler
            result = subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O1", "-g",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            "-I", str(ROOT / "vendored/api/include"), *map(str, sources), "-o", str(binary)],
                           capture_output=True, text=True)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            cls.binaries.append(binary)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_core(self, data, mode):
        path = self.directory / "plan.bin"
        path.write_bytes(data)
        for binary in self.binaries:
            with self.subTest(compiler=binary.name, mode=mode):
                result = subprocess.run([str(binary), str(path), mode], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_independent_table_calls_prefixes_frames_and_thread_boundaries(self):
        values = fixtures()
        self.run_core(encode(values, list(values)), "valid")

    def test_v7_retains_v6_publication_and_consumer_registration(self):
        values = fixtures()
        for value in values.values():
            value.update(abi="MoonLab_ModStart/v7", requires_host={"interaction": 1})
        self.run_core(encode(values, list(values)), "valid")

    def test_input_adapter_preserves_each_observed_walker_for_unrelated_frames(self):
        values = fixtures()
        self.run_core(encode(values, list(values)), "actor-delivery")

    def test_missing_publications_and_failed_startup_rollback_apis_and_frames(self):
        values = fixtures()
        for mode in ("missing", "rollback"):
            self.run_core(encode(values, list(values)), mode)

    def test_readiness_rejects_incomplete_owners_and_failed_hook_installation(self):
        values = fixtures()
        for mode in ("incomplete-startup", "hooks-failed"):
            self.run_core(encode(values, list(values)), mode)

    def test_managed_only_empty_native_plan_reaches_ready_without_hooks(self):
        values={'managed-only':{'id':'managed-only','kind':'bepinex-il2cpp',
                'abi':'BepInEx.IL2CPP/6-be791','requires':[]}}
        self.run_core(encode(values,list(values)),"empty-startup")

    def test_every_truncated_prefix_and_trailing_bytes_reject(self):
        data = encode(fixtures(), list(fixtures()))
        self.run_core(data, "truncations")
        self.run_core(data + b"unexpected", "reject")
        self.run_core(MAGIC + struct.pack("<I", 65), "reject")

    def test_package_ids_match_sdk_key_including_numeric_prefixes(self):
        from moon_mod_api.storage import key
        for name in ('3d-tools', '123', 'test-3d', 'a-1-b'):
            with self.subTest(name=name):
                key(name)
                values = {name: {'id':name, 'kind':'native', 'abi':'MoonLab_ModStart/v1', 'requires':[]}}
                self.run_core(encode(values, [name]), 'parse')

    def test_numeric_provider_and_consumer_api_owners_match_sdk(self):
        for provider in ('3d-tools', 'test-3d', '7'):
            consumer = '1-feature'; api = provider + '.building.api'
            values = {
                provider: {'id':provider, 'kind':'native', 'abi':'MoonLab_ModStart/v6',
                           'runtime_api_abi':1, 'requires':[], 'provides':{api:{'abi':1,'size':16}}},
                consumer: {'id':consumer, 'kind':'native', 'abi':'MoonLab_ModStart/v6',
                           'runtime_api_abi':1, 'requires':[provider],
                           'requires_apis':[{'api':api,'abi':1,'min_size':8}]}}
            with self.subTest(provider=provider): self.run_core(encode(values, list(values)), 'parse')

    def test_capacity_and_api_limits_match_package_and_c_parser(self):
        values = {}
        for i in range(4):
            name = "library-" + str(i)
            values[name] = {"id": name, "kind": "native", "abi": "MoonLab_ModStart/v6",
                            "runtime_api_abi": 1, "requires": [], "provides": {
                                name + ".api-" + str(j): {"abi": 1, "size": 8,
                                    "limits": {"cap_" + str(k): k for k in range(32)}} for j in range(64)}}
        self.run_core(encode(values, list(values)), "parse")
        values["extra-library"] = {"id": "extra-library", "kind": "native", "abi": "MoonLab_ModStart/v6",
            "runtime_api_abi": 1, "requires": [], "provides": {"extra-library.api": {"abi": 1, "size": 8}}}
        with self.assertRaisesRegex(ValueError, "capacity"):
            encode(values, list(values))

    def test_actual_camera_adapter_thread_exclusivity_restore_retry_and_capacity(self):
        for compiler in ("clang", "gcc"):
            with self.subTest(compiler=compiler):
                binary = self.directory / (compiler + "-camera")
                subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O1",
                                "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                                str(ROOT / "tests/native_camera_service_checks.c"), "-o", str(binary)], check=True)
                result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
                self.assertIn("restoration passed", result.stdout)

    def test_shared_native_prologues_preserve_register_stack_flags_and_continuation(self):
        for compiler in ("clang", "gcc"):
            with self.subTest(compiler=compiler):
                binary = self.directory / (compiler + "-prologues")
                subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O1",
                                "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                                str(ROOT / "tests/native_vessel_hook_checks.c"), "-o", str(binary)], check=True)
                result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
                self.assertIn("exact stack offsets, flags and continuation", result.stdout)
