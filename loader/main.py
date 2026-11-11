"""Source and portable distribution entry point. CLI checks never launch a game."""
import argparse
import json
import os
from pathlib import Path
import sys
# Portable Linux starts isolated Python, which omits the script directory.
# Admit only this application's own modules rather than the caller's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from moonloader import __version__
from moonloader import diagnostics


def main():
    session = diagnostics.start(diagnostics.requested_root(sys.argv[1:]))
    diagnostics.install_exception_hooks()
    session.event('application-start', 'Moon Sweepers Mod Loader '+__version__)
    from moonloader.service import Service
    from moonloader import discovery, launch, steam_options
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            session.event('cli-error', message, 'ERROR')
            super().error(message)
    parser = Parser(description='Moon Sweepers Mod Loader '+__version__)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--discover', action='store_true')
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--compatibility', action='store_true', help='Report mod requirements for this game without importing, selecting, preparing or launching mods')
    parser.add_argument('--steam-setup', action='store_true', help='Preview Steam launch options without changing them')
    parser.add_argument('--apply-steam-setup', action='store_true', help='Explicitly apply the previewed Proton override; quit Steam first')
    parser.add_argument('--prepare', action='store_true', help='Apply files for the selected mode; never starts a game')
    parser.add_argument('--mode', choices=('installed', 'private'), help='Existing Steam game or separate private copy; legacy data keeps private mode')
    parser.add_argument('--disable', action='store_true', help='Disable installed mods on next launch')
    parser.add_argument('--enable', action='store_true', help='Enable the prepared installed selection on next launch')
    parser.add_argument('--uninstall-loader', action='store_true', help='Remove owned installed payloads, preserving saves/settings')
    parser.add_argument('--backup-steam-saves', type=Path, help='Back up this explicitly chosen Steam save folder and its sidecars')
    parser.add_argument('--normal-saves', choices=('backed-up', 'fresh'), help='Confirm existing Steam saves are backed up, or this is a fresh Steam profile')
    parser.add_argument('--game', type=Path)
    parser.add_argument('--install', type=Path, help='Add a local .msmod, supported ZIP download or mod folder')
    parser.add_argument('--no-launch', action='store_true', help='Disable game launching while inspecting the UI')
    parser.add_argument('--smoke-test', action='store_true', help='Check the desktop GUI with temporary data, then exit without starting a game')
    args = parser.parse_args()
    if args.compatibility and any((args.install, args.prepare, args.mode, args.disable, args.enable,
                                  args.uninstall_loader, args.backup_steam_saves, args.normal_saves,
                                  args.apply_steam_setup, args.plan, args.discover, args.steam_setup)):
        raise ValueError('Compatibility reporting is read-only; use it separately from other operations')
    if args.smoke_test:
        from check_portable_windows import main as smoke_test
        return smoke_test()
    default = diagnostics.default_root()
    service = Service(args.data or default, args.bundle)
    if not args.compatibility: service.seed()
    if args.install:
        result = service.import_downloads([args.install])
        if result['errors']:
            raise ValueError('; '.join(item['path'] + ': ' + item['error'] for item in result['errors']))
    requested = discovery.manual(args.game) if args.game and args.compatibility else None
    if args.game and not args.compatibility: service.add_installation(args.game)
    installations, errors = service.installations()
    if args.discover:
        print(json.dumps({'installations':[x.record() for x in installations], 'errors':errors}, indent=2)); return 0
    if args.compatibility or args.steam_setup or args.apply_steam_setup or args.plan or args.prepare or args.mode or args.disable or args.enable or args.uninstall_loader or args.backup_steam_saves or args.normal_saves:
        selected = requested or next((x for x in installations if x.path == service.state['installation']), installations[0] if len(installations) == 1 else None)
        if not selected: raise ValueError('Choose an installation with --game PATH')
        if args.compatibility:
            print(json.dumps(service.compatibility(selected), indent=2)); return 0
        if args.steam_setup or args.apply_steam_setup:
            library, _ = service.library()
            preview = steam_options.inspect(selected, managed=any(library[name][0]['kind'] == 'bepinex-il2cpp' for name in service.state['selected'] if name in library))
            print(json.dumps(preview, indent=2))
            if args.apply_steam_setup:
                if preview['status'] not in ('required', 'ready'): raise ValueError(preview['message'])
                print(json.dumps(steam_options.apply(selected, service.root, preview), indent=2))
            return 0
        if args.mode: service.set_mode(selected, args.mode)
        if args.backup_steam_saves: print('Steam save backup: ' + str(service.backup_saves(selected, args.backup_steam_saves)))
        if args.normal_saves: service.accept_normal_saves(selected, args.normal_saves)
        if sum((args.disable, args.enable, args.uninstall_loader)) > 1: raise ValueError('Choose one enable, disable or uninstall action')
        if args.disable or args.enable:
            service.set_enabled(selected, args.enable); print('Next-launch state updated'); return 0
        if args.uninstall_loader:
            service.uninstall(selected); print('Owned installed files removed; saves/settings preserved'); return 0
        if not args.plan and not args.prepare: return 0
        print(json.dumps({'prepared':str(service.prepare(selected))} if args.prepare else launch.plan(service, selected, check_client=False), indent=2)); return 0
    from moonloader.linux_desktop import prepare as prepare_linux_desktop
    prepare_linux_desktop()
    try: from PySide6.QtWidgets import QApplication
    except ImportError: raise ValueError('PySide6 is required for the desktop UI. See README.md; no dependency was downloaded.')
    diagnostics.install_qt_handler()
    from moonloader.ui import Window
    app=QApplication(sys.argv[:1]); app.setApplicationName('Moon Sweepers Mod Loader'); app.setOrganizationName('MoonLab')
    window=Window(service,args.no_launch); window.show(); return app.exec()


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError) as error:
        diagnostics.exception('application-error', error)
        print('Mod loader: '+str(error),file=sys.stderr); raise SystemExit(2)
