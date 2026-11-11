#!/usr/bin/env python3
"""Explicitly stage the already-reviewed runtime lock; verify bytes before use."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def download(item, temporary):
    # Retry transport failures, never changed publisher bytes or permission errors.
    for attempt in range(3):
        digest = hashlib.sha256()
        size = 0
        try:
            with urllib.request.urlopen(item['url'], timeout=60) as response, temporary.open('wb') as out:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 256 * 1024 * 1024:
                        raise ValueError('Input exceeds bounded download size: ' + item['name'])
                    digest.update(chunk)
                    out.write(chunk)
            if digest.hexdigest() != item['sha256']:
                raise ValueError('Publisher bytes changed; intake review required: ' + item['name'])
            return
        except OSError as error:
            temporary.unlink(missing_ok=True)
            if (attempt == 2 or isinstance(error, urllib.error.HTTPError)
                    and error.code not in (429, 500, 502, 503, 504)):
                raise
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lock', type=Path, default=ROOT/'vendored/windows-runtime.lock.json')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    lock = json.loads(args.lock.read_text())
    for item in lock['files']:
        name = item['name']
        if Path(name).name != name or not item['url'].startswith('https://'):
            raise ValueError('Invalid locked input: ' + name)
        target = args.output / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == item['sha256']:
            continue
        if item.get('local_path'):
            source = ROOT/item['local_path']
            if not source.resolve().is_relative_to(ROOT) or source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Vendored runtime identity mismatch: '+name)
            shutil.copyfile(source, target)
            continue
        temporary = target.with_name(name + '.download')
        try:
            download(item, temporary)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print('Verified ' + name, flush=True)


if __name__ == '__main__':
    main()
