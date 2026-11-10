# Moon Sweepers Mod Loader

A desktop mod loader for Moon Sweepers, with local `.msmod` installation, dependency and compatibility checks, private game copies and separate modded profiles.

Repository: [swooping-mods/moon-sweepers-mod-loader](https://github.com/swooping-mods/moon-sweepers-mod-loader). The reviewed source is hosted privately on GitHub. The detailed [repository split proposal](design/repository-split.md) explains the three repositories, issue routing and Nexus release flow.

The extracted adapter supports the previously pinned Steam Windows x64 IL2CPP 1.0.5 build (app 5335510). Exact executable hashes, rather than the version label alone, determine acceptance. Windows launches the native game; Linux uses the user's installed Steam/Proton Experimental. Other game builds and storefront runtimes require separate qualification.

## Run locally

Use installed Python 3.11+ and PySide6 6.x. `loader/requirements.txt` documents the UI dependency; nothing is installed automatically.

```sh
./run.sh --no-launch --data local/review
```

Windows: run `Start-Mod-Loader.cmd`, or `py -3 loader/main.py --no-launch --data local/review`.

This source checkout opens an empty mod library. Import your `.msmod` files through **Install mod package**. The native bootstrap is produced by the build command below. For a usable portable bundle, extract `artifacts/moon-sweepers-mod-loader-0.1.0-source.zip`, then use its root launcher. The archive includes the native bootstrap and diagnostic, but requires host Python/PySide6. No standalone GUI executable is built.

Only the explicit Launch action starts a game. **Prepare files** creates a loader-owned private copy; original game installations stay read-only. Fresh private profiles are not seeded from personal Steam/Bottles saves. `--no-launch` disables the launch action for inspection. Avoid choosing an existing development data directory when reviewing this clean copy.

## Verify and build

```sh
python3 tools/check.py
python3 tools/build.py
```

Checks cover the package/API snapshot, dependency resolution, deployment recovery, profile isolation, native dispatcher and offscreen Qt interactions. `--host-only` explicitly excludes the two Qt tests for CI runners without PySide6. The native build requires installed `clang`, `lld-link` and `llvm-dlltool`; it downloads nothing. Build outputs and verification receipts remain ignored under `artifacts/`.

`vendored/api/` is the pinned first-party SDK from `moon-sweepers-api`, with a file-hash lock. The loader owns the desktop application, native bootstrap, supported game pins and profile/deployment behavior. Gameplay mod implementations and assets are not bundled. Existing `MoonLab_*` native symbols remain unchanged.

## Downloads and contributions

Nexus Mods is the intended main player portal. GitHub Issues/PRs own code and review. CI validates changes and can create a release candidate; publishing and remote catalog discovery are not enabled in this preparation. Importing a local package is the current supported install path. See [release plan](design/nexus-release.md).

Read [specs/_readme.md](specs/_readme.md) and [third-party notices](vendored/THIRD_PARTY_NOTICES.md). The repository split has not rerun game, Wine, native Windows or co-op qualification. No project license is assigned.
