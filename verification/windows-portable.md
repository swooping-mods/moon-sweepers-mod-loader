# Windows portable packaging verification

The portable Windows x64 ZIP and extracted folder are under `artifacts/`. Extract
the entire archive before running `Mod Loader.exe`; Python/PySide installation is
not required. The launcher and native runtime are built with the installed LLVM
cross tools. The launcher has the Windows GUI subsystem and only Kernel32/User32
imports. `python/qt.conf` fixes the bundled Qt plugin path.

Checks:

- `python3 tools/check.py`: 44 passing checks, no failures/skips/exclusions. Includes
  existing headless Qt checks, native dispatcher checks and a new production C
  launcher harness with mocked Win32 APIs. The harness checks quoted executable,
  script and profile paths, exact argument forwarding, child failure, process-create
  failure and path truncation. Static assertions pin the Windows x64 startup structs.
- `python3 tools/build_windows.py --inputs /home/cachyos-gaming/workspace/local/windows-intake`:
  builds offline, verifies every input hash, produces source and Windows ZIPs.
- `python3 tools/check_windows_bundle.py`: verifies 44 required files, 55 AMD64
  runtime images, Windows GUI subsystem, DLL import closure, isolated Python/Qt
  paths, actual ZIP contents, licenses and matching LGPL source archive hashes.
- Rebuilding the initial Windows ZIP reproduced its SHA-256 exactly. Final hashes
  for both output ZIPs are in `artifacts/SHA256SUMS`.
- `git diff --check`: passed.

External acquisition used the external-intake skill. The exact input URLs/hashes
are in `vendored/windows-runtime.lock.json`. Runtime static inspection has zero
coverage gaps; expected native-code and dormant developer-helper leads were
manually reviewed. Final runtime ClamAV scan: exit 0, 69 files, zero infected files.
ClamAV 1.5.4 database 28158 is dated 2026-10-19 and stale; no refresh was performed.
Broad source/wheel scans initially hit byte/time bounds; the selected runtime was
materialized and fully rescanned. Matching LGPL source archives are inert data,
not executed. PySide/QtSvg sources and Microsoft license scans passed. The final QtBase source
scan hit MaxScanTime (exit 1 after 347.597 seconds, 338.97 MiB scanned); this is an
unresolved full-archive antivirus coverage limit, not a malware signature. Its
source remains unmodified, inert reference data; no source build/test hooks run.
Do not describe the entire ZIP as antivirus-cleared.
Detailed per-source logs and manual disposition are retained in
`~/external-repos/.local/security/moon-loader-windows/`.

The GitHub Checks workflow now executes the bundled Python/Qt/SVG smoke test and
actual EXE on a Windows runner. Hosted run evidence is recorded in
`artifacts/github-ci.json`; `specs/ci.md` owns this gate.

Local limits: no native Windows/Wine/Proton execution environment was available. The
Windows launcher, bundled GUI, supported game and co-op were not executed on
Windows. The included `loader/check_portable_windows.py` is the Windows-side Qt/SVG
smoke check and must be run with the bundled Python. No signing certificate was
supplied; the launcher is unsigned. No release, push, PR or upload was performed.
No project license was assigned; the package preserves dependency licenses only.
