"""Verify and package inert notices/corresponding sources for the managed host."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def payload(root=ROOT):
    root = Path(root)
    folder = root/'vendored/bepinex-notices'
    manifest_path = folder/'manifest.json'
    if folder.is_symlink() or manifest_path.is_symlink():
        raise ValueError('Aliased BepInEx notices')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema') != 'moon-loader-bepinex-component-notices/v1':
        raise ValueError('Unknown BepInEx notice manifest')
    expected = manifest['notice_files']
    if not expected or {p.name for p in folder.iterdir()} != set(expected)|{'manifest.json'}:
        raise ValueError('BepInEx notice inventory changed')
    files = {}
    for name, digest in expected.items():
        path = folder/name
        if Path(name).name != name or path.is_symlink() or not path.is_file():
            raise ValueError('Invalid BepInEx notice member: '+name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('BepInEx notice changed: '+name)
        files['BepInEx/third-party-sources/'+name] = data
    covered = set()
    for component in manifest['components']:
        if component['notice'] not in expected or component.get('source_archive', component['notice']) not in expected:
            raise ValueError('Missing BepInEx component notice/source')
        for name in component['files']:
            if name in covered:
                raise ValueError('Duplicate BepInEx component ownership')
            covered.add(name)
    for name in manifest['additional_notices']:
        if name not in expected:
            raise ValueError('Missing BepInEx additional notice')
    files['BepInEx/third-party-sources/components.json'] = manifest_path.read_bytes()
    files['BepInEx/third-party-sources/README.md'] = (root/'vendored/bepinex-runtime-notices.md').read_bytes()
    return files


if __name__ == '__main__':
    print(json.dumps({'notice_source_files':len(payload()), 'upstream_code_executed':False}))
