"""Loader process ownership and operation locking over the shared API storage."""
from contextlib import contextmanager
import os
from pathlib import Path
from moon_mod_api.storage import sha, load, write, key, relative, is_alias, contained


@contextmanager
def locked(root, filename="operation.lock"):
    root = Path(root)
    contained(root, filename)
    root.mkdir(parents=True, exist_ok=True)
    stream = (root / filename).open('a+b')
    stream.seek(0, os.SEEK_END)
    if not stream.tell():
        stream.write(b'\0')
        stream.flush()
    stream.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        stream.close()
        raise ValueError('Another loader operation is running') from error
    try:
        yield
    finally:
        stream.close()


def process_birth(pid):
    """PID plus creation time prevents reuse from claiming a stranger's process."""
    if os.name != 'nt':
        try: return (Path('/proc') / str(int(pid)) / 'stat').read_text().rsplit(') ',1)[1].split()[19]
        except FileNotFoundError: return None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000,False,int(pid))
    if not handle:
        if ctypes.get_last_error() == 87: return None
        raise ValueError('Cannot verify the recorded game process; preserve active.json before inspection')
    try:
        times=[wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*(ctypes.byref(t) for t in times)): raise ValueError('Cannot query game creation time')
        return str((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)
    finally: kernel.CloseHandle(handle)


def assert_inactive(root):
    record = load(Path(root) / 'active.json')
    if record and record.get('state') in ('steam-starting', 'steam-unconfirmed', 'private-unconfirmed'):
        raise ValueError('Game lifetime is unconfirmed. Close the game or confirm it did not start in the loader before changing files or launching again.')
    if record and record.get('state') == 'starting':
        raise ValueError('An interrupted launch record needs inspection before changing game files: active.json')
    if record and record.get('birth') is not None and process_birth(record['pid']) == record['birth']:
        raise ValueError('A modded game from this loader is still running. Close it normally before changing its files.')


def pending_launch(root):
    record = load(contained(root, 'active.json'), {})
    if not isinstance(record, dict): raise ValueError('Invalid launch state: inspect active.json before launching')
    return record if record.get('state') in ('steam-starting', 'steam-unconfirmed', 'private-unconfirmed') else None


def acknowledge_launch_closed(root, run):
    """Clear only the reviewed request, after a conservative no-game check."""
    from . import public
    with locked(root, 'session.lock'), locked(root):
        record = pending_launch(root)
        if not record or record.get('run') != run:
            raise ValueError('Launch state changed; review the current request before continuing')
        public.assert_stopped()
        write(Path(root) / 'active.json', {'state':'closed', 'run':run})


def retain_private_uncertainty(root, run):
    """Called while the private process lease is still held, before releasing it."""
    active = contained(root, 'active.json')
    record = load(active, {})
    if not isinstance(record, dict) or record.get('run') != run:
        raise ValueError('Private launch state changed; inspect active.json before continuing')
    write(active, {'state':'private-unconfirmed', 'run':run})
