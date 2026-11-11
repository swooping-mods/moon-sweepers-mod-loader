# Native author adapter

The full local transfer retains the API/loader/independent-mod split. Core
contracts and package tools remain in Moon Sweepers API. This loader also owns
the source-only, game-specific native author adapter under `sdk/native/`.
Framework implementations and domain SDKs stay in their individual mod repos.

The adapter preserves `runtime/native/` and `runtime/sdk/` relative paths so
existing independently exported mod sources compile without a workshop sibling.
It includes IL2CPP binding, local actor/input/camera/interaction connectors,
mapping, storage/wallet, static scene presentation and Steam transport helpers.
It contains no mod implementation, models, game binaries or saves.

`snapshot.json` identifies the reviewed initial working-tree export by every
file hash. `tools/check_native_sdk.py` rejects extra/missing/changed files and
symlinks, and compares copied core headers with the pinned API. The source
distribution includes this author SDK; the player Windows folder needs no SDK
installation. The workshop consumes these helpers through its explicit source
sync instead of maintaining a second independently edited production adapter.

Changes require review, updating the source lock and rebuilding affected mods.
Exact prior qualified DLLs remain separately retained; a new compilation never
inherits their gameplay proof. Host compilation and hash checks do not qualify
Unity behavior, native Windows gameplay, real co-op or performance.

SDK 0.7 also supplies `runtime/sdk/game_adapter.h`, copied from the public API
snapshot. This is the broker-only native v8 context and typed game-clock
contract. New v8 code uses logical game capabilities and framework APIs; it
does not receive the raw domain/module pointers used by the legacy bindings.
The remaining game-specific native headers still target the pinned 1.0.5
layout and do not become forward-compatible through this header addition.
The snapshot records that distinction and the new header's API provenance.
