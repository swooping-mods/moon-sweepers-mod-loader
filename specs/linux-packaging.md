# Linux desktop packaging

`tools/build_linux.py` reads the exact checked source ZIP and its build receipt
under artifacts, verifies its version and digest, then emits a deterministic
`moon-sweepers-mod-loader-VERSION-linux-x64.tar.gz`. It retains the desktop app,
assets, API snapshot and native Windows bootstrap used by the game under Proton.
The desktop payload bundles CPython 3.13.18 and the selected PySide6/Shiboken/Qt
6.8.3 modules from hash-locked publisher inputs. No user Python/Qt setup or
installer runs. `linux_runtime.py` copies only selected regular runtime members,
omitting pip, ensurepip and unused test/Tk components; it materializes desktop
helper aliases as ordinary files. The Linux lock owns the exact file selection.
The matching full Python distribution supplies its native dependency notices;
Qt/PySide/Wayland and AppImage sources/notices accompany recipients under LICENSES.
No project-wide license is added.

The archive also retains the [nine handpicked packages](bundled-mods.md), their
lock and provenance. The package checker verifies their exact inventory and
hashes; the optional GUI smoke asserts first-run import and unchecked defaults.
It also carries the same checked BepInEx adapter/maintained Windows CoreCLR host
as Windows, for installed and private managed deployment under Proton. The archive checker
validates every host byte and the portable smoke verifies backend availability;
no managed plugin or game binding is included or started by those checks.

The executable `Moon Sweepers Mod Loader` launcher resolves its own directory,
quotes paths/arguments and invokes the bundled isolated interpreter or the explicit
`MOON_LOADER_PYTHON` override. The archive
supports paths containing spaces. Mutable data uses the existing XDG application
directory. The builder adds the archive to SHA256SUMS and records all included
hashes and the exact source archive identity in linux-build-receipt.json.

`tools/check_linux_bundle.py` rejects unsafe paths, aliases, duplicate or non-file
members and inconsistent inventories/digests. It materializes files in a private
temporary directory with spaces, runs the actual launcher with --help and isolates
XDG data. `--gui` additionally runs the same Qt/SVG/no-launch smoke check used on
Windows, with bundled PySide6 and temporary data. Child-process output remains visible in
CI so runtime or host-library failures can be diagnosed. No game starts.

The root launcher is the only application entry point in the extracted folder.
Runtime files stay under `.runtime/`. Small XCB/XKB helper libraries are taken
from a signature-verified Ubuntu Noble package index, with their notices.
`linux_desktop.prepare()` loads these in dependency order for the desktop route;
it does not set global LD_LIBRARY_PATH, which could contaminate Steam children.
The bundle requires glibc 2.38+ (the highest inspected helper symbol requirement),
such as Ubuntu 24.04, and the system graphics/display
drivers. It is not an Alpine/musl or graphics-driver distribution.

## Single-file downloads

`build_linux_formats.py` consumes the exact sealed tar.gz. The `.run` wrapper
extracts it under a version-and-full-digest XDG cache directory using a private
temporary directory and atomic publication, then execs the same entry point.
It needs neither FUSE nor administrator access. No package manager is invoked.

The AppImage concatenates the pinned Type-2 runtime and a deterministic SquashFS
AppDir containing that same payload, desktop metadata and icon. The small reviewed
runtime is vendored because upstream replaces its continuous-release asset.
Its source revision and dependency archives remain locked. The build-only
SquashFS executable/libraries are extracted from pinned packages without running
maintainer scripts; they are not added to the application payload.

GitHub Ubuntu runs the actual archive launcher with --help and the bundled Qt/SVG
and nine-mod smoke check, and checks the desktop helper loader separately.
`check_linux_formats.py` runs both single-file downloads with --help and
--smoke-test in paths containing spaces, using private XDG data/cache. AppImage
uses its built-in extract-and-run mode, so CI does not require FUSE. These checks
start no game. Linux format receipts bind both file digests to their sealed
tar.gz; release verification requires successful actual CLI and Qt checks for
all three Linux formats alongside the source/Windows checks. See [CI](ci.md).
