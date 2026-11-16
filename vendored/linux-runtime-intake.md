# Portable Linux runtime inputs

`linux-runtime.lock.json` pins the selected CPython 3.13.18 standalone build,
PySide6/Shiboken 6.8.3 wheels, matching notices/source archives, desktop helper
libraries and build-only SquashFS tool. Builds copy selected files and never run
wheel installers, package-maintainer scripts or a dependency resolver.

Python and AppImage release digests were verified through their publishers'
GitHub asset metadata; wheel digests came from PyPI's version metadata. Ubuntu
package hashes were checked against the main/universe Noble indexes and their
SHA-256 entries in InRelease, whose Ubuntu Archive signature was verified using
the existing trusted Ubuntu keyring. Sources and original license texts accompany
the replaceable runtime components; no project license is introduced.

The actual selected executable distribution was staged inertly. Standard-library
Python startup, PySide/Shiboken initialization, plugin/library selection, native
ELF dependency surfaces, package paths and original build/runtime scripts were
reviewed. Static triage covered the materialized execution closure with no
remaining coverage gaps. Its leads are ordinary standard-library network/process
APIs, native binaries and upstream notice/source references, not extra application
startup actions. No candidate installer or upstream CI script was executed.

ClamAV 1.5.4, database 28158 dated 2026-10-19, scanned the final selected raw files
and packaging runtime/tool with zero infections. Signatures were 23 days old;
this limits malware screening and was not silently refreshed. The initial broad
compressed-archive pass timed out and had static archive-budget gaps; it is not
counted as full coverage. Follow-up inspection/scanning used the exact materialized
runtime files instead. Publisher-integrity and manual review complement, rather
than replace, that bounded scan. Private manifests, scan output and dispositions
remain in the maintainer's ignored intake records.

Decision: eligible for the explicitly requested portable builds and bounded
launcher/Qt tests with private data, no game or credentials. This is not a claim
that every upstream source file or arbitrary library use was qualified. The build
and release checks bind the delivered archive and both single-file formats to
the reviewed input hashes and actual runtime smoke checks.

The upstream AppImage continuous asset is replaceable, so its exact 944,632-byte
runtime is retained under `vendored/appimage/` with its MIT notice. Its source
commit is `fedfad51acc2860b2916a1eef32ba4a500ff31ef`; original component source
archives and FUSE patches/build scripts accompany the application. Build-only
SquashFS packages are not application payloads. See [component terms](LINUX-LICENSES.md).

## CI-only graphics loader

Ubuntu Noble libegl1 and libglvnd0 1.7.0-1build1 are locked as ci-library inputs.
Their publisher hashes come from the retained signature-verified main Packages
index. Packages were unpacked without installation; control/triggers, ELF
dependencies and copyright were inspected. ClamAV 1.5.4 (signatures 2026-10-19,
23 days old) scanned the packages and materialized members: 20 files, zero
detections. Static triage had 12 reviewed container/native/license-URL leads,
zero gaps. These MIT runtime libraries support only headless CI Qt checks and
are not delivered or used to qualify real graphics drivers. No ldconfig runs.

## Complete offscreen CI suite

November 16: the existing PySide6 Essentials 6.8.3 Linux wheel also supplies
`PySide6/QtTest.abi3.so` (SHA-256
`dad7a440dd93c550c0dca8e6d4e7a6046d5f8f75b304ca71b4e1563216346252`)
and `PySide6/Qt/lib/libQt6Test.so.6` (SHA-256
`cda690965ca0b18b20b9c280eb3c55a8e05cd1ad7e49fa6dbe462406b03b57dd`).
Their ELF dependencies and library-relative paths use the existing reviewed
Qt/PySide/Shiboken and system library closure. Matching QtBase testlib event
helpers/environment handling and PySide QtTest binding imports were inspected.
ClamAV 1.5.4, database 28179 dated November 10 (six days old), scanned both
materialized files with zero detections; static triage found two expected ELF
leads and zero gaps. No signatures were refreshed.

Eligible use: load these exact members only in the disposable extracted Linux
runtime to run the project's complete offscreen host/Qt tests with temporary
application data and no game. The wheel lock and downloadable runtime selection
are unchanged; QtTest is not shipped, installed or resolved as a new dependency.
Private scan/review receipts remain under ignored `.local/`. Native provenance
is not an independent reproducible-build proof.
