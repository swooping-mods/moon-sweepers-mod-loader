"""Portable, crash-resistant JSON storage and exclusive operations."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path, default=None):
    return json.loads(Path(path).read_text('utf-8')) if Path(path).exists() else default


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def key(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value) or len(value) > 64:
        raise ValueError('Expected a short lowercase package ID')
    return value


def relative(value):
    """One portable spelling on both Windows and Unix; never accept aliases."""
    if not isinstance(value, str) or len(value) > 220 or '\\' in value or ':' in value:
        raise ValueError('Invalid package path')
    parts = value.split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    for part in parts:
        if (not part or part in ('.', '..') or part.rstrip(' .') != part
                or part.split('.')[0].upper() in reserved
                or any(ord(c) < 32 or c in '<>"|?*' for c in part)):
            raise ValueError('Invalid package path: ' + value)
    return value


def is_alias(path):
    path=Path(path)
    if path.is_symlink(): return True
    try: return bool(getattr(path.lstat(),'st_file_attributes',0) & getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400))
    except FileNotFoundError: return False


def contained(root, name):
    relative(name)
    root = Path(root).absolute()
    result = root / name
    for parent in (root, *result.parents, result):
        if is_alias(parent):
            raise ValueError('Symlink in owned path: ' + str(parent))
        if parent == root:
            break
    # Check from the leaf as well: the root may itself have an aliasing ancestor.
    for p in (result, *result.parents):
        if is_alias(p):
            raise ValueError('Symlink in owned path: ' + str(p))
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escaped owned storage')
    return result
