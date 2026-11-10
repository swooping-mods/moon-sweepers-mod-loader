# Windows runtime intake provenance

Scope: the exact publisher files in `windows-runtime.lock.json`, and only the
explicit selected runtime wheel members. PyPI wheel digests were compared with
publisher JSON; all acquired input SHA-256 identities and HTTPS URLs are locked.
Publisher signatures were not independently verified. Do not update this lock
without a new external-intake review. Re-fetching the same bytes is permitted by
this review; `tools/fetch_windows_inputs.py` stages without activation and rejects
changed bytes before replacing its destination. Packaging also rechecks hashes.

Review on 2026-11-10: archive paths/types, Python isolated paths, wheel metadata,
PySide/Shiboken initialization code, native AMD64 import closure, LGPL source SPDX
headers, source manifests and Microsoft runtime/redistribution documents. No setup,
installer, package build backend or source build/test hook runs. The runtime uses
only Qt Core/Gui/Widgets/Svg, Windows/SVG plugins and the offscreen test platform.
The source archives are inert LGPL source-access payloads. Libraries remain
replaceable and the lock is enforced at build time only.

Final selected-runtime static scan: zero coverage gaps; expected PE images,
license URLs and dormant developer helpers were manually reviewed. ClamAV 1.5.4
scanned 69 selected runtime files with exit 0 and no detections. The additional
qoffscreen.dll CI-path review found one expected PE lead, zero static gaps, only
bundled/system imports, and ClamAV exit 0 with no detections. Signatures were DB
28158 dated 2026-10-19 and stale; no refresh was performed.

PySide/QtSvg source and Microsoft document scans passed. QtBase's full-source
archive scan hit MaxScanTime after 347.597 seconds and 338.97 MiB scanned, following
an earlier size-limit scan. This is a remaining full-source antivirus coverage
limit, not a malware signature; do not describe the entire bundle as antivirus
cleared. The unmodified source is reference/distribution data and is never
executed. The broad archive static scan had budget gaps, resolved for the actual
reachable runtime by materializing and rescanning selected files. Unselected tools
and source/test entrypoints remain outside the runtime execution scope.

Allowed use: offline packaging of these exact inputs, host checks, and bounded
bundled-runtime/launcher smoke tests on disposable GitHub-hosted Windows runners.
Smoke tests use temporary application data, have timeouts, never start a game and
receive no repository credentials. GitHub's maintained runner supplies LLVM/Python
build tools; existing pinned checkout/upload actions are retained without updates.
CI downloads need no package installer and no dependency resolution. Raw local
scan logs remain private; the repository preserves this sanitized disposition.
