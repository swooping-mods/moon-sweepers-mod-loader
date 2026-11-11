"""Exercise the shipped selection as real packages, without loading game code."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from build import source_payload
from mod_bundle import ROOT, payload
from moonloader import packages
from moonloader.discovery import PIN
from moonloader.service import Service


IDS = {'squishy-plushie', 'futuristic-car', 'manual-power-poles', 'debug-menu',
       'sound-framework', 'pickup-hands', 'hints-framework',
       'vehicle-framework', 'build-menu-framework'}


class ModBundleChecks(unittest.TestCase):
    def materialize(self, root):
        bundle = root / 'loader'
        for name, data in payload().items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return bundle

    def test_shipped_library_is_complete_unchecked_and_resolves(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.materialize(root)
            service = Service(root / 'data', bundle)
            service.seed()
            library, errors = service.library()
            self.assertFalse(errors)
            self.assertEqual(set(library), IDS)
            self.assertEqual(service.state['selected'], [])
            manifests = {name: pair[0] for name, pair in library.items()}
            order = packages.resolve(manifests, list(IDS), PIN,
                                     runtime_api_abi=1, runtime_readiness_abi=1,
                                     host_capabilities={'interaction': 1})
            self.assertEqual(set(order), IDS)
            for name, manifest in manifests.items():
                for dependency in manifest['requires']:
                    self.assertLess(order.index(dependency), order.index(name))
            with self.assertRaises(ValueError):
                packages.resolve(manifests, ['squishy-plushie'], PIN,
                                 runtime_api_abi=1, runtime_readiness_abi=1,
                                 host_capabilities={'interaction': 1})

    def test_seed_preserves_user_package_version_and_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = self.materialize(root)
            original = next((bundle / 'packages').glob('debug-menu-*.msmod'))
            custom = root / 'custom.msmod'
            with zipfile.ZipFile(original) as source, zipfile.ZipFile(custom, 'w') as target:
                manifest = json.loads(source.read('manifest.json'))
                manifest['version'] = '99.0.0'
                target.writestr('manifest.json', json.dumps(manifest))
                for name in manifest['files']:
                    target.writestr(name, source.read(name))
            service = Service(root / 'data', bundle)
            service.import_package(custom, select=True)
            service.seed()
            service.seed()
            self.assertEqual(service.state['selected'], ['debug-menu'])
            self.assertEqual(service.library()[0]['debug-menu'][0]['version'], '99.0.0')
            service.state['selected'] = []
            service.save()
            restored = Service(root / 'data', bundle)
            restored.seed()
            self.assertEqual(restored.state['selected'], [])
            self.assertEqual(set(restored.library()[0]), IDS)

    def test_build_inputs_reject_missing_changed_or_extra_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = self.materialize(root) / 'packages'
            package = next(folder.glob('*.msmod'))
            data = package.read_bytes()
            package.write_bytes(data + b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                payload(folder)
            package.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing'):
                payload(folder)
            package.write_bytes(data)
            shutil.copyfile(package, folder / 'unpicked.msmod')
            with self.assertRaisesRegex(ValueError, 'inventory'):
                payload(folder)

    def test_source_distribution_has_runnable_packages_without_duplicate_inputs(self):
        files = source_payload()
        self.assertEqual({name for name in files if name.startswith('loader/packages/')},
                         set(payload()))
        self.assertFalse(any(name.startswith('vendored/mod-bundle/packages/') for name in files))
        self.assertIn('vendored/mod-bundle.json', files)

    def test_source_checkout_seeds_the_same_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = Service(Path(temporary), ROOT / 'loader')
            service.seed()
            self.assertEqual(set(service.library()[0]), IDS)
            self.assertFalse(service.state['selected'])
