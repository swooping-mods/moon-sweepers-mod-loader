# Moon Sweepers Mod Loader

A desktop mod loader for Moon Sweepers, with local `.msmod` installation, dependency and compatibility checks, installation into the existing Steam game, and an optional private-copy mode.

Repository: [swooping-mods/moon-sweepers-mod-loader](https://github.com/swooping-mods/moon-sweepers-mod-loader). The source is public on GitHub.

The extracted adapter supports the previously pinned Steam Windows x64 IL2CPP 1.0.5 build (app 5335510). Exact executable hashes, rather than the version label alone, determine acceptance. Installed mode requests Steam's selected runtime; private mode uses native Windows or the user's installed Proton Experimental. Other game builds and storefront runtimes require separate qualification.

## Windows portable download

Download the Windows x64 ZIP from [GitHub Releases](https://github.com/swooping-mods/moon-sweepers-mod-loader/releases), extract it completely, and
double-click **Mod Loader.exe**. Python, PySide6/Qt and the native bootstrap are
included; no Python installation or administrator access is needed. This is a
Windows x64 portable folder, not a single-file executable. The launcher is unsigned.

Import `.msmod` files, select a supported game installation, use **Prepare files**,
then **Launch**. The game and mod packages are not bundled. Application state and private
profiles use `%LOCALAPPDATA%/MoonLab/Loader`; pass `--data PATH` for another location.
Installed-mode mod settings live under the game's `MoonLab/settings/` directory.
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

Only the explicit Launch action requests a game start. New loader data uses **Existing Steam game**: **Prepare files** adds the bootstrap and selected mods without copying the game or Proton or replacing original game DLLs. Existing loader data keeps **Private game copy**, with its existing isolated profiles. Changing the selector never deletes or migrates a private setup. `--no-launch` disables launch for inspection.

Installed mode uses normal Steam saves. Back up the save folder and sidecars before enabling save-affecting mods, or explicitly confirm a fresh Steam profile when prompted. The UI can back up an explicitly chosen Steam save folder. **Disable mods** applies on the next start; **Uninstall loader** removes unchanged owned additions and retains saves/settings. Binary removal cannot make every modded save compatible with vanilla. Conflicting loaders or externally changed files are preserved and reported.

On Proton, merge `WINEDLLOVERRIDES="version=n,b"` into the game's Steam launch options, preserving existing settings; the simple case is `WINEDLLOVERRIDES="version=n,b" %command%`. Use **View launch plan** for the selected mode. Installed mode asks Steam to launch app 5335510 using its chosen runtime/prefix. A successful request is not confirmation that the game or mods started. Steam options are not edited automatically.

CLI examples (all preparation/removal actions start no game):

```sh
./run.sh --game /path/to/MoonSweepers --mode installed --normal-saves backed-up --prepare
./run.sh --game /path/to/MoonSweepers --disable
./run.sh --game /path/to/MoonSweepers --uninstall-loader
```

Use `--backup-steam-saves PATH` to make a verified copy of an explicitly chosen Steam save folder, including sidecars. Fresh private profiles never use personal Steam/Bottles saves. Creating a new private copy requires a clean source; uninstall the public bootstrap first if needed. See the [deployment contract](specs/public-deployment.md) for recovery, path limits and qualification boundaries. Native Windows gameplay, Cloud and two-account co-op remain separate qualification requirements.

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

The SDK pin is 0.4.0 and understands managed packages and independently owned
framework interfaces. Native v6 packages use the implemented runtime registry,
typed frames, input and camera services. Default builds host native mods;
importing a managed package does not install its required host. Unsupported
backends and unavailable runtime capabilities reject before game preparation.

## Downloads and contributions

Download versioned builds from [GitHub Releases](https://github.com/swooping-mods/moon-sweepers-mod-loader/releases). Import local `.msmod` packages through **Install mod package**. Hosted mod discovery is not implemented.

Report desktop, installation, profile, compatibility-check and launch problems in this repository's [issue tracker](https://github.com/swooping-mods/moon-sweepers-mod-loader/issues). Gameplay mod issues belong with the mod author. See [contributing](CONTRIBUTING.md) for development and release instructions.

Read [specs/_readme.md](specs/_readme.md) and [third-party notices](vendored/THIRD_PARTY_NOTICES.md). The launcher is unsigned. Windows CI checks the bundled GUI and launcher; gameplay and co-op require separate qualification. No project license is assigned.
