#!/usr/bin/env python3
"""Check real import widgets/drops under private headless Gamescope; no game."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'loader'), str(ROOT / 'tests')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mars-download', type=Path, help='Existing reviewed Mars folder/ZIP; no acquisition or execution')
    args = parser.parse_args()
    if not os.environ.get('GAMESCOPE_WAYLAND_DISPLAY') or os.environ.get('DISPLAY') in ('', ':0', ':0.0', None):
        raise ValueError('Run under private headless Gamescope')
    from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDropEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog
    from moonloader.service import Service
    from moonloader.ui import Window
    from test_loader import package
    out = ROOT / 'artifacts/mod-import-ui'; out.mkdir(parents=True, exist_ok=True)
    (out / 'result.json').unlink(missing_ok=True)
    app = QApplication([])
    captures = []
    with tempfile.TemporaryDirectory(prefix='MoonLoader-import-ui-') as temporary:
        root = Path(temporary)
        service = Service(root / 'data', ROOT / 'loader'); service.seed()
        with patch.object(service, 'installations', return_value=([], [])), patch('moonloader.launch.start') as start:
            window = Window(service, no_launch=True); window.show()
            def capture(name):
                app.processEvents(); QTest.qWait(100)
                if not window.grab().save(str(out / (name + '.png'))): raise ValueError('Capture failed')
                captures.append(name + '.png')
            def finish():
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    app.processEvents()
                    if not window._busy: return
                    # Release Python's GIL while the import worker hashes and
                    # repacks larger downloads; Qt event waits can retain it.
                    time.sleep(.01)
                raise ValueError('Import worker did not finish')
            def drop(path, target):
                mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(path))])
                enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime,
                                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                QApplication.sendEvent(target, enter)
                if not enter.isAccepted(): raise ValueError('Local mod drag was not accepted')
                event = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime,
                                   Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                QApplication.sendEvent(target, event); finish()
                if not event.isAccepted(): raise ValueError('Local mod drop was not accepted')
            capture('after-wide')
            first = root / 'picked.msmod'; package(first, 'picked-example')
            second = root / 'second.msmod'; package(second, 'second-example')
            archive = root / 'download.zip'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('Download/' + second.name, second.read_bytes())
            with patch.object(QFileDialog, 'getOpenFileNames', return_value=([str(first), str(archive)], '')):
                window.import_button.click(); finish()
            assert {'picked-example', 'second-example'} <= window.mods.keys()
            folder = root / 'Extracted mod'; folder.mkdir()
            package(folder / 'folder.msmod', 'folder-example')
            with patch.object(QFileDialog, 'getExistingDirectory', return_value=str(folder)):
                window.import_folder_button.click(); finish()
            assert 'folder-example' in window.mods
            capture('picker-success')
            for view in ('grid', 'details', 'text'):
                window.set_view(view)
                path = root / ('drop-' + view + '.msmod'); package(path, 'drop-' + view)
                drop(path, window.list.viewport())
                assert 'drop-' + view in window.mods
            drop(folder, window)
            window.set_view('grid'); capture('drop-success')
            assert service.state['selected'] == []
            with patch.object(QFileDialog, 'getOpenFileNames', return_value=([], '')):
                window.import_button.click(); assert not window._busy
            with patch.object(QFileDialog, 'getExistingDirectory', return_value=''):
                window.import_folder_button.click(); assert not window._busy
            bad = root / 'unsupported.dll'; bad.write_bytes(b'Original inert error fixture')
            drop(bad, window.list.viewport())
            assert 'complete mod folder' in window.message.text()
            capture('unsupported-download')
            if args.mars_download:
                drop(args.mars_download.resolve(), window.list.viewport())
                assert window.mods['marssweepers'][0]['mode'] == 'external'
                assert 'BepInEx' in window.message.text()
                window.search.setText('MarsSweepers'); capture('mars-import')
                window.search.clear()
            window.resize(760, 650); capture('after-narrow')
            assert not window.details.isVisible()
            assert window.import_button.isVisible() and window.import_folder_button.isVisible()
            window.search.setText('no-matching-download'); capture('filtered-empty')
            window.search.clear()
            window._busy = True; window.update_actions()
            assert not window.import_button.isEnabled() and not window.import_folder_button.isEnabled()
            mime = QMimeData(); mime.setUrls([QUrl('https://example.invalid/mod.zip')])
            enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime,
                                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            window.dragEnterEvent(enter); assert not enter.isAccepted()
            window._busy = False; window.update_actions()
            assert not window.launch_button.isEnabled()
            start.assert_not_called(); window.close()
    result = {'success': True, 'backend': 'gamescope-headless', 'game_started': False,
              'checks': ['multiple file picker', 'folder picker', 'drops in all three views',
                         'window folder drop', 'cancelled pickers', 'import error guidance',
                         'unchanged selections', 'busy state', 'wide and narrow layouts', 'no game launch'],
              'real_mars_import': bool(args.mars_download), 'captures': captures}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(out / 'result.json')


if __name__ == '__main__': main()
