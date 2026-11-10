# Bundled Windows runtime licenses

The portable download bundles CPython 3.13.17, PySide6/Shiboken 6.8.3, Qt 6.8.3
(Core, Gui, Widgets and Svg, with Windows platform/style and SVG plugins), and
the Microsoft Visual C++ runtime DLLs supplied in the upstream distributions.
Versions, input hashes, publisher URLs and selected wheel members are recorded
in `runtime-manifest.json` in the portable package.

Python's license and its included third-party notices are in `Python/LICENSE.txt`.
Qt/PySide/Shiboken are distributed under LGPL-3.0-only; the complete license texts,
third-party copyright/license files and Qt attribution manifests are preserved
under `upstream/`, grouped by original source archive. Qt's bundled third-party
components retain their individual licenses; inclusion of other upstream license
texts does not change the license of the loader.

Matching, unmodified LGPL library source archives are included here, in the same download:
`pyside-setup-everywhere-src-6.8.3.tar.xz`,
`qtbase-everywhere-src-6.8.3.tar.xz`, and `qtsvg-everywhere-src-6.8.3.tar.xz`.
These include upstream build instructions and third-party sources/notices.
No library source changes are made. Wheel deployment is reduced to the runtime
members listed in the manifest, without changing those members' contents.

The libraries remain separate DLLs under `python/PySide6/` and `python/shiboken6/`.
You may replace them with compatible modified versions; no signature or hash
check prevents replacement at application startup. The input hash checks apply
only while building the bundle. Debugging and reverse engineering for modifying
these LGPL libraries are permitted. For replacement builds, follow the upstream
source build instructions, use CPython 3.13 Windows x64 and compatible PySide6,
Shiboken and Qt versions, and replace the matching DLLs/PYD files together.
The editable application code is in `loader/`; the launcher only invokes the
adjacent `python/pythonw.exe` with `loader/main.py`.

Microsoft runtime terms are preserved in the `Visual-C-Runtime-*.docx` document;
Visual Studio redistribution terms are preserved in `Visual-Studio-*.docx`.
Readable extracted copies are alongside them. These apply only to Microsoft's
components, not to Qt, PySide6 or application code. Microsoft's redistribution list:
https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution
Copyright Microsoft Corporation. All rights reserved.

No license is assigned here to the loader's original code or the first-party SDK.
Steam, Proton, game files and third-party mods are not included.
