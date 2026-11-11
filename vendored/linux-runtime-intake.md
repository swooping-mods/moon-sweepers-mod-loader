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
