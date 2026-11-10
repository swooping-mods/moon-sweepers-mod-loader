# Building API snapshot integration — 2026-11-10

Updated the first-party snapshot from API 0.1.0's 11 files to API 0.2.0's 18
files, including the building headers, stable ID registry, author conventions and
shared validator. The runtime remains owned by the separate Build Menu Framework
mod; no gameplay mod/DLL was bundled with this snapshot update.

The loader's existing `moonloader.packages` reexport now rejects duplicate
declared saved building kinds and providers requiring IDs beyond the selected
framework capability. Existing legacy framework metadata defaults to 224.
Package ordering preserves explicit IDs rather than deriving them from selected
or startup order.

`tools/check_snapshot.py` passes for all 18 content hashes. `python3 tools/check.py`
in headless Gamescope: **41 tests passed**, no skips/exclusions, including the
two new real-reexport selection cases. `python3 tools/build.py` passes and emits
the portable source candidate using the existing installed toolchain. This
verification does not qualify concurrently authored Windows packaging work.

Evidence: ignored `artifacts/building-api-checks.json`, `artifacts/building-api-check.log`,
`artifacts/building-api-build.log`, `artifacts/building-api-snapshot-upgrade.json`
and `artifacts/building-api-final-snapshot.json`. No game, native Windows gameplay,
co-op, new dependency acquisition or feature publication occurred here. Native
save/reload evidence belongs to the development project's
`verification/2026-11-10-build-api-384.md`.
