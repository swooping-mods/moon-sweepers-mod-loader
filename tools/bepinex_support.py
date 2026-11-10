"""Shared validation for offline adapter builds; no acquisition or activation."""
import json
import os
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'loader'))
from moonloader.storage import contained, is_alias, relative, sha


def managed(path):
    """Classify a checked PE using bounded headers, not a whole DLL allocation."""
    try:
        with Path(path).open('rb') as stream:
            header = stream.read(64)
            if len(header) != 64 or header[:2] != b'MZ':
                return False
            offset = struct.unpack_from('<I', header, 0x3c)[0]
            if offset > os.fstat(stream.fileno()).st_size - 24:
                return False
            stream.seek(offset)
            header = stream.read(24)
            if header[:4] != b'PE\0\0':
                return False
            size = struct.unpack_from('<H', header, 20)[0]
            optional = stream.read(min(size, 240))
            if len(optional) < 2:
                return False
            magic = struct.unpack_from('<H', optional)[0]
            directories = {0x10b: 96, 0x20b: 112}.get(magic)
            if directories is None or len(optional) < directories + 15 * 8:
                return False
            count = struct.unpack_from('<I', optional, directories - 4)[0]
            return count >= 15 and bool(struct.unpack_from('<I', optional, directories + 14 * 8)[0])
    except (OSError, struct.error):
        return False


def verify_tree(root, expected):
    """Check complete bytes and reject aliases before copying any tree."""
    root = Path(root).absolute()
    contained(root, 'tree-check')
    if not root.is_dir():raise ValueError('Checked tree is missing: ' + str(root))
    names = set()
    for name in expected:
        relative(name)
        if name.casefold() in names:
            raise ValueError('Aliased manifest file: ' + name)
        names.add(name.casefold())
    actual = set()
    def fail(error):
        raise error
    for folder, directories, files in os.walk(root, followlinks=False, onerror=fail):
        for name in directories + files:
            path = Path(folder) / name
            if is_alias(path):
                raise ValueError('Alias in checked tree: ' + str(path))
        for name in files:
            path = Path(folder) / name
            name = path.relative_to(root).as_posix()
            if name not in expected or name.casefold() in actual or sha(path) != expected[name]:
                raise ValueError('Changed or unlisted checked file: ' + name)
            actual.add(name.casefold())
    if actual != names:
        raise ValueError('Missing checked files: ' + str(root))


def compile_atomic(command, target, inputs, log, timeout=90):
    """A failed compiler or source drift cannot replace a previous binary."""
    target = Path(target)
    before = {str(p): expected for p, expected in inputs.items()} if isinstance(inputs, dict) else {str(p): sha(p) for p in inputs}
    if any(sha(path) != expected for path, expected in before.items()):
        raise ValueError('Compilation input changed before build')
    stage_dir = target.parent / ('.compile-' + uuid.uuid4().hex)
    stage = stage_dir / target.name
    output = '/out:' + str(target)
    if command.count(output) != 1:
        raise ValueError('Compiler output must name the owned target once')
    command = [('/out:' + str(stage)) if arg == output else arg for arg in command]
    stage_dir.mkdir()
    # Keep the filename stable: the compiler derives the CLR assembly identity
    # from it. Only the staging directory may have a random name.
    try:
        with Path(log).open('w') as stream:
            run = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout,
                                 env={**os.environ, 'DOTNET_CLI_TELEMETRY_OPTOUT': '1'})
        if run.returncode:
            return run.returncode
        if any(sha(path) != expected for path, expected in before.items()):
            raise ValueError('Compilation inputs changed during build')
        os.replace(stage, target)
        return 0
    finally:
        shutil.rmtree(stage_dir)


def owned_snapshot(path):
    path = Path(path).absolute()
    contained(ROOT / 'artifacts', path.relative_to(ROOT / 'artifacts').as_posix())
    if path.name != 'metadata.json' or path.parent.parent.name != 'runs' or not path.parent.parent.parent.name.startswith('bepinex-'):
        raise ValueError('Use an owned BepInEx live snapshot')
    run = json.loads((path.parent / 'result.json').read_text())
    if not all(run.get(name) for name in ('success', 'snapshot_only', 'source_preserved', 'prefix_restored', 'profile_restored')):
        raise ValueError('Generation requires a successful restored snapshot run')
    return path


def verified_generation(generation):
    """Legacy and current generation receipts must both close over real bytes."""
    if not generation.get('success'):
        raise ValueError('Generate and validate original bindings first')
    output = Path(generation['output']).absolute()
    contained(ROOT / 'artifacts', output.relative_to(ROOT / 'artifacts').as_posix())
    interop = output / 'interop'
    receipt = interop / 'moonlab-interop.json'
    receipt_hash = sha(receipt)
    if generation.get('interop_receipt_sha256', receipt_hash) != receipt_hash:
        raise ValueError('Generated binding receipt changed')
    metadata = json.loads(receipt.read_text())
    if metadata.get('schema') not in ('moonlab-interop/v2', 'moonlab-interop/v3'):
        raise ValueError('Unknown generated binding schema')
    files = dict(metadata['files'])
    files[receipt.name] = receipt_hash
    stamp = interop / 'assembly-hash.txt'
    if stamp.exists():
        files[stamp.name] = sha(stamp)
    verify_tree(interop, files)
    return interop
