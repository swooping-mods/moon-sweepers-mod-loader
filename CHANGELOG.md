# Changelog

## 0.3.0 — Unreleased

- Add a compatibility report for the selected game, mod requirements and framework providers, with explicit reasons for unknown or incompatible targets.
- Introduce an opt-in native v8 game-adapter contract so new mods can use stable typed capabilities while build-specific bindings stay in the reviewed adapter.
- Bind reviewed game profiles to native runtime support and preparation; preserve exact-build checks for existing native and managed packages.

Only the existing Steam 1.0.5 game profile is qualified input. Synthetic multi-profile checks demonstrate the new contract; they do not establish compatibility with a later game release. Requirements matching and scoped gameplay verification remain separate.

## 0.2.1 — 2026-11-11

- Check Steam Proton launch options before starting installed mods, preventing a successful Steam request from silently starting the game without its native mod bootstrap.
- Add **Steam setup…** with current/proposed options and an explicit **Apply required launch options** action. Quit Steam before applying; existing DLL overrides, supported wrappers and game arguments are preserved, and the previous configuration is backed up and verified.
- Missing, ambiguous or unsupported Steam settings provide manual setup guidance. Windows keeps its normal launch arguments without Proton environment syntax.
- Save rotating informational/error logs, Python/worker/Qt tracebacks, available fatal-crash diagnostics and bounded launch log snapshots. **Open logs** refreshes attributable native bootstrap logs; Steam request completion remains distinct from game startup or crash confirmation.
- Include the supported BepInEx adapter/runtime in release and prerelease downloads. Native and BepInEx mods can use **Existing Steam game** without a game copy; private copies remain optional. MarsSweepers remains a separate user-supplied mod.
- Harden the MarsSweepers compatibility companion with bounded packet/decompression handling, initial-state retries, receive recovery, host version/weather checks and username-safe diagnostic commands. The original Mars DLL and wire protocol remain unchanged; real co-op is not yet qualified.

The AppImage startup failure was reproduced with the released nine-mod payload in an isolated Linux/Proton game copy: no mods initialized without the version DLL override; all nine initialized with it. The maintained BepInEx host also passes Mars solo movement/save/reload/shutdown in private and installed modes, plus installed enable/disable/uninstall checks. These tests use a private Proton bridge instead of changing personal Steam configuration or saves. Native Windows gameplay and real co-op remain unqualified. Gamescope crashes during teardown after successful Unity shutdown; the compositor failure is separate from the game checks.

## 0.2.0 — 2026-11-11

- Windows portable ZIP and Linux portable archive, `.run` and AppImage downloads. Python and Qt are included in the desktop builds.
- Nine starter packages: Squishy Plushie, Futuristic Courier, Power Poles, F4 Debug Menu and their five required frameworks. New libraries start unchecked; existing selections are preserved.
- Add several mod files, import an extracted folder, or drag downloads onto the loader. Supported inputs include `.msmod`, package ZIPs and the reviewed MarsSweepers 0.6.1 layout.
- Additive installation into the existing Steam game, with save-backup acknowledgement, owned-file recovery and Proton launch guidance. Private game copies remain available.
- Current native runtime services, input, camera, interaction and dependency checks for supported v6/v7 packages.
- Tag-triggered CI builds and checks every platform artifact, exercises the Windows EXE and all Linux entry points, then publishes the checked files with SHA-256 checksums.

The game is not included. MarsSweepers import requires its separate supported BepInEx runtime and Private game copy mode; that runtime is not bundled. This release targets the pinned Moon Sweepers Steam Windows x64 IL2CPP 1.0.5 build. Loader/package checks do not qualify native gameplay, saves or real co-op for every selected mod combination.

## 0.1.0

- Initial Windows and source prerelease with local mod-package installation and private game copies.
