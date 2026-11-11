# Changelog

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
