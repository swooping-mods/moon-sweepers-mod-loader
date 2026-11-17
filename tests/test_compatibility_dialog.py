"""Player warning and preflight use real Qt without launching a game."""
import copy
import os
from pathlib import Path
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QDialog
import test_loader
import test_compatibility_player
from moonloader.compatibility_dialog import CompatibilityDialog
from moonloader import compatibility
from moonloader.ui import Window


class CompatibilityDialogChecks(unittest.TestCase):
    setUp = test_loader.LoaderChecks.setUp
    prepared_fixture = test_loader.LoaderChecks.prepared_fixture
    fixture = test_compatibility_player.CompatibilityPlayerChecks.fixture
    add_mod = test_compatibility_player.CompatibilityPlayerChecks.add_mod

    def test_missing_framework_names_only_the_affected_mod(self):
        service,installation=self.fixture()
        self.add_mod(service,'needs-framework',requires=['absent-framework'])
        service.state['selected']=['portable-feature','needs-framework']
        result=service.compatibility(installation)
        self.assertFalse(result['allowed'])
        rows=compatibility.compact(result)
        self.assertEqual([row['id'] for row in rows],['needs-framework'])
        self.assertEqual(rows[0]['reason'],'Required framework unavailable: absent-framework')
        app=QApplication.instance() or QApplication([])
        dialog=CompatibilityDialog(result);self.addCleanup(dialog.close)
        dialog.show();app.processEvents()
        self.assertEqual(dialog.table.topLevelItemCount(),1)

    def test_compact_rows_do_not_blame_a_matching_neighbor(self):
        result = {'status':'incompatible','selected':['good','old','future'], 'mods':{
            'good':{'status':'incompatible','assessment_status':'requirements-matched'},
            'old':{'name':'Old mod','version':'1.0.0','assessment_status':'incompatible',
                   'reasons':[{'code':'game-pin-mismatch','message':'Technical detail'}]},
            'future':{'name':'Future mod','assessment_status':'unknown','reasons':[]}}}
        rows = compatibility.compact(result)
        self.assertEqual([r['id'] for r in rows], ['old','future'])
        self.assertEqual([r['status'] for r in rows], ['Blocked','Unverified'])
        self.assertNotIn('Technical detail', rows[0]['reason'])

    def test_dialog_keeps_long_lists_compact_and_details_collapsed(self):
        app=QApplication.instance() or QApplication([])
        result={'status':'unknown','selected':[str(i) for i in range(60)],'game':{},'mods':{
            str(i):{'name':'Long mod name '+str(i)*60,'status':'unknown','assessment_status':'unknown','reasons':[]}
            for i in range(60)}}
        original=copy.deepcopy(result)
        dialog=CompatibilityDialog(result);self.addCleanup(dialog.close)
        dialog.resize(540,390);dialog.show();app.processEvents()
        self.assertEqual(dialog.table.topLevelItemCount(),60)
        self.assertFalse(dialog.details.isVisible())
        self.assertLessEqual(dialog.width(),720)
        self.assertLess(dialog.table.height(),300)
        dialog.details_button.click();app.processEvents()
        self.assertTrue(dialog.details.isVisible())
        dialog.deselect_button.click()
        self.assertEqual(len(dialog.excluded_ids),60)
        self.assertEqual(result,original)

    def test_unknown_launch_opens_warning_before_steam_or_game_start(self):
        app=QApplication.instance() or QApplication([])
        service,installation=self.fixture()
        (Path(installation.path)/'GameAssembly.dll').write_bytes(b'new unreviewed build')
        with patch.object(service,'installations',return_value=([installation],[])), patch('moonloader.launch.start') as start:
            window=Window(service);self.addCleanup(window.close);window.show();app.processEvents()
            self.assertTrue(window.launch_button.isEnabled())
            self.assertEqual(window.launch_button.text(),'Review compatibility…')
            state=(service.root/'state.json').read_bytes()
            with patch.object(CompatibilityDialog,'exec',return_value=QDialog.DialogCode.Rejected) as warning, patch.object(window,'steam_setup') as setup:
                window.start_game()
            warning.assert_called_once();setup.assert_not_called();start.assert_not_called()
            self.assertEqual((service.root/'state.json').read_bytes(),state)

    def test_explicit_deselection_still_requires_another_launch_attempt(self):
        app=QApplication.instance() or QApplication([])
        service,installation=self.fixture()
        self.add_mod(service,'matching-neighbor')
        service.state['selected'].append('matching-neighbor');service.save()
        original=service.compatibility(installation)
        bad=original['mods']['portable-feature']
        bad.update(status='incompatible',assessment_status='incompatible',allowed=False,
                   reasons=[{'code':'game-pin-mismatch','message':'Old addresses'}])
        original.update(allowed=False,status='incompatible')
        with patch.object(service,'installations',return_value=([installation],[])):
            window=Window(service);self.addCleanup(window.close);app.processEvents()
            def choose(dialog):
                dialog.deselect_button.click()
                return QDialog.DialogCode.Accepted
            with patch.object(service,'compatibility',return_value=original), patch.object(CompatibilityDialog,'exec',choose), patch('moonloader.launch.start') as start:
                self.assertFalse(window.compatibility_preflight(installation))
                start.assert_not_called()
            self.assertEqual(service.state['selected'],['matching-neighbor'])

    def test_unrelated_integrity_failure_does_not_relabel_a_matching_mod(self):
        result={'allowed':True,'status':'requirements-matched','mods':{
            name:dict(status='requirements-matched',assessment_status='requirements-matched',allowed=True,reasons=[])
            for name in ('good','changed')}}
        compatibility._blocked(result,compatibility.reason('package-integrity','Changed files',mod='changed'))
        self.assertFalse(result['allowed'])
        self.assertEqual(result['mods']['good']['assessment_status'],'requirements-matched')
        self.assertTrue(result['mods']['good']['blocked_by_selection'])
        self.assertEqual([row['id'] for row in compatibility.compact(result)],['changed'])

