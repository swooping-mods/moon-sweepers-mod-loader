#!/usr/bin/env python3
"""Derive an inert host/compiler input from the exact screened be.791 archive."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from bepinex_support import managed
from managed_bundle import archive_files

UPSTREAM_SHA256 = 'bb1c510909b69522733791f3a0817a487379a52da6468a492f1c9c19b3ec6f9a'


def derive(source, output):
    raw = Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != UPSTREAM_SHA256:
        raise ValueError('Derivation requires the exact reviewed be.791 archive')
    original = archive_files(source)
    retained = {}; excluded = {}
    with tempfile.TemporaryDirectory(prefix='be791 metadata classification ') as temporary:
        for name, data in original.items():
            if name.startswith('dotnet/'):
                path = Path(temporary)/Path(name).name; path.write_bytes(data)
                if not name.endswith('.dll') or not managed(path):
                    excluded[name] = hashlib.sha256(data).hexdigest()
                    continue
            retained[name] = data
    # Preserve every compiler reference and host member verbatim. In particular,
    # no namespace, assembly identity, C# reference or deployed runtime changes.
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(retained.items()):
            member = zipfile.ZipInfo(name, (2026, 11, 10, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            archive.writestr(member, data)
    return {'schema':'moon-loader-derived-bepinex-input/v1',
            'upstream_sha256':UPSTREAM_SHA256,
            'derived_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'retained_members':{name:hashlib.sha256(data).hexdigest() for name,data in sorted(retained.items())},
            'excluded_members':dict(sorted(excluded.items())),
            'compiler_reference_members':[name for name in sorted(retained) if name.startswith('dotnet/')],
            'scope':'Source/build input only. Managed .NET 6 compiler-reference images are inert; no retired native CLR/JIT/GC/debug host or runtime configuration is retained.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    args = parser.parse_args()
    args.manifest.write_text(json.dumps(derive(args.source,args.output),indent=2)+'\n')
