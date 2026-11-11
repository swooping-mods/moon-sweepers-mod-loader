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

Linux desktop downloads bundle **CPython 3.13.18**, the selected Qt for Python /
PySide6, Shiboken and Qt 6.8.3 libraries, ICU 73.2, and the small XCB/XKB desktop
helpers named in `linux-runtime.lock.json`. Their original notices and Python's
dependency license texts are in `LICENSES/`. Matching Qt/PySide/Wayland sources
accompany the replaceable libraries. Python is from Astral's pinned
python-build-standalone distribution; no pip or dependency installer ships.

AppImage includes the Type-2 runtime at commit
`fedfad51acc2860b2916a1eef32ba4a500ff31ef`; its MIT notice is retained in
`vendored/appimage/LICENSE.txt`. Its FUSE, SquashFUSE, musl, mimalloc, zstd and zlib
notices and sources accompany the payload. The SquashFS build executable is a
build input, not an application payload. See [Linux runtime intake](linux-runtime-intake.md).

The native bootstrap, diagnostic, application source, launcher and included SVG
are original project code/artwork. `vendored/api/` is a first-party content-pinned
snapshot from `swooping-mods/moon-sweepers-api`. It retains the MoonLab ABI.

GitHub Actions are referenced by immutable revisions and remain subject to their
upstream terms; they are not included in this source tree. No Nexus uploader is
bundled or activated. Steam, Proton, game binaries, extracted game assets and
third-party mods are excluded. The maintainer's selected mods and dependencies
are included as pinned prebuilt packages; see [bundle provenance](mod-bundle/README.md).
Their applicable credits and licenses remain inside the packages.

The [download recognition profiles](import-profiles/README.md) include the
original first-party Mars compatibility companion, wrapper artwork and metadata.
The upstream MarsSweepers DLL, voices and source are not bundled; users supply
their own exact supported download. Import grants no redistribution rights.

Normal desktop and source distributions also include BepInEx 6.0.0-be.791,
Il2CppInterop 1.5.3, Unity Doorstop and their component libraries, with the original
Moon Sweepers adapter. [Managed component notices](bepinex-runtime-notices.md)
describe their terms. Exact LGPL corresponding sources and component license
texts travel under `loader/runtime/bepinex/files/BepInEx/third-party-sources/`.
The maintained Windows CoreCLR runtime is the MIT-licensed Microsoft NuGet
runtime pack pinned by `managed-runtime.lock.json`; its complete original
`LICENSE.TXT`, `THIRD-PARTY-NOTICES.TXT` and package metadata remain in the
host's `dotnet/` folder. No generated proprietary game bindings are included.

No project license is assigned.
