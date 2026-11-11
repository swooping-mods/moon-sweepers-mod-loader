# Linux desktop packaging

`tools/build_linux.py` reads the exact checked source ZIP and its build receipt
under artifacts, verifies its version and digest, then emits a deterministic
`moon-sweepers-mod-loader-VERSION-linux-x64.tar.gz`. It retains the desktop app,
assets, API snapshot and native Windows bootstrap used by the game under Proton.
The desktop app runs on Linux with installed Python 3.11+ and PySide6 6.8–6.x;
Python/Qt are system prerequisites rather than bundled runtime payloads.

The archive also retains the [nine handpicked packages](bundled-mods.md), their
lock and provenance. The package checker verifies their exact inventory and
hashes; the optional GUI smoke asserts first-run import and unchecked defaults.

The executable `Moon Sweepers Mod Loader` launcher resolves its own directory,
quotes paths/arguments and invokes `MOON_LOADER_PYTHON` or python3. The archive
supports paths containing spaces. Mutable data uses the existing XDG application
directory. The builder adds the archive to SHA256SUMS and records all included
hashes and the exact source archive identity in linux-build-receipt.json.

`tools/check_linux_bundle.py` rejects unsafe paths, aliases, duplicate or non-file
members and inconsistent inventories/digests. It materializes files in a private
temporary directory with spaces, runs the actual launcher with --help and isolates
XDG data. `--gui` additionally runs the same Qt/SVG/no-launch smoke check used on
Windows, with installed PySide6 and temporary data. No game starts.

GitHub Ubuntu checks the CLI launcher without installing PySide6. The local full
suite and explicit Linux --gui smoke cover Qt; the hosted Windows job checks its
bundled Qt and EXE. CLI-only Linux CI records that GUI coverage limit explicitly.
The release verifier requires the Linux archive/check receipt alongside the
source and Windows ZIPs. See [CI](ci.md) for the final publishing gate.
