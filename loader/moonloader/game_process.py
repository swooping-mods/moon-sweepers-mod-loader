"""Passive executable identity observations, independent of a Steam request.

This reports a process name, never successful startup, mod loading, installation
ownership or a crash. No command lines or environments leave this module.
"""
import os
from pathlib import Path
import sys

from .storage import process_birth


_GAME = 'MoonSweepers.exe'
_PROC = Path('/proc')
_MAX_SCAN_ENTRIES = 8192
_MAX_CMDLINE_BYTES = 4096
_MAX_COMM_BYTES = 64


def _result(processes, incomplete=False):
    if processes:
        return {'status': 'running', 'processes': processes,
                'reason': 'Game executable identity observed; startup and mod loading are unverified.'}
    if incomplete:
        return {'status': 'unavailable', 'processes': [],
                'reason': 'Process identity could not be completely checked within observation limits.'}
    return {'status': 'absent', 'processes': [],
            'reason': 'No matching game executable was observed in the completed process scan.'}


def _bounded_read(path, limit):
    with path.open('rb') as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError('Process identity exceeds observation limit')
    return value


def _argv_game(path):
    command = _bounded_read(path / 'cmdline', _MAX_CMDLINE_BYTES)
    if not command:
        return False  # Kernel threads and zombies have no executable argv[0].
    if b'\0' not in command:
        raise ValueError('Incomplete process identity')
    # Wine may use either POSIX or Windows separators. Only argv[0] counts:
    # a Steam/Proton/wine wrapper merely mentioning the game is insufficient.
    executable = command.split(b'\0', 1)[0].replace(b'\\', b'/').rsplit(b'/', 1)[-1]
    return executable == _GAME.encode('ascii')


def _linux_observe():
    processes, incomplete = [], False
    try:
        with os.scandir(_PROC) as entries:
            for index, entry in enumerate(entries):
                if index >= _MAX_SCAN_ENTRIES:
                    incomplete = True
                    break
                if not entry.name.isascii() or not entry.name.isdecimal():
                    continue
                pid = int(entry.name)
                if pid <= 0:
                    continue
                path = _PROC / entry.name
                candidate = False
                try:
                    candidate = _argv_game(path)
                    if not candidate:
                        continue
                    before = process_birth(pid)
                    # Recheck identity inside the birth interval: the PID could
                    # have been reused after the initial argv[0] read.
                    identity = _argv_game(path)
                    comm = _bounded_read(path / 'comm', _MAX_COMM_BYTES).rstrip(b'\n')
                    after = process_birth(pid)
                    # Linux task comm is limited to 15 bytes. A Wine launcher
                    # comm does not establish the identity of its argument.
                    if (before is not None and before == after and identity
                            and comm == _GAME.encode('ascii')[:15]):
                        processes.append({'pid': pid, 'birth': str(before)})
                    else:
                        incomplete = True
                except (FileNotFoundError, ProcessLookupError):
                    # A disappearing noncandidate cannot conceal a live game.
                    incomplete = incomplete or candidate
                except (OSError, ValueError, IndexError):
                    incomplete = True
    except (OSError, ValueError):
        incomplete = True
    return _result(processes, incomplete)


def _windows_snapshot():
    """Return bounded Toolhelp executable names and whether enumeration finished."""
    import ctypes
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
                    ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ('Process32FirstW', 'Process32NextW'):
        function = getattr(kernel, name)
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
        function.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if handle == ctypes.c_void_p(-1).value or handle is None:
        raise OSError('Process snapshot unavailable')
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        result = []
        available = kernel.Process32FirstW(handle, ctypes.byref(entry))
        for _ in range(_MAX_SCAN_ENTRIES):
            if not available:
                return result, ctypes.get_last_error() == 18  # ERROR_NO_MORE_FILES
            result.append((int(entry.th32ProcessID), entry.szExeFile))
            available = kernel.Process32NextW(handle, ctypes.byref(entry))
        return result, not available and ctypes.get_last_error() == 18
    finally:
        kernel.CloseHandle(handle)


def _windows_observe():
    processes = []
    try:
        initial, complete = _windows_snapshot()
        candidates = {pid for pid, name in initial if pid > 0 and name.casefold() == _GAME.casefold()}
        if not candidates:
            return _result([], not complete)
        births, incomplete = {}, not complete
        for pid in sorted(candidates):
            try:
                birth = process_birth(pid)
                if birth is not None:
                    births[pid] = birth
                else:
                    incomplete = True
            except (OSError, ValueError, IndexError):
                incomplete = True
        # A second identity snapshot between birth queries excludes a reused
        # snapshot PID now belonging to an unrelated executable.
        current, complete = _windows_snapshot()
        incomplete = incomplete or not complete
        current_ids = {pid for pid, name in current if name.casefold() == _GAME.casefold()}
        for pid, birth in births.items():
            try:
                if pid in current_ids and process_birth(pid) == birth:
                    processes.append({'pid': pid, 'birth': str(birth)})
                else:
                    incomplete = True
            except (OSError, ValueError, IndexError):
                incomplete = True
        return _result(processes, incomplete)
    except (OSError, ValueError, AttributeError):
        return _result([], True)


def observe():
    """Return running/absent/unavailable plus PID/birth executable identities.

    This does not acquire ownership of any process. A caller must retain the
    creation token when comparing observations and must not treat unavailable
    as exit evidence. Linux Wine configurations without matching argv[0] and
    task comm cannot establish running through this conservative observer.
    """
    if os.name == 'nt':
        return _windows_observe()
    if sys.platform.startswith('linux'):
        return _linux_observe()
    return _result([], True)
