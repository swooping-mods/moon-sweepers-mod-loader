# Contributing

This repository owns the Moon Sweepers desktop loader, native bootstrap, supported
game pins, private profile/deployment behavior and portable distributions. It
includes a content-pinned [API SDK](https://github.com/swooping-mods/moon-sweepers-api)
snapshot used by the loader. Gameplay mods and their assets belong with their authors.

Use installed Python 3.11+, LLVM cross tools and PySide6 6.x. Run
`python3 tools/check.py` for the complete host/Qt suite; no tests are excluded.
CI runs the same suite with its reviewed bundled Python/PySide6 runtime after
building the Linux archive. QtTest is staged only in the disposable test copy.
To reproduce it, run `python3 tools/check_linux_bundle.py --suite-inputs /path/to/reviewed-linux-inputs`
against the built archive (use `--output` for a nondefault artifact directory).
Stage the reviewed managed inputs explicitly with
`tools/fetch_windows_inputs.py --lock vendored/managed-runtime.lock.json --output local/managed-inputs`
and the same command with `vendored/modern-harmony.lock.json`. Then
`python3 tools/build.py --dotnet PATH_TO_EXISTING_SDK` builds the native runtime,
bundled managed host and source distribution offline. `--managed-inputs PATH`
can reuse an existing checked input folder. No SDK or dependency installer runs.
See [Windows packaging](specs/windows-packaging.md) for the bundled Windows build
and [CI](specs/ci.md) for runner behavior. Dependency updates require a new review;
builds never resolve unpinned packages.

## Build and release CI

The Checks workflow produces source, Windows x64 and Linux x64 archives. Tagged
versions run the same gates before publishing a GitHub prerelease. The exact
asset and permission contract is documented in [CI](specs/ci.md).
