# Desktop application

Run from the repository root with `./run.sh`, or use `Start-Mod-Loader.cmd` on Windows. Python 3.11+ and host PySide6 6.x are required. No dependencies are downloaded by the launcher.

Use `--no-launch --data local/review` for an isolated review. The handpicked bundle seeds Squishy Plushie, Futuristic Courier, Power Poles, F4 Debug Menu and their five dependencies, initially unchecked. Existing versions and checkmarks are preserved.

Use **Add mods…** for one or several `.msmod`/supported ZIP downloads, **Add folder…** for an extracted mod, or drag files/folders onto the window. Unpacked packages retain their manifest checksums. The complete MarsSweepers 0.6.1 folder/ZIP is recognized; running it still needs the supported BepInEx runtime in private-copy mode. The root README describes the native build, deployment/profile policy and qualification limits.
