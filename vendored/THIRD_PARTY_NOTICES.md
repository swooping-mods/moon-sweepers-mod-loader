# Third-party notices

The Windows portable bundle includes **Python 3.13.17** and **Qt for Python /
PySide6, Shiboken and Qt 6.8.3**. Python uses the PSF license and included
third-party terms. PySide6, Shiboken and the selected Qt libraries use LGPLv3;
Qt's embedded third-party components retain their own licenses. Microsoft Visual
C++ runtime DLLs from the publisher distributions retain Microsoft's terms.

The portable archive's `LICENSES/` directory contains license texts, copyright
notices, upstream attribution files and matching library source archives.
See `LICENSES/README.md` for component details and how to replace LGPL libraries.
The application does not restrict replacement or debugging of these libraries.
`vendored/windows-runtime.lock.json` pins the exact distribution inputs.
Source-only use continues to use host-installed Python/PySide6.

The native bootstrap, diagnostic, application source, launcher and included SVG
are original project code/artwork. `vendored/api/` is a first-party content-pinned
snapshot from `swooping-mods/moon-sweepers-api`. It retains the MoonLab ABI.

GitHub Actions are referenced by immutable revisions and remain subject to their
upstream terms; they are not included in this source tree. No Nexus uploader is
bundled or activated. Steam, Proton, game binaries, extracted game assets and
third-party mods are excluded. The maintainer's selected mods and dependencies
are included as pinned prebuilt packages; see [bundle provenance](mod-bundle/README.md).
Their applicable credits and licenses remain inside the packages.

No project license is assigned.
