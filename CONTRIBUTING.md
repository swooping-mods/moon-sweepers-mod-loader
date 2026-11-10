# Contributing

This repository owns the Moon Sweepers desktop loader, native bootstrap, supported
game pins, private profile/deployment behavior and portable distributions. It
includes a content-pinned [API SDK](https://github.com/swooping-mods/moon-sweepers-api)
snapshot used by the loader. Gameplay mods and their assets belong with their authors.

Use installed Python 3.11+, LLVM cross tools and PySide6 6.x. Run
`python3 tools/check.py` for the complete host suite. `--host-only` explicitly
excludes the two Qt interaction checks when PySide6 is unavailable.
`python3 tools/build.py` builds the native runtime and source distribution offline.
See [Windows packaging](specs/windows-packaging.md) for the bundled Windows build
and [CI](specs/ci.md) for runner behavior. Dependency updates require a new review;
builds never resolve unpinned packages.

## Releases

1. Set `__version__` in `loader/moonloader/__init__.py` to the intended `MAJOR.MINOR.PATCH`.
   Both ZIP filenames and build receipts use that value.
2. Merge the intended source onto `main` and let **Checks** pass, including the
   Windows bundled-runtime and actual EXE smoke tests.
3. Create a `vMAJOR.MINOR.PATCH` tag at that reviewed commit and push the tag.
   **Publish release** checks that tag against the package version, rebuilds and
   verifies both ZIPs, runs Windows smoke checks, then publishes those exact
   assets and `SHA256SUMS` to GitHub Releases.

The release job uses GitHub's scoped token; no personal token or Nexus credentials
are required. Pull requests and branch pushes cannot publish releases. Only the
final publishing job has `contents: write`. Assets are uploaded to a draft before
it becomes a published release. Existing releases are never overwritten; if upload
fails, inspect/remove the incomplete draft before rerunning the failed publishing
job. Do not move a released tag to different source.

Release CI qualifies the Windows launcher and bundled Python/Qt runtime without
starting the game. Supported-game behavior and co-op require separate testing.
The launcher is unsigned. GitHub's generated source archive differs from the
explicit loader source ZIP, which also contains the compiled native bootstrap.
