"""Steam setup uses synthetic accounts/configs only; never starts Steam."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loader'))
from moonloader import steam_options as setup
from moonloader.discovery import Installation, vdf


class SteamOptionsChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.steam = self.root / 'Flatpak Steam'
        self.installation = Installation(str(self.root/'game'), 'steam', str(self.steam), True)
        (self.steam / 'config').mkdir(parents=True)
        self.login = self.steam / 'config/loginusers.vdf'
        self.login.write_text('"users" {"76561197960265770" {"MostRecent" "1"}}')
        self.config = self.steam / 'userdata/42/config/localconfig.vdf'; self.config.parent.mkdir(parents=True)
        self.config.write_text('// preserved comment\n"UserLocalConfigStore" {"Software" {"Valve" {"Steam" {"apps" {"5335510" {"Other" "leave me"}}}}}}\n')
        self.stopped = patch.object(setup, 'assert_steam_stopped'); self.stopped.start(); self.addCleanup(self.stopped.stop)

    def options(self, text):
        self.config.write_text('"UserLocalConfigStore" {"Software" {"Valve" {"Steam" {"apps" {"5335510" {"LaunchOptions" ' + setup._quoted(text) + ' "Other" "keep"}}}}}}')

    def test_merge_empty_and_argument_only(self):
        self.assertEqual(setup.merge(''), 'WINEDLLOVERRIDES="version=n,b" %command%')
        self.assertEqual(setup.merge('-logFile "file with spaces"'), 'WINEDLLOVERRIDES="version=n,b" %command% -logFile "file with spaces"')

    def test_wrappers_arguments_whitespace_and_other_overrides_survive(self):
        text = '  env FOO="a b" WINEDLLOVERRIDES="winhttp=n,b;version=b;dinput8=n" gamemoderun %command% --argument "quoted path"  '
        expected = text.replace('version=b;', 'version=n,b;')
        self.assertEqual(setup.merge(text), expected)
        self.assertEqual(setup.merge(expected), expected)
        self.assertEqual(setup.merge('mangohud %command% -x'), 'WINEDLLOVERRIDES="version=n,b" mangohud %command% -x')

    def test_environment_clearing_wrappers_never_become_ready(self):
        for prefix in ('env -i', 'env --ignore-environment', 'env -u WINEDLLOVERRIDES', 'env --unset=WINEDLLOVERRIDES', '/usr/bin/env -i', 'gamemoderun env -i', 'bwrap --clearenv', 'sh -c'):
            for text in (prefix + ' %command%', 'WINEDLLOVERRIDES="version=n,b" ' + prefix + ' %command%'):
                with self.subTest(text=text):
                    with self.assertRaises(ValueError): setup.merge(text)
                    self.options(text)
                    self.assertEqual(setup.inspect(self.installation)['status'], 'unsupported')

    def test_shared_dll_clause_preserves_other_dll_modes(self):
        self.assertEqual(setup.merge('WINEDLLOVERRIDES="foo,version=b;bar=n" %command%'), 'WINEDLLOVERRIDES="foo=b;version=n,b;bar=n" %command%')
        self.assertEqual(setup.merge("WINEDLLOVERRIDES='winhttp=n,b' %command%"), 'WINEDLLOVERRIDES="winhttp=n,b;version=n,b" %command%')

    def test_unsupported_options_are_not_guessed(self):
        for text in ('wrapper -x', '%command% %command%', 'echo; %command%', 'X=$(bad) %command%', 'wrapper WINEDLLOVERRIDES="foo=b" %command%', '%command% WINEDLLOVERRIDES="foo=b"', 'WINEDLLOVERRIDES="version=b;version=n" %command%', '"unclosed %command%', '"WINEDLLOVERRIDES=version=n,b" %command%', 'WINEDLLOVERRIDES="*=b" %command%'):
            with self.subTest(text=text), self.assertRaises(ValueError): setup.merge(text)

    def test_inspect_resolves_recent_account_and_preserves_comment(self):
        preview = setup.inspect(self.installation, 'linux')
        self.assertEqual(preview['status'], 'required'); self.assertEqual(preview['account'], '42')
        before = self.config.read_bytes(); result = setup.apply(self.installation, self.root/'data', preview)
        self.assertTrue(result['changed']); self.assertEqual((Path(result['backup'])/'localconfig.vdf').read_bytes(), before)
        self.assertTrue(self.config.read_text().startswith('// preserved comment\n'))
        apps = vdf(self.config.read_text())['UserLocalConfigStore']['Software']['Valve']['Steam']['apps']
        self.assertEqual(apps['5335510']['Other'], 'leave me'); self.assertEqual(apps['5335510']['LaunchOptions'], preview['proposed'])
        self.assertEqual(setup.inspect(self.installation, 'linux')['status'], 'ready')
        self.assertFalse(setup.apply(self.installation, self.root/'data', setup.inspect(self.installation))['changed'])

    def test_sole_account_without_mostrecent_matches_current_steam_shape(self):
        self.login.write_text('"users" {"76561197960265770" {"AccountName" "synthetic" "PersonaName" "Fixture" "RememberPassword" "1" "WantsOfflineMode" "0" "SkipOfflineModeWarning" "0" "AutoLogin" "1" "timestamp" "123"}}')
        preview = setup.inspect(self.installation)
        self.assertEqual(preview['status'], 'required'); self.assertEqual(preview['account'], '42')
        setup.apply(self.installation, self.root/'data', preview)
        self.assertEqual(setup.inspect(self.installation)['status'], 'ready')

    def test_multiple_unmarked_or_contradictory_accounts_remain_unsupported(self):
        for users in ('"76561197960265770" {"AutoLogin" "1"} "76561197960265771" {"AutoLogin" "0"}', '"76561197960265770" {"MostRecent" "0"}', '"76561197960265770" {"MostRecent" "unknown"}', '"76561197960265770" {"MostRecent" "1"} "76561197960265771" {"MostRecent" "1"}'):
            with self.subTest(users=users):
                self.login.write_text('"users" {' + users + '}')
                self.assertEqual(setup.inspect(self.installation)['status'], 'unsupported')

    def test_existing_options_replace_only_value_and_preserve_bom_crlf(self):
        self.options('WINEDLLOVERRIDES="version=b;winhttp=n,b" gamemoderun %command% -x')
        self.config.write_bytes(b'\xef\xbb\xbf' + self.config.read_bytes().replace(b' ', b'\r\n', 1))
        before = self.config.read_bytes(); preview = setup.inspect(self.installation)
        self.assertEqual(preview['status'], 'required')
        setup.apply(self.installation, self.root/'data', preview)
        self.assertEqual(self.config.read_bytes(), before.replace(b'version=b;', b'version=n,b;'))

    def test_changed_preview_and_changed_account_reject_without_write(self):
        preview = setup.inspect(self.installation)
        self.options('%command% -changed'); before = self.config.read_bytes()
        with self.assertRaisesRegex(ValueError, 'settings changed'): setup.apply(self.installation, self.root/'data', preview)
        self.assertEqual(self.config.read_bytes(), before)
        preview = setup.inspect(self.installation); self.login.write_text(self.login.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'settings changed'): setup.apply(self.installation, self.root/'data', preview)
        self.assertEqual(self.config.read_bytes(), before)

    def test_running_steam_rejects_without_write_or_backup(self):
        preview = setup.inspect(self.installation); before = self.config.read_bytes()
        with patch.object(setup, 'assert_steam_stopped', side_effect=ValueError('Quit Steam completely')):
            with self.assertRaisesRegex(ValueError, 'Quit Steam'): setup.apply(self.installation, self.root/'data', preview)
        self.assertEqual(self.config.read_bytes(), before); self.assertFalse((self.root/'data/steam-options-backups').exists())

    def test_mid_apply_config_change_is_preserved(self):
        preview = setup.inspect(self.installation); changed = self.config.read_bytes() + b'\n// external edit\n'
        calls = 0
        def race():
            nonlocal calls
            calls += 1
            if calls == 2: self.config.write_bytes(changed)
        with patch.object(setup, 'assert_steam_stopped', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'changed during'): setup.apply(self.installation, self.root/'data', preview)
        self.assertEqual(self.config.read_bytes(), changed)
        self.assertFalse(list(self.config.parent.glob('.moon-launch-options-*')))

    def test_account_ambiguity_duplicate_keys_and_aliases_are_unsupported(self):
        original = self.login.read_bytes()
        self.login.write_text('"users" {"76561197960265770" {"MostRecent" "1"} "76561197960265771" {"MostRecent" "1"}}')
        self.assertEqual(setup.inspect(self.installation)['status'], 'unsupported')
        self.login.write_bytes(original)
        self.config.write_text('"a" "1" "A" "2"')
        self.assertIn('duplicate', setup.inspect(self.installation)['message'])
        self.config.unlink(); target = self.root/'other'; target.write_text('"a" "b"'); self.config.symlink_to(target)
        self.assertIn('symlinks', setup.inspect(self.installation)['message'])

    def test_windows_preserves_options_without_reading_config(self):
        before = self.config.read_bytes()
        self.assertEqual(setup.inspect(self.installation, 'win32')['status'], 'not-required')
        setup.require_ready(self.installation, 'win32')
        self.assertEqual(self.config.read_bytes(), before)

    def test_real_process_scanner_detects_flatpak_steam(self):
        proc = self.root/'123'; proc.mkdir(); (proc/'cmdline').write_bytes(b'/app/steam/ubuntu12_32/steam\0')
        original = Path.iterdir
        def entries(path): return iter([proc]) if path == Path('/proc') else original(path)
        self.stopped.stop()
        with patch.object(Path, 'iterdir', entries):
            with self.assertRaisesRegex(ValueError, 'Quit Steam'): setup.assert_steam_stopped()
        self.stopped.start()

    def test_launch_rejects_missing_options_before_game_preparation(self):
        from moonloader import launch
        from types import SimpleNamespace
        from contextlib import nullcontext
        service = SimpleNamespace(root=self.root/'data')
        record = {'mode': 'installed', 'order': ['test'], 'platform': 'linux'}
        with patch.object(launch, 'plan', return_value=record), patch.object(launch, 'assert_inactive'), patch.object(launch, 'locked', return_value=nullcontext()):
            with self.assertRaisesRegex(ValueError, 'Steam setup required'): launch.start(service, self.installation)
