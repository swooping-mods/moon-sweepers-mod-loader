"""Tiny source-phase checks: no Qt, native compilation or subprocess execution."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'loader'))
from moonloader.launch_feedback import LaunchFeedback
from moonloader import launch, storage


class FeedbackChecks(unittest.TestCase):
    def test_zero_request_exit_stays_unconfirmed_and_blocked(self):
        state = LaunchFeedback(); state.requested(); state.request_finished(0)
        self.assertEqual(state.phase, 'unconfirmed'); self.assertTrue(state.blocked)
        state.observe('absent'); self.assertTrue(state.blocked)
        self.assertNotIn('Exit code', state.message)

    def test_nonzero_request_is_request_failure_and_never_game_crash(self):
        state = LaunchFeedback(); state.requested(); state.request_finished(-11)
        self.assertEqual(state.phase, 'failed'); self.assertTrue(state.blocked)
        self.assertIn('launch request', state.message); self.assertNotIn('crash', state.message)

    def test_observed_running_and_exit_are_separate_from_request(self):
        state = LaunchFeedback(); state.requested(); state.observe('running')
        state.request_finished(0); self.assertEqual(state.phase, 'running')
        state.observe('absent'); self.assertEqual(state.phase, 'closed'); self.assertFalse(state.blocked)

    def test_unreadable_lifetime_never_releases_a_running_game(self):
        state = LaunchFeedback(); state.requested(); state.observe('running')
        state.observe('unavailable'); self.assertTrue(state.blocked); self.assertEqual(state.phase, 'unconfirmed')
        state.observe('running'); self.assertEqual(state.phase, 'running')

    def test_private_runner_is_not_confirmed_game_startup(self):
        state = LaunchFeedback(); state.requested(False)
        self.assertIn('startup is unconfirmed', state.message); self.assertNotIn('Steam', state.message)


class GuardChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def record(self, state='steam-unconfirmed', run='first'):
        storage.write(self.root / 'active.json', {'state':state, 'run':run})

    def test_guard_survives_a_new_reader_and_blocks_file_changes(self):
        for state in ('steam-starting', 'steam-unconfirmed', 'private-unconfirmed', 'running'):
            self.record(state)
            self.assertEqual(storage.pending_launch(self.root)['state'], state)
            with self.assertRaisesRegex(ValueError, 'lifetime is unconfirmed'): storage.assert_inactive(self.root)

    def test_acknowledgement_requires_same_request_and_stopped_game(self):
        self.record()
        with patch('moonloader.public.assert_stopped', side_effect=ValueError('still running')):
            with self.assertRaisesRegex(ValueError, 'still running'): storage.acknowledge_launch_closed(self.root, 'first')
        self.assertIsNotNone(storage.pending_launch(self.root))
        with patch('moonloader.public.assert_stopped') as stopped:
            with self.assertRaisesRegex(ValueError, 'state changed'): storage.acknowledge_launch_closed(self.root, 'another')
            stopped.assert_not_called()
            storage.acknowledge_launch_closed(self.root, 'first')
        self.assertIsNone(storage.pending_launch(self.root)); storage.assert_inactive(self.root)

    def test_pending_guard_refuses_second_launch_before_plan_or_preparation(self):
        self.record(); service = SimpleNamespace(root=self.root, prepare=Mock())
        with patch.object(launch, 'plan') as plan:
            with self.assertRaisesRegex(ValueError, 'lifetime is unconfirmed'): launch.start(service, None)
            plan.assert_not_called(); service.prepare.assert_not_called()

    def test_guard_written_before_spawn_and_request_pid_never_claimed_as_game(self):
        run = self.root / 'runs' / 'current'
        record = {'mode':'installed', 'run':str(run), 'command':['never-executed'], 'cwd':str(self.root), 'order':[], 'platform':'linux'}
        service = SimpleNamespace(root=self.root, prepare=Mock())
        process = SimpleNamespace(pid=1234)
        def spawn(*args, **kwargs):
            self.assertEqual(storage.pending_launch(self.root)['state'], 'steam-starting')
            return process
        progress = Mock()
        with patch.object(launch, 'plan', return_value=record), patch.object(launch.diagnostics, 'prepare_installed'), patch.object(launch.subprocess, 'Popen', side_effect=spawn):
            observed, _ = launch.start(service, None, progress)
        self.assertIs(observed, process); self.assertFalse(hasattr(process, '_moon_lease'))
        active = storage.pending_launch(self.root); self.assertNotIn('pid', active)
        self.assertEqual(active['state'], 'steam-unconfirmed')
        self.assertTrue(any('automatically' in call.args[0] for call in progress.call_args_list))
        with storage.locked(self.root, 'session.lock'): pass


    def test_closed_window_retains_private_guard_after_runner_pid_dies(self):
        storage.write(self.root / 'active.json', {'state':'running', 'run':'private-run', 'pid':123, 'birth':'old'})
        with patch.object(storage, 'process_birth', return_value=None), patch('moonloader.public.assert_stopped'):
            self.assertIsNotNone(storage.pending_launch(self.root))
            with self.assertRaisesRegex(ValueError, 'lifetime is unconfirmed'): storage.assert_inactive(self.root)
            storage.acknowledge_launch_closed(self.root, 'private-run')
        self.assertIsNone(storage.pending_launch(self.root))

    def test_private_running_guard_cannot_be_acknowledged_while_runner_active(self):
        storage.write(self.root / 'active.json', {'state':'running', 'run':'private-run', 'pid':123, 'birth':'live'})
        with patch.object(storage, 'process_birth', return_value='live'), patch('moonloader.public.assert_stopped'):
            with self.assertRaisesRegex(ValueError, 'still active'): storage.acknowledge_launch_closed(self.root, 'private-run')
        self.assertIsNotNone(storage.pending_launch(self.root))

    def test_private_runner_exit_retains_uncertainty_before_releasing_lease(self):
        self.record('running', 'private-run')
        storage.retain_private_uncertainty(self.root, 'private-run')
        self.assertEqual(storage.pending_launch(self.root)['state'], 'private-unconfirmed')
        with self.assertRaisesRegex(ValueError, 'lifetime is unconfirmed'): storage.assert_inactive(self.root)
        with self.assertRaisesRegex(ValueError, 'state changed'): storage.retain_private_uncertainty(self.root, 'another')

    def test_spawn_failure_clears_pending_guard_without_running_a_process(self):
        record = {'mode':'installed', 'run':str(self.root / 'runs' / 'failed'), 'command':['never-executed'], 'cwd':str(self.root), 'order':[], 'platform':'linux'}
        service = SimpleNamespace(root=self.root, prepare=Mock())
        with patch.object(launch, 'plan', return_value=record), patch.object(launch.diagnostics, 'prepare_installed'), patch.object(launch.subprocess, 'Popen', side_effect=OSError('fixture spawn failure')):
            with self.assertRaisesRegex(OSError, 'fixture spawn failure'): launch.start(service, None)
        self.assertIsNone(storage.pending_launch(self.root)); storage.assert_inactive(self.root)
        with storage.locked(self.root, 'session.lock'): pass
