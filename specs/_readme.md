# Moon Sweepers Mod Loader specs

| Spec | Owning source | Read when |
|---|---|---|
| [GitHub CI](ci.md) | `.github/workflows/`, `tools/fetch_windows_inputs.py` | Changing CI triggers, runtime input staging, artifacts or Windows smoke checks |
| [Windows portable packaging](windows-packaging.md) | `tools/build_windows.py`, `runtime/loader/desktop.c`, `vendored/windows-runtime.lock.json` | Changing bundled dependencies, launcher, licenses or package checks |
| [Desktop, bootstrap and API ownership](loader.md) | `loader/`, `runtime/`, `vendored/api/`, `tools/`, `tests/` | Changing install/launch, native dispatch, pinned API or build/check behavior |

[Repository split](../design/repository-split.md) and [Nexus rollout](../design/nexus-release.md) are design proposals. `verification/local-preparation.md` owns the focused evidence summary.
