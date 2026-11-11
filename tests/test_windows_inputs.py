"""Pinned downloads stay inert and cannot replace reviewed bytes on mismatch."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import fetch_windows_inputs


class WindowsInputChecks(unittest.TestCase):
    def test_vendored_input_stages_offline_and_tampering_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'vendored').mkdir()
            source = root/'vendored/input.zip'
            source.write_bytes(b'reviewed')
            lock = root/'vendored/windows-runtime.lock.json'
            lock.write_text(json.dumps({'files': [{
                'name': 'input.zip', 'url': 'https://publisher.invalid/input.zip',
                'local_path': 'vendored/input.zip',
                'sha256': hashlib.sha256(b'reviewed').hexdigest()}]}))
            output = root/'staged'
            with patch.object(fetch_windows_inputs, 'ROOT', root), \
                    patch('sys.argv', ['fetch', '--output', str(output)]), \
                    patch.object(fetch_windows_inputs.urllib.request, 'urlopen') as request:
                fetch_windows_inputs.main()
                self.assertEqual((output/'input.zip').read_bytes(), b'reviewed')
                (output/'input.zip').unlink()
                source.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'Vendored runtime identity'):
                    fetch_windows_inputs.main()
                request.assert_not_called()

    def test_transient_download_retries_but_changed_bytes_do_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'input.download'
            item = {'name': 'input.zip', 'url': 'https://publisher.invalid/input.zip',
                    'sha256': hashlib.sha256(b'reviewed').hexdigest()}
            with patch.object(fetch_windows_inputs.urllib.request, 'urlopen',
                              side_effect=[OSError('connection reset'), io.BytesIO(b'reviewed')]) as request, \
                    patch.object(fetch_windows_inputs.time, 'sleep'):
                fetch_windows_inputs.download(item, target)
                self.assertEqual(request.call_count, 2)
                self.assertEqual(target.read_bytes(), b'reviewed')
            with patch.object(fetch_windows_inputs.urllib.request, 'urlopen',
                              return_value=io.BytesIO(b'changed')) as request:
                with self.assertRaisesRegex(ValueError, 'intake review required'):
                    fetch_windows_inputs.download(item, target)
                self.assertEqual(request.call_count, 1)

    def test_mismatch_preserves_prior_file_and_removes_partial_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'vendored').mkdir()
            (root / 'vendored/windows-runtime.lock.json').write_text(json.dumps({'files': [{
                'name': 'input.zip', 'url': 'https://publisher.invalid/input.zip',
                'sha256': hashlib.sha256(b'reviewed').hexdigest()}]}))
            output = root / 'staged'
            output.mkdir()
            target = output / 'input.zip'
            target.write_bytes(b'prior')
            with patch.object(fetch_windows_inputs, 'ROOT', root), patch('sys.argv', ['fetch', '--output', str(output)]), patch.object(fetch_windows_inputs.urllib.request, 'urlopen', return_value=io.BytesIO(b'changed')):
                with self.assertRaisesRegex(ValueError, 'intake review required'):
                    fetch_windows_inputs.main()
            self.assertEqual(target.read_bytes(), b'prior')
            self.assertFalse((output / 'input.zip.download').exists())

    def test_matching_staged_bytes_do_not_contact_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'vendored').mkdir()
            (root / 'vendored/windows-runtime.lock.json').write_text(json.dumps({'files': [{
                'name': 'input.zip', 'url': 'https://publisher.invalid/input.zip',
                'sha256': hashlib.sha256(b'reviewed').hexdigest()}]}))
            output = root / 'staged'
            output.mkdir()
            (output / 'input.zip').write_bytes(b'reviewed')
            with patch.object(fetch_windows_inputs, 'ROOT', root), patch('sys.argv', ['fetch', '--output', str(output)]), patch.object(fetch_windows_inputs.urllib.request, 'urlopen') as request:
                fetch_windows_inputs.main()
                request.assert_not_called()
