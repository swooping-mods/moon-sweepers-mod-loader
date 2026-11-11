"""Load portable XCB helper libraries without leaking search paths to Steam."""
import ctypes
import os
from pathlib import Path
import sys


def prepare():
    if sys.platform != 'linux' or os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        return
    root = Path(__file__).resolve().parents[2]/'.runtime/desktop-libs'
    if not root.is_dir():
        return
    # Load in dependency order. A process-global LD_LIBRARY_PATH would also be
    # inherited by Steam/game children and could replace their own libraries.
    for name in ('libxcb-randr.so.0', 'libxcb-render.so.0', 'libxcb-shape.so.0',
                 'libxcb-shm.so.0', 'libxcb-sync.so.1', 'libxcb-xfixes.so.0',
                 'libxcb-xkb.so.1', 'libX11-xcb.so.1', 'libxkbcommon.so.0',
                 'libxcb-util.so.1', 'libxcb-icccm.so.4', 'libxcb-keysyms.so.1',
                 'libxcb-render-util.so.0', 'libxcb-image.so.0', 'libxcb-cursor.so.0',
                 'libxkbcommon-x11.so.0'):
        ctypes.CDLL(str(root/name), mode=ctypes.RTLD_GLOBAL)
