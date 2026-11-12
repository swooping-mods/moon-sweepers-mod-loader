"""Synthetic process identities only: no game, Steam or live process scans."""
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loader'))
from moonloader import game_process


class LinuxObservationChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.proc = Path(temporary.name)
        location = patch.object(game_process, '_PROC', self.proc)
        location.start()
        self.addCleanup(location.stop)
        birth = patch.object(game_process, 'process_birth', return_value='birth-1')
        self.birth = birth.start()
        self.addCleanup(birth.stop)

    def process(self, pid, command, comm=b'MoonSweepers.ex\n'):
        path = self.proc / str(pid)
        path.mkdir()
        (path / 'cmdline').write_bytes(command)
        (path / 'comm').write_bytes(comm)
        return path

    def observe(self):
        return game_process._linux_observe()

    def test_game_requires_exact_argv0_and_comm(self):
        self.process(22, b'/installed/MoonSweepers.exe\0-private-argument\0')
        self.assertEqual(self.observe(), {
            'status': 'running', 'processes': [{'pid': 22, 'birth': 'birth-1'}],
            'reason': 'Game executable identity observed; startup and mod loading are unverified.'})
        self.assertEqual(self.birth.call_count, 2)

    def test_windows_path_in_wine_argv0_is_supported(self):
        self.process(22, b'Z:\\installed\\MoonSweepers.exe\0')
        self.assertEqual(self.observe()['status'], 'running')

    def test_steam_proton_wine_and_python_wrappers_are_not_game(self):
        for pid, command in enumerate((
                b'steam\0-applaunch\0' + b'5335510\0',
                b'/runtime/proton\0waitforexitandrun\0/game/MoonSweepers.exe\0',
                b'/usr/bin/wine64\0/game/MoonSweepers.exe\0',
                b'python3\0proton\0run\0MoonSweepers.exe\0',
                b'/game/MoonSweepers.exe.backup\0',
                b'/game/moonsweepers.exe\0'), 1):
            self.process(pid, command)
        self.assertEqual(self.observe()['status'], 'absent')
        self.birth.assert_not_called()

    def test_wine_comm_cannot_confirm_game_argv0(self):
        self.process(22, b'MoonSweepers.exe\0', b'wine64\n')
        self.assertEqual(self.observe()['status'], 'unavailable')

    def test_empty_kernel_command_is_not_game(self):
        self.process(22, b'', b'kernel-thread\n')
        self.assertEqual(self.observe()['status'], 'absent')

    def test_pid_birth_change_or_disappearance_is_unavailable(self):
        self.process(22, b'MoonSweepers.exe\0')
        for births in (['birth-1', 'birth-2'], [None, None], ['birth-1', None]):
            with self.subTest(births=births):
                self.birth.side_effect = births
                self.assertEqual(self.observe()['status'], 'unavailable')

    def test_identity_is_rechecked_after_initial_match(self):
        self.process(22, b'MoonSweepers.exe\0')
        with patch.object(game_process, '_argv_game', side_effect=[True, False]):
            self.assertEqual(self.observe()['status'], 'unavailable')

    def test_unreadable_identity_and_birth_are_unavailable_without_error_details(self):
        self.process(22, b'MoonSweepers.exe\0')
        for target in ('_bounded_read', 'process_birth'):
            with self.subTest(target=target), patch.object(
                    game_process, target, side_effect=PermissionError('private-process-details')):
                result = self.observe()
                self.assertEqual(result['status'], 'unavailable')
                self.assertNotIn('private-process-details', str(result))

    def test_disappearing_candidate_is_unavailable(self):
        self.process(22, b'MoonSweepers.exe\0')
        with patch.object(game_process, '_argv_game', side_effect=[True, FileNotFoundError()]):
            self.assertEqual(self.observe()['status'], 'unavailable')

    def test_disappearing_noncandidate_does_not_prevent_completed_scan(self):
        self.process(22, b'other\0')
        with patch.object(game_process, '_argv_game', side_effect=FileNotFoundError()):
            self.assertEqual(self.observe()['status'], 'absent')

    def test_cmdline_and_comm_read_bounds(self):
        path = self.process(22, b'x' * (game_process._MAX_CMDLINE_BYTES + 1))
        self.assertEqual(self.observe()['status'], 'unavailable')
        (path / 'cmdline').write_bytes(b'MoonSweepers.exe\0')
        (path / 'comm').write_bytes(b'x' * (game_process._MAX_COMM_BYTES + 1))
        self.assertEqual(self.observe()['status'], 'unavailable')
        with patch.object(Path, 'open') as opened:
            stream = opened.return_value.__enter__.return_value
            stream.read.return_value = b'fixture'
            self.assertEqual(game_process._bounded_read(path, 11), b'fixture')
            stream.read.assert_called_once_with(12)

    def test_unterminated_identity_is_unavailable(self):
        self.process(22, b'MoonSweepers.exe')
        self.assertEqual(self.observe()['status'], 'unavailable')

    def test_proc_scan_is_capped_even_for_nonnumeric_entries(self):
        with patch.object(game_process, '_MAX_SCAN_ENTRIES', 2):
            for name in ('self', 'net', 'mounts'):
                (self.proc / name).touch()
            self.assertEqual(self.observe()['status'], 'unavailable')

    def test_exact_scan_limit_can_complete(self):
        self.process(22, b'other\0')
        with patch.object(game_process, '_MAX_SCAN_ENTRIES', 1):
            self.assertEqual(self.observe()['status'], 'absent')

    def test_proc_scan_failure_is_unavailable(self):
        with patch.object(game_process.os, 'scandir', side_effect=PermissionError()):
            self.assertEqual(self.observe()['status'], 'unavailable')

    def test_confirmed_game_is_reported_even_if_another_read_fails(self):
        self.process(22, b'MoonSweepers.exe\0')
        self.process(23, b'x' * (game_process._MAX_CMDLINE_BYTES + 1))
        result = self.observe()
        self.assertEqual(result['status'], 'running')
        self.assertEqual(result['processes'], [{'pid': 22, 'birth': 'birth-1'}])
        self.assertEqual(set(result), {'status', 'processes', 'reason'})

    def test_unsupported_platform_does_not_scan(self):
        with patch.object(game_process.sys, 'platform', 'synthetic-unsupported'), \
                patch.object(game_process.os, 'name', 'posix'), \
                patch.object(game_process, '_linux_observe') as scan:
            self.assertEqual(game_process.observe()['status'], 'unavailable')
            scan.assert_not_called()


class WindowsObservationChecks(unittest.TestCase):
    def observe(self, snapshots, births):
        with patch.object(game_process, '_windows_snapshot', side_effect=snapshots), \
                patch.object(game_process, 'process_birth', side_effect=births):
            return game_process._windows_observe()

    def test_exact_case_insensitive_toolhelp_identity_and_birth(self):
        game = ([(12, 'MOONSWEEPERS.EXE'), (13, 'steam.exe')], True)
        result = self.observe([game, game], ['birth', 'birth'])
        self.assertEqual(result['status'], 'running')
        self.assertEqual(result['processes'], [{'pid': 12, 'birth': 'birth'}])

    def test_wrapper_names_and_partial_names_do_not_match(self):
        snapshot = ([(12, 'steam.exe'), (13, 'proton.exe'), (14, 'wine.exe'),
                     (15, 'MoonSweepers.exe.backup')], True)
        self.assertEqual(self.observe([snapshot], [])['status'], 'absent')

    def test_reused_snapshot_pid_cannot_confirm_stranger(self):
        game = ([(12, 'MoonSweepers.exe')], True)
        other = ([(12, 'other.exe')], True)
        result = self.observe([game, other], ['new-birth'])
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['processes'], [])

    def test_changed_birth_or_lost_process_is_unavailable(self):
        game = ([(12, 'MoonSweepers.exe')], True)
        for births in (['old', 'new'], [None], [PermissionError()], ['old', ValueError()]):
            with self.subTest(births=births):
                self.assertEqual(self.observe([game, game], births)['status'], 'unavailable')

    def test_capped_or_failed_snapshot_is_unavailable(self):
        for snapshots in ([([], False)], [OSError()], [AttributeError()]):
            with self.subTest(snapshots=snapshots):
                self.assertEqual(self.observe(snapshots, [])['status'], 'unavailable')

    def test_missing_second_snapshot_cannot_establish_running(self):
        game = ([(12, 'MoonSweepers.exe')], True)
        self.assertEqual(self.observe([game, OSError()], ['birth'])['status'], 'unavailable')


class ToolhelpBackendChecks(unittest.TestCase):
    def snapshot(self, rows, limit, terminal_error=18):
        # Exercise the ctypes structure/iterator glue with a synthetic kernel.
        # No WinDLL or real process API is invoked, even on Windows hosts.
        import ctypes
        iterator = iter(rows)
        error = [0]

        def advance(handle, pointer):
            try:
                pid, name = next(iterator)
            except StopIteration:
                error[0] = terminal_error
                return False
            pointer._obj.th32ProcessID = pid
            pointer._obj.szExeFile = name
            return True

        kernel = SimpleNamespace(
            CreateToolhelp32Snapshot=Mock(return_value=123),
            Process32FirstW=Mock(side_effect=advance),
            Process32NextW=Mock(side_effect=advance),
            CloseHandle=Mock())
        with patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
                patch.object(ctypes, 'get_last_error', side_effect=lambda: error[0], create=True), \
                patch.object(game_process, '_MAX_SCAN_ENTRIES', limit):
            result = game_process._windows_snapshot()
        kernel.CloseHandle.assert_called_once_with(123)
        self.assertLessEqual(kernel.Process32NextW.call_count, limit)
        return result

    def test_complete_snapshot_and_exact_limit(self):
        rows = [(12, 'MoonSweepers.exe'), (13, 'steam.exe')]
        self.assertEqual(self.snapshot(rows, 2), (rows, True))

    def test_truncated_snapshot_is_incomplete(self):
        rows = [(12, 'steam.exe'), (13, 'MoonSweepers.exe')]
        self.assertEqual(self.snapshot(rows, 1), (rows[:1], False))

    def test_enumeration_error_is_incomplete_even_after_readable_entries(self):
        self.assertEqual(self.snapshot([(12, 'steam.exe')], 2, terminal_error=5),
                         ([(12, 'steam.exe')], False))

    def test_empty_snapshot_requires_no_more_files_status(self):
        self.assertEqual(self.snapshot([], 2), ([], True))
        self.assertEqual(self.snapshot([], 2, terminal_error=5), ([], False))


if __name__ == '__main__':
    unittest.main()
