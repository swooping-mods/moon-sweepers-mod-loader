#!/usr/bin/env python3
"""Promote an existing checked prerelease without rebuilding or replacing assets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

REPO = 'swooping-mods/moon-sweepers-mod-loader'


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', f'repos/{REPO}/{path}'], text=True))


def validate_candidate(tag, release, checksums, commit, runs):
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError('Choose an existing numeric vMAJOR.MINOR.PATCH tag')
    if release['tag_name'] != tag or release['draft']:
        raise ValueError('Promotion requires a published release for the chosen tag')
    if not any(r['head_sha'] == commit and r['head_branch'] == tag
               and r['event'] == 'push' and r['conclusion'] == 'success' for r in runs):
        raise ValueError('No successful tag publishing workflow for this exact commit')
    prefix = 'moon-sweepers-mod-loader-' + tag[1:]
    expected = {prefix + suffix for suffix in ('-source.zip', '-windows-x64.zip',
                '-linux-x64.tar.gz', '-linux-x64.run', '-linux-x64.AppImage')}
    hashes = {}
    for line in checksums.decode('utf-8').splitlines():
        sha, name = line.split('  ', 1)
        if not re.fullmatch('[a-f0-9]{64}', sha) or name in hashes:
            raise ValueError('Invalid release checksums')
        hashes[name] = sha
    if set(hashes) != expected:
        raise ValueError('Release checksums must cover the exact five platform/source files')
    hashes['SHA256SUMS'] = hashlib.sha256(checksums).hexdigest()
    assets = release['assets']
    if len(assets) != 6 or {a['name'] for a in assets} != set(hashes):
        raise ValueError('Missing or unexpected release assets')
    for asset in assets:
        if (asset['state'] != 'uploaded' or asset['size'] <= 0
                or asset.get('digest') != 'sha256:' + hashes[asset['name']]):
            raise ValueError('Incomplete or changed release asset: ' + asset['name'])


def promote(tag):
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError('Choose an existing numeric vMAJOR.MINOR.PATCH tag')
    ref = api('git/ref/tags/' + tag)['object']
    commit = api('git/tags/' + ref['sha'])['object']['sha'] if ref['type'] == 'tag' else ref['sha']
    runs = api('actions/workflows/release.yml/runs?head_sha=' + commit + '&event=push&per_page=100')['workflow_runs']
    before = api('releases/tags/' + tag)
    with tempfile.TemporaryDirectory(prefix='moon-release-promotion-') as temporary:
        subprocess.run(['gh', 'release', 'download', tag, '--repo', REPO,
                        '--pattern', 'SHA256SUMS', '--dir', temporary], check=True)
        sums = (Path(temporary)/'SHA256SUMS').read_bytes()
    validate_candidate(tag, before, sums, commit, runs)
    subprocess.run(['gh', 'release', 'edit', tag, '--repo', REPO,
                    '--prerelease=false', '--latest=true'], check=True)
    after = api('releases/tags/' + tag)
    validate_candidate(tag, after, sums, commit, runs)
    identity = lambda r: [(a['id'], a['name'], a['size'], a['digest']) for a in r['assets']]
    if after['prerelease'] or identity(before) != identity(after):
        raise ValueError('Release promotion did not preserve the checked assets')
    if api('releases/latest')['id'] != after['id']:
        raise ValueError('Promoted release is not marked latest')
    print(json.dumps({'tag': tag, 'commit': commit, 'url': after['html_url'],
                      'prerelease': False, 'latest': True, 'assets_preserved': True}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag')
    promote(parser.parse_args().tag)
