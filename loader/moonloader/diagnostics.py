"""Local, bounded launcher diagnostics. Recording must never replace an error."""
from datetime import datetime, timezone
from contextlib import contextmanager
import faulthandler
import hashlib
from itertools import islice
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
CONTROL_BYTES = 2 * 1024 * 1024
SCAN_ENTRIES = 4096
COLLECT_LOGS = 16
_PRELOADER = re.compile(r'preloader_(\d{8}_\d{6})_\d{3}\.log')
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


def _preloader_name(name):
    match = _PRELOADER.fullmatch(name)
    if not match: return False
    try: datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')
    except ValueError: return False
    return True


def _directory_entries(folder, limit=SCAN_ENTRIES):
    # Path.iterdir() can enumerate eagerly before islice applies its limit.
    with os.scandir(folder) as entries:
        return [Path(entry.path) for entry in islice(entries, limit)]


@contextmanager
def _input_file(path):
    def independent(info):
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Diagnostics input is not an independent regular file')
    independent(path.stat())
    # Avoid blocking on a FIFO if a regular file changes between stat and open.
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        independent(os.fstat(stream.fileno()))
        yield stream


def _load_json(path, default=None):
    try:
        with _input_file(path) as stream:
            if os.fstat(stream.fileno()).st_size > CONTROL_BYTES:
                raise ValueError('Diagnostics control file exceeds its size limit')
            content = stream.read(CONTROL_BYTES+1)
    except FileNotFoundError:
        return default
    if len(content) > CONTROL_BYTES:
        raise ValueError('Diagnostics control file exceeds its size limit')
    return json.loads(content.decode('utf-8'))


def _receipt(data, installation):
    from . import public
    from .storage import contained
    # Retain the deployment owner's complete validator. Its storage reader has
    # no byte cap, so reject oversized inputs before invoking it.
    try:
        with _input_file(contained(data, 'deployment.json')) as stream:
            if os.fstat(stream.fileno()).st_size > CONTROL_BYTES:
                raise ValueError('Diagnostics deployment receipt exceeds its size limit')
    except FileNotFoundError:
        pass
    return public.receipt(data, installation)


def _preloader_snapshot(game):
    entries = _directory_entries(game, SCAN_ENTRIES+1)
    return {'names': [item.name for item in entries[:SCAN_ENTRIES] if _preloader_name(item.name)],
            'complete': len(entries) <= SCAN_ENTRIES, 'since_ns': time.time_ns()}


def _preloader_logs(game, baseline):
    """Doorstop writes these before either the normal host log or adapter exists."""
    from .storage import contained
    if not isinstance(baseline, dict) or baseline.get('complete') is not True: return []
    since = baseline.get('since_ns')
    if not isinstance(since, int) or since < 1: return []
    previous = set(baseline.get('names', [])); candidates = []
    for entry in _directory_entries(game):
        if not _preloader_name(entry.name) or entry.name in previous: continue
        try:
            path = contained(game, entry.name); info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mtime_ns < since or not info.st_size: continue
            candidates.append((info.st_mtime_ns, path))
        except (OSError, ValueError): continue
    result = []
    for _, path in sorted(candidates, reverse=True)[:COLLECT_LOGS]:
        try:
            path = contained(game, path.name)
            with _input_file(path) as stream:
                if os.fstat(stream.fileno()).st_mtime_ns < since: continue
                stream.seek(0, 2); size = stream.tell(); stream.seek(max(0, size-TAIL_BYTES))
                tail = stream.read(TAIL_BYTES).decode('utf-8', errors='replace')
            if tail:
                result.append({'name': path.name, 'path': str(path), 'bytes': size,
                               'tail': tail, 'truncated': size > TAIL_BYTES,
                               'failure': 'BepInEx preloader failed before adapter startup'})
        except (OSError, ValueError): continue
    return result


def _managed_snapshot(game):
    from .storage import contained
    path = contained(game, 'BepInEx/LogOutput.log')
    info = path.stat() if path.is_file() else None
    if info and info.st_nlink != 1: raise ValueError('Aliased managed log refused')
    prefix = b''
    if info:
        with _input_file(path) as stream:
            info = os.fstat(stream.fileno())
            prefix = stream.read(min(info.st_size, TAIL_BYTES))
    return {'path':str(path), 'before':[info.st_ino, info.st_size, info.st_mtime_ns] if info else None,
            'prefix_bytes':len(prefix), 'prefix_sha256':hashlib.sha256(prefix).hexdigest(), 'since_ns':time.time_ns()}


def _managed_log(game, baseline, since=0):
    from .storage import contained
    if not isinstance(baseline, dict): return None
    path = contained(game, 'BepInEx/LogOutput.log')
    if baseline.get('path') != str(path) or not path.is_file(): return None
    info = path.stat(); before = baseline['before']
    if info.st_nlink != 1 or info.st_mtime_ns < max(since, baseline.get('since_ns', 0)): return None
    if [info.st_ino, info.st_size, info.st_mtime_ns] == before: return None
    count = baseline['prefix_bytes']
    if not isinstance(count, int) or not 0 <= count <= TAIL_BYTES: raise ValueError('Invalid managed log baseline')
    offset = before[1] if before and info.st_ino == before[0] and info.st_size > before[1] else 0
    with _input_file(path) as stream:
        prefix = stream.read(count)
        if hashlib.sha256(prefix).hexdigest() != baseline['prefix_sha256']: offset = 0
        stream.seek(max(offset, info.st_size-TAIL_BYTES)); tail = stream.read(TAIL_BYTES).decode('utf-8', errors='replace')
    return {'bytes':info.st_size-offset, 'tail':tail, 'truncated':info.st_size-offset > TAIL_BYTES}


def prepare_run(root, record):
    """Mark the private managed log so an unchanged previous run is not copied."""
    if record.get('mode') == 'installed': return
    try:
        from .storage import contained
        root = Path(root).absolute(); game = Path(record['cwd']).absolute()
        game = contained(root, game.relative_to(root).as_posix())
        record['diagnostic_preloader_logs'] = _preloader_snapshot(game)
        record['diagnostic_managed_log'] = _managed_snapshot(game)
    except Exception:
        # A malformed/synthetic plan cannot expand the collection boundary.
        return


def prepare_installed(service, installation, record):
    """Remember the exact deployed generation before the short Steam request."""
    try:
        from .storage import contained, write
        data = service.install_root(installation)
        deployed = _receipt(data, installation)
        watch = {'mode': 'installed', 'cwd': installation.path, 'run': record['run'],
                 'installed_log_watch': {'installation': installation.record(),
                     'generation': deployed['generation'], 'data': str(data), 'since_ns': time.time_ns(),
                     'preloader_baseline': _preloader_snapshot(Path(installation.path))}}
        if deployed.get('managed') is True:
            watch['installed_log_watch']['managed_log'] = _managed_snapshot(Path(installation.path))
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
        from .storage import contained, write
        meta = record['installed_log_watch']; installation = Installation(**meta['installation'])
        data = Path(meta['data']).absolute()
        data = contained(session.root, data.relative_to(session.root).as_posix())
        run = Path(record['run']).absolute()
        if run.parent != data/'runs': raise ValueError('Installed diagnostic watch has an unrelated run')
        contained(data, run.relative_to(data).as_posix())
        game = Path(installation.path).absolute()
        if record['cwd'] != installation.path: raise ValueError('Installed diagnostic watch changed its game')
        owner = _load_json(contained(game, 'MoonLab/owner.json'), {})
        if owner != {'schema': public.SCHEMA, 'data': str(data)}: raise ValueError('Installed log ownership changed')
        deployed = _receipt(data, installation)
        generation = meta['generation']
        if not re.fullmatch('[a-f0-9]{32}', generation) or deployed['generation'] != generation:
            raise ValueError('Installed diagnostic generation changed')
        since = meta['since_ns']
        if not isinstance(since, int) or since < 1: raise ValueError('Invalid installed diagnostic start time')
        result['preloader_logs'] = _preloader_logs(game, meta.get('preloader_baseline'))
        result['adapter_logs'] = []
        if deployed.get('managed') is True:
            managed_log = _managed_log(game, meta.get('managed_log'), since)
            if managed_log: result['managed_log'] = managed_log
        folder = contained(game, 'MoonLab/logs')
        if folder.is_dir():
            candidates = []
            for item in _directory_entries(folder):
                if not re.fullmatch(r'run-[a-f0-9]{16}-[a-f0-9]{8}', item.name): continue
                try:
                    path = contained(game, 'MoonLab/logs/'+item.name+'/loader.jsonl'); info = path.stat()
                    if stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_mtime_ns >= since:
                        candidates.append((info.st_mtime_ns, path))
                except (OSError, ValueError): continue
            for _, path in sorted(candidates, reverse=True):
                if len(result['logs']) >= COLLECT_LOGS: break
                try:
                    path = contained(game, 'MoonLab/logs/'+path.parent.name+'/loader.jsonl')
                    with _input_file(path) as stream:
                        if os.fstat(stream.fileno()).st_mtime_ns < since: continue
                        head = stream.read(16384)
                        attributed = False
                        for line in head.splitlines():
                            try: event = json.loads(line)
                            except (ValueError, UnicodeError): continue
                            if isinstance(event, dict) and event.get('case') == 'deployment' and event.get('success') is True and event.get('installation') == installation.identity and event.get('generation') == generation:
                                attributed = True; break
                        if not attributed: continue
                        stream.seek(0, 2); size = stream.tell(); stream.seek(max(0, size-TAIL_BYTES))
                        tail = stream.read(TAIL_BYTES).decode('utf-8', errors='replace')
                except (OSError, ValueError): continue
                result['logs'].append({'run': path.parent.name, 'path': str(path), 'bytes': size,
                                       'tail': tail, 'truncated': size > TAIL_BYTES})
                if deployed.get('managed') is not True: continue
                for name in ('adapter-ready.json', 'adapter-failed.json', 'adapter-failure.txt'):
                    try:
                        sidecar = contained(game, 'MoonLab/logs/'+path.parent.name+'/'+name)
                        with _input_file(sidecar) as stream:
                            info = os.fstat(stream.fileno())
                            if info.st_mtime_ns < since or not info.st_size: continue
                            stream.seek(max(0, info.st_size-TAIL_BYTES)); tail = stream.read(TAIL_BYTES).decode('utf-8', errors='replace')
                        result['adapter_logs'].append({'run':path.parent.name, 'name':name, 'path':str(sidecar),
                            'bytes':info.st_size, 'tail':tail, 'truncated':info.st_size > TAIL_BYTES})
                    except (OSError, ValueError): continue
        adapter_failed = any(row['name'] != 'adapter-ready.json' for row in result['adapter_logs'])
        result.update(installation=installation.identity, generation=generation,
                      status='preloader-failed' if result['preloader_logs'] else 'adapter-failed' if adapter_failed else 'bootstrap-observed' if result['logs'] else 'no-attributed-bootstrap-log-yet')
        write(_log_path(session.root, 'installed-bootstrap.json'), result)
        session.event('installed-bootstrap-collected', result['status'], 'ERROR' if result['preloader_logs'] or adapter_failed else 'INFO', logs=len(result['logs']), preloader_logs=len(result['preloader_logs']), adapter_logs=len(result['adapter_logs']))
    except Exception as error:
        result.update(status='collection-unavailable', message=str(error))
        try:
            from .storage import write
            write(_log_path(session.root, 'installed-bootstrap.json'), result)
        except Exception: pass
        session.exception('installed-log-collection-failed', error)
    return result


def collect_selected_installed(service, installation):
    """Open logs refresh, including a preloader failure blocked on its dialog."""
    try:
        from .storage import contained, write
        if service.mode(installation) != 'installed':
            active = _load_json(contained(service.root, 'active.json'), {})
            if not active.get('run'): return
            data = service.install_root(installation); run = Path(active['run']).absolute()
            if run.parent != data/'runs': return
            run = contained(service.root, run.relative_to(service.root).as_posix())
            record = _load_json(contained(run, 'launch.json'), {})
            if record.get('run') != str(run) or record.get('cwd') != str(data/'game'): return
            game = contained(service.root, (data/'game').relative_to(service.root).as_posix())
            logs = _preloader_logs(game, record.get('diagnostic_preloader_logs'))
            result = {'schema':'moon-loader-private-preloader/v1', 'run':str(run),
                      'status':'preloader-failed' if logs else 'no-attributed-preloader-log-yet',
                      'process_exit':'not observed by this collection', 'preloader_logs':logs}
            write(_log_path(service.root, 'private-preloader.json'), result)
            if logs: start(service.root).event('private-preloader-failed', 'BepInEx preloader failed before adapter startup', 'ERROR', logs=len(logs), run=str(run))
            return result
        record = _load_json(contained(service.install_root(installation), 'diagnostics-watch.json'))
        if record: return collect_installed(service.root, record)
    except Exception as error:
        start(service.root).exception('installed-log-collection-failed', error)


def finish_run(root, record, code, detail=''):
    """Summarize only a loader-owned current run, without guessing Steam lifetime."""
    session = start(root)
    installed = record.get('mode') == 'installed'
    direct_game = not installed and record.get('platform') == 'win32'
    runner = not installed and not direct_game
    status = ('steam-request-failed' if code else 'startup-unconfirmed') if installed else ('failed' if code or detail else 'closed')
    if runner: status = 'runner-failed' if code or detail else 'lifetime-unconfirmed'
    summary = {'schema': 'moon-loader-run-diagnostics/v1', 'status': status,
               'exit_code': code, 'mode': record.get('mode', 'private'),
               'game_startup_confirmed': False if installed or runner else None,
               'process_role': 'steam-request' if installed else 'game' if direct_game else 'private-runner',
               'game_lifetime': 'unverified' if installed or runner else 'direct-process-exit',
               'message': detail, 'tails': {}}
    try:
        from .storage import contained, write
        run = Path(record['run']).absolute()
        relative = run.relative_to(session.root).as_posix()
        if 'runs' not in Path(relative).parts[:-1]: raise ValueError('Not a loader launch run')
        run = contained(session.root, relative)
        if not run.is_dir(): raise ValueError('Current run directory is missing')
        for name in ('process.log', 'Player.log', 'loader.jsonl', 'bepinex.jsonl', 'adapter-ready.json', 'adapter-failed.json', 'adapter-failure.txt'):
            try:
                path = contained(run, name)
                with _input_file(path) as stream:
                    stream.seek(0, 2); size = stream.tell(); stream.seek(max(0, size-TAIL_BYTES))
                    tail = stream.read(TAIL_BYTES).decode('utf-8', errors='replace')
                if not tail: continue
            except (OSError, ValueError): continue
            summary['tails'][name] = {'bytes': size, 'tail': tail, 'truncated': size > TAIL_BYTES}
        managed = record.get('diagnostic_managed_log') if not installed else None
        if managed:
            game = Path(record['cwd']).absolute()
            game = contained(session.root, game.relative_to(session.root).as_posix())
            tail = _managed_log(game, managed)
            if tail: summary['tails']['BepInEx/LogOutput.log'] = tail
        if not installed:
            player = summary['tails'].get('Player.log', {}).get('tail', '')
            if any(marker in player for marker in ('Crash!!!', 'Native Crash Reporting', 'Received signal ', 'FATAL ERROR:')):
                summary['status'] = status = 'crashed'
            elif direct_game and (code < 0 or code >= 0x80000000):
                summary['status'] = status = 'crashed'
            if any(name in summary['tails'] for name in ('adapter-failed.json', 'adapter-failure.txt')):
                summary['status'] = status = 'adapter-failed'
                summary['message'] = 'BepInEx adapter startup failed.'
            if record.get('diagnostic_preloader_logs'):
                game = Path(record['cwd']).absolute()
                game = contained(session.root, game.relative_to(session.root).as_posix())
                preloader = _preloader_logs(game, record['diagnostic_preloader_logs'])
                if preloader:
                    summary['preloader_logs'] = preloader
                    summary['status'] = status = 'preloader-failed'
                    summary['message'] = 'BepInEx preloader failed before adapter startup.'
        write(contained(run, 'diagnostics.json'), summary)
        if installed and record.get('installed_log_watch'):
            summary['installed_bootstrap'] = collect_installed(root, record)
            if summary['installed_bootstrap'].get('preloader_logs'):
                summary['steam_request_status'] = status
                summary['status'] = status = 'preloader-failed'
                summary['message'] = 'BepInEx preloader failed before adapter startup; game-process lifetime remains unverified.'
            elif summary['installed_bootstrap'].get('status') == 'adapter-failed':
                summary['steam_request_status'] = status
                summary['status'] = status = 'adapter-failed'
                summary['message'] = 'BepInEx adapter startup failed; game-process lifetime remains unverified.'
            write(contained(run, 'diagnostics.json'), summary)
        session.event('launch-finished', summary['message'] or status, 'ERROR' if code or detail or status in ('crashed', 'failed', 'steam-request-failed', 'preloader-failed', 'adapter-failed') else 'INFO',
                      run=str(run), status=status, exit_code=code)
    except Exception as error:
        session.exception('run-diagnostics-failed', error)
    return summary
