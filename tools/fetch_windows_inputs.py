#!/usr/bin/env python3
"""Explicitly stage the already-reviewed runtime lock; verify bytes before use."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / 'vendored/windows-runtime.lock.json').read_text())
    for item in lock['files']:
        name = item['name']
        if Path(name).name != name or not item['url'].startswith('https://'):
            raise ValueError('Invalid locked input: ' + name)
        target = args.output / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == item['sha256']:
            continue
        temporary = target.with_name(name + '.download')
        digest = hashlib.sha256()
        size = 0
        try:
            with urllib.request.urlopen(item['url'], timeout=60) as response, temporary.open('wb') as out:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 256 * 1024 * 1024:
                        raise ValueError('Input exceeds bounded download size: ' + name)
                    digest.update(chunk)
                    out.write(chunk)
            if digest.hexdigest() != item['sha256']:
                raise ValueError('Publisher bytes changed; intake review required: ' + name)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print('Verified ' + name, flush=True)


if __name__ == '__main__':
    main()
