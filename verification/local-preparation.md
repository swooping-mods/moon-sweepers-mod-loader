# Local preparation verification

Date: 2026-11-10. Target: `swooping-mods/moon-sweepers-mod-loader`. Source is a selected first-party extraction, with source byte identities under `vendored/extraction.json`.

Outcome: 39 focused tests pass, with no skipped or excluded tests in the final local run. All 39 tests pass, including the three compiled native host programs and the two Qt interaction cases. Qt runs in headless Gamescope on the NVIDIA GeForce RTX 2080 Ti. Strict AMD64 bootstrap/diagnostic builds and proxy export checks pass. An extracted portable bundle passes isolated CLI/import/empty-library and API lock checks without sibling checkout access. The initial extraction omitted private exception declarations; two native checks failed, the declarations were restored, and the complete suite and build subsequently passed.

All Python files parse. Both workflow YAML files parse and reference full action commit pins with read-only repository permissions. This is local structural review, not an actual GitHub Actions run. Source hygiene review found no game/compiled/asset payloads, private absolute paths, personal remote references or common credential/private-key markers in the source tree. Generated outputs are ignored. Specs routing links resolve to existing files.

Evidence: `artifacts/checks.json`, `artifacts/qt-checks.log`, `artifacts/build-receipt.json`, `artifacts/portable-smoke.json`, `artifacts/extraction-first-check.json`. Generated evidence is retained locally under ignored `artifacts/`; it is not part of the new source repository's initial history.

Limits: no game, Wine, native Windows or co-op replay; no GitHub-hosted CI execution; no Nexus upload or URL liveness checks. The loader's current-game adapter and legacy ABI are preserved, not newly gameplay-qualified. No external dependencies were downloaded, organization repositories/remotes created, pushes performed or PRs opened.
