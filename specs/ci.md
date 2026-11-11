# GitHub Actions checks and prerelease publishing

`.github/workflows/check.yml` runs on main pushes, pull requests, manual dispatch
and reusable workflow calls. Checkout/upload actions retain their reviewed
immutable pins; checkout does not persist credentials. Build/test jobs have
read-only permissions. Same-ref runs within each caller workflow cancel older
unfinished runs; ordinary checks, candidates and releases do not cancel one another.

The Ubuntu 24.04 job uses installed Python/LLVM, runs focused host checks, stages
exact hash-locked publisher inputs, and calls the offline Windows/Linux builders and
package verifiers. No Python packages or source installers run.
`vendored/runtime-intake.md` records dependency review and scan limits.
`tools/fetch_windows_inputs.py` stages the reviewed lock; changed bytes fail.
Matching LGPL source archives remain inert distribution payloads.

Host-only checks explicitly exclude the three Linux Qt interaction cases; the local
full suite covers those. A downstream Windows Server 2022 job checks the Windows
ZIP digest, extracts into a path containing spaces, runs the bundled Python/Qt/SVG
smoke test, then runs `Mod Loader.exe --smoke-test`. Temporary application data is
used; no game starts. Only the artifact download step receives a read-only token.
Job/process timeouts bound failures.

The artifact `moon-sweepers-mod-loader-builds` retains source/Windows ZIPs,
the Linux x64 tar.gz,
SHA256SUMS and build/check receipts for 14 days. The manual release-candidate
workflow reuses both build and Windows smoke jobs without publishing.

Linux uses installed Python/PySide6. Ubuntu CI checks archive hashes and runs the
actual Linux launcher with --help in a path containing spaces; --gui is a separate
local smoke using installed PySide6. The Linux check receipt records that hosted
GUI limit. See [Linux packaging](linux-packaging.md).

## GitHub prereleases

`.github/workflows/release.yml` runs only on pushed `v*` tags. It calls the same
Checks workflow and waits for both jobs. Tags must exactly equal `v` plus the
package's numeric `MAJOR.MINOR.PATCH` version; mismatches fail before build/download.
Version comes from `loader/moonloader/__init__.py`, used by both builders, the
Windows checker and `tools/release.py`.

The publishing job downloads this run's tested artifact without rebuilding.
`tools/release.py` checks both build versions/filenames, the exact three-archive
checksum set, all archive digests and successful host/Windows/Linux package receipts. Only
the documented Qt host exclusions are allowed. Native Windows execution is gated
by the reusable job result, not inferred from static receipts.

Only the publishing job receives `contents: write`. It uses installed `gh` and
`GITHUB_TOKEN` to upload the source ZIP, Windows ZIP and SHA256SUMS into a draft
release for the existing tag, then publishes the completed prerelease. Both create
and edit explicitly set
`--prerelease --latest=false`, so tested candidates never become stable/latest
releases through this workflow. Existing releases/assets are not overwritten. A failed upload may leave a draft requiring
inspection/removal before retry. Per-tag concurrency never cancels an active
publication. No Nexus upload, catalog update or signing occurs.

See [contributing](../CONTRIBUTING.md) for the release procedure. Only pushed version tags trigger publication; branch pushes and CI configuration
alone create no tag or release. Windows/game/co-op are distinct qualifications;
these workflows do not claim gameplay compatibility.
