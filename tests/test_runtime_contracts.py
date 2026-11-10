"""Public SDK acceptance must not imply an unavailable in-game host."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "loader"))
import test_loader
from moonloader import packages


def managed_package(path, pins):
    value = test_loader.descriptor("independent-managed")
    value.update(kind=packages.MANAGED_KIND, abi=packages.MANAGED_ABI,
                 bepinex={"guid": "another.author.plugin", "data_root": "AnotherAuthor"})
    value["game"]["hashes"] = pins
    files = {"mod.dll": b"Never executed managed fixture", "icon.png": test_loader.PNG}
    value["files"] = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(value))
        for name, data in files.items():
            archive.writestr(name, data)
    return value


class RuntimeContractChecks(unittest.TestCase):
    setUp = test_loader.LoaderChecks.setUp
    prepared_fixture = test_loader.LoaderChecks.prepared_fixture

    def test_managed_package_can_be_imported_but_missing_host_prevents_copy(self):
        service, installation = self.prepared_fixture()
        pins = service.library()[0]["test-mod"][0]["game"]["hashes"]
        source = self.root / "managed.msmod"
        managed_package(source, pins)
        imported = service.import_package(source, select=True)
        self.assertTrue(packages.game_mod(imported))
        self.assertIn(imported["id"], service.state["selected"])
        with patch("subprocess.Popen") as spawn:
            with self.assertRaisesRegex(ValueError, "Runtime is unavailable"):
                service.prepare(installation)
        spawn.assert_not_called()
        self.assertFalse(service.install_root(installation).exists())
        self.assertFalse((Path(installation.path) / "MoonLab").exists())

    def test_interface_contract_requires_runtime_registry_before_copy(self):
        service, installation = self.prepared_fixture()
        order, library = service.selected(installation)
        library["test-mod"][0].update(runtime_api_abi=1, provides={
            "test-mod.independent": {"abi": 1, "size": 32}})
        with patch.object(service, "selected", return_value=(order, library)):
            with self.assertRaisesRegex(ValueError, "runtime API ABI"):
                service.prepare(installation)
        self.assertFalse(service.install_root(installation).exists())

    def test_pinned_resolver_handles_an_independent_managed_dependency(self):
        native = test_loader.descriptor("another-library")
        plugin = test_loader.descriptor("another-feature")
        plugin.update(kind=packages.MANAGED_KIND, abi=packages.MANAGED_ABI,
                      bepinex={"guid": "another.feature", "data_root": "AnotherFeature"},
                      requires=[native["id"]])
        mods = {native["id"]: native, plugin["id"]: plugin}
        self.assertEqual(packages.resolve(mods, list(reversed(mods)), native["game"]["hashes"]),
                         [native["id"], plugin["id"]])
