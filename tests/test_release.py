"""Publication must reject mismatched versions, stale evidence and altered ZIPs."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from release import VERSION, validate_tag, verify_artifacts


class ReleaseChecks(unittest.TestCase):
    def candidate(self, root):
        sums = []
        identities={}
        for kind, receipt in [('source', 'build-receipt.json'), ('windows-x64', 'windows-build-receipt.json'), ('linux-x64', 'linux-build-receipt.json')]:
            name = f'moon-sweepers-mod-loader-{VERSION}-{kind}'+('.tar.gz' if kind=='linux-x64' else '.zip')
            payload = ('candidate ' + kind).encode()
            (root / name).write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            identities[kind]=digest
            sums.append(digest + '  ' + name + '\n')
            (root / receipt).write_text(json.dumps({'version': VERSION, 'archive': name, 'sha256': digest}))
        (root / 'SHA256SUMS').write_text(''.join(sums))
        (root / 'checks.json').write_text(json.dumps({'success': True, 'tests_run': 40, 'failures': 0, 'errors': 0, 'skipped': [], 'excluded': ['test_loader.LoaderChecks.test_gui_checkboxes_views_filter_and_no_launch', 'test_loader.LoaderChecks.test_grid_wheel_travel_ignores_global_lines_and_preserves_precise_input', 'test_categories.CategoryChecks.test_ui_categories_tags_and_enabled_combine_in_every_view']}))
        (root / 'windows-checks.json').write_text(json.dumps({'success': True, 'sha256': identities['windows-x64']}))
        (root / 'linux-checks.json').write_text(json.dumps({'success': True, 'sha256': identities['linux-x64'], 'actual_launcher_cli_passed':True}))

    def test_tag_must_match_package_version(self):
        validate_tag('v' + VERSION)
        for tag in ('main', 'v999.0.0', 'v' + VERSION + '-rc1', VERSION):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                validate_tag(tag)

    def test_verified_assets_are_exact_release_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.candidate(root)
            assets = verify_artifacts(root, 'v' + VERSION)
            self.assertEqual(len(assets), 4)
            self.assertEqual(assets[-1].name, 'SHA256SUMS')

    def test_changed_payload_or_receipt_blocks_upload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for broken in ('zip', 'version', 'failed', 'excluded', 'extra', 'stale', 'linux-stale', 'linux-not-run'):
                self.candidate(root)
                if broken == 'zip':
                    (root / f'moon-sweepers-mod-loader-{VERSION}-windows-x64.zip').write_bytes(b'changed')
                elif broken == 'version':
                    p = root / 'build-receipt.json'
                    r = json.loads(p.read_text()); r['version'] = '999.0.0'; p.write_text(json.dumps(r))
                elif broken in ('failed', 'excluded'):
                    p = root / 'checks.json'
                    r = json.loads(p.read_text())
                    if broken == 'failed': r['success'] = False
                    else: r['excluded'].append('test_security')
                    p.write_text(json.dumps(r))
                elif broken == 'extra':
                    with (root / 'SHA256SUMS').open('a') as stream:
                        stream.write('0' * 64 + '  other.zip\n')
                elif broken == 'stale':
                    (root / 'windows-checks.json').write_text(json.dumps({'success': True, 'sha256': '0' * 64}))
                elif broken.startswith('linux-'):
                    p=root/'linux-checks.json';r=json.loads(p.read_text())
                    if broken=='linux-stale':r['sha256']='0'*64
                    else:r['actual_launcher_cli_passed']=False
                    p.write_text(json.dumps(r))
                with self.subTest(broken=broken), self.assertRaises(ValueError):
                    verify_artifacts(root, 'v' + VERSION)
