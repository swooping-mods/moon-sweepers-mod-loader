"""Check host-only discovery without executing Qt or native fixtures."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


class CheckSelectionChecks(unittest.TestCase):
    def test_host_only_excludes_compatibility_ui_but_full_gate_retains_it(self):
        spec = importlib.util.spec_from_file_location('loader_check_selection', ROOT / 'tools/check.py')
        check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check)
        ui_name = 'test_ui_unknown_build_still_explains_compatibility_without_starting'
        for host_only in (True, False):
            with self.subTest(host_only=host_only), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                ui = unittest.FunctionTestCase(lambda: None)
                ui._testMethodName = ui_name
                ui.id = lambda: 'compatibility.ui.' + ui_name
                host = unittest.FunctionTestCase(lambda: None)
                host._testMethodName = 'test_host_sentinel'
                host.id = lambda: 'host.test_host_sentinel'
                suite = unittest.TestSuite([ui, unittest.TestSuite([host])])
                result = SimpleNamespace(wasSuccessful=lambda: True, testsRun=1 if host_only else 2,
                                         failures=[], errors=[], skipped=[])
                runner = Mock()
                runner.run.return_value = result
                dependencies = {name: SimpleNamespace(**{entry: Mock()}) for name, entry in (
                    ('check_native_sdk', 'check'), ('check_managed_sources', 'check'),
                    ('mod_bundle', 'payload'))}
                argv = ['check.py', '--host-only'] if host_only else ['check.py']
                # Intercept execution: selection must not compile native code or create Qt widgets.
                with patch.object(check, 'ROOT', root), patch.object(sys, 'argv', argv), \
                        patch.dict(sys.modules, dependencies), patch.object(sys, 'path', list(sys.path)), \
                        patch.object(check.unittest.defaultTestLoader, 'discover', return_value=suite), \
                        patch.object(check.unittest, 'TextTestRunner', return_value=runner):
                    self.assertEqual(check.main(), 0)
                selected = [test.id() for test in check.flatten(runner.run.call_args.args[0])]
                self.assertEqual(selected, [host.id()] if host_only else [ui.id(), host.id()])
                receipt = json.loads((root / 'artifacts/checks.json').read_text())
                self.assertEqual(receipt['excluded'], [ui.id()] if host_only else [])
                self.assertEqual(receipt['skipped'], [])
                for module in dependencies.values():
                    next(iter(vars(module).values())).assert_called_once_with()
