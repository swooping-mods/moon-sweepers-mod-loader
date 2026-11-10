"""Regress direct-hardware fallback and preserve private capture/loader routing."""
from pathlib import Path
import ast
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audio_policy import audio_environment


def overrides(env):
    result = {}
    for entry in env['WINEDLLOVERRIDES'].split(';'):
        names, mode = entry.split('=', 1)
        for name in names.split(','):
            result[name.lower()] = mode
    return result


class AudioPolicyChecks(unittest.TestCase):
    def test_launchers_do_not_reintroduce_fake_pulse_server_muting(self):
        tools = Path(__file__).resolve().parents[1] / 'tools'
        for source in tools.glob('*.py'):
            for value in ast.walk(ast.parse(source.read_text())):
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    self.assertNotIn('unix:/nonexistent', value.value, str(source))

    def test_mute_blocks_drivers_even_with_hostile_existing_overrides(self):
        original = dict(WINEDLLOVERRIDES='version=n,b;winhttp=n,b;*WINEALSA.DRV,mshtml=b;winepulse.drv=b',
                        PULSE_SERVER='unix:/nonexistent/old-mute', PULSE_SINK='desktop',
                        ALSOFT_DRIVERS='alsa', SDL_AUDIODRIVER='alsa')
        env = audio_environment(original)
        modes = overrides(env)
        for driver in ('winepulse.drv', 'winealsa.drv', 'wineoss.drv', 'winepipewire.drv'):
            self.assertEqual(modes[driver], '')
        self.assertNotIn('*winealsa.drv', modes)
        self.assertEqual(modes['version'], 'n,b')
        self.assertEqual(modes['winhttp'], 'n,b')
        self.assertEqual(modes['mshtml'], 'b')
        self.assertEqual(env['ALSOFT_DRIVERS'], 'null')
        self.assertEqual(env['SDL_AUDIODRIVER'], 'dummy')
        self.assertEqual(env['PULSE_SERVER'], '')
        self.assertEqual(env['PULSE_SINK'], '')
        self.assertEqual(original['ALSOFT_DRIVERS'], 'alsa')

    def test_capture_allows_only_pulse_and_preserves_loader_overrides(self):
        sink = 'moonlab_slime_012345abcdef'
        env = audio_environment(dict(WINEDLLOVERRIDES='version=n,b;winhttp=n,b'), capture_sink=sink)
        modes = overrides(env)
        self.assertEqual(modes['winepulse.drv'], 'b')
        for driver in ('winealsa.drv', 'wineoss.drv', 'winepipewire.drv'):
            self.assertEqual(modes[driver], '')
        self.assertEqual(modes['version'], 'n,b')
        self.assertEqual(modes['winhttp'], 'n,b')
        self.assertEqual(env['PULSE_SINK'], sink)
        self.assertTrue(env['PULSE_SERVER'].endswith('/pulse/native'))

    def test_arbitrary_capture_targets_are_rejected(self):
        for sink in ('', '@DEFAULT_SINK@', 'alsa_output.headphones', 'moonlab_slime_invalid'):
            with self.subTest(sink=sink), self.assertRaises(ValueError):
                audio_environment({}, capture_sink=sink)

    def test_policy_is_idempotent_and_capture_can_be_muted_again(self):
        env = audio_environment(dict(WINEDLLOVERRIDES='version=n,b'))
        self.assertEqual(audio_environment(env), env)
        captured = audio_environment(env, capture_sink='moonlab_slime_012345abcdef')
        self.assertEqual(audio_environment(captured), env)


if __name__ == '__main__':
    unittest.main()
