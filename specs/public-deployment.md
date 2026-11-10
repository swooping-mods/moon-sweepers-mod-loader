# Installed-game deployment

`loader/moonloader/public.py` owns additive installation into a supported Steam game. New loader data defaults to `installed`; existing state without deployment-mode fields remains `private`. Per-installation mode selections are explicit, use separate receipt roots, and never migrate/delete existing copies or profiles. The private copy/launch implementation remains available.

## Files and compatibility

Installed mode adds `version.dll`, `MoonLab/active.txt`, selected `MoonLab/mods/<id>/` files, an ABI-qualified runtime plan and a generation-specific file inventory. Existing packages resolve assets and framework DLLs under `MoonLab/mods/`, so that path is preserved. Generations identify validated selections; they are not parallel immutable copies of every package.

Original EXE, GameAssembly and UnityPlayer files are hashed against the supported pins and never replaced. No game/Proton copy or public steam_appid.txt is created. Original-file patching/restoration is unsupported in this mode; consequently there are no redundant original-DLL backups. Unknown existing proxies, competing winhttp/winmm/Doorstop/BepInEx/MelonLoader installations and foreign MoonLab directories reject. A single loader data directory owns each target. Launch-plan preview reports destinations, removals, conflicts and the backup scope without writes.

Receipts enumerate exact immutable additions and hashes. Mutable `MoonLab/settings/`, logs, mod-generated sidecars, unrelated files and manually chosen save backups survive uninstall. Ownership metadata and empty directories may remain; they load no code. The current native mod ABI requires a short ASCII game path and bounded ASCII payload paths.

## Transaction and recovery

`pending-installed.json` and `deployment.json` live in the installation's loader data. Backups of previously owned additions and new payloads stage under a unique `.moonlab-stage-<id>` folder on the game filesystem. This supports loader data on a different volume. Target symlinks/reparse points, hardlinked destinations and case aliases reject.

Preparation validates supported runtime capabilities before installed writes. It rejects a running MoonSweepers.exe conservatively across installations, serializes our operations using a target lock, and checks a Steam manifest's installed state where present. Our lock does not control Steam. Input signatures are checked during mutations and full build hashes before enabling the committed selection; startup independently hashes them again.

The active selection is removed before stable payload paths change and published last after staging. Per-file replacements use same-filesystem rename and read-back checks. A pending journal allows interrupted updates to restore verified prior owned additions. Recovery checks running processes and destination hashes before each mutation; a newly running game or unknown edit leaves the journal pending for a later retry. Recovery backup bytes are verified again when read. Unknown recovery temporary files are preserved. Linux file/directory fsync is used; Windows relies on flushed staged files and OS rename behavior. Failure injection and process interruption are tested; hardware power-loss recovery remains unqualified on both platforms. A pre-journal staging interruption can leave inert files requiring inspection. Process scans do not provide an atomic lock against an external Steam launch.

Disable applies to the next launch; no hot unload is offered. Disable and uninstall are allowed after an unknown game update, provided owned payloads still match. They never restore stale game binaries. Unexpected edits/deletions to owned additions report a conflict instead of silently deleting/restoring them. Uninstall removes only receipt-listed unchanged additions, preserving settings, saves, unknown contents and Steam launch options.

## Bootstrap

`runtime/loader/public.h` supplies bounded ASCII configuration/inventory parsing and Windows BCrypt SHA-256 validation. The configuration includes schema, installation ID, generation, enabled state and ordered IDs. A public ownership marker takes precedence over private-launch environment values. Absent/disabled/empty/malformed selections, unsupported builds or mismatching payloads skip mod initialization while retaining version API forwarding. This does not make a modded save compatible with vanilla.

Configuration, build and payload validation happen on the worker thread before pinned native pointer reads, hook registration or mod LoadLibrary. The inventory must include exactly one runtime plan and every selected entry DLL. Required original inputs are held open against replacement for the process lifetime after successful validation. Current EXE and loaded GameAssembly paths must match the target. Loader-lock work remains limited to bootstrap selection/thread creation for installed mode; private synchronous save protection remains unchanged.

Each successful startup creates a new `MoonLab/logs/run-<timestamp>-<pid>` evidence directory and binds its initial log to installation/generation IDs. Known test switches are cleared and feature INI paths target mutable `MoonLab/settings`. A concise OutputDebugString diagnostic explains pre-initialization rejection. Errors after mod code begins still follow the runtime's fail-fast policy; no fault isolation is claimed.

## Steam and saves

Installed launch requests Steam `-applaunch 5335510`; Steam owns the real game/runtime/prefix. The short request process is never recorded as our game PID or confirmation that mods loaded. Proton requires the player to merge `WINEDLLOVERRIDES="version=n,b"` into the game's launch options while retaining existing wrappers/arguments. The loader shows the exact simple-case option in its launch plan and does not edit Steam options automatically.

Installed mode uses normal Steam saves. Before a nonempty selection, the UI/CLI requires explicit confirmation of backed-up saves or a fresh Steam profile. Consent is bound to the selected package closure and invalidated by changed packages/selections. An optional user-chosen Steam folder backup includes all files/sidecars, verifies a stable copy, records game/mod versions and hashes, and never automatically restores over progress. Game trees/ancestors and loader storage cannot be chosen as save-backup sources. The caller supplies the save origin; this is not automatic storefront-origin detection. Steam/Bottles profiles are never discovered, imported or merged by public setup. Existing private profiles remain isolated.

Native Windows gameplay, loaded-world save compatibility, Cloud/overlay/invitations and two-account co-op need separate execution evidence. Host tests and Wine synthetic startup do not establish them. No FPS improvement is inferred from avoiding game copies.

## Operations and checks

CLI: `--mode installed|private`, `--prepare`, `--plan`, `--disable`, `--enable`, `--uninstall-loader`, `--backup-steam-saves PATH` and `--normal-saves backed-up|fresh`. Mode changes are configuration only. Library removal remains separate from deployment removal; applying an empty installed selection undeploys selected mods and disables initialization.

The desktop exposes the mode selector, normal-save choice, preparation, next-launch enable/disable and receipt-aware uninstall. Creating a new private copy requires a clean source; uninstall the additive public loader first if it is already present and there is no existing private baseline.

`tests/test_installed.py` uses synthetic targets for original preservation, legacy/private behavior, aliases, ownership conflicts, running-process detection, fault recovery, updates, save backups, Steam launch semantics and cross-volume staging. `native_public_checks.c` exercises the actual C parser/guard ordering with mocked IO/crypto. `tools/check_installed_ui.py` runs only in private headless Gamescope. Current routine results remain in `artifacts/checks.json` and the build receipts; game/platform observations must be reported separately.
