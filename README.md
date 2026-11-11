# Moon Sweepers Mod Loader

Install and select local `.msmod` packages, check dependencies and compatibility,
and launch Moon Sweepers with the selected mods.

## Download and install

Get a checked build from [GitHub Releases](https://github.com/swooping-mods/moon-sweepers-mod-loader/releases).
Newer development builds are available from successful
[Checks runs](https://github.com/swooping-mods/moon-sweepers-mod-loader/actions/workflows/check.yml)
as the `moon-sweepers-mod-loader-builds` artifact.

- **Windows x64:** extract the entire Windows ZIP and open **Mod Loader.exe**.
  Python and Qt are included; no administrator access is needed.
- **Linux x64:** extract the Linux `.tar.gz` and run `./Moon\ Sweepers\ Mod\ Loader`.
  Requires installed Python 3.11+ and PySide6 6.8–6.x. Set
  `MOON_LOADER_PYTHON=/path/to/python` to use an existing Python environment.
  The game runs through Steam Proton.

Downloads include **Squishy Plushie**, **Futuristic Courier**, **Power Poles**,
**Debug Menu (F4)**, and all five required dependencies: Sound Framework, Pickup
Hands, Hints Framework, Vehicle Framework and Build Menu Framework. They appear
in the library on first start, initially unchecked. Existing versions and
checkmarks are preserved. See the [bundle details](specs/bundled-mods.md).

Select the mods and their required frameworks, or use **Select all**, choose the
supported game installation, then **Prepare files** and
**Launch**. Search matches names, descriptions, categories and tags. Grid, Details
and Text views share the same filters and enabled selections. Add other packages
with **Install mod package**.

## Game compatibility and saves

The adapter targets the pinned Steam Windows x64 IL2CPP 1.0.5 build (app 5335510).
Exact executable hashes determine compatibility. Other game builds require a
matching adapter. Gameplay, real co-op and physical-controller qualification are
separate from launcher checks.

**Existing Steam game** adds owned loader files and selected mods without copying
the game or replacing original game DLLs. It uses normal Steam saves: back up the
save folder and sidecars before enabling save-affecting mods, or choose a fresh
Steam profile. The UI can back up an explicitly selected save folder.

On Proton, merge `WINEDLLOVERRIDES="version=n,b"` into the Steam launch options,
preserving existing settings. The simple case is
`WINEDLLOVERRIDES="version=n,b" %command%`. **View launch plan** shows the selected
mode. Steam accepting a launch request does not confirm that the game started.

**Disable mods** applies on the next start. **Uninstall loader** removes unchanged
owned additions and retains settings/saves; externally changed files are preserved
and reported. Removing mods cannot make every modded save compatible with vanilla.
Existing private-copy profiles remain available through **Private game copy**.
See [deployment details](specs/public-deployment.md) for recovery and path limits.

Application data uses `%LOCALAPPDATA%/MoonLab/Loader` on Windows and
`$XDG_DATA_HOME/moonlab-loader` (normally `~/.local/share/moonlab-loader`) on Linux.
Use `--data PATH` for another location, or `--no-launch` to inspect the UI with
launch disabled.

## Build and development

With installed Python 3.11+, PySide6 6.8–6.x and LLVM cross tools:

```sh
./run.sh --no-launch
python3 tools/check.py
python3 tools/build.py
python3 tools/build_linux.py
python3 tools/check_linux_bundle.py --gui
```

The Linux archive uses system Python/PySide6. Windows packaging uses the exact
reviewed inputs pinned in `vendored/windows-runtime.lock.json`:

```sh
python3 tools/build_windows.py --inputs /path/to/reviewed-inputs
python3 tools/check_windows_bundle.py
python3 tools/build_linux.py
```

Builders run offline. The full host suite includes Qt interactions; `--host-only`
explicitly excludes three Qt tests on runners without PySide6. CI builds both
platform archives and checks the Linux launcher, Windows bundled Qt runtime and
actual Windows EXE. Version tags run the same gates before publishing prerelease
assets. See [CI](specs/ci.md) and [contributing](CONTRIBUTING.md).

## SDK and credits

The loader pins [Moon Sweepers API](https://github.com/swooping-mods/moon-sweepers-api)
0.6.1. Native v6/v7 mods use its runtime registry; v7 declares exact adapter ABIs
in `requires_host`. Unsupported hosts or missing capabilities reject before game
preparation. The checked game bindings under `sdk/native/` and optional managed
adapter sources under `runtime/bepinex/` support independent mod builds. Gameplay
frameworks remain separate mods. See [native authoring](specs/native-adapter.md)
and [managed runtime](specs/managed-runtime.md).

The Windows bundle retains Python, Qt/PySide and Microsoft notices, licenses and
matching Qt/PySide sources in `LICENSES/`; its shared libraries remain replaceable.
See [third-party notices](vendored/THIRD_PARTY_NOTICES.md). The Windows launcher is
unsigned. No project-wide license has been assigned.

Report loader and deployment issues in [this repository](https://github.com/swooping-mods/moon-sweepers-mod-loader/issues).
Gameplay issues belong in the mod's repository. Current contracts are indexed by
[specs/_readme.md](specs/_readme.md).
