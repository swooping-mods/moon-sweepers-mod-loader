#!/usr/bin/env python3
"""Reject mismatched tags, failed checks and changed release assets before upload."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from build import VERSION


def validate_tag(tag):
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag) or tag != 'v' + VERSION:
        raise ValueError(f'Release tag must match package version: v{VERSION}')


def verify_artifacts(folder, tag):
    validate_tag(tag)
    names = [f'moon-sweepers-mod-loader-{VERSION}-{kind}.zip'
             for kind in ('source', 'windows-x64')]
    names.append(f'moon-sweepers-mod-loader-{VERSION}-linux-x64.tar.gz')
    checksums = {}
    for line in (folder / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if name in checksums or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Invalid or duplicate checksum')
        checksums[name] = digest
    if set(checksums) != set(names):
        raise ValueError('Checksums must cover exactly this version\'s source, Windows and Linux archives')
    for name, receipt_name in zip(names, ('build-receipt.json', 'windows-build-receipt.json', 'linux-build-receipt.json')):
        receipt = json.loads((folder / receipt_name).read_text())
        with (folder / name).open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if receipt.get('version') != VERSION or receipt['archive'] != name:
            raise ValueError('Build receipt version/archive mismatch')
        if receipt['sha256'] != digest or checksums[name] != digest:
            raise ValueError('Release ZIP checksum mismatch: ' + name)
    for name in ('checks.json', 'windows-checks.json', 'linux-checks.json'):
        check = json.loads((folder / name).read_text())
        if check.get('success') is not True or check.get('failures', 0) or check.get('errors', 0) or check.get('skipped'):
            raise ValueError('Unsuccessful verification receipt: ' + name)
    host = json.loads((folder / 'checks.json').read_text())
    allowed = {'test_gui_checkboxes_views_filter_and_no_launch',
               'test_grid_wheel_travel_ignores_global_lines_and_preserves_precise_input',
               'test_ui_categories_tags_and_enabled_combine_in_every_view'}
    if not host.get('tests_run') or any(t.rsplit('.', 1)[-1] not in allowed for t in host.get('excluded', [])):
        raise ValueError('Missing host checks or unexpected exclusions')
    windows = json.loads((folder / 'windows-checks.json').read_text())
    if windows.get('sha256') != checksums[names[1]]:
        raise ValueError('Static Windows check belongs to a different ZIP')
    linux = json.loads((folder / 'linux-checks.json').read_text())
    if linux.get('sha256') != checksums[names[2]] or not linux.get('actual_launcher_cli_passed'):
        raise ValueError('Linux launcher check belongs to a different archive or did not run')
    return [folder / name for name in names] + [folder / 'SHA256SUMS']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate-tag', 'verify-artifacts'])
    parser.add_argument('tag')
    parser.add_argument('--artifacts', type=Path, default=Path('artifacts'))
    args = parser.parse_args()
    if args.command == 'validate-tag':
        validate_tag(args.tag)
    else:
        for path in verify_artifacts(args.artifacts, args.tag):
            print(path)


if __name__ == '__main__':
    main()
