"""Local diagnostics retain actionable failures without hiding the original error."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import shutil
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'loader'))
from moonloader import diagnostics, launch
from moonloader.storage import locked


class DiagnosticsChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def rows(self, root=None):
        return [json.loads(line) for line in ((root or self.root)/'logs/loader.jsonl').read_text().splitlines()]

    def test_info_and_error_keep_levels_session_and_traceback(self):
        logger = diagnostics.Session(self.root)
        self.assertTrue(logger.event('prepared', 'Files ready'))
        try: raise ValueError('broken package')
        except ValueError as error: self.assertTrue(logger.exception('prepare-error', error))
        rows = self.rows(); self.assertEqual([r['level'] for r in rows], ['INFO', 'ERROR'])
        self.assertEqual(rows[0]['session'], rows[1]['session'])
        self.assertIn('ValueError: broken package', rows[1]['traceback'])
        self.assertIn('test_info_and_error', rows[1]['traceback'])

    def test_rotation_and_large_messages_remain_bounded(self):
        logger = diagnostics.Session(self.root, max_bytes=1500, backups=2)
        for index in range(80): logger.event('progress', 'x'*300, index=index)
        logger.event('oversize', 'y'*100000, huge_detail='z'*100000)
        files = list((self.root/'logs').glob('loader.jsonl*'))
        self.assertEqual(len(files), 3)
        self.assertTrue(all(path.stat().st_size <= 1500 for path in files))
        self.assertTrue(self.rows()[-1]['details_truncated'])
        self.assertNotIn('huge_detail', self.rows()[-1])

    def test_simultaneous_sessions_serialize_rotation_without_losing_rows(self):
        code = ('import sys;sys.path.insert(0,sys.argv[1]);from moonloader.diagnostics import Session;'
                's=Session(sys.argv[2],max_bytes=4096,backups=8);'
                'exec("for i in range(60):\\n assert s.event(\'parallel\',sys.argv[3],index=i)")')
        processes = [subprocess.Popen([sys.executable,'-c',code,str(ROOT/'loader'),str(self.root),name]) for name in ('one','two')]
        self.assertEqual([p.wait(timeout=20) for p in processes], [0,0])
        files = list((self.root/'logs').glob('loader.jsonl*'))
        self.assertTrue(all(p.stat().st_size <= 4096 for p in files))
        rows = [json.loads(line) for p in files for line in p.read_text().splitlines()]
        self.assertEqual({(row['message'], row['index']) for row in rows}, {(name,i) for name in ('one','two') for i in range(60)})

    def test_logging_failure_and_alias_do_not_replace_original_error(self):
        self.root.joinpath('logs').write_text('blocked directory')
        logger = diagnostics.Session(self.root)
        error = ValueError('original error')
        self.assertFalse(logger.exception('failure', error)); self.assertTrue(logger.error)
        self.assertEqual(str(error), 'original error')
        self.root.joinpath('logs').unlink(); self.root.joinpath('logs').mkdir()
        outside = self.root/'outside'; outside.write_text('preserve')
        self.root.joinpath('logs/loader.jsonl').symlink_to(outside)
        self.assertFalse(logger.event('notice', 'must not append'))
        self.assertEqual(outside.read_text(), 'preserve')

    def test_unhandled_python_and_thread_exceptions_keep_stderr_reporting(self):
        diagnostics.start(self.root)
        import threading
        previous, old_thread = sys.excepthook, threading.excepthook
        with patch.object(diagnostics.Session, 'fatal_output'), patch.object(sys, 'excepthook') as stderr, patch.object(threading, 'excepthook') as thread_stderr:
            diagnostics.install_exception_hooks()
            error = RuntimeError('unhandled fixture')
            sys.excepthook(RuntimeError, error, None)
            args = SimpleNamespace(exc_value=error, thread=SimpleNamespace(name='fixture-worker'))
            threading.excepthook(args)
            stderr.assert_called_once(); thread_stderr.assert_called_once()
        sys.excepthook, threading.excepthook = previous, old_thread
        rows = self.rows()
        self.assertEqual([r['event'] for r in rows[-2:]], ['unhandled-exception', 'unhandled-thread-exception'])

    def test_bad_cli_arguments_are_logged_in_explicit_data_directory(self):
        data = self.root/'cli-data'
        result = subprocess.run([sys.executable, str(ROOT/'loader/main.py'), '--data', str(data), '--unknown-fixture-option'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('unrecognized arguments', result.stderr)
        self.assertTrue(any(r['event']=='cli-error' and '--unknown-fixture-option' in r['message'] for r in self.rows(data)))

    def test_cli_operation_failure_retains_full_traceback(self):
        data = self.root/'cli-data'
        result = subprocess.run([sys.executable, str(ROOT/'loader/main.py'), '--data', str(data), '--bundle', str(self.root/'empty-bundle'), '--game', str(self.root/'missing'), '--prepare'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        row = next(r for r in self.rows(data) if r['event']=='application-error')
        self.assertIn('ValueError', row['traceback']); self.assertIn('MoonSweepers.exe', row['message'])

    def test_core_import_failure_is_logged_before_application_imports(self):
        app = self.root/'broken-app'; package = app/'moonloader'; package.mkdir(parents=True)
        for name in ('__init__.py','diagnostics.py'):
            shutil.copyfile(ROOT/'loader/moonloader'/name, package/name)
        shutil.copyfile(ROOT/'loader/main.py',app/'main.py')
        (package/'service.py').write_text('raise ImportError("Synthetic damaged application import")\n')
        data = self.root/'broken-data'
        result = subprocess.run([sys.executable,str(app/'main.py'),'--data',str(data)],capture_output=True,text=True,timeout=15)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Synthetic damaged application import',result.stderr)
        row = next(r for r in self.rows(data) if r['event']=='unhandled-exception')
        self.assertIn('ImportError',row['traceback'])

    def test_fatal_python_crash_keeps_traceback_in_private_log(self):
        data = self.root/'fatal-data'
        code = ('import os,sys;sys.path.insert(0,sys.argv[1]);'
                'from moonloader import diagnostics;'
                'diagnostics.start(sys.argv[2]);diagnostics.install_exception_hooks();'
                'exec("if os.name != \'nt\':\\n import resource;resource.setrlimit(resource.RLIMIT_CORE,(0,0))");'
                'os.abort()')
        result = subprocess.run([sys.executable, '-c', code, str(ROOT/'loader'), str(data)], capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Fatal Python error', (data/'logs/crash.log').read_text())

    def test_spawn_failure_keeps_launch_log_and_releases_lease(self):
        service = SimpleNamespace(root=self.root, prepare=Mock())
        record = {'mode':'installed','order':[],'platform':'linux','command':['missing-program'],
                  'run':str(self.root/'runs/fixture'),'cwd':str(self.root)}
        with patch.object(launch, 'plan', return_value=record), patch.object(launch, 'assert_inactive'), patch('subprocess.Popen', side_effect=OSError('spawn failed')):
            with self.assertRaisesRegex(OSError, 'spawn failed'): launch.start(service, None)
        self.assertTrue((self.root/'runs/fixture/launch.json').is_file())
        self.assertTrue(any(r['event']=='launch-error' and 'spawn failed' in r['traceback'] for r in self.rows()))
        with locked(self.root, 'session.lock'): pass

    def test_private_crash_collects_only_current_run_bounded_tails(self):
        run = self.root/'installs/id/runs/fixture'; run.mkdir(parents=True)
        (run/'Player.log').write_text('x'*100000+'\nCrash!!!\n')
        (run/'loader.jsonl').write_text('{"case":"mod-start-failed","success":false}\n')
        outside = self.root/'unrelated-profile'; outside.mkdir(); (outside/'secret-save').write_text('do not read')
        summary = diagnostics.finish_run(self.root, {'run':str(run),'mode':'private'}, 0)
        self.assertEqual(summary['status'], 'crashed')
        self.assertEqual(next(row for row in self.rows() if row['event']=='launch-finished')['level'], 'ERROR')
        self.assertEqual(set(summary['tails']), {'Player.log','loader.jsonl'})
        self.assertTrue(summary['tails']['Player.log']['truncated'])
        self.assertLessEqual(len(summary['tails']['Player.log']['tail']), diagnostics.TAIL_BYTES)
        self.assertTrue((run/'diagnostics.json').is_file())

    def test_steam_request_exit_is_never_a_game_crash_or_startup_confirmation(self):
        run = self.root/'runs/fixture'; run.mkdir(parents=True)
        for code, status in ((0, 'startup-unconfirmed'), (1, 'steam-request-failed'), (-11, 'steam-request-failed')):
            result = diagnostics.finish_run(self.root, {'run':str(run),'mode':'installed'}, code)
            self.assertEqual(result['status'], status)
            self.assertIs(result['game_startup_confirmed'], False)

    def test_managed_log_preserves_only_updated_private_output(self):
        game = self.root/'installs/id/game'; (game/'BepInEx').mkdir(parents=True)
        path = game/'BepInEx/LogOutput.log'; path.write_text('previous run\n')
        run = self.root/'installs/id/runs/fixture'; run.mkdir(parents=True)
        record = {'run':str(run),'cwd':str(game),'mode':'private'}
        diagnostics.prepare_run(self.root, record)
        self.assertNotIn('BepInEx/LogOutput.log', diagnostics.finish_run(self.root, record, 1)['tails'])
        with path.open('a') as stream: stream.write('current failure\n')
        tail = diagnostics.finish_run(self.root, record, 1)['tails']['BepInEx/LogOutput.log']['tail']
        self.assertEqual(tail, 'current failure\n')
        path.write_text('new startup and a longer replacement failure\n')
        tail = diagnostics.finish_run(self.root, record, 1)['tails']['BepInEx/LogOutput.log']['tail']
        self.assertEqual(tail, path.read_text())

    def test_outside_run_cannot_be_written(self):
        outside = self.root/'outside'; outside.mkdir()
        result = diagnostics.finish_run(self.root/'data', {'run':str(outside)}, 1)
        self.assertFalse((outside/'diagnostics.json').exists())
        self.assertEqual(result['tails'], {})

    def installed_fixture(self, managed=False, previous_log=None):
        from moonloader import public
        from moonloader.discovery import Installation
        from moonloader.storage import write
        data = self.root/'data'; install = data/'installs/test-installed'; game = self.root/'game'
        (game/'MoonLab/logs').mkdir(parents=True); install.mkdir(parents=True)
        installation = Installation(str(game), 'steam', str(self.root/'steam'), True)
        deployed = {**public.empty(installation), 'generation':'a'*32, 'enabled':True}
        if managed: deployed['managed'] = True
        if previous_log is not None:
            log = game/'BepInEx/LogOutput.log';log.parent.mkdir(parents=True);log.write_text(previous_log)
        write(install/'deployment.json',deployed)
        write(game/'MoonLab/owner.json',{'schema':public.SCHEMA,'data':str(install)})
        service = SimpleNamespace(root=data,install_root=lambda _:install,mode=lambda _:'installed')
        record = {'mode':'installed','cwd':str(game),'run':str(install/'runs/fixture')}
        diagnostics.prepare_installed(service,installation,record)
        return service,installation,record,deployed

    def bootstrap(self, installation, name, generation='a'*32, identity=None):
        path = Path(installation.path)/'MoonLab/logs'/name/'loader.jsonl';path.parent.mkdir()
        rows = [{'case':'loader-ready','success':True},
                {'case':'deployment','success':True,'installation':identity or installation.identity,'generation':generation},
                {'case':'mod-start-failed','success':False,'mod':'fixture'}]
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return path

    def test_installed_bootstrap_collects_only_fresh_attributed_generation(self):
        service,installation,record,_ = self.installed_fixture()
        fresh = self.bootstrap(installation,'run-0000000000000001-00000001')
        stale = self.bootstrap(installation,'run-0000000000000002-00000001');os.utime(stale,ns=(1,1))
        self.bootstrap(installation,'run-0000000000000003-00000001',generation='b'*32)
        self.bootstrap(installation,'run-0000000000000004-00000001',identity='other-installation')
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual([row['path'] for row in result['logs']],[str(fresh)])
        self.assertEqual(result['status'],'bootstrap-observed')
        self.assertEqual(result['game_process_lifetime'],'unverified')
        self.assertEqual(result['game_crash'],'not established')
        self.assertIn('mod-start-failed',result['logs'][0]['tail'])

    def test_open_logs_can_refresh_late_bootstrap_after_request_exit(self):
        service,installation,record,_ = self.installed_fixture()
        self.assertEqual(diagnostics.collect_installed(service.root,record)['status'],'no-attributed-bootstrap-log-yet')
        fresh = self.bootstrap(installation,'run-0000000000000001-00000001')
        result = diagnostics.collect_selected_installed(service,installation)
        self.assertEqual([row['path'] for row in result['logs']],[str(fresh)])
        self.assertTrue((service.root/'logs/installed-bootstrap.json').is_file())

    def test_changed_installed_owner_or_generation_cannot_attribute_logs(self):
        from moonloader.storage import write
        service,installation,record,deployed = self.installed_fixture()
        self.bootstrap(installation,'run-0000000000000001-00000001')
        write(service.install_root(installation)/'deployment.json',{**deployed,'generation':'b'*32})
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['status'],'collection-unavailable');self.assertEqual(result['logs'],[])
        write(service.install_root(installation)/'deployment.json',deployed)
        write(Path(installation.path)/'MoonLab/owner.json',{'schema':'foreign-owner','data':'elsewhere'})
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['status'],'collection-unavailable');self.assertEqual(result['logs'],[])

    def test_private_preloader_failure_is_error_even_when_runner_exits_zero(self):
        game = self.root/'installs/id/game'; game.mkdir(parents=True)
        run = self.root/'installs/id/runs/fixture'; run.mkdir(parents=True)
        old = game/'preloader_20261111_120000_001.log'; old.write_text('old failure')
        record = {'run':str(run),'cwd':str(game),'mode':'private'}
        diagnostics.prepare_run(self.root,record)
        old.write_text('rewritten prior filename must not be attributed to this launch')
        stale = game/'preloader_20261111_120001_001.log'; stale.write_text('stale new name');os.utime(stale,ns=(1,1))
        (game/'preloader_20261311_120001_001.log').write_text('invalid month')
        (game/'preloader_20261111_120001_2.log').write_text('malformed suffix')
        (game/'preloader_20261111_120001_003.log').symlink_to(old)
        (game/'preloader_20261111_120001_004.log').hardlink_to(old)
        fresh = game/'preloader_20261111_120002_001.log'
        fresh.write_text('x'*100000+"\nSystem.IO.FileNotFoundException: Microsoft.Extensions.Logging.Abstractions\n at Doorstop.Entrypoint.Start()\n")
        result = diagnostics.finish_run(self.root,record,0)
        self.assertEqual(result['status'],'preloader-failed')
        self.assertEqual([row['name'] for row in result['preloader_logs']],[fresh.name])
        self.assertLessEqual(len(result['preloader_logs'][0]['tail']),diagnostics.TAIL_BYTES)
        self.assertTrue(result['preloader_logs'][0]['truncated'])
        self.assertIn('Microsoft.Extensions.Logging.Abstractions',result['preloader_logs'][0]['tail'])
        self.assertEqual(next(r for r in self.rows() if r['event']=='launch-finished')['level'],'ERROR')

    def test_preloader_file_count_and_incomplete_baseline_are_bounded(self):
        game = self.root/'installs/id/game'; game.mkdir(parents=True)
        run = self.root/'installs/id/runs/fixture'; run.mkdir(parents=True)
        record = {'run':str(run),'cwd':str(game),'mode':'private'}
        diagnostics.prepare_run(self.root,record)
        for index in range(20):
            (game/f'preloader_20261111_120001_{index:03d}.log').write_text('fresh preloader failure')
        result = diagnostics.finish_run(self.root,record,0)
        self.assertEqual(len(result['preloader_logs']),16)
        record['diagnostic_preloader_logs']['complete'] = False
        result = diagnostics.finish_run(self.root,record,0)
        self.assertNotIn('preloader_logs',result)

    def test_installed_preloader_capture_requires_current_owner_and_watch(self):
        from moonloader.storage import write
        service,installation,record,_ = self.installed_fixture()
        path = Path(installation.path)/'preloader_20261111_120001_001.log'
        path.write_text('System.IO.FileNotFoundException: Microsoft.Extensions.Logging.Abstractions')
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['status'],'preloader-failed')
        self.assertEqual([row['name'] for row in result['preloader_logs']],[path.name])
        self.assertEqual(result['game_process_lifetime'],'unverified')
        self.assertEqual(result['game_crash'],'not established')
        write(Path(installation.path)/'MoonLab/owner.json',{'schema':'foreign-owner'})
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['status'],'collection-unavailable')
        self.assertNotIn('preloader_logs',result)

    def test_open_logs_collects_private_preloader_before_process_exit(self):
        from moonloader.storage import write
        data = self.root/'data'; install = data/'installs/private'; game = install/'game'; game.mkdir(parents=True)
        run = install/'runs/fixture'; run.mkdir(parents=True)
        record = {'mode':'private','cwd':str(game),'run':str(run)}
        diagnostics.prepare_run(data,record)
        write(run/'launch.json',record); write(data/'active.json',{'state':'running','run':str(run)})
        path = game/'preloader_20261111_120001_001.log'; path.write_text('Doorstop failed before adapter startup')
        service = SimpleNamespace(root=data,install_root=lambda _:install,mode=lambda _:'private')
        result = diagnostics.collect_selected_installed(service,None)
        self.assertEqual(result['status'],'preloader-failed')
        self.assertEqual([row['name'] for row in result['preloader_logs']],[path.name])
        self.assertEqual(result['process_exit'],'not observed by this collection')
        self.assertTrue((data/'logs/private-preloader.json').is_file())

    def test_installed_adapter_sidecars_require_fresh_attributed_managed_run(self):
        service,installation,record,_ = self.installed_fixture(managed=True)
        native = self.bootstrap(installation,'run-0000000000000001-00000001')
        (native.parent/'adapter-ready.json').write_text('{"success":true}')
        failure = native.parent/'adapter-failure.txt';failure.write_text('x'*100000+'\nFatal adapter validation failed')
        other = self.bootstrap(installation,'run-0000000000000002-00000001',generation='b'*32)
        (other.parent/'adapter-failed.json').write_text('{"success":false,"error":"foreign generation"}')
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['status'],'adapter-failed')
        self.assertEqual({row['name'] for row in result['adapter_logs']},{'adapter-ready.json','adapter-failure.txt'})
        captured = next(row for row in result['adapter_logs'] if row['name']=='adapter-failure.txt')
        self.assertLessEqual(len(captured['tail']),diagnostics.TAIL_BYTES);self.assertTrue(captured['truncated'])
        self.assertEqual(result['game_process_lifetime'],'unverified')
        self.assertEqual(next(row for row in self.rows(service.root) if row['event']=='installed-bootstrap-collected')['level'],'ERROR')
        Path(record['run']).mkdir(parents=True)
        summary = diagnostics.finish_run(service.root,record,0)
        self.assertEqual(summary['status'],'adapter-failed')
        self.assertEqual(summary['steam_request_status'],'startup-unconfirmed')
        self.assertIs(summary['game_startup_confirmed'],False)
        from moonloader.storage import write
        write(Path(installation.path)/'MoonLab/owner.json',{'schema':'foreign-owner'})
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['status'],'collection-unavailable');self.assertNotIn('adapter_logs',result)

    def test_stale_alias_and_native_only_adapter_files_are_not_attributed(self):
        service,installation,record,_ = self.installed_fixture(managed=True)
        native = self.bootstrap(installation,'run-0000000000000001-00000001')
        failure = native.parent/'adapter-failure.txt';failure.write_text('old failure');os.utime(failure,ns=(1,1))
        (native.parent/'adapter-failed.json').symlink_to(native)
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['status'],'bootstrap-observed');self.assertEqual(result['adapter_logs'],[])
        from moonloader.storage import load,write
        path = service.install_root(installation)/'deployment.json';deployed=load(path);deployed.pop('managed');write(path,deployed)
        (native.parent/'adapter-ready.json').write_text('{"success":true}')
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['adapter_logs'],[])

    def test_installed_managed_log_requires_changed_fresh_owned_deployment(self):
        from moonloader.storage import write
        service,installation,record,_ = self.installed_fixture(managed=True,previous_log='previous run\n')
        log = Path(installation.path)/'BepInEx/LogOutput.log'
        self.assertNotIn('managed_log',diagnostics.collect_installed(service.root,record))
        with log.open('a') as stream: stream.write('current adapter failure\n')
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['managed_log']['tail'],'current adapter failure\n')
        os.utime(log,ns=(1,1))
        self.assertNotIn('managed_log',diagnostics.collect_installed(service.root,record))
        write(Path(installation.path)/'MoonLab/owner.json',{'schema':'foreign-owner'})
        result = diagnostics.collect_installed(service.root,record)
        self.assertEqual(result['status'],'collection-unavailable');self.assertNotIn('managed_log',result)

    def test_private_adapter_failure_sidecar_is_error_even_with_exit_zero(self):
        run = self.root/'runs/fixture';run.mkdir(parents=True)
        (run/'adapter-failed.json').write_text('{"success":false,"error":"adapter startup failed"}')
        result = diagnostics.finish_run(self.root,{'run':str(run)},0)
        self.assertEqual(result['status'],'adapter-failed')
        self.assertEqual(next(row for row in self.rows() if row['event']=='launch-finished')['level'],'ERROR')


if __name__ == '__main__': unittest.main()
