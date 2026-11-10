"""Exercise the loader's public import against the pinned building API."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loader'))
from moonloader import packages


class BuildingSelectionChecks(unittest.TestCase):
    def fixtures(self):
        pins = {'GameAssembly.dll': 'a' * 64}
        values = {}
        for name, kind in (('build-menu-framework', None), ('old-pole', 193), ('new-relay', 384)):
            value = {'id': name, 'name': name, 'kind': 'native', 'game': {'hashes': pins},
                     'requires': [], 'conflicts': [], 'claims': []}
            if kind is not None:
                value.update(requires=['build-menu-framework'], build_items=[{'kind': kind, 'key': name + '.power.item'}])
            else:
                value['build_menu_max_kind'] = 384
            values[name] = value
        return pins, values

    def test_old_and_new_ids_resolve_independently_of_selection_order(self):
        pins, values = self.fixtures()
        self.assertEqual(packages.resolve(values, list(reversed(values)), pins),
                         ['build-menu-framework', 'new-relay', 'old-pole'])
        values['new-relay']['build_items'][0]['kind'] = 193
        with self.assertRaisesRegex(ValueError, '193'):
            packages.resolve(values, list(values), pins)

    def test_old_framework_is_rejected_before_launch(self):
        pins, values = self.fixtures()
        del values['build-menu-framework']['build_menu_max_kind']
        with self.assertRaisesRegex(ValueError, 'through 224'):
            packages.resolve(values, list(values), pins)


if __name__ == '__main__':
    unittest.main()
