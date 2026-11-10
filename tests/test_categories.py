"""Workshop discovery behavior through the independent loader and real Qt controls."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'loader'),str(ROOT/'tools')]
from moonloader.catalog import CATEGORIES,description,matches,metadata,tags
from moonloader.service import Service
from test_loader import descriptor,PNG

def archive(path,files):
    with zipfile.ZipFile(path,'w') as z:
        for name,data in files.items():z.writestr(name,data)

def fixture(root, name, fields=None):
    manifest = descriptor(name); manifest['name'] = name.replace('-', ' ').title()
    manifest.update(fields or {})
    payload = {'mod.dll': b'MZ unchanged fixture', 'icon.png': PNG}
    import hashlib
    manifest['files'] = {key: hashlib.sha256(value).hexdigest() for key,value in payload.items()}
    archive(root/(name+'.msmod'), {**payload, 'manifest.json': json.dumps(manifest).encode()})
    return manifest

class CategoryChecks(unittest.TestCase):

    def test_search_combines_category_tags_description_and_partial_words(self):
            mod = {'id':'base', 'name':'Shared Base', 'summary':'Foundation',
                   'description':'Host session ownership', 'category':'framework',
                   'tags':['spatial-index', 'co-op', 'networking']}
            for query in ('FRAMEWORK #spatial-index', 'co op', 'network own', 'foundation session', '  '):
                self.assertTrue(matches(mod, query), query)
            self.assertFalse(matches(mod, 'spatial missing'))
            self.assertFalse(matches(mod, '', 'qol'))
            self.assertFalse(matches(mod, '', 'enabled', False))
            self.assertTrue(matches(mod, 'network', 'framework', False))
            self.assertTrue(matches(mod, 'network', 'enabled', True))

    def test_legacy_and_invalid_presentation_extensions_remain_safe(self):
            self.assertEqual(metadata({}), {})
            self.assertTrue(matches({'id':'old', 'name':'Old Mod'}, 'old'))
            self.assertEqual(tags({'tags':'invalid'}), [])
            self.assertTrue(matches({'name':'Older', 'category':[], 'tags':[{}]}, 'older'))
            for values in ({'category':'new category'}, {'tags':['bad tag']},
                           {'tags':['same','same']}, {'tags':['x'*49]}, {'tags':['t']*25}):
                with self.subTest(values=values), self.assertRaises(ValueError): metadata(values)

    def test_ui_categories_tags_and_enabled_combine_in_every_view(self):
            os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import Qt
            from PySide6.QtTest import QTest
            from moonloader.ui import Window
            app=QApplication.instance() or QApplication([])
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);service=Service(root/'data',root/'bundle')
                for name, category, values in [('base-kit','framework',['spatial-index','shared-state']),
                                               ('small-tweak','qol',['map','shortcuts']),
                                               ('toy-box','additions',['map','collectibles'])]:
                    fixture(root,name,{'category':category,'tags':values})
                    service.import_package(root/(name+'.msmod'), select=name=='small-tweak')
                fixture(root,'old-package');service.import_package(root/'old-package.msmod')
                with patch('moonloader.launch.start') as start:
                    window=Window(service,True);self.addCleanup(window.close);window.show();app.processEvents()
                    self.assertEqual([window.filter.itemText(i) for i in range(window.filter.count())],
                                     ['All mods','Enabled','Framework','QoL','Additions'])
                    def ids():return {window.list.item(i).data(Qt.ItemDataRole.UserRole)['id'] for i in range(window.list.count())}
                    def filter_to(value):window.filter.setCurrentIndex(window.filter.findData(value));app.processEvents()
                    for view in ('grid','details','text'):
                        window.set_view(view);filter_to('framework');window.search.setText('FRAMEWORK #spatial-index');app.processEvents()
                        self.assertEqual(ids(),{'base-kit'});self.assertIn('shared-state',window.detail_catalog.text())
                        window.search.setText('map');self.assertFalse(ids());self.assertEqual(window.detail_catalog.text(),'')
                        filter_to('additions');self.assertEqual(ids(),{'toy-box'})
                        filter_to('all');self.assertEqual(ids(),{'small-tweak','toy-box'})
                        filter_to('enabled');self.assertEqual(ids(),{'small-tweak'})
                        self.assertEqual(service.state['selected'],['small-tweak'])
                    window.list.setFocus();QTest.keyClick(window.list,Qt.Key.Key_Space);app.processEvents()
                    self.assertEqual(ids(),set());self.assertEqual(service.state['selected'],[])
                    window.search.clear();filter_to('all');self.assertIn('old-package',ids())
                    window.resize(760,650);app.processEvents();self.assertFalse(window.details.isVisible())
                    with patch.object(window,'text_dialog') as dialog:
                        window.details_dialog(window.mods['base-kit'][0]);self.assertIn('Tags: spatial-index',dialog.call_args.args[1])
                    start.assert_not_called();window.close()
