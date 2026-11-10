# Third-party notices

The desktop UI uses host-installed [Qt for Python / PySide6](https://doc.qt.io/qtforpython-6/), under its applicable LGPL/GPL/commercial terms. Python, PySide6, Qt, Steam and Proton binaries are not bundled. A future standalone GUI package must carry the notices for its actual dependency closure.

The native bootstrap, diagnostic, application source and included SVG are original project code/artwork. `vendored/api/` is a first-party content-pinned snapshot from `swooping-mods/moon-sweepers-api`, not an external dependency acquisition. It retains the existing MoonLab ABI.

GitHub Actions are referenced by immutable revisions and remain subject to their upstream terms; they are not included in this source tree. No Nexus uploader is bundled or activated. Game binaries, extracted game assets, third-party mod assets and dependency runtimes are excluded.

No project license is assigned by this preparation. Source extraction provenance is recorded in `extraction.json`.
