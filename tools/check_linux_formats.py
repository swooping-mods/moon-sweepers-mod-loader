#!/usr/bin/env python3
"""Execute both single-file Linux launchers, including bundled Qt, without a game."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import build
from build_linux_formats import digest


def check(out):
    receipt = json.loads((out/'linux-formats-receipt.json').read_text())
    linux = json.loads((out/'linux-build-receipt.json').read_text())
    if receipt['version'] != build.VERSION or receipt['source_archive_sha256'] != linux['sha256']:
        raise ValueError('Linux formats refer to a different source payload')
    results = {}
    with tempfile.TemporaryDirectory(prefix='Moon Loader single file ') as temporary:
        root = Path(temporary)
        env = {**os.environ, 'XDG_CACHE_HOME': str(root/'cache'), 'XDG_DATA_HOME': str(root/'data'),
               'TMPDIR': str(root), 'QT_QPA_PLATFORM': 'offscreen'}
        env.pop('MOON_LOADER_PYTHON', None)
        for name, sha in receipt['files'].items():
            source = out/name
            if digest(source) != sha:
                raise ValueError('Single-file Linux artifact changed: '+name)
            target = root/name
            shutil.copyfile(source, target)
            target.chmod(0o755)
            command = [str(target)]
            if name.endswith('.AppImage'):
                command.append('--appimage-extract-and-run')
            for option in ('--help', '--smoke-test'):
                subprocess.run(command+[option], env=env, check=True, capture_output=True, timeout=120)
            results[name] = {'sha256': sha, 'actual_cli_passed': True, 'bundled_gui_smoke_passed': True}
    result = {'success': True, 'version': build.VERSION, 'files': results,
              'game_started': False, 'fuse_required_for_check': False}
    (out/'linux-formats-checks.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=build.ROOT/'artifacts')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve()), indent=2))
