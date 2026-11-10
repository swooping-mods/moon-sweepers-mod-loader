"""Check the exported game adapter independently of the author's workshop."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    root = ROOT/'sdk/native'
    lock = json.loads((root/'snapshot.json').read_text())
    if lock.get('schema') != 'moon-native-adapter-snapshot/v1':
        raise ValueError('Unexpected native adapter snapshot')
    actual = {}
    for p in root.rglob('*'):
        if p.is_symlink():
            raise ValueError('Native adapter aliases are forbidden')
        if p.is_file() and p != root/'snapshot.json':
            actual[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != lock['files']:
        raise ValueError('Native adapter differs from its reviewed file table')
    # The adapter retains relative include paths; core contracts still belong
    # to the pinned API and cannot acquire an independently edited ABI here.
    for name, expected in actual.items():
        api = ROOT/'vendored/api/include/moon_sweepers'/Path(name).relative_to('runtime/sdk') if name.startswith('runtime/sdk/') else None
        if api and api.is_file() and hashlib.sha256(api.read_bytes()).hexdigest() != expected:
            raise ValueError('Core API/adapter header drift: '+name)
    return {'success': True, 'headers': len(actual)}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
