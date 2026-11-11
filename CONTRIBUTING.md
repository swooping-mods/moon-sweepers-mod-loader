# Contributing

This repository owns the Moon Sweepers desktop loader, native bootstrap, supported
game pins, private profile/deployment behavior and portable distributions. It
includes a content-pinned [API SDK](https://github.com/swooping-mods/moon-sweepers-api)
snapshot used by the loader. Gameplay mods and their assets belong with their authors.

Use installed Python 3.11+, LLVM cross tools and PySide6 6.x. Run
`python3 tools/check.py` for the complete host suite. `--host-only` explicitly
excludes the three Qt interaction checks when PySide6 is unavailable.
`python3 tools/build.py` builds the native runtime and source distribution offline.
See [Windows packaging](specs/windows-packaging.md) for the bundled Windows build
and [CI](specs/ci.md) for runner behavior. Dependency updates require a new review;
builds never resolve unpinned packages.

## Build and release CI

The Checks workflow produces source, Windows x64 and Linux x64 archives. Tagged
versions run the same gates before publishing a GitHub prerelease. The exact
asset and permission contract is documented in [CI](specs/ci.md).
