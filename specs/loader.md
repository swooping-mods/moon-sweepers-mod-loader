# Desktop, bootstrap and API ownership

The source repository is public. Versioned portable downloads are published through the existing GitHub prerelease workflow. Local recovery records remain ignored. The obsolete `loader/check_windows.py` development-package diagnostic is removed; public Windows smoke checks use `loader/check_portable_windows.py` and the bundled launcher.

The repository owns the Python/PySide6 desktop app, its native Windows AMD64 bootstrap, game-build compatibility pins and private deployment/profile boundaries. It contains no gameplay mod implementations or mod asset library.

`loader/main.py` is the CLI and desktop entrypoint. Root launchers retain the `loader/` layout so source and portable bundles locate the same pinned SDK. Default application data remains compatible with the prior loader; use `--data local/review` for an isolated review. No source-checkout mod catalog is seeded.

`loader/moonloader/discovery.py` owns supported game executable hashes and Steam discovery (app 5335510). The adapter targets the pinned Steam Windows x64 IL2CPP build. Manual discovery does not establish support for other storefront runtimes. Installed mode requests Steam launch using its selected compatibility runtime on Linux or native game on Windows. Private mode retains installed Proton Experimental and its separate launch route.

`service.py`, `storage.py` and `launch.py` preserve private game-copy deployment, rollback/recovery, selected dependencies, editable per-mod settings, explicit launch plans, operation/session locks and process ownership. New data defaults to [installed-game deployment](public-deployment.md), which adds owned files to the existing Steam installation without copying game files; legacy data stays private. Private profiles start fresh and never use personal Steam/Bottles save data as a fallback. The app starts a game only via the Launch action; `--no-launch` disables it.

`vendored/api/` is the content-pinned first-party SDK. `moonloader.packages` reexports its validator/resolver, and `moonloader.storage` reexports its portable storage functions while retaining loader locks/process identity locally. `moonloader.__init__` resolves the snapshot relative to the repository, never to a sibling development checkout. `tools/check_snapshot.py` verifies every pinned payload file and rejects extra/changed files and symlinks.

The SDK pin is 0.4.0. It validates native v1–v6, ordinary/external managed mods,
and companions; the UI treats managed packages as selectable game mods. This
standalone distribution currently hosts native mods only. `available_runtimes`
is passed to both UI readiness and service selection, and preparation repeats
the runtime check before creating a game copy. A managed package can be stored
without being routed to native ModStart. Native v6 interface packages require
`runtime_api_abi: 1`; the native receipt advertises the implemented registry,
typed frame, input and camera tables. The deployment includes a bounded startup
plan and validates actual publications before committing provider startup; see
[runtime services](runtime-services.md). The development managed host remains a separate
integration rather than an implied capability of this distribution.

`runtime/loader/` implements the hook registry, startup sealing, shared Update, camera override/observers and vehicle input/physics ownership. It uses the pinned public SDK. `runtime/native/` retains the private exception bridge, original instruction emulator and version exports. Existing MoonLab symbols and package ABIs retain compatibility. Game pins require separate gameplay qualification.

`tools/build.py` requires installed clang, lld-link and llvm-dlltool (unversioned or version-suffixed names). It compiles the original bootstrap and standalone diagnostic with warnings as errors, checks AMD64/export surfaces and creates a deterministic portable source ZIP plus SHA256SUMS. The ZIP retains `loader/` and `vendored/` and includes native binaries under `loader/runtime/`. This source ZIP requires host Python/PySide6 and bundles no mods or game files. `tools/build_windows.py` adds the separate fully bundled Windows portable ZIP; see [Windows packaging](windows-packaging.md).

`tools/check.py` checks the API snapshot and runs the focused loader suite, including three compiled host-native programs and two Qt interaction cases. `--host-only` explicitly excludes those two Qt cases for runners without PySide6. Automated Qt verification uses a private headless Gamescope session. GitHub checks and manual candidate workflows have read-only repository permissions. The tag-triggered release workflow publishes checked artifacts to GitHub Releases; see [CI](ci.md). Hosted index consumption remains unimplemented; the loader accepts local `.msmod` files.
