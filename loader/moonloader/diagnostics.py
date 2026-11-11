"""Local, bounded launcher diagnostics. Recording must never replace an error."""
from datetime import datetime, timezone
from contextlib import contextmanager
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import stat
import threading
import time
import traceback
import uuid

MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 4
TAIL_BYTES = 64 * 1024
_current = None


def _log_path(root, name):
    """Bootstrap logging must work even when the SDK/storage import is broken."""
    root = Path(root).absolute(); path = root/'logs'/name
    for item in (path, *path.parents):
        if item.is_symlink(): raise ValueError('Aliased diagnostics path refused')
        if item.exists() and getattr(item.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise ValueError('Aliased diagnostics path refused')
    return path


@contextmanager
def _process_lock(root):
    path = _log_path(root, 'diagnostics.lock')
    with path.open('a+b') as stream:
        if path.stat().st_nlink != 1: raise ValueError('Hardlinked diagnostics lock refused')
        if not stream.tell(): stream.write(b'\0'); stream.flush()
        deadline = time.monotonic()+1
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline: raise
                time.sleep(.01)
        yield


def default_root():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'MoonLab/Loader'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'moonlab-loader'


def requested_root(argv):
    # Resolve only the application's own data option before argparse reports an
    # error. Never interpret the rest of the command or store a full argument list.
    for index, arg in enumerate(argv):
        if arg.startswith('--data='): return Path(arg.partition('=')[2])
        if arg == '--data' and index + 1 < len(argv): return Path(argv[index + 1])
    return default_root()


class Session:
    def __init__(self, root, max_bytes=MAX_BYTES, backups=BACKUPS):
        self.root = Path(root).expanduser().absolute()
        self.folder = self.root/'logs'
        self.session = uuid.uuid4().hex
        self.max_bytes = max_bytes
        self.backups = backups
        self.lock = threading.RLock()
        self.error = ''
        self.fault_output = None

    def event(self, event, message='', level='INFO', **fields):
        try:
            row = {'time': datetime.now(timezone.utc).isoformat(), 'session': self.session,
                   'level': level, 'event': event, 'message': str(message)[:TAIL_BYTES]}
            # Details are supplied explicitly by our call sites. Full process
            # environments/CLI arguments are intentionally never captured.
            row.update(fields)
            line = (json.dumps(row, ensure_ascii=True, default=str)+'\n').encode()
            if len(line) > self.max_bytes // 2:
                row = {**row, 'message': str(message)[:max(64, self.max_bytes//8)],
                       'details_truncated': True}
                for key in fields: row.pop(key, None)
                line = (json.dumps(row, ensure_ascii=True)+'\n').encode()
            with self.lock:
                path = _log_path(self.root, 'loader.jsonl')
                self.folder.mkdir(parents=True, exist_ok=True)
                with _process_lock(self.root):
                    if path.exists() and path.stat().st_nlink != 1: raise ValueError('Hardlinked diagnostics file refused')
                    if path.exists() and path.stat().st_size + len(line) > self.max_bytes:
                        for index in range(self.backups, 0, -1):
                            target = _log_path(self.root, 'loader.jsonl.'+str(index))
                            source = _log_path(self.root, 'loader.jsonl'+('.'+str(index-1) if index > 1 else ''))
                            if index == self.backups: target.unlink(missing_ok=True)
                            if source.exists(): os.replace(source, target)
                    with path.open('ab') as output:
                        output.write(line); output.flush(); os.fsync(output.fileno())
            self.error = ''
            return True
        except Exception as error:
            self.error = str(error)
            return False

    def fatal_output(self):
        """Keep a file descriptor open for Python/Qt native crash tracebacks."""
        try:
            with self.lock:
                path = _log_path(self.root, 'crash.log')
                self.folder.mkdir(parents=True, exist_ok=True)
                if path.exists() and path.stat().st_nlink != 1: raise ValueError('Hardlinked crash log refused')
                if path.exists() and path.stat().st_size:
                    previous = _log_path(self.root, 'crash.previous.log')
                    os.replace(path, previous)
                self.fault_output = path.open('ab')
                faulthandler.enable(file=self.fault_output, all_threads=True)
            return True
        except Exception as error:
            self.error = str(error)
            return False

    def exception(self, event, error, **fields):
        return self.event(event, str(error), 'ERROR',
                          traceback=''.join(traceback.format_exception(type(error), error, error.__traceback__))[-TAIL_BYTES:], **fields)


def start(root):
    global _current
    root = Path(root).expanduser().absolute()
    if _current is None or _current.root != root:
        _current = Session(root)
        _current.event('session-start', 'Loader diagnostics started')
    return _current


def current():
    return _current


def event(name, message='', level='INFO', **fields):
    return bool(_current and _current.event(name, message, level, **fields))


def exception(name, error, **fields):
    return bool(_current and _current.exception(name, error, **fields))


def install_exception_hooks():
    """Keep normal stderr reporting; add local evidence before fatal exit."""
    previous = sys.excepthook
    def unhandled(kind, error, stack):
        if not issubclass(kind, KeyboardInterrupt): exception('unhandled-exception', error)
        previous(kind, error, stack)
    sys.excepthook = unhandled
    old_thread = threading.excepthook
    def thread_unhandled(args):
        exception('unhandled-thread-exception', args.exc_value, thread=args.thread.name)
        old_thread(args)
    threading.excepthook = thread_unhandled
    if _current: _current.fatal_output()
    return previous, old_thread


def install_qt_handler():
    from PySide6.QtCore import qInstallMessageHandler, QtMsgType
    old = None
    def message(kind, context, text):
        level = 'ERROR' if kind in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg) else 'WARNING' if kind == QtMsgType.QtWarningMsg else 'INFO'
        event('qt-message', text, level)
        if old: old(kind, context, text)
        else:
            try: sys.stderr.write(text+'\n')
            except Exception: pass
    old = qInstallMessageHandler(message)
    return old


def prepare_run(root, record):
    """Mark the private managed log so an unchanged previous run is not copied."""
    if record.get('mode') == 'installed': return
    try:
        from .storage import contained
        root = Path(root).absolute(); game = Path(record['cwd']).absolute()
        game = contained(root, game.relative_to(root).as_posix())
        path = contained(game, 'BepInEx/LogOutput.log')
        info = path.stat() if path.is_file() else None
        prefix = b''
        if info:
            with path.open('rb') as stream: prefix = stream.read(min(info.st_size, TAIL_BYTES))
        record['diagnostic_managed_log'] = {'path': str(path),
            'before': [info.st_ino, info.st_size, info.st_mtime_ns] if info else None,
            'prefix_bytes': len(prefix), 'prefix_sha256': hashlib.sha256(prefix).hexdigest()}
    except Exception:
        # A malformed/synthetic plan cannot expand the collection boundary.
        return


def prepare_installed(service, installation, record):
    """Remember the exact deployed generation before the short Steam request."""
    try:
        from . import public
        from .storage import contained, write
        data = service.install_root(installation)
        deployed = public.receipt(data, installation)
        watch = {'mode': 'installed', 'cwd': installation.path, 'run': record['run'],
                 'installed_log_watch': {'installation': installation.record(),
                     'generation': deployed['generation'], 'data': str(data), 'since_ns': time.time_ns()}}
        record['installed_log_watch'] = watch['installed_log_watch']
        write(contained(data, 'diagnostics-watch.json'), watch)
    except Exception as error:
        start(service.root).exception('installed-diagnostics-setup-failed', error)


def collect_installed(root, record):
    """Copy only fresh bootstrap logs attributed to the prepared installed generation."""
    session = start(root)
    result = {'schema': 'moon-loader-installed-diagnostics/v1',
              'game_process_lifetime': 'unverified', 'game_crash': 'not established', 'logs': []}
    try:
        from . import public
        from .discovery import Installation
        from .storage import contained, load, write
        meta = record['installed_log_watch']; installation = Installation(**meta['installation'])
        data = Path(meta['data']).absolute()
        data = contained(session.root, data.relative_to(session.root).as_posix())
        run = Path(record['run']).absolute()
        if run.parent != data/'runs': raise ValueError('Installed diagnostic watch has an unrelated run')
        contained(data, run.relative_to(data).as_posix())
        game = Path(installation.path).absolute()
        if record['cwd'] != installation.path: raise ValueError('Installed diagnostic watch changed its game')
        owner = load(contained(game, 'MoonLab/owner.json'), {})
        if owner != {'schema': public.SCHEMA, 'data': str(data)}: raise ValueError('Installed log ownership changed')
        deployed = public.receipt(data, installation)
        generation = meta['generation']
        if not re.fullmatch('[a-f0-9]{32}', generation) or deployed['generation'] != generation:
            raise ValueError('Installed diagnostic generation changed')
        since = meta['since_ns']
        if not isinstance(since, int) or since < 1: raise ValueError('Invalid installed diagnostic start time')
        folder = contained(game, 'MoonLab/logs')
        if folder.is_dir():
            from itertools import islice
            candidates = []
            for item in islice(folder.iterdir(), 4096):
                if not re.fullmatch(r'run-[a-f0-9]{16}-[a-f0-9]{8}', item.name): continue
                path = contained(game, 'MoonLab/logs/'+item.name+'/loader.jsonl')
                if path.is_file() and path.stat().st_mtime_ns >= since: candidates.append(path)
            for path in sorted(candidates, key=lambda p: p.stat().st_mtime_ns, reverse=True)[:16]:
                with path.open('rb') as stream:
                    head = stream.read(16384)
                    stream.seek(0, 2); size = stream.tell(); stream.seek(max(0, size-TAIL_BYTES))
                    tail = stream.read(TAIL_BYTES).decode('utf-8', errors='replace')
                attributed = False
                for line in head.splitlines():
                    try: event = json.loads(line)
                    except (ValueError, UnicodeError): continue
                    if isinstance(event, dict) and event.get('case') == 'deployment' and event.get('success') is True and event.get('installation') == installation.identity and event.get('generation') == generation:
                        attributed = True; break
                if attributed:
                    result['logs'].append({'run': path.parent.name, 'path': str(path), 'bytes': size,
                                           'tail': tail, 'truncated': size > TAIL_BYTES})
        result.update(installation=installation.identity, generation=generation,
                      status='bootstrap-observed' if result['logs'] else 'no-attributed-bootstrap-log-yet')
        write(_log_path(session.root, 'installed-bootstrap.json'), result)
        session.event('installed-bootstrap-collected', result['status'], logs=len(result['logs']))
    except Exception as error:
        result.update(status='collection-unavailable', message=str(error))
        try:
            from .storage import write
            write(_log_path(session.root, 'installed-bootstrap.json'), result)
        except Exception: pass
        session.exception('installed-log-collection-failed', error)
    return result


def collect_selected_installed(service, installation):
    """Explicit Open logs refresh, including evidence produced after request exit."""
    try:
        from .storage import contained, load
        if service.mode(installation) != 'installed': return
        record = load(contained(service.install_root(installation), 'diagnostics-watch.json'))
        if record: return collect_installed(service.root, record)
    except Exception as error:
        start(service.root).exception('installed-log-collection-failed', error)


def finish_run(root, record, code, detail=''):
    """Summarize only a loader-owned current run, without guessing Steam lifetime."""
    session = start(root)
    installed = record.get('mode') == 'installed'
    status = ('steam-request-failed' if code else 'startup-unconfirmed') if installed else ('failed' if code or detail else 'closed')
    summary = {'schema': 'moon-loader-run-diagnostics/v1', 'status': status,
               'exit_code': code, 'mode': record.get('mode', 'private'),
               'game_startup_confirmed': False if installed else None,
               'message': detail, 'tails': {}}
    try:
        from .storage import contained, write
        run = Path(record['run']).absolute()
        relative = run.relative_to(session.root).as_posix()
        if 'runs' not in Path(relative).parts[:-1]: raise ValueError('Not a loader launch run')
        run = contained(session.root, relative)
        if not run.is_dir(): raise ValueError('Current run directory is missing')
        for name in ('process.log', 'Player.log', 'loader.jsonl', 'bepinex.jsonl'):
            path = contained(run, name)
            if not path.is_file(): continue
            with path.open('rb') as stream:
                stream.seek(0, 2); size = stream.tell(); stream.seek(max(0, size-TAIL_BYTES))
                tail = stream.read(TAIL_BYTES).decode('utf-8', errors='replace')
            summary['tails'][name] = {'bytes': size, 'tail': tail, 'truncated': size > TAIL_BYTES}
        managed = record.get('diagnostic_managed_log') if not installed else None
        if managed:
            path = Path(managed['path']).absolute()
            game = Path(record['cwd']).absolute()
            game = contained(session.root, game.relative_to(session.root).as_posix())
            if path != contained(game, 'BepInEx/LogOutput.log'): raise ValueError('Unexpected managed log path')
            if path.is_file():
                info = path.stat(); before = managed['before']
                changed = [info.st_ino, info.st_size, info.st_mtime_ns] != before
                if changed:
                    offset = before[1] if before and info.st_ino == before[0] and info.st_size > before[1] else 0
                    with path.open('rb') as stream:
                        prefix = stream.read(managed['prefix_bytes'])
                        if hashlib.sha256(prefix).hexdigest() != managed['prefix_sha256']: offset = 0
                        stream.seek(max(offset, info.st_size-TAIL_BYTES)); tail = stream.read(TAIL_BYTES).decode('utf-8', errors='replace')
                    summary['tails']['BepInEx/LogOutput.log'] = {'bytes': info.st_size-offset, 'tail': tail, 'truncated': info.st_size-offset > TAIL_BYTES}
        if not installed:
            player = summary['tails'].get('Player.log', {}).get('tail', '')
            if any(marker in player for marker in ('Crash!!!', 'Native Crash Reporting', 'Received signal ', 'FATAL ERROR:')):
                summary['status'] = status = 'crashed'
            elif code < 0 or code >= 0x80000000:
                summary['status'] = status = 'crashed'
        write(contained(run, 'diagnostics.json'), summary)
        if installed and record.get('installed_log_watch'):
            summary['installed_bootstrap'] = collect_installed(root, record)
            write(contained(run, 'diagnostics.json'), summary)
        session.event('launch-finished', detail or status, 'ERROR' if code or detail or status in ('crashed', 'failed', 'steam-request-failed') else 'INFO',
                      run=str(run), status=status, exit_code=code)
    except Exception as error:
        session.exception('run-diagnostics-failed', error)
    return summary
