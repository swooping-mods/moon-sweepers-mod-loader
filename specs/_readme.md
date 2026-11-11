# Moon Sweepers Mod Loader specs

| Spec | Owning source | Read when |
|---|---|---|
| [Downloaded mod imports](download-imports.md) | `loader/moonloader/downloads.py`, import controls, `vendored/import-profiles/` | Changing file/folder/ZIP imports, drag-and-drop or third-party layout recognition |
| [Bundled mods](bundled-mods.md) | `vendored/mod-bundle*`, `tools/mod_bundle.py`, package seeding and platform builders/checkers | Changing the handpicked mod selection, dependency closure or distribution inputs |
| [Native author adapter](native-adapter.md) | `sdk/native/`, `tools/check_native_sdk.py` | Building mods independently of the workshop or changing shared game bindings |
| [Optional managed runtime](managed-runtime.md) | `loader/moonloader/managed.py`, private service/launch selection, `tools/build.py` | Changing explicit BepInEx attachment, managed private deployment, config/allowlist or backend availability |
| [Native runtime services](runtime-services.md) | `runtime/loader/{services,service_plan,dispatch,input,camera,interaction}.h`, native startup, `service.py`, pinned SDK | Changing v6/v7 publication, dependency startup, typed frames, input/camera adapters or runtime-plan deployment |
| [Installed-game deployment](public-deployment.md) | `loader/moonloader/public.py`, mode-aware service/launch/UI, `runtime/loader/public.h` | Changing additive public installation, recovery, enable/disable, uninstall or normal-save policy |
| [GitHub CI](ci.md) | `.github/workflows/`, `tools/fetch_windows_inputs.py` | Changing CI triggers, runtime input staging, artifacts or Windows smoke checks |
| [Windows portable packaging](windows-packaging.md) | `tools/build_windows.py`, `runtime/loader/desktop.c`, `vendored/windows-runtime.lock.json` | Changing bundled dependencies, launcher, licenses or package checks |
| [Linux packaging](linux-packaging.md) | `tools/build_linux*.py`, `tools/check_linux*.py`, `tools/linux_runtime.py`, `loader/moonloader/linux_desktop.py`, `vendored/linux-runtime.lock.json` | Changing portable Python/Qt, the single Linux entry point, `.run`/AppImage formats or their checks |
| [Desktop, bootstrap and API ownership](loader.md) | `loader/`, `runtime/`, `vendored/api/`, `tools/`, `tests/` | Changing install/launch, native dispatch, pinned API or build/check behavior |

Contributor and release instructions are in [CONTRIBUTING.md](../CONTRIBUTING.md).
