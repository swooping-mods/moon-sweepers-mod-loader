# Building API snapshot milestone

Objective: consume the shared building API and cross-mod saved-ID conventions
while keeping the existing loader/runtime boundary.

Decisions: pin first-party API 0.2.0 as an explicit content snapshot. Preserve
MoonLab ABI names, package compatibility and saved IDs. Add building conflict and
framework-range preflight through the existing API reexport; bundle no gameplay
mod DLL. Keep concurrent Windows packaging work separate.

State: 18-file snapshot verified; 41 focused host/native/Qt checks pass in
headless Gamescope, with no skips/exclusions. The portable source build passes.
The two new loader tests exercise real package selection, duplicate-ID rejection
and rejection of legacy 224-only framework metadata. The development project
separately proves native 225/256/384 save/reload alongside old kind 193.

Next action: this API integration is complete locally. Future source changes
require a reviewed snapshot refresh. No feature push/PR/Nexus publication, game
launch or co-op qualification was performed in this repository. Earlier private
baseline publication and current Windows packaging have their own handoffs.

Evidence: `verification/building-api-0.2.0.md`, `vendored/api/snapshot.json`,
`tests/test_build_items.py`, ignored `artifacts/{building-api-checks.json,building-api-check.log,building-api-build.log}`.
