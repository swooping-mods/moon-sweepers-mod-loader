"""Source and portable distribution entry point. CLI checks never launch a game."""
import argparse
import json
import os
from pathlib import Path
import sys
from moonloader import __version__
from moonloader.service import Service
from moonloader import discovery, launch


def main():
    parser = argparse.ArgumentParser(description='Moon Sweepers Mod Loader '+__version__)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--discover', action='store_true')
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--prepare', action='store_true', help='Apply files for the selected mode; never starts a game')
    parser.add_argument('--mode', choices=('installed', 'private'), help='Existing Steam game or separate private copy; legacy data keeps private mode')
    parser.add_argument('--disable', action='store_true', help='Disable installed mods on next launch')
    parser.add_argument('--enable', action='store_true', help='Enable the prepared installed selection on next launch')
    parser.add_argument('--uninstall-loader', action='store_true', help='Remove owned installed payloads, preserving saves/settings')
    parser.add_argument('--backup-steam-saves', type=Path, help='Back up this explicitly chosen Steam save folder and its sidecars')
    parser.add_argument('--normal-saves', choices=('backed-up', 'fresh'), help='Confirm existing Steam saves are backed up, or this is a fresh Steam profile')
    parser.add_argument('--game', type=Path)
    parser.add_argument('--install', type=Path, help='Import a local .msmod package')
    parser.add_argument('--no-launch', action='store_true', help='Disable game launching while inspecting the UI')
    parser.add_argument('--smoke-test', action='store_true', help='Check the bundled Windows GUI with temporary data, then exit without starting a game')
    args = parser.parse_args()
    if args.smoke_test:
        from check_portable_windows import main as smoke_test
        return smoke_test()
    default = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'MoonLab/Loader' if sys.platform == 'win32' else Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'moonlab-loader'
    service = Service(args.data or default, args.bundle)
    service.seed()
    if args.install: service.import_package(args.install)
    if args.game: service.add_installation(args.game)
    installations, errors = service.installations()
    if args.discover:
        print(json.dumps({'installations':[x.record() for x in installations], 'errors':errors}, indent=2)); return 0
    if args.plan or args.prepare or args.mode or args.disable or args.enable or args.uninstall_loader or args.backup_steam_saves or args.normal_saves:
        selected = next((x for x in installations if x.path == service.state['installation']), installations[0] if len(installations) == 1 else None)
        if not selected: raise ValueError('Choose an installation with --game PATH')
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
    try: from PySide6.QtWidgets import QApplication
    except ImportError: raise ValueError('PySide6 is required for the desktop UI. See README.md; no dependency was downloaded.')
    from moonloader.ui import Window
    app=QApplication(sys.argv[:1]); app.setApplicationName('Moon Sweepers Mod Loader'); app.setOrganizationName('MoonLab')
    window=Window(service,args.no_launch); window.show(); return app.exec()


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError) as error:
        print('Mod loader: '+str(error),file=sys.stderr); raise SystemExit(2)
