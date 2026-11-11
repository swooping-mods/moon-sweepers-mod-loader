# Desktop, bootstrap and API ownership

The source repository is public. Versioned portable downloads are published through the existing GitHub prerelease workflow. Local recovery records remain ignored. The obsolete `loader/check_windows.py` development-package diagnostic is removed; public Windows smoke checks use `loader/check_portable_windows.py` and the bundled launcher.

The repository owns the Python/PySide6 desktop app, its native Windows AMD64 bootstrap, game-build compatibility pins and private deployment/profile boundaries. Gameplay source remains in owning projects; the [handpicked bundle](bundled-mods.md) vendors nine pinned prebuilt distribution inputs.

The independent desktop includes the workshop's optional category/tag discovery.
`moonloader/catalog.py` owns its presentation validation and matching. Search
combines words across names, descriptions, categories and tags in Grid, Details
and Text views; category and Enabled filters retain checkmarks. Missing or
malformed optional presentation extensions remain visible through ordinary
search. This transfer preserves installed-game preparation, save backup,
enable/disable and uninstall controls. `tests/test_categories.py` exercises
actual Qt selection/filter/detail behavior without launching a game.

`loader/main.py` is the CLI and desktop entrypoint. Root launchers retain the `loader/` layout so source and portable bundles locate the same pinned SDK. Default application data remains compatible with the prior loader; use `--data local/review` for an isolated review. Bundles and the source checkout seed the same nine pinned packages, initially unchecked, while preserving existing versions and selections.

`moonloader/diagnostics.py` saves local session diagnostics under the selected data folder's `logs/`, accessible through **Open logs**. `loader.jsonl` records UTC timestamps, session IDs, information, notices, operation errors, worker tracebacks, Python/thread exceptions and Qt messages. Each record is flushed to disk; logging failures are contained and never replace an operation's original error. A bounded cross-process lock serializes writes/rotation from concurrent loader sessions, with a one-second timeout instead of indefinite UI blocking. Logs rotate at 2 MiB with four backups; a single oversized event is truncated. Python's fatal-error handler retains native Python/Qt crash tracebacks in `crash.log`, with the previous nonempty crash log preserved as `crash.previous.log`. This does not intercept every native OS termination or power loss. Full process environments and argument lists are not recorded, and nothing is uploaded automatically. CLI argument/operation errors use the same data location, including an explicit `--data` before normal argument parsing. The diagnostics bootstrap uses only Python's standard library and starts before the application/SDK imports, so damaged application imports can still leave a traceback.

Launch preflight/spawn failures retain their traceback in the session log. Existing per-run `launch.json` and `process.log` remain in their owned run directories. When an observed process exits, `diagnostics.json` summarizes that exit and preserves at most 64 KiB from each known current-run log (`process.log`, `Player.log`, `loader.jsonl`, `bepinex.jsonl`). Private managed runs also retain the changed portion/tail of their own `BepInEx/LogOutput.log`; an unchanged previous-run log is excluded. Private Unity crash markers or fatal process exit codes are reported as crashes. In installed mode, the observed process is only the Steam launch request: even exit zero leaves game startup unconfirmed, and its failure is a Steam-request failure, never inferred game-crash evidence. The logger does not search personal saves, global Unity logs or arbitrary crash dumps. Closing the loader leaves a user-started game alone; later game exit cannot be observed by that closed window. Existing launch evidence remains available, but no unattended installed-game crash monitor is claimed.

Installed launch preparation saves a `diagnostics-watch.json` under that installation's loader data. On Steam-request exit and when **Open logs** is clicked, the collector revalidates the game's `MoonLab/owner.json`, the live installed deployment receipt and the request's exact installation/generation. It examines at most 4096 correctly named bootstrap run directories and copies at most 16 matching `loader.jsonl` tails of 64 KiB each into `logs/installed-bootstrap.json`. A log must be modified after this request began and contain the matching native `deployment` event; stale, foreign-generation or foreign-installation logs are excluded. This refresh survives a loader restart and catches bootstrap evidence written after the short Steam request ended. Changed ownership/generation records an unavailable collection rather than attributing another launch. Observing a matching bootstrap log is explicitly labeled as bootstrap evidence; game-process lifetime and game-crash attribution remain unverified.

`tests/test_diagnostics.py` covers information/error tracebacks, rotation, unavailable/aliased storage, early CLI failures, an actual isolated Python abort, spawn failure/lease cleanup, private crash-tail collection, current-only managed output, ownership rejection and Steam request uncertainty. Qt worker/warning/Open logs behavior is also exercised in the private offscreen UI check; no game is needed for those checks.

`loader/moonloader/discovery.py` owns supported game executable hashes and Steam discovery (app 5335510). The adapter targets the pinned Steam Windows x64 IL2CPP build. Manual discovery does not establish support for other storefront runtimes. Installed mode requests Steam launch using its selected compatibility runtime on Linux or native game on Windows. Private mode retains installed Proton Experimental and its separate launch route.

`service.py`, `storage.py` and `launch.py` preserve private game-copy deployment, rollback/recovery, selected dependencies, editable per-mod settings, explicit launch plans, operation/session locks and process ownership. New data defaults to [installed-game deployment](public-deployment.md), which adds owned files to the existing Steam installation without copying game files; legacy data stays private. Private profiles start fresh and never use personal Steam/Bottles save data as a fallback. The app starts a game only via the Launch action; `--no-launch` disables it.

`vendored/api/` is the content-pinned first-party SDK. `moonloader.packages` reexports its validator/resolver, and `moonloader.storage` reexports its portable storage functions while retaining loader locks/process identity locally. `moonloader.__init__` resolves the snapshot relative to the repository, never to a sibling development checkout. `tools/check_snapshot.py` verifies every pinned payload file and rejects extra/changed files and symlinks.

The SDK pin is 0.6.0. It validates native v1–v7, ordinary/external managed mods,
and companions; the UI treats managed packages as selectable game mods. This
default distribution hosts native mods. An explicitly attached checked managed
runtime enables [private managed deployment](managed-runtime.md).
`available_runtimes(installation)` accounts for the selected deployment mode in
both UI readiness and service selection, and preparation repeats the runtime
check before creating a game copy. A managed package can be stored without
being routed to native ModStart. Native v6/v7 interface packages require
`runtime_api_abi: 1`; the native receipt advertises the implemented registry,
typed frame, input and camera tables. The deployment includes a bounded startup
plan and validates actual publications before committing provider startup; see
[runtime services](runtime-services.md). Installed-game managed hosting and
broader native/managed framework presentation remain separate qualification work.
Native v7 additionally requires a nonempty `requires_host` map. Selection and
preparation compare exact adapter ABI values against `host_capabilities` in the
runtime receipt, treating absent/null maps as empty targets. A cached selection
cannot bypass replacement of that receipt before preparation. Older package
ABIs retain their existing admission rules.

`runtime/loader/` implements the hook registry, startup sealing, shared Update, camera override/observers and vehicle input/physics ownership. It uses the pinned public SDK. `runtime/native/` retains the private exception bridge, original instruction emulator and version exports. Existing MoonLab symbols and package ABIs retain compatibility. Game pins require separate gameplay qualification.

`tools/build.py` requires installed clang, lld-link and llvm-dlltool (unversioned or version-suffixed names). It compiles the original bootstrap and standalone diagnostic with warnings as errors, checks AMD64/export surfaces and creates a deterministic portable source ZIP plus SHA256SUMS. The ZIP retains `loader/` and `vendored/`, includes native binaries under `loader/runtime/` and the nine handpicked packages under `loader/packages/`. This source ZIP requires host Python/PySide6 and bundles no game files. `tools/build_windows.py` adds the separate fully bundled Windows portable ZIP; see [Windows packaging](windows-packaging.md).

`tools/check.py` checks the API snapshot and runs the focused loader suite, including three compiled host-native programs and three Qt interaction cases. `--host-only` explicitly excludes those three Qt cases for runners without PySide6. Automated Qt verification uses a private headless Gamescope session. GitHub checks and manual candidate workflows have read-only repository permissions. The tag-triggered release workflow publishes checked artifacts to GitHub Releases; see [CI](ci.md). Hosted index consumption remains unimplemented. [Downloaded mod imports](download-imports.md) add file/folder pickers and local drag-and-drop for `.msmod`, unpacked packages, supported ZIPs and the reviewed MarsSweepers layout.


`tools/check_public_wine.py` applies `tools/audio_policy.py` after building its
process environment. Non-game Wine/portable diagnostics disable Wine's Pulse,
ALSA, OSS and direct PipeWire drivers, select OpenAL null/SDL dummy backends,
and retain bootstrap overrides. A nonexistent Pulse socket is not a mute and
must not be used: Wine can fall back to ALSA and block desktop headphones.
No prefix registry, desktop volume/default device or shared service is changed.
`tests/test_audio_policy.py` covers merged overrides and explicit capture mode;
the development workspace owns live Wine/Proton driver/PCM qualification.
