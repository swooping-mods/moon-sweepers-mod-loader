"""Publication must reject mismatched versions, stale evidence and altered ZIPs."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from release import VERSION, validate_tag, verify_artifacts, release_notes


class ReleaseChecks(unittest.TestCase):
    def candidate(self, root):
        sums = []
        identities={}
        coreclr = json.loads((Path(__file__).resolve().parents[1]/'vendored/managed-runtime.lock.json').read_text())['coreclr_version']
        for kind, receipt in [('source', 'build-receipt.json'), ('windows-x64', 'windows-build-receipt.json'), ('linux-x64', 'linux-build-receipt.json')]:
            name = f'moon-sweepers-mod-loader-{VERSION}-{kind}'+('.tar.gz' if kind=='linux-x64' else '.zip')
            payload = ('candidate ' + kind).encode()
            (root / name).write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            identities[kind]=digest
            sums.append(digest + '  ' + name + '\n')
            (root / receipt).write_text(json.dumps({'version': VERSION, 'archive': name, 'sha256': digest, 'python_qt_bundled':True, 'managed_coreclr_version': coreclr}))
        formats={}
        for suffix in ('.run','.AppImage'):
            name=f'moon-sweepers-mod-loader-{VERSION}-linux-x64'+suffix
            data=('checked format '+suffix).encode();(root/name).write_bytes(data)
            formats[name]=hashlib.sha256(data).hexdigest();sums.append(formats[name]+'  '+name+'\n')
        (root/'linux-formats-receipt.json').write_text(json.dumps({'version':VERSION,'source_archive_sha256':identities['linux-x64'],'files':formats}))
        (root/'linux-formats-checks.json').write_text(json.dumps({'success':True,'version':VERSION,'files':{n:{'sha256':sha,'actual_cli_passed':True,'bundled_gui_smoke_passed':True} for n,sha in formats.items()}}))
        (root / 'SHA256SUMS').write_text(''.join(sums))
        (root / 'checks.json').write_text(json.dumps({'success': True, 'tests_run': 40, 'failures': 0, 'errors': 0, 'skipped': [], 'excluded': ['test_loader.LoaderChecks.test_gui_checkboxes_views_filter_and_no_launch', 'test_loader.LoaderChecks.test_grid_wheel_travel_ignores_global_lines_and_preserves_precise_input', 'test_categories.CategoryChecks.test_ui_categories_tags_and_enabled_combine_in_every_view']}))
        (root / 'windows-checks.json').write_text(json.dumps({'success': True, 'sha256': identities['windows-x64'], 'managed_coreclr_version': coreclr}))
        (root / 'linux-checks.json').write_text(json.dumps({'success': True, 'sha256': identities['linux-x64'], 'actual_launcher_cli_passed':True, 'gui_smoke_passed':True, 'portable_desktop_libraries_passed':True, 'managed_coreclr_version': coreclr}))

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
            self.assertEqual(len(assets), 6)
            self.assertEqual(assets[-1].name, 'SHA256SUMS')

    def test_changed_payload_or_receipt_blocks_upload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for broken in ('zip', 'version', 'failed', 'excluded', 'extra', 'stale', 'linux-stale', 'linux-not-run', 'format-changed', 'format-not-run', 'managed-missing', 'managed-unverified'):
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
                elif broken == 'format-changed':
                    (root/f'moon-sweepers-mod-loader-{VERSION}-linux-x64.AppImage').write_bytes(b'changed')
                elif broken == 'format-not-run':
                    p=root/'linux-formats-checks.json';r=json.loads(p.read_text())
                    next(iter(r['files'].values()))['bundled_gui_smoke_passed']=False;p.write_text(json.dumps(r))
                elif broken.startswith('managed-'):
                    p=root/('build-receipt.json' if broken=='managed-missing' else 'windows-checks.json')
                    r=json.loads(p.read_text());r.pop('managed_coreclr_version');p.write_text(json.dumps(r))
                with self.subTest(broken=broken), self.assertRaises(ValueError):
                    verify_artifacts(root, 'v' + VERSION)

    def test_release_notes_select_only_the_matching_changelog(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'CHANGELOG.md'
            path.write_text(f'# Changelog\n\n## {VERSION} — today\n\nNew player behavior.\n\n## 0.0.0\n\nOld release.\n')
            self.assertEqual(release_notes('v'+VERSION,path),'New player behavior.\n')
            path.write_text('# Changelog\n\n## 0.0.0\n\nOther release.\n')
            with self.assertRaisesRegex(ValueError,'Missing release changelog'):
                release_notes('v'+VERSION,path)
