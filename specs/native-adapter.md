# Native author adapter

The full local transfer retains the API/loader/independent-mod split. Core
contracts and package tools remain in Moon Sweepers API. This loader also owns
the source-only, game-specific native author adapter under `sdk/native/`.
Framework implementations and domain SDKs stay in their individual mod repos.

The source-pinned helpers below remain the legacy direct-game path. New ABI8
modules can instead use the public SDK's broker-only startup context and typed
game/framework tables; see [native game adapter](game-adapter.md). Existing
compiled modules do not become forward-compatible by changing their labels.

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

The pinned native `gameplay.h` integer/Boolean readers and reflection
`dnumber`/`dvector` reject failed invocation, absent boxes and absent unboxed
payloads before dereferencing/copying. Failure returns the historical zero value
and preserves/sets the caller's sticky `ok=0`. They never turn an already failed
query back into a successful observation. Nonnull `ok` remains the caller contract.
Unity `su_number`/`su_vector` keep their original zero defaults;
`su_number_checked`/`su_vector_checked` additionally return success/failure and
preserve the supplied output on failure. A null output refuses before invocation.
`su_alive` and `su_rotation` also guard payloads, preserving false/identity
defaults. These compile-time helper changes add no service ABI or game capability.

Null checks do not validate a boxed type or payload size; the existing exact
binding and Unity-thread admission remain prerequisites. Finite values, allowed
ranges, occupancy/authority and other business policy remain caller-owned. In
particular, a readable zero is not an error and a nonfinite float still reaches
the caller for its existing policy to handle. Vehicle Statistics/caller fixes are
owned separately and are not supplied by these shared helper changes.

`tests/native_unbox_checks.c` includes the actual three SDK headers and injects
missing boxes, null payloads, exceptions with nonnull boxes, sticky query failure,
valid zero/negative/Boolean/vector/quaternion values and nonfinite transport. It
checks legacy defaults, checked-output preservation and refused null outputs.
The fixture's Windows-only unused functions are discarded by the host runner;
no game library or managed runtime is loaded. Neither this new fixture nor its
runner has been compiled/executed in the source-only workstation pass. Later run
`PYTHONPATH=tests:tools python3 -m unittest test_native_unbox.NativeUnboxHostChecks`,
then relocated Windows source compilation, affected consumer rebuilds and the
normal native/runtime gates in an admitted execution window. Exact old DLL
qualification does not transfer to rebuilt headers or consumers.

SDK 0.7 also supplies `runtime/sdk/game_adapter.h`, copied from the public API
snapshot. This is the broker-only native v8 context and typed game-clock
contract. New v8 code uses logical game capabilities and framework APIs; it
does not receive the raw domain/module pointers used by the legacy bindings.
The remaining game-specific native headers still target the pinned 1.0.5
layout and do not become forward-compatible through this header addition.
The snapshot records that distinction and the new header's API provenance.
