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

Launch preflight/spawn failures retain their traceback in the session log. Existing per-run `launch.json` and `process.log` remain in their owned run directories. When an observed process exits, `diagnostics.json` summarizes that exit and preserves at most 64 KiB from each known current-run log (`process.log`, `Player.log`, `loader.jsonl`, `bepinex.jsonl`). Private managed runs also retain the changed portion/tail of their own `BepInEx/LogOutput.log`; an unchanged previous-run log is excluded. Private Unity crash markers or fatal direct Windows game process exit codes are reported as crashes. Linux Proton/Flatpak runner exits are labeled `lifetime-unconfirmed` or `runner-failed`, with game lifetime unverified; a runner exit code alone is not game-crash evidence. In installed mode, the observed process is only the Steam launch request: even exit zero leaves game startup unconfirmed, and its failure is a Steam-request failure, never inferred game-crash evidence. The logger does not search personal saves, global Unity logs or arbitrary crash dumps. Closing the loader leaves a user-started game alone; later game exit cannot be observed by that closed window. Existing launch evidence remains available, but no unattended installed-game crash monitor is claimed.

Installed launch preparation saves a `diagnostics-watch.json` under that installation's loader data. On Steam-request exit and when **Open logs** is clicked, the collector revalidates the game's `MoonLab/owner.json`, the live installed deployment receipt and the request's exact installation/generation. It examines at most 4096 correctly named bootstrap run directories and copies at most 16 matching `loader.jsonl` tails of 64 KiB each into `logs/installed-bootstrap.json`. A log must be modified after this request began and contain the matching native `deployment` event; stale, foreign-generation or foreign-installation logs are excluded. This refresh survives a loader restart and catches bootstrap evidence written after the short Steam request ended. Changed ownership/generation records an unavailable collection rather than attributing another launch. Observing a matching bootstrap log is explicitly labeled as bootstrap evidence; game-process lifetime and game-crash attribution remain unverified.

Doorstop can fail before `BepInEx/LogOutput.log` or the adapter exists, writing a game-root `preloader_yyyyMMdd_HHmmss_NNN.log` and presenting a blocking error dialog. Pre-launch diagnostics snapshot existing valid preloader basenames and a start time in each private game; installed watches retain the same baseline. Collection scans at most 4096 entries and keeps at most 16 new, nonempty regular-file tails of 64 KiB. Names must contain a valid timestamp, be absent from the baseline and have a modification time after it. Existing names are excluded even if rewritten; stale timestamps, malformed names, symlinks and hardlinks are excluded. An incomplete baseline prevents attribution. Installed collection additionally requires its current owner/deployment validation before reading these game-root logs. Fresh preloader evidence is labeled `preloader-failed` and logged at ERROR even if a runner returns exit zero, without claiming a game crash or verified process lifetime. **Open logs** also refreshes private preloader evidence from the selected private installation's owned active-run `launch.json`, saving `logs/private-preloader.json` without waiting for that blocking dialog/process to exit. This covers the observed missing `Microsoft.Extensions.Logging.Abstractions` failure at `Doorstop.Entrypoint.Start()` before adapter initialization.

For an installed deployment whose current receipt explicitly declares `managed: true`, the collector also retains fresh `adapter-ready.json`, `adapter-failed.json` and `adapter-failure.txt` sidecars from those same generation-attributed native run directories. Only these three known names are read, each bounded to a 64 KiB tail; stale/aliased files and sidecars without the matching native deployment event are excluded. `adapter-failure.txt` is the adapter's fatal Exit(23) report, including failures before its normal logger exists. Fresh failure sidecars set `adapter-failed` and ERROR regardless of the short Steam request's zero exit code; the request result remains separately recorded and game lifetime remains unverified. The current owned game's `BepInEx/LogOutput.log` is retained only for such managed receipts, with the matching live ownership marker, pre-launch baseline/fingerprint and a fresh changed modification time. Unchanged old output and stale timestamps are excluded. Private owned-run summaries retain the same known adapter sidecars and failure classification.

Diagnostics directory enumeration streams through `scandir` and closes after at
most 4096 entries (4097 only to detect an incomplete preloader baseline).
Diagnostics-owned JSON controls have a 2 MiB read cap. Deployment receipts receive
an independent-file/size precheck before the unchanged public validator; because
that validator reopens the path, concurrent replacement between those operations
remains a size-check race. Inputs are checked as independent regular files again
after open. Installed attribution examines bounded 16 KiB heads and retains at
most 16 matching 64 KiB tails; foreign or aliased child logs neither consume the
matching allowance nor hide valid siblings.

### Desktop launch feedback and lifetime

Launch automatically checks setup and applies selected mods before requesting
Steam or starting the private runner. **Prepare files** remains optional. Worker
progress reports checking, applying and handoff stages. Normal notices use neutral
styling; failures use the error treatment. The launch status has its own
`launchStatusText` object selector with an explicit error-state override so its neutral
foreground cannot mask a failed request. The deferred Qt gate asserts the
resolved palette foreground through handoff, failed request and observed-running
transitions, while retaining duplicate-launch guards. **Launch diagnostics** is collapsed by
default and contains the observed process type, exit code and local log path.
Neither a successful Steam request nor a private runner PID proves mod startup.

Installed requests journal `steam-starting` before spawn and `steam-unconfirmed`
after spawn in the loader data's `active.json`. A spawn failure marks that journal
failed; after a successful spawn, exit zero, request failure or elapsed time never
unlocks a second launch. The journal also blocks prepare, enable/disable and
uninstall through service admission, surviving a loader restart. Private runner
exit transfers its lease to a `private-unconfirmed` journal before release rather
than treating runner completion as confirmed game exit. Existing private `running`
journals remain pending even if the recorded runner dies after the window closes;
acknowledgement also refuses a still-live recorded runner. A failed uncertainty
transfer therefore preserves the original persistent guard. Closing the window does
not stop any process.

`game_process.py` passively samples bounded process identity. Linux requires the
exact game basename in argv[0], the matching kernel command name and an unchanged
PID birth token; names only in a Steam/Proton/wine argument do not count. Windows
requires exact Toolhelp executable names and stable birth tokens across two
snapshots. Read errors, incomplete/capped scans and inaccessible identities are
unavailable evidence. Detection says that Moon Sweepers is running, without
attributing that process to an installation, selected mods or a successful loaded
world. An absent sample unlocks only after a game was observed running and the
existing conservative stopped-game check also passes. Otherwise the user must
choose **Game closed / did not start…** after checking Steam and the game. That
acknowledgement rechecks that no game is running under session/operation locks and
clears only the same reviewed request; it never stops a process. A delayed Steam
launch after explicit acknowledgement remains outside the loader's process
ownership. Failed/incomplete private starting journals retain their prior manual
inspection policy.

Source-phase checks are `tests/test_launch_feedback.py` and
`tests/test_game_process.py` (synthetic process data, no game or subprocess farm).
`tests/test_launch_feedback_ui.py` authors real Qt interaction gates for neutral
handoff, collapsed technical details, duplicate suppression, observed running/exit,
restart uncertainty and a request outliving an observed game. `tools/check.py --host-only` explicitly excludes these
Qt checks along with the existing three. No Qt, game, package/build or full suite
qualification was run during the workstation-use implementation pass.

Deferred gates, when workstation testing is authorized: run the two pure test
modules, `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -p test_launch_feedback_ui.py`, then the existing
`python tools/check.py` full host/Qt checks and platform packaging checks. Review
expanded/collapsed status at 1190×760 and 700×540 with keyboard navigation and long
paths. In a separately authorized real Steam replay, verify slow first managed
startup, zero/nonzero short request exit, no detected game, running game,
unreadable identity, game exit, loader restart, duplicate clicks and explicit
acknowledgement; preserve Steam configuration and selections. These are gates,
not results of this source pass. Gamescope teardown has a separate
[static ownership/evidence design](../design/gamescope-teardown.md).

`tests/test_diagnostics.py` covers information/error tracebacks, rotation, unavailable/aliased storage, early CLI failures, an actual isolated Python abort, spawn failure/lease cleanup, private crash-tail collection, current-only managed output, ownership rejection and Steam request uncertainty. Qt worker/warning/Open logs behavior is also exercised in the private offscreen UI check; no game is needed for those checks.

`loader/moonloader/discovery.py` owns Steam discovery (app 5335510); `game_profiles.json` owns reviewed exact-hash game identities and adapter capabilities. `compatibility.py` composes those with the actual runtime and selected framework contracts. The initial adapter targets Steam Windows x64 IL2CPP 1.0.5. Manual discovery does not establish support for other storefront runtimes. Installed mode requests Steam launch using its selected compatibility runtime on Linux or native game on Windows. Private mode retains installed Proton Experimental and its separate launch route.

`service.py`, `storage.py` and `launch.py` preserve private game-copy deployment, rollback/recovery, selected dependencies, editable per-mod settings, explicit launch plans, operation/session locks and process ownership. New data defaults to [installed-game deployment](public-deployment.md), which adds owned files to the existing Steam installation without copying game files; legacy data stays private. Private profiles start fresh and never use personal Steam/Bottles save data as a fallback. The app starts a game only via the Launch action; `--no-launch` disables it.

`vendored/api/` is the content-pinned first-party SDK. `moonloader.packages` reexports its validator/resolver, and `moonloader.storage` reexports its portable storage functions while retaining loader locks/process identity locally. `moonloader.__init__` resolves the snapshot relative to the repository, never to a sibling development checkout. `tools/check_snapshot.py` verifies every pinned payload file and rejects extra/changed files and symlinks.

The SDK pin is 0.7.0. It validates native v1–v8, ordinary/external managed mods,
and companions; the UI treats managed packages as selectable game mods. This
default distribution includes the checked [managed host](managed-runtime.md)
for installed and private modes, alongside the native runtime.
`available_runtimes(installation)` accounts for the selected deployment mode in
both UI readiness and service selection, and preparation repeats the runtime
check before creating a game copy. A managed package can be stored without
being routed to native ModStart. Native v6/v7 interface packages require
`runtime_api_abi: 1`; the native receipt advertises the implemented registry,
typed frame, input and camera tables. The deployment includes a bounded startup
plan and validates actual publications before committing provider startup; see
[runtime services](runtime-services.md). Installed-game managed hosting and
broader native/managed framework presentation remain separate qualification work.
Native v8 instead uses the [game broker](game-adapter.md), with logical game
requirements, scoped framework lookups and a profile-bound runtime plan v2.
Legacy packages retain their current exact-build path.
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
