# Portable Linux components

The application has no assigned project-wide license. Third-party terms remain
applicable to the components distributed here.

- CPython 3.13.18 uses the Python/CNRI/PSF terms. Its matching full standalone
  build provides the original dependency texts in
  `standalone-python/python/licenses/` and its `PYTHON.json` component metadata.
  The runtime's standard-library LICENSE.txt is retained too. Not every component
  named by that full-build metadata is shipped: pip, Tk and unused test modules
  are excluded from the selected application payload.
- PySide6, Shiboken and the selected Qt 6.8.3 libraries use LGPLv3 and their
  original third-party terms. Exact Qt Base, SVG, Wayland and PySide source
  archives are supplied in `sources/`; their original license/attribution files
  are retained under `upstream/`.
- ICU 73.2 retains `ICU-73.2-LICENSE`. XCB/XKB desktop helper packages retain their
  original package copyright/license texts under `desktop/`.
- The Type-2 AppImage runtime retains its MIT notice in the runtime source
  archive's extracted `upstream/` directory. FUSE, SquashFUSE, musl, mimalloc, zstd
  and zlib source/notice archives accompany it. The runtime source retains its
  build scripts and FUSE patches. The SquashFS packaging executable is build-only.

The shared Python/Qt libraries remain replaceable under `.runtime/`; the loader
does not restrict modification or debugging of them. Use the source ZIP's build
tools to repackage an altered runtime into the archive, `.run` or AppImage.
`linux-runtime-manifest.json` records the exact original distribution inputs and
selected wheel members. Sources accompany recipients directly rather than
depending on a future source offer.
