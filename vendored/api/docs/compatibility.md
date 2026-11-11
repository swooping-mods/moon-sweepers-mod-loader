# Game and framework compatibility

A feature can depend on the vanilla game adapter, ordinary framework mods, or
both. The loader evaluates that complete selected base. A matching version
string or an author's “verified” description is not execution evidence.

Native v1–v7 and managed packages retain exact game pins and existing startup
contracts. They may contain raw offsets, tokens or generated bindings. The
loader must not forward them merely because another profile offers similarly
named services; actual legacy profile support is supplied per backend.

## Native v8 packages

V8 exports `MoonLab_ModStart_v8(const MoonModContextV8 *)`. Its broker-only context
supplies the existing public runtime table and a game adapter, with no IL2CPP
domain, module base or machine hook context. A compatibility declaration is:

```json
{
  "kind": "native",
  "abi": "MoonLab_ModStart/v8",
  "runtime_api_abi": 1,
  "game_access": "adapter",
  "game_api_abi": 1,
  "game": {"id": "moon-sweepers", "appid": "5335510"},
  "requires_game": {"unity.clock": {"abi": 1, "min_size": 16}},
  "claims": []
}
```

The remaining ordinary fields and payload hashes are still required.
`requires_game` is an explicit map of up to 64 logical capabilities, each with an
exact positive ABI, minimum table prefix (up to 65536 bytes) and optional bounded
integer capacities. Names match `[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+`, up to 160
characters. An empty map is valid for a feature using only framework services.

Framework requirements still use `requires_apis` and ordinary `requires`
dependencies. Providers retain their own versions, ownership and contracts.
The whole dependency closure must fit: a portable feature cannot make a pinned
framework portable. An absent optional provider is omitted, while a selected
optional provider must satisfy its contract. Vanilla and framework offers keep
their provenance; publishing a similarly named mod API cannot satisfy a vanilla
requirement.

V8 may additionally declare `game.hashes`. Those are extra exact restrictions,
never an ignored tested-on hint. V8 cannot declare raw exclusive/shared hooks,
vehicle/late-update roles or a hook framework marker. Semantic hooks need their
own reviewed capability. Optional v8 `requires_host` retains exact ABI checks.
Older validators reject v8 rather than silently ignoring its mandatory fields.
Existing DLLs need an actual author port/rebuild to this entry and access
contract; relabeling a legacy manifest does not make its binary portable.

## Typed game access

Include `moon_sweepers/game_adapter.h`. Find a declared capability during this
owner's startup scope, cache the typed pointer, and obey its call/thread rules.
The requested ABI must match the declaration, and the requested prefix cannot
exceed its declared minimum. The v8 context's runtime table has the unchanged
ABI1 layout but scopes `find` to this owner's declared `requires_apis` during
startup, with the same ABI/prefix restriction. Cache framework tables as well;
later lookup and undeclared provider APIs return null. Existing global legacy/
managed runtime lookup is unchanged. Ordinary publication/frame ownership stays.

```c
#include "moon_sweepers/game_adapter.h"
static const MoonGameClockV1 *clock_api;
static void on_frame(void *opaque_walker, void *user) {
    (void)opaque_walker; (void)user;
    MoonGameClockSampleV1 sample = {sizeof(sample), MOON_GAME_CLOCK_ABI, 0, 0, 0};
    if (clock_api->sample(&sample)) {
        /* Consume scaled time/delta and frame here. */
    }
}
__declspec(dllexport) int MoonLab_RuntimeServicesAbi(void) { return 1; }
__declspec(dllexport) int MoonLab_ModStart_v8(const MoonModContextV8 *context) {
    if (!moon_mod_context_v8_valid(context)) return 0;
    clock_api = context->game->find("unity.clock", 1, sizeof(*clock_api));
    if (!moon_game_clock_valid(clock_api)) return 0;
    MoonFrameSubscriptionV1 frame = {sizeof(frame), MOON_PHASE_NORMAL, 0, on_frame, 0};
    return context->runtime->subscribe_frame(&frame) != 0;
}
```

`unity.clock` ABI 1 is a 16-byte AMD64 table with a 32-byte sample. Callers
initialize sample size/ABI. `sample` returns zero without calling Unity outside
an admitted game-thread frame. Success supplies Unity scaled time and `deltaTime`
as doubles, plus zero-extended unsigned32 `frameCount` (which can wrap). The
adapter may widen the engine's single-precision time; the C storage type does
not promise additional source precision or a particular retained Unity getter.
Existing frame callbacks carry a borrowed walker for legacy consumers; v8
adapter-only consumers treat it as opaque and never dereference game internals.
The clock contract does not imply other game services.

Native DLLs are not sandboxed. V8 is an authoring/runtime contract, not a binary
proof that arbitrary code never calls another Win32 export.

A framework-only feature sets `requires_game: {}`, declares a dependency such as
`requires: ["another-library"]` and a matching requirement such as
`{api: "another-library.catalog", abi: 1, min_size: 32}` in `requires_apis`.
Its startup binds `context->runtime->find("another-library", "catalog", 1, 32)`
and casts/caches the result using that framework's own public header. It needs no
clock or dummy vanilla capability. The same feature binary can use an updated
compatible provider on another reviewed game profile; the provider itself must
also satisfy admission and preserve its declared semantics.

## Reports and admission

`moon_mod_api.compatibility.evaluate` takes manifests, selected IDs and observed
game hashes, with explicit loader-owned targets:

- `game_profile`: reviewed row with `id`, `digest`, all three original game
  hashes and capability offers. Every field, including bindings/layouts and
  presentation, participates in the canonical digest except `digest` itself.
- `game_adapter`: `{abi: 1, profiles: {id: {digest, capabilities}}}` from the
  actual native receipt. Profile digest and capability offers must match.
- Actual runtime availability, API/readiness ABIs, host capabilities,
  `native_package_abis` (ABI strings) and `legacy_profile_ids` (backend to IDs).

`profile_digest` and `validate_profile` establish complete reviewed-row identity;
they do not supply default game hashes or authenticate an arbitrary caller's
catalog. The loader owns review and integrity. `allowed` is authoritative.
Status is `unknown` without a reviewed target, `incompatible` when requirements
fail, and `requirements-matched` when the complete selected base fits. Coded
per-mod reasons and requirement rows expose provider version, optional status,
required/actual ABI, size, capacities and satisfaction. `packages.resolve` repeats
admission with the same target arguments before preparation.

`verified` requires trusted loader evidence with explicit `success: true`, binding every selected canonical
manifest digest (including payload hashes), full selection digest, profile
digest, runtime binary SHA-256, scope (`startup`, `world` or `co-op`) and record
identity. Provider, payload, physical binding or runtime changes invalidate that
match. Author description/verification text is never read as evidence. Verified
startup is not a world/multiplayer claim. No future-release qualification or
automatic online adapter acquisition is implied.
The loader must validate all gates for the stated scope before constructing a
successful qualification row. Failed/incomplete diagnostic receipts do not
qualify, even if every identity matches. At most 128 evidence rows are accepted;
an oversized evidence list does not grant verified status.

Omitted legacy resolver target arguments retain old offline inspection behavior.
Player loaders must supply explicit actual targets and legacy backend policy;
an omitted check is not support. V8 always needs an advertised native ABI.
