# Moon Sweepers Mod Loader

A desktop mod loader for Moon Sweepers, with local `.msmod` installation, dependency and compatibility checks, private game copies and separate modded profiles.

Repository: [swooping-mods/moon-sweepers-mod-loader](https://github.com/swooping-mods/moon-sweepers-mod-loader).

The extracted adapter supports the previously pinned Steam Windows x64 IL2CPP 1.0.5 build (app 5335510). Exact executable hashes, rather than the version label alone, determine acceptance. Windows launches the native game; Linux uses the user's installed Steam/Proton Experimental. Other game builds and storefront runtimes require separate qualification.

## Windows portable download

Download the Windows x64 ZIP from [GitHub Releases](https://github.com/swooping-mods/moon-sweepers-mod-loader/releases), extract it completely, and
double-click **Mod Loader.exe**. Python, PySide6/Qt and the native bootstrap are
included; no Python installation or administrator access is needed. This is a
Windows x64 portable folder, not a single-file executable. The launcher is unsigned.

Import `.msmod` files, select a supported game installation, use **Prepare files**,
then **Launch**. The game and mod packages are not bundled. Settings and private
profiles use `%LOCALAPPDATA%/MoonLab/Loader`; pass `--data PATH` for another location.
For inspection, run `"Mod Loader.exe" --no-launch`.

`THIRD_PARTY_NOTICES.md` and `LICENSES/` in the ZIP contain bundled component licenses,
copyright notices, attribution manifests and matching Qt/PySide source archives.
Qt and PySide libraries remain replaceable under LGPLv3. No project license is assigned.

## GitHub CI downloads

The **Checks** workflow runs on main pushes and pull requests. It checks the source,
builds the bundled Windows ZIP, then tests the bundled Qt runtime and actual EXE
on a Windows runner. After both jobs pass, download the
`moon-sweepers-mod-loader-windows-x64` artifact from the run's Actions page; artifacts
are retained for 14 days. Manual **Release candidate** builds remain available.
Tagged versions also run these checks before the **Publish prerelease** workflow publishes the verified ZIPs and SHA-256 checksums
as GitHub prerelease assets, excluded from the stable/latest channel.

## Run locally

Use installed Python 3.11+ and PySide6 6.x. `loader/requirements.txt` documents the UI dependency; nothing is installed automatically.

```sh
./run.sh --no-launch --data local/review
```

Windows: run `Start-Mod-Loader.cmd`, or `py -3 loader/main.py --no-launch --data local/review`.

This source checkout opens an empty mod library. Import your `.msmod` files through **Install mod package**. The native bootstrap is produced by the build command below. The separate `artifacts/moon-sweepers-mod-loader-0.1.0-source.zip` includes the native bootstrap and diagnostic but requires host Python/PySide6. The Windows portable ZIP above includes those dependencies and an executable launcher.

Only the explicit Launch action starts a game. **Prepare files** creates a loader-owned private copy; original game installations stay read-only. Fresh private profiles are not seeded from personal Steam/Bottles saves. `--no-launch` disables the launch action for inspection. Avoid choosing an existing development data directory when reviewing this clean copy.

## Verify and build

```sh
python3 tools/check.py
python3 tools/build.py
```

Checks cover the package/API snapshot, dependency resolution, deployment recovery, profile isolation, native dispatcher and offscreen Qt interactions. `--host-only` explicitly excludes the two Qt tests for CI runners without PySide6. The native build requires installed `clang`, `lld-link` and `llvm-dlltool`; it downloads nothing. Build outputs and verification receipts remain ignored under `artifacts/`.

To reproduce the Windows package offline, provide the previously screened publisher
files matching `vendored/windows-runtime.lock.json`:

```sh
python3 tools/build_windows.py --inputs /absolute/path/to/reviewed-inputs
python3 tools/check_windows_bundle.py
```

This command verifies input hashes and downloads nothing. Before acquiring new
inputs, follow the workstation external-intake workflow. The package check verifies
AMD64 images, DLL import closure, required runtime files, licenses and source hashes.
On Windows, the bundled runtime smoke check is:

```bat
python\python.exe loader\check_portable_windows.py
```

It constructs the UI with temporary data, checks SVG loading, then exits without
starting a game. Native Windows execution remains a separate qualification gate;
the Linux host checks do not establish it.


`vendored/api/` is the pinned first-party SDK from `moon-sweepers-api`, with a file-hash lock. The loader owns the desktop application, native bootstrap, supported game pins and profile/deployment behavior. Gameplay mod implementations and assets are not bundled. Existing `MoonLab_*` native symbols remain unchanged.

## Downloads and contributions

Download versioned builds from [GitHub Releases](https://github.com/swooping-mods/moon-sweepers-mod-loader/releases). Import local `.msmod` packages through **Install mod package**. Hosted mod discovery is not implemented.

Report desktop, installation, profile, compatibility-check and launch problems in this repository's [issue tracker](https://github.com/swooping-mods/moon-sweepers-mod-loader/issues). Gameplay mod issues belong with the mod author. See [contributing](CONTRIBUTING.md) for development and release instructions.

Read [specs/_readme.md](specs/_readme.md) and [third-party notices](vendored/THIRD_PARTY_NOTICES.md). The launcher is unsigned. Windows CI checks the bundled GUI and launcher; gameplay and co-op require separate qualification. No project license is assigned.
