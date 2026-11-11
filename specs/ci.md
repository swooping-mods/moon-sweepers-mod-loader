# GitHub Actions checks and release channels

`.github/workflows/check.yml` runs on main pushes, pull requests, manual dispatch
and reusable workflow calls. Checkout/upload actions retain their reviewed
immutable pins; checkout does not persist credentials. Build/test jobs have
read-only permissions. Same-ref runs within each caller workflow cancel older
unfinished runs; ordinary checks, candidates and releases do not cancel one another.

The Ubuntu 24.04 job uses installed Python/LLVM, runs focused host checks, stages
exact hash-locked publisher inputs, and calls the offline Windows/Linux builders and
package verifiers. Wheels are copied as selected files, never installed. Build-only
SquashFS packages are extracted without maintainer scripts. No package resolver,
Python installer or system package install runs.
`vendored/runtime-intake.md` records dependency review and scan limits.
`tools/fetch_windows_inputs.py` stages the reviewed lock; changed bytes fail.
Matching LGPL source archives remain inert distribution payloads.
The reviewed Microsoft license DOCX inputs are vendored at unchanged hashes
because their publisher intermittently denies CI requests. Other downloads retry
transport errors up to three attempts; permission errors and changed hashes fail.

Host-only checks explicitly exclude the three Linux Qt interaction cases; the local
full suite covers those. A downstream Windows Server 2022 job checks the Windows
ZIP digest, extracts into a path containing spaces, runs the bundled Python/Qt/SVG
smoke test, then runs `Mod Loader.exe --smoke-test`. Temporary application data is
used; no game starts. Only the artifact download step receives a read-only token.
Job/process timeouts bound failures.

The headless Ubuntu runner lacks EGL. Two hash-locked Ubuntu Noble libglvnd
packages provide libEGL/GLdispatch only for CI offscreen checks, extracted by
`stage_linux_tools.py` without installers or ldconfig. Their search path is
limited to Linux build/check steps. They are not shipped as graphics drivers;
desktop users still need system graphics/display libraries.

The artifact `moon-sweepers-mod-loader-builds` retains source/Windows ZIPs,
the portable Linux x64 tar.gz, `.run` and AppImage,
SHA256SUMS and build/check receipts for 14 days. The manual release-candidate
workflow reuses both build and Windows smoke jobs without publishing.

Linux bundles its checked Python/PySide6 and desktop helper libraries. Ubuntu CI
executes the real archive launcher and both single-file formats with isolated
temporary data, verifies the bundled Qt/SVG and starter library, and exercises
AppImage without FUSE. Host-only checks still exclude the three system-PySide6
interaction cases; the local complete suite covers them. See [Linux packaging](linux-packaging.md).

## GitHub prereleases

`.github/workflows/release.yml` runs only on pushed `v*` tags. It calls the same
Checks workflow and waits for both jobs. Tags must exactly equal `v` plus the
package's numeric `MAJOR.MINOR.PATCH` version; mismatches fail before build/download.
Version comes from `loader/moonloader/__init__.py`, used by both builders, the
Windows checker and `tools/release.py`.

The publishing job downloads this run's tested artifact without rebuilding.
`tools/release.py` checks build versions/filenames, the exact five-artifact
checksum set, all archive digests and successful host/Windows/Linux package receipts. Only
the documented Qt host exclusions are allowed. Native Windows execution is gated
by the reusable job result, not inferred from static receipts.

Only the publishing job receives `contents: write`. It uses installed `gh` and
`GITHUB_TOKEN` to upload the source ZIP, Windows ZIP, all three Linux downloads
and SHA256SUMS into a draft
release for the existing tag, then publishes the completed prerelease. Both create
and edit explicitly set
`--prerelease --latest=false`, so tested candidates never become stable/latest
releases through this workflow. Existing releases/assets are not overwritten. A failed upload may leave a draft requiring
inspection/removal before retry. Per-tag concurrency never cancels an active
publication. No Nexus upload, catalog update or signing occurs.

The release title is `Moon Sweepers Mod Loader vVERSION`. Notes come from the
matching nonempty CHANGELOG.md section through the tag/version validator; raw
commit history and author-only procedures are not release notes. Release steps,
including README/version/download-link upkeep and post-publication verification,
are documented in the maintainer's ignored `.local/release-flow.md`.

See [contributing](../CONTRIBUTING.md) for the release procedure. Pushed version tags create prereleases; the explicit promotion workflow changes an
existing checked release to full/latest. Branch pushes and CI configuration
alone create no tag or release. Windows/game/co-op are distinct qualifications;
these workflows do not claim gameplay compatibility.

## Full release promotion

Normal `v*` pushes retain the prerelease/default-not-latest behavior above.
`.github/workflows/promote-release.yml` is a separate manual dispatch with an
existing numeric tag input. Its only write-scoped job calls
`tools/promote_release.py`; it does not build or upload assets. Promotion requires
a published release, a successful push-triggered `release.yml` run for that
exact tag commit and the complete six-asset inventory. The five platform/source
asset digests must match the downloaded SHA256SUMS, whose own GitHub digest is
also verified. A draft, missing files, changed digests or failed/other-tag CI
evidence blocks promotion.

The tool sets `prerelease=false` and `latest=true`, rechecks the release, verifies
asset IDs/names/sizes/digests were preserved and confirms GitHub's latest endpoint.
The manual workflow shares the tag publisher's concurrency group. The input is
passed through an environment variable and validated as a numeric version before
any remote operation. No released tag or binary changes. An older version may be
promoted explicitly; it is checked against its own tag and publishing evidence,
not the current source version. Local maintainer commands and README/channel
upkeep remain in ignored `.local/release-flow.md`.
