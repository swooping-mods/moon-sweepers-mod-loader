#!/usr/bin/env python3
"""Exercise installed-mode controls on synthetic data in headless Gamescope."""
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'loader'), str(ROOT/'tests')]


def main():
    if not os.environ.get('GAMESCOPE_WAYLAND_DISPLAY') or os.environ.get('DISPLAY') in ('', ':0', ':0.0', None):
        raise ValueError('Run under private headless Gamescope')
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtTest import QTest
    from moonloader.ui import Window
    from test_installed import InstalledChecks
    case = InstalledChecks(); case.setUp()
    out = ROOT/'artifacts/installed-ui'; out.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    try:
        service, installation = case.fixture()
        with patch.object(service, 'installations', return_value=([installation], [])), patch('moonloader.launch.start') as start:
            window = Window(service, no_launch=True); window.show()
            def capture(name):
                app.processEvents(); QTest.qWait(100); window.grab().save(str(out/(name+'.png')))
            def finish_job():
                for _ in range(200):
                    app.processEvents(); QTest.qWait(10)
                    if not window._busy: return
                raise ValueError('UI file operation did not finish')
            capture('installed')
            assert window.disable_button.isVisible() and not window.launch_button.isEnabled()
            window.deployment_mode.setCurrentIndex(1); capture('private')
            assert service.mode(installation) == 'private' and not window.disable_button.isVisible()
            window.deployment_mode.setCurrentIndex(0)
            window.resize(760,650); capture('installed-narrow'); assert not window.details.isVisible()
            window.prepare_button.click(); finish_job(); capture('prepared')
            assert (Path(installation.path)/'version.dll').exists()
            window.disable_button.click(); finish_job(); capture('disabled')
            assert 'disabled' in window.message.text()
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):
                window.uninstall_button.click(); finish_job()
            capture('uninstalled'); assert not (Path(installation.path)/'version.dll').exists()
            window.search.setText('missing'); capture('empty')
            start.assert_not_called(); window.close()
            (out/'result.json').write_text(json.dumps({'success':True,'game_started':False,
                'backend':'gamescope-headless','checks':['mode switch','normal-save notice','narrow layout',
                'prepare','disable','uninstall','empty state','no game launch'],
                'captures':[p.name for p in out.glob('*.png')]},indent=2)+'\n')
    finally: case.doCleanups()
    print(out/'result.json')


if __name__ == '__main__': main()
