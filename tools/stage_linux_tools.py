#!/usr/bin/env python3
"""Extract the hash-locked build-only SquashFS tool without running a package installer."""
import argparse
import io
from pathlib import Path
import subprocess
import tarfile

from linux_runtime import locked_inputs, safe


def stage(inputs, output):
    lock = locked_inputs(inputs)
    for item in lock['files']:
        if item['role'] not in ('build-tool', 'build-library'):
            continue
        path = inputs/item['name']
        raw = subprocess.check_output(['ar', 'p', str(path), 'data.tar.zst'])
        raw = subprocess.check_output(['zstd', '-dc'], input=raw)
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            members = {safe(member.name): member for member in archive if not member.isdir()}
            for name, member in members.items():
                if not (name == 'usr/bin/mksquashfs' or name.startswith('usr/lib/x86_64-linux-gnu/') and '.so' in name):
                    continue
                source = member
                if member.issym():
                    link = safe(str(Path(name).parent/member.linkname))
                    source = members[link]
                if not source.isfile():
                    raise ValueError('Unsupported build-tool member')
                target = output/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(source).read())
                target.chmod(0o755 if name == 'usr/bin/mksquashfs' else 0o644)
    if not (output/'usr/bin/mksquashfs').is_file():
        raise ValueError('Missing locked SquashFS tool')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage(args.inputs.resolve(), args.output.resolve())
