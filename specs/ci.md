# GitHub Actions checks and portable artifacts

`.github/workflows/check.yml` runs on main pushes, pull requests and manual
workflow dispatch. Actions are pinned to immutable revisions; checkout does not
persist credentials. Workflow permissions are read-only. Same-ref runs cancel
older unfinished runs.

The Ubuntu 24.04 job uses the runner's installed Python/LLVM, runs focused host
checks, explicitly stages exact hash-locked publisher inputs, then calls the
offline portable builder and package verifier. It does not install Python packages
or run source installers. `vendored/runtime-intake.md` records the reviewed scope
and scan limits. `tools/fetch_windows_inputs.py` is the explicit network step;
changed bytes fail rather than silently updating dependencies. Library source
archives remain unexecuted, inert license-compliance payloads.

Host-only checks explicitly exclude the two Linux Qt interaction cases because
PySide6 is not installed on that job. The local required full suite still covers
them. A downstream Windows Server 2022 job verifies the artifact ZIP digest,
extracts it into a path containing spaces, and runs the bundled Python/Qt/SVG
smoke test and the actual `Mod Loader.exe --smoke-test`. The offscreen Qt platform
is bundled for these tests. Temporary application data is used and no game starts.
The artifact download step alone receives a read-only GitHub token; the runtime
execution steps do not receive that token. Job/process timeouts bound failures.

The artifact `moon-sweepers-mod-loader-windows-x64` retains source and Windows ZIPs,
SHA256SUMS, build receipts and check receipts for 14 days. Artifacts are candidates;
check that both jobs passed before using a download. No GitHub release, Nexus
upload, catalog update or signing happens. Gameplay/co-op are separate gates.

The manual `release-candidate.yml` workflow builds and statically verifies the same
portable package and stores a candidate artifact without publication. Its host
checks have the same explicit Qt exclusions. Windows execution qualification
belongs to the main Checks workflow.
