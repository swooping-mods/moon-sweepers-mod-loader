# Windows portable packaging

`tools/build_windows.py --inputs PATH` builds an offline Windows AMD64 portable
folder and ZIP under `artifacts/`. It requires the installed native build tools
used by `tools/build.py`. Exact reviewed input names, SHA-256 hashes, publisher
URLs and selected wheel members are pinned in `vendored/windows-runtime.lock.json`.
The command never downloads, installs dependencies or executes Windows payloads.
The separate explicit `tools/fetch_windows_inputs.py` stages the already-reviewed
lock inputs for CI; [CI](ci.md) defines the hosted-runner execution gates.
New input bytes require the workstation external-intake review before use.

The folder contains `Mod Loader.exe`, `python/`, `loader/`, `vendored/api/`,
`THIRD_PARTY_NOTICES.md` and `LICENSES/`. The native Windows-subsystem launcher
resolves its own directory, uses the adjacent `python/pythonw.exe`, and passes
`loader/main.py` plus the original command-line arguments to CreateProcessW.
Paths with spaces are quoted; it does not invoke a shell, host Python, registry
Python or PATH lookup. Process creation errors and nonzero exit produce a message
with a console diagnostic command. The launcher is unsigned.

The CPython embeddable runtime uses an isolated `python313._pth` that includes
only its standard-library ZIP, runtime directory, loader and pinned API paths.
No site initialization or dependency installer is included. `python/qt.conf` points
Qt at the adjacent PySide6 plugin directory. The app's profile
and save data policy remains unchanged: LOCALAPPDATA/MoonLab/Loader by default;
`--data` explicitly selects another path. Portable means no installation is required.

The runtime is CPython 3.13.17 with PySide6/Shiboken 6.8.3 and Qt 6.8.3 Core,
Gui, Widgets and Svg. Windows platform/style, SVG plugins and the offscreen test platform are included.
Only manifest-selected wheel members are copied; none are modified. Qt Quick,
WebEngine and GPL-only application modules are excluded. Required MSVC runtime
DLLs are retained from the publishers' distributions. Windows system DLLs and
UCRT are supplied by Windows 10/11 x64.

Libraries remain external, user-replaceable DLL/PYD files. The build input hash
check does not run at application startup. `LICENSES/` includes the original
Python license/notices, upstream Qt/PySide/Shiboken license/copyright files,
attribution manifests, complete matching source archives, and Microsoft runtime
and redistribution terms in original and readable form. No loader project license
is inferred or assigned. `vendored/WINDOWS-LICENSES.md` owns recipient instructions.

`tests/test_desktop_launcher.py` compiles the actual launcher with mocked Win32
APIs to check quoted paths, argument forwarding and failures without running Windows.

`tools/check_windows_bundle.py` checks the produced archive and materialized files,
AMD64 PE headers, DLL dependency closure against bundled libraries and Windows
system imports, required licenses and source archive hashes. It never executes
Windows binaries. `loader/check_portable_windows.py`, run with the bundled Python
on Windows, checks Qt Widgets and SVG loading with temporary data and no game start.
`Mod Loader.exe --smoke-test` runs the same bounded smoke check through the actual
launcher. GitHub CI executes both smoke paths on Windows; game compatibility and
co-op remain distinct qualification work. Build and static-check receipts are `artifacts/windows-*.json`;
`artifacts/SHA256SUMS` covers both source and Windows ZIP outputs.
