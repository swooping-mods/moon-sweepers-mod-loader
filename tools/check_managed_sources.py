"""Verify the singly owned managed adapter sources without loading any CLR code."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'loader'))
from moonloader.storage import contained


def check():
    lock = json.loads((ROOT/'runtime/bepinex/source-snapshot.json').read_text())
    if lock.get('schema') != 'moon-managed-adapter-source/v1':
        raise ValueError('Unexpected managed adapter source pin')
    actual = {}
    for p in (ROOT/'runtime/bepinex').rglob('*.cs'):
        contained(ROOT, p.relative_to(ROOT).as_posix())
        actual[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    for name in ('tools/bepinex_sources.py', 'tools/bepinex_support.py'):
        p = contained(ROOT, name)
        actual[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != lock['files']:
        raise ValueError('Managed adapter source inventory changed; review the delta and update its pin')
    return {'success': True, 'source_files': len(actual)}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
