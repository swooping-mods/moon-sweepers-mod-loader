# Game and mod compatibility

The user's forward-compatibility request treats vanilla game services and
selected mod/framework services as the effective base available to a feature.
The feature binary can stay immutable when that base preserves its declared
contracts. This is an explicit native v8 path; existing native and managed
packages keep their build-pinned behavior.

## Identity and adapter ownership

`loader/moonloader/game_profiles.json` is the reviewed catalog owned with the
native game adapter. The reader in `game_profiles.py` requires all three exact
game executable hashes, a unique profile identity, backend/architecture,
adapter ABI/layout, logical capability contracts and physical native bindings.
The SHA-256 of the complete canonical profile binds every field, including
physical bindings. Version strings are labels, never compatibility evidence.
Only the current Steam IL2CPP game profile is reviewed and shipped; synthetic
second-profile tests do not establish support for an unreleased game. Actual
runtime/gameplay qualification retains its separately recorded scope.

The compiled native runtime and its build receipt must advertise the identical
profile digest and capability inventory. Adding a catalog row alone cannot
grant startup. A runtime without the new descriptor preserves legacy admission
only for the exact current profile and matching `game_pins`; it gains no game
API and cannot host native v8. Missing/changed runtime bytes block preparation.
Legacy native v1–v7 and the current managed host remain restricted to their
reviewed current profile, including legacy packages that pinned only a subset
of the game modules.

The API owns pure package requirement evaluation and runtime-plan encoding.
The loader owns discovery, reviewed target/runtime selection, UI/CLI reports,
deployment and repeated executable checks. Native startup separately selects
the compiled profile before using build-relative pointers. Framework APIs
remain ordinary owner-qualified package services, not loader special cases.

## Player assessment

`compatibility.py` wraps the API evaluator with actual game/runtime identity and
package-integrity failures. `Service.compatibility` produces one structured
`moon-loader-compatibility/v1` report; `Service.selected`, preparation and UI
readiness consume that same assessment. Native v8 needs explicit adapter game
access, game API ABI 1, `requires_game` and advertised native package ABI 8.
Optional package game hashes are additional restrictions. Required framework
APIs, ABI/table sizes/capacities, dependencies and conflicts remain mandatory.
An unavailable optional integration is reported without inventing a provider.

Reports distinguish:

- **Requirements matched:** all declared contracts and loader admission checks
  pass. This does not qualify gameplay, saves, co-op or performance.
- **Verified:** the API evaluator can accept loader-owned evidence for the exact
  complete manifests, dependency closure, game profile, runtime and stated test
  scope. This loader currently supplies no such evidence rows. Author-written
  `verification` notes never grant this state.
- **Unknown:** the executable identity lacks an admitted reviewed game profile.
- **Incompatible:** a known requirement, runtime/integrity check or legacy build
  restriction fails. A report can explain definite incompatibility even when
  the overall game build is unknown.

The desktop's **Compatibility…** action remains available for unknown builds
while Launch/Prepare stay disabled. It describes the selected closure and the
actual provider/game API needs. Per-mod details independently assess that mod,
its required frameworks and selected optional integrations without changing any
checkboxes; unrelated selected feature conflicts do not contaminate that
individual assessment. Existing author notes are explicitly labeled separately.
Normal enable/disable/uninstall actions retain their ownership/recovery rules.

CLI `--compatibility [--game PATH]` emits the structured report without seeding
packages, saving an installation/selection, preparing files or launching a
process. Unknown reports are ordinary successful report output; inspect
`allowed` and reasons. Combining it with mutating operations is rejected.
Normal session diagnostics can still write their own logs.

## Preparation and stale decisions

UI inspection may cache a game fingerprint for display. Selection and
preparation inspect again, verify the actual runtime bytes, and compare the
full profile/runtime receipt before writing the executable plan. Installed
receipts retain the chosen profile identity/digest and exact hashes. New v8
plans carry that profile through the inventory-sealed native startup plan;
legacy plans and legacy startup remain distinct. The immutable package payload
is copied unchanged in either case.

Installed transactions continue to hash and hold the original inputs, detect
Steam changes during mutation, publish active selection last and recover
owned bytes on failure. Re-enable requires the original prepared profile;
changed game/profile data needs a new preparation. Disable/uninstall remain
available after an unknown game update and never replace original game files.

## Checks and limits

`tests/test_compatibility_player.py` covers immutable v8 preparation on two
synthetic reviewed profiles, catalog-only/stale-profile refusal, legacy subset
pins, missing v8 runtime support, runtime tampering, explicit fixture catalogs,
concurrent game changes, individual framework assessment without selection,
and read-only CLI/Qt explanations on unknown builds. Existing installed/private,
managed, dependency, checkbox/filter and scrolling regressions remain required.

These are inert host fixtures. Native broker contract tests and production
build receipts are separate gates; actual game/world/platform observations
belong to their existing verification records. No future game build, arbitrary
third-party binary or mod that embeds old addresses becomes compatible merely
because its version number or API names look similar.
