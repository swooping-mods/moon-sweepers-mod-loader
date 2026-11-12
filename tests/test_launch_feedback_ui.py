"""Deferred Qt interaction gates. Fixtures never start Steam or a game."""
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loader'))


class LaunchFeedbackUiChecks(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        from moonloader.service import Service
        from moonloader.ui import Window
        self.app = QApplication.instance() or QApplication([])
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.service = Service(self.root / 'data', self.root / 'bundle')
        discovery = patch.object(self.service, 'installations', return_value=([], []))
        discovery.start(); self.addCleanup(discovery.stop)
        self.Window = Window

    def window(self):
        window = self.Window(self.service)
        self.addCleanup(window.close)
        return window

    def test_ui_launch_handoff_is_neutral_collapsed_and_blocks_duplicates(self):
        from moonloader import storage
        window = self.window()
        record = {'mode':'installed', 'run':str(self.root / 'data/runs/fixture')}
        storage.write(self.service.root / 'active.json', {'state':'steam-unconfirmed', 'run':record['run']})
        window.started((SimpleNamespace(poll=lambda:0, returncode=0), record))
        with patch('moonloader.ui.diagnostics.finish_run', return_value={'status':'startup-unconfirmed'}), patch('moonloader.ui.launch.failure_detail', return_value=''), patch('moonloader.ui.game_process.observe', return_value={'status':'absent'}):
            window.poll_process()
        self.assertEqual(window.feedback.phase, 'unconfirmed')
        self.assertFalse(window.launch_button.isEnabled())
        self.assertEqual(window.message.property('severity'), 'info')
        self.assertNotIn('Exit code', window.message.text())
        self.assertNotIn(record['run'], window.launch_status.text())
        self.assertFalse(window.launch_details.isVisible())
        self.assertIn('exit code: 0', window.launch_details.toPlainText())
        window.launch_details_button.click(); self.assertFalse(window.launch_details.isHidden())
        with patch('moonloader.ui.launch.start') as start:
            window.start_game(); start.assert_not_called()

    def test_ui_launch_running_observation_and_closed_release(self):
        from moonloader import storage
        window = self.window()
        run = str(self.root / 'data/runs/fixture')
        storage.write(self.service.root / 'active.json', {'state':'steam-unconfirmed', 'run':run})
        window.launch_record = {'mode':'installed', 'run':run}; window.feedback.requested(); window.feedback.request_finished(0)
        with patch('moonloader.ui.game_process.observe', return_value={'status':'running'}): window.poll_process()
        self.assertEqual(window.launch_button.text(), 'Game running'); self.assertFalse(window.launch_reset_button.isEnabled())
        with patch('moonloader.ui.game_process.observe', return_value={'status':'absent'}), patch('moonloader.public.assert_stopped'):
            window.poll_process()
        self.assertEqual(window.feedback.phase, 'closed'); self.assertIsNone(storage.pending_launch(self.service.root))

    def test_ui_launch_restart_restores_uncertainty_and_inspection_cannot_start(self):
        from moonloader import storage
        storage.write(self.service.root / 'active.json', {'state':'steam-unconfirmed', 'run':'retained request'})
        window = self.window()
        self.assertTrue(window.feedback.blocked); self.assertFalse(window.launch_button.isEnabled())
        self.assertIn('unconfirmed', window.launch_status.text())
        window.no_launch = True
        with patch('moonloader.ui.launch.start') as start:
            window.start_game(); start.assert_not_called()

    def test_ui_launch_request_outliving_game_does_not_claim_running(self):
        window = self.window()
        window.started((SimpleNamespace(poll=lambda:None), {'mode':'installed', 'run':'fixture'}))
        with patch('moonloader.ui.game_process.observe', return_value={'status':'running'}): window.poll_process()
        with patch('moonloader.ui.game_process.observe', return_value={'status':'absent'}): window.poll_process()
        self.assertEqual(window.feedback.phase, 'finishing')
        self.assertFalse(window.launch_button.isEnabled())
        self.assertIn('Waiting for the launch', window.launch_status.text())
        self.assertNotIn('is running', window.launch_status.text())
