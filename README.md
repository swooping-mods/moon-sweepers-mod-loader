# Moon Sweepers Mod Loader

A desktop mod loader for Moon Sweepers. Install `.msmod` packages, choose your
mods, check dependencies and game compatibility, then launch through Steam.
Available for Windows x64 and Linux x64 with Steam Proton.

[Downloads](#installation) · [Quick start](#quick-start) ·
[Find mods](https://github.com/swooping-mods/mod-index) ·
[Report an issue](https://github.com/swooping-mods/moon-sweepers-mod-loader/issues)

![Moon Sweepers Mod Loader showing the nine bundled mods, import controls and mod details](loader/assets/mod-loader-screenshot.png)

*Development preview with the bundled library. The Add mods, Add folder and
drag-and-drop controls shown here are pending publication; see [adding mods](#adding-mods).*

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Bundled mods](#bundled-mods)
- [Adding mods](#adding-mods)
- [Compatibility and saves](#compatibility-and-saves)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Credits and licensing](#credits-and-licensing)

## Installation

### Choose a build

| Channel | Download | What it includes |
| --- | --- | --- |
| Current development builds | [Successful Checks runs on main](https://github.com/swooping-mods/moon-sweepers-mod-loader/actions/workflows/check.yml?query=branch%3Amain) | Windows, Linux and source archives, the nine bundled mods, and SHA-256 checksums. Open a successful run and download `moon-sweepers-mod-loader-builds` under **Artifacts**. GitHub sign-in is required; artifacts expire after 14 days. |
| Tagged prerelease | [v0.1.0](https://github.com/swooping-mods/moon-sweepers-mod-loader/releases/tag/v0.1.0) | Older Windows and source ZIPs. This version uses private game copies and has no starter mod bundle or Linux archive. Follow its [version-specific instructions](https://github.com/swooping-mods/moon-sweepers-mod-loader/blob/v0.1.0/README.md). |

The instructions below describe current `main` builds. Tagged downloads are listed
on [Releases](https://github.com/swooping-mods/moon-sweepers-mod-loader/releases);
there is currently no stable release. The game itself is not included.

### Platform requirements

| Platform | Archive | Start the loader | Requirements |
| --- | --- | --- | --- |
| Windows x64 | `moon-sweepers-mod-loader-VERSION-windows-x64.zip` | Extract the entire ZIP, then open **Mod Loader.exe**. Keep its adjacent folders. | Windows 10/11 x64 and Steam. Python and Qt are included; no administrator access is needed. The launcher is unsigned. |
| Linux x64 | `moon-sweepers-mod-loader-VERSION-linux-x64.tar.gz` | Extract, then run `./Moon\ Sweepers\ Mod\ Loader` from the extracted folder. | Installed Python 3.11+, PySide6 6.8–6.x, and Steam Proton for the game. Set `MOON_LOADER_PYTHON=/path/to/python` to use an existing Python environment. |

The source ZIP includes the native bootstrap but requires your own Python and
PySide6. GitHub's automatic source-code archives require a [native build](#development).

## Quick start

1. Start the loader and select a supported game installation. Use **Browse…** if
   it was not detected.
2. Choose **Existing Steam game** to use your installed game and normal Steam
   saves. Confirm that your saves are backed up, or use a fresh Steam profile.
3. On Linux, set the game's Steam launch options as described under
   [Proton setup](#proton-setup).
4. Check the mods you want and their required frameworks. **Select all** selects
   the whole library, including mods hidden by search or filters.
5. Click **Prepare files**, resolve any reported dependency or compatibility
   problems, then click **Launch via Steam**.

Search covers names, descriptions, categories and tags. Grid, Details and Text
views share the same filters and selections. Importing packages and preparing
files do not start the game.

## Bundled mods

Current development builds include these handpicked mods and all five required
dependencies:

| Mod | Repository |
| --- | --- |
| Squishy Plushie | [squishy-plushie](https://github.com/swooping-mods/squishy-plushie) |
| Futuristic Courier | [futuristic-car](https://github.com/swooping-mods/futuristic-car) |
| Power Poles | [manual-power-poles](https://github.com/swooping-mods/manual-power-poles) |
| Debug Menu (F4), for testing | [debug-menu](https://github.com/swooping-mods/debug-menu) |

The included dependencies are **Sound Framework**, **Pickup Hands**, **Hints
Framework**, **Vehicle Framework** and **Build Menu Framework**. All nine packages
appear in the library on first start, initially unchecked. Existing versions and
checkmarks are preserved. The [bundle specification](specs/bundled-mods.md) and
[package lock](vendored/mod-bundle.json) record the exact contents and versions.

## Adding mods

Browse the [Moon Sweepers Mod Index](https://github.com/swooping-mods/mod-index),
then download the mod's `.msmod` file and any required framework packages from
their repositories. The index is a separate website; the loader imports local
packages.

### Available in published builds

Click **Install mod package…** and select a `.msmod` file. Repeat for its
dependencies, check the desired mods and frameworks, then **Prepare files** and
launch. New imports stay unchecked; existing checkmarks are preserved.

### Upcoming import controls

The development preview shown above adds these methods. They are not yet included
in the published `main` builds or v0.1.0 download:

| Method | Accepted input |
| --- | --- |
| Drag and drop onto the loader | One or more `.msmod` files, supported ZIP downloads or extracted mod folders. |
| **Add mods…** | Select one or several `.msmod` or supported `.zip` files with the file picker. |
| **Add folder…** | Choose an extracted folder containing `.msmod` files or unpacked packages with manifests. |

This pending importer also recognizes the complete **MarsSweepers 0.6.1** download.
Running it requires a separately attached supported BepInEx runtime and **Private
game copy** mode. Standard loader downloads do not include that runtime, and
importing does not attach it. Other raw third-party DLLs require a compatible mod
package. See the [managed runtime contract](specs/managed-runtime.md).

## Compatibility and saves

The adapter targets the pinned Steam Windows x64 IL2CPP **1.0.5** build
(app **5335510**). Exact executable hashes determine compatibility; the version
label alone is insufficient. Other builds require a matching adapter.

**Existing Steam game** adds owned loader files and selected mods without copying
the game or replacing original game DLLs. It uses normal Steam saves. Back up the
save folder and its sidecars before enabling mods that affect saves, or choose a
fresh Steam profile. The loader can back up an explicitly selected save folder.

**Private game copy** keeps a separate copy and modded profile. Existing private
profiles remain available. See [deployment details](specs/public-deployment.md)
for path requirements, conflicts and recovery.

### Proton setup

For **Existing Steam game** on Linux, open the game's **Properties → General →
Launch Options** in Steam. With no existing options, use:

```sh
WINEDLLOVERRIDES="version=n,b" %command%
```

If you already use launch options, merge the `version=n,b` override while keeping
your other overrides, wrappers and arguments. **View launch plan** shows the
selected deployment mode and launch settings. A successful Steam launch request
does not confirm that the game started or loaded mods.

### Disable or remove mods

**Disable mods** takes effect on the next game start. **Uninstall loader** removes
unchanged files owned by the loader and retains settings and saves. Files changed
externally are preserved and reported. Removing mods cannot make every modded
save compatible with vanilla.

Launcher and package checks cover installation behavior. Native Windows gameplay,
the full nine-mod combination in a loaded world, save/reload, real co-op and
physical controllers require separate qualification.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Missing dependency | Import and select the frameworks declared by the mod. **Select all** is convenient for the starter bundle. |
| Unsupported game build | Check the installation selected in the loader. Compatibility uses executable hashes; renaming files does not make another build supported. |
| Different buttons or an empty library | Check which build you downloaded. v0.1.0 predates the starter bundle; the screenshot also shows pending import controls. |
| Linux loader does not open | Confirm Python 3.11+ and PySide6 6.8–6.x are available to the chosen interpreter. Use `MOON_LOADER_PYTHON` for an existing environment. |
| Steam opens but mods do not load on Proton | Check the [Steam launch options](#proton-setup) and **View launch plan**. |

Application data is stored in `%LOCALAPPDATA%/MoonLab/Loader` on Windows and
`$XDG_DATA_HOME/moonlab-loader` (normally `~/.local/share/moonlab-loader`) on Linux.
Use `--data PATH` to choose another location, or `--no-launch` to inspect the UI
with launching disabled.

Report loader, installation and launch issues in
[this repository's issue tracker](https://github.com/swooping-mods/moon-sweepers-mod-loader/issues).
Include the loader build, operating system, game build and the error shown.
Report gameplay issues in the mod's repository.

## Development

Use installed **Python 3.11+**, **PySide6 6.8–6.x** and the LLVM cross tools
`clang`, `lld-link` and `llvm-dlltool`. Commands run from the repository root:

```sh
./run.sh --no-launch --data local/review
python3 tools/check.py
python3 tools/build.py
python3 tools/build_linux.py
python3 tools/check_linux_bundle.py --gui
```

On Windows, use `Start-Mod-Loader.cmd` or
`py -3 loader/main.py --no-launch --data local/review` to run the desktop source.
To package Windows offline, supply the reviewed inputs pinned in
`vendored/windows-runtime.lock.json`:

```sh
python3 tools/build_windows.py --inputs /path/to/reviewed-inputs
python3 tools/check_windows_bundle.py
```

Builders download nothing. Build outputs and verification receipts go under
ignored `artifacts/`. The full host check includes Qt interactions;
`python3 tools/check.py --host-only` explicitly excludes three Qt tests on runners
without PySide6. CI builds both platform archives, checks the Linux launcher,
and runs the bundled Qt runtime and actual EXE on Windows. Version tags run the
same gates before publishing prerelease assets.

### Mod authoring and project documentation

The loader pins [Moon Sweepers API](https://github.com/swooping-mods/moon-sweepers-api)
**0.6.1**. Native v6/v7 mods use its runtime registry; v7 declares exact adapter
ABIs in `requires_host`. Unsupported hosts or missing capabilities reject before
game preparation. Gameplay frameworks remain separate mods.

- [Contributing](CONTRIBUTING.md): development and release workflow.
- [Native mod authoring](specs/native-adapter.md): checked bindings in `sdk/native/`.
- [Managed runtime](specs/managed-runtime.md): optional BepInEx attachment and private mode.
- [Windows packaging](specs/windows-packaging.md) and [Linux packaging](specs/linux-packaging.md).
- [CI](specs/ci.md): required checks and distribution artifacts.
- [Specifications index](specs/_readme.md): current implementation contracts.

## Credits and licensing

Bundled mods retain their authorship and provenance in the
[package lock](vendored/mod-bundle.json) and
[third-party notices](vendored/THIRD_PARTY_NOTICES.md).

The Windows bundle includes Python, Qt/PySide and Microsoft notices, licenses and
matching Qt/PySide sources in `LICENSES/`. Its shared libraries remain replaceable.
No project-wide license has been assigned.
