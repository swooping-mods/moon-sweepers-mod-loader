"""Desktop GUI/runtime smoke check; temporary data, no game launch."""
import os
import json
from pathlib import Path
import sys
import tempfile


def main():
    if sys.platform not in ('win32', 'linux'):
        raise SystemExit('This smoke check supports Windows and Linux desktops.')
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from PySide6.QtCore import QTimer
    from moonloader.service import Service
    from moonloader.ui import Window
    bundle = Path(__file__).resolve().parent
    app = QApplication([])
    with tempfile.TemporaryDirectory(prefix='MoonLoader-portable-check-') as temporary:
        service = Service(Path(temporary), bundle)
        service.seed()
        expected = json.loads((bundle.parent / 'vendored/mod-bundle.json').read_text())
        library, errors = service.library()
        assert not errors
        assert set(library) == {item['id'] for item in expected['packages']}
        assert not service.state['selected']
        window = Window(service, no_launch=True)
        window.show()
        assert not QIcon(str(bundle / 'assets/electricity-toggle.svg')).pixmap(32, 32).isNull()
        assert not window.launch_button.isEnabled()
        QTimer.singleShot(250, app.quit)
        result = app.exec()
        window.close()
    print('Python, PySide6, Qt Widgets, SVG and bundled mod library passed; no game started.')
    return result


if __name__ == '__main__':
    raise SystemExit(main())
