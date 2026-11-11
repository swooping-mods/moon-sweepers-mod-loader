# Native game adapter and profile admission

The user's forward-compatibility request treats vanilla game services and
selected framework services as the foundation a feature needs. A feature binary
should survive a changed physical implementation when its declared semantics,
ABI, table prefix and capacities remain available. This does not make an old
binary containing game addresses relocatable.

## Profile ownership

`loader/moonloader/game_profiles.json` is the reviewed source catalog. A profile
contains the complete three-code-file identity, descriptive game/backend/
architecture labels, native adapter/layout family, implemented game capability
tables and core physical bindings. Its digest is SHA-256 of the entire row as
sorted, compact ASCII JSON, excluding an added `digest` field. No version-range
comparison establishes game compatibility.

`tools/game_profiles_native.py` validates supported layout families and real
implemented table sizes, generates `runtime/loader/game_profiles.generated.h`,
and checks that the committed header remains exact. `check()` returns the
runtime receipt's `game_adapter` object; `legacy_profile_ids()` records the
current build allowed to load legacy native binaries. Production has one real
profile. There are no synthetic or speculative future-game rows in that catalog.

The compiled profile table cannot be replaced by a player-edited deployment
file. Installed and private startup hash the actual EXE, GameAssembly and
UnityPlayer, choose an exact compiled identity and retain the input handles.
The EXE and resident engine/game module paths must match the loader's game
root. The selected profile's native offsets must fit the mapped PE64 image.
These checks run before the first game-relative domain read. The private
synchronous save guard continues to inspect generic PE imports before engine
entry; it is not a game-relative binding operation.

Runtime plan v2 binds the exact selected profile ID and digest before module
startup. A changed row, stale plan, mixed three-file identity or unsupported
profile rejects. Plan v1 and native package ABIs 1–7 remain supported only for
the explicit current legacy profile; their raw tokens, object layouts and
addresses cannot acquire support from another profile's capability labels.
Core input/camera/interaction assumptions remain part of the reviewed current
adapter family. Adding a future profile requires qualifying that family or
implementing another one, rather than copying a capability map.

The three code hashes do not hash all assets, global metadata, third-party
content or saved-world semantics. Descriptive metadata version 108 is a known
profile fact, not proof that arbitrary metadata/content replacements are safe.
Each domain's binding and behavior checks remain necessary.

## ABI 8 startup and requirements

The public SDK owns `moon_sweepers/game_adapter.h`. An ABI 8 module exports the
distinct `MoonLab_ModStart_v8` entry and the existing `MoonLab_RuntimeServicesAbi` marker returning 1.
Its startup context supplies the resident game broker and a scoped runtime
service table; it receives no raw domain, module base or machine hook context.
The context is borrowed during startup. The tables it supplies or successfully
resolves remain resident; clients cache those table pointers.

Native plan v2 encodes all declared game requirements as well as framework
requirements. The game broker checks each requirement's explicit ABI, minimum
table size and limits. Its `find` function is admitted only within the current
owner's startup scope, for that owner's declared requirement. Requests cannot
ask for a larger prefix or different ABI than the declaration. Framework-only
modules may declare an empty `requires_game` map and depend transitively on
ordinary framework providers.

The supplied ABI 8 runtime table likewise permits only declared framework
lookups during startup. Its publication and frame callbacks use the existing
owner-scoped production registry. Older native/managed global runtime lookup
semantics remain unchanged. ABI 8 raw hook subscriptions and the legacy hook
shims refuse even if a caller locates them; ordinary frame subscriptions remain
available. No fallback reinterprets a legacy entry as ABI 8. Native modules are
not sandboxed: this contract governs the supplied interface, not arbitrary code
that independently locates game memory or system functions.

## Implemented clock service

`unity.clock` ABI 1 is a 16-byte typed table on AMD64. Its 32-byte sample contains
size, ABI, Unity scaled timeAsDouble, scaled deltaTime and zero-extended
unsigned 32-bit frameCount (which may wrap). The Windows binder checks zero-argument
static getter signatures and exact Int32/Double/Single return types, then caches
the known native icalls once. It performs this work only when a selected module
requires the clock; an unused capability creates no per-frame work.

Sampling requires Ready and an admitted shared Update-frame scope. The first
observed game frame establishes thread identity atomically. Foreign threads
reject before reading mutable frame scope or calling Unity; startup, outside-
frame and failed-runtime calls also reject. No reflection/name lookup, boxing
or allocation occurs in sampling. Cached clock pointers do not make calls valid
on arbitrary threads. This is a narrow implemented service, not an API for raw
objects, array layouts, physics or all existing framework bindings.

## Verification and bounds

`tools/check_game_adapter.py` compiles an original framework and feature once,
records their binary hashes, and runs the production profile selector, v2
parser, registry, frame dispatch, broker and clock binder against two synthetic
relocated engine implementations. The unchanged framework consumes game clock;
the unchanged feature consumes only the framework's elapsed-time API. It cannot
lookup an undeclared game service, another published framework service or an
undeclared larger prefix.

The executable checks cover complete truncations, stale/mixed profile identity,
unsupported capabilities/ABIs/sizes/limits, runtime readiness, getter signatures,
raw-hook refusal, missing v8 entries without legacy fallback, missing/wrong
runtime markers, foreign-thread calls and 1,000 concurrent sampling attempts
while admitted frames execute. These use ASan/UBSan and owned fake exports.
`tests/native_public_checks.c` separately exercises actual file/path/PE bounds
and hashing guard order with bounded mocked Windows IO. Strict Windows AMD64
compilation/link/export checks cover the real native DLL.

Host proof establishes the architectural boundary, not a second supported Moon
Sweepers release, actual Unity clock qualification, native Windows gameplay,
saved-world compatibility, arbitrary mod combinations or co-op. Game execution
and final packaged-product checks are separate qualifications. Results remain
in the existing verification record and ignored artifacts.
