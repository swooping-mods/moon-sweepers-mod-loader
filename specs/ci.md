# GitHub Actions checks and publishing

`.github/workflows/check.yml` runs on main pushes, pull requests, manual dispatch
and reusable workflow calls. Checkout/upload actions retain their reviewed
immutable pins; checkout does not persist credentials. Build/test jobs have
read-only permissions. Same-ref Checks runs cancel older unfinished runs.

The Ubuntu 24.04 job uses installed Python/LLVM, runs focused host checks, stages
exact hash-locked publisher inputs, and calls the offline Windows builder and
package verifier. No Python packages or source installers run.
`vendored/runtime-intake.md` records dependency review and scan limits.
`tools/fetch_windows_inputs.py` stages the reviewed lock; changed bytes fail.
Matching LGPL source archives remain inert distribution payloads.

Host-only checks explicitly exclude the two Linux Qt interaction cases; the local
full suite covers those. A downstream Windows Server 2022 job checks the Windows
ZIP digest, extracts into a path containing spaces, runs the bundled Python/Qt/SVG
smoke test, then runs `Mod Loader.exe --smoke-test`. Temporary application data is
used; no game starts. Only the artifact download step receives a read-only token.
Job/process timeouts bound failures.

The artifact `moon-sweepers-mod-loader-windows-x64` retains source/Windows ZIPs,
SHA256SUMS and build/check receipts for 14 days. The manual release-candidate
workflow reuses both build and Windows smoke jobs without publishing.

## GitHub Releases

`.github/workflows/release.yml` runs only on pushed `v*` tags. It calls the same
Checks workflow and waits for both jobs. Tags must exactly equal `v` plus the
package's numeric `MAJOR.MINOR.PATCH` version; mismatches fail before build/download.
Version comes from `loader/moonloader/__init__.py`, used by both builders, the
Windows checker and `tools/release.py`.

The publishing job downloads this run's tested artifact without rebuilding.
`tools/release.py` checks both build versions/filenames, the exact two-asset
checksum set, both ZIP digests and successful host/static package receipts. Only
the documented Qt host exclusions are allowed. Native Windows execution is gated
by the reusable job result, not inferred from static receipts.

Only the publishing job receives `contents: write`. It uses installed `gh` and
`GITHUB_TOKEN` to upload the source ZIP, Windows ZIP and SHA256SUMS into a draft
release for the existing tag, then publishes the completed release. Existing
releases/assets are not overwritten. A failed upload may leave a draft requiring
inspection/removal before retry. Per-tag concurrency never cancels an active
publication. No Nexus upload, catalog update or signing occurs.

See [contributing](../CONTRIBUTING.md) for the release procedure. CI configuration
alone creates no tag or release. Windows/game/co-op are distinct qualifications;
these workflows do not claim gameplay compatibility.
