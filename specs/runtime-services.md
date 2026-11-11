# Native runtime services

Native startup accepts package IDs using the SDK's lowercase alphanumeric groups separated by single hyphens, including numeric prefixes. API owner prefixes use the same package grammar; service names keep their separate letter-leading grammar.

The pinned SDK 0.7 owns public C tables, interface/package validation and
`runtime_plan.encode`. This loader owns the executable implementation. Domain
framework APIs remain ordinary independent mod packages with opaque tables.

`services.h` extends the existing owner/thread-scoped hook registry rather than
creating another callback scheduler. `MoonLab_GetRuntimeApi_v1` exposes publish,
find, typed Update subscribe and unsubscribe. V6/v7 DLLs export
`MoonLab_RuntimeServicesAbi` returning 1. Legacy v1–v5 exports share the same
hook registry and retain their existing layouts and startup order.

Both deployment modes write `MoonLab/runtime-plan.bin` with selected native
IDs, package ABIs, provided tables and selected required APIs/capacities.
Private mode journals the plan with payloads. Installed mode additionally
hashes it in the public startup inventory. The native bootstrap reads at most
2 MiB into one process-lifetime allocation and fully parses it before loading
mods. Invalid/truncated/trailing bytes, names, counts, foreign namespaces,
incompatible requirements and provider-after-consumer order reject. The actual
DLL startup list must exactly match the plan's native order.

Each dependency-ordered ModStart is one registration transaction. Required API
tables must already be committed. Publication matches the exact advertised ABI,
table byte size and capacities; the loader supplies the provider ID. Caller
names/descriptors/limit arrays are inspected synchronously and may be discarded
after publish returns. Opaque API tables and code remain resident. Uncommitted
publications are hidden. A successful ModStart that omits an advertised table
fails; APIs and raw/typed callbacks roll back together. Effective commit success
is checked by the bootstrap before proceeding to the next mod.

`find` requires exact ABI and a provider table covering the requested prefix.
Mutable startup reads/writes are bootstrap-thread-only. Once sealed, the
registry is immutable and lookup is allowed from other threads, while provider
functions define their own thread rules. No per-call allocation or automatic
provider substitution occurs. Typed frame subscriptions use existing phase,
ascending priority and stable registration order. A callback's walker is
borrowed for that Update invocation, before the original game method.

`input.h` adapts the SDK's bounded portable action registry to Windows
GetAsyncKeyState. `MoonLab_GetInputApi_v1` returns ABI 1; callers serialize access
on the game thread and provide focus/typing/menu/world/authority gates. Input
does not intercept vanilla keys. `camera.h` forwards to the canonical SDK
`camera_host.h`, sharing the same 16-claim registry and observed game dispatch
thread implementation with independent native SDKs. `MoonLab_GetCameraApi_v1` requires exact
ABI/table size. Providers root targets, capture snapshots, restore while held
and release only after successful restoration. Scene changes do not silently
expire a live claim. Game-specific camera capture remains provider-owned.

`MoonLab_RuntimeState_v1` is a separate atomic query: Pending (0), Ready (1),
Failed (2). Ready is released only after every selected native owner commits and
`seal_updates` successfully installs the shared hooks. Missing providers,
failed hooks or disabled/invalid installed startup cannot report Ready. The
40-byte runtime function table is unchanged. The source-only SDK C# connector
checks this query before managed consumer lookup; it does not publish native
tables or register callbacks from BepInEx Load. Frameworks own typed wrappers
and stricter game-thread/object admission.

`tools/build.py` verifies the runtime/state/input/camera exports and records
runtime/input/camera/readiness ABI 1 and native v6 capability in the hashed runtime receipt. Preparation
refuses a distribution without the required capability before deployment.

Verification: `tests/test_service_plan.py` builds the production C registry and
parser with separate public-SDK provider/consumer translation units under
Clang and GCC ASan/UBSan. Checks include actual typed calls, compatible prefixes,
wrong ABI/size/capacities, borrowed publication storage, duplicate/missing tables,
thread boundaries, callback rollback, sealing, 256 APIs/32 limits, every truncated
prefix and trailing bytes. `tests/test_runtime_contracts.py` exercises actual
v6 archives, deterministic plan deployment and preservation of unknown edits.
The full check gate and AMD64 cross-build remain required.

The optional managed host is described in [its spec](managed-runtime.md).
Managed API consumers require runtime API/readiness ABI 1 before copying a game;
preparation repeats this gate if selection was cached. Ordinary managed plugins
retain their existing requirements.

Limits: compiled C#/C and native registry checks qualify host interop and startup
admission. The separate b36 readiness runtime passes its original managed interop and
independent typed native-service startup diagnostic under private Steam/Proton.
Its actual initial state was already Ready; Pending timing remains host-tested.
It has not repeated the retained managed world/save qualification, and actual
framework presentation remains separate. The
workshop pins/synchronizes the reviewed core separately; its framework migration
has independent qualification. These host checks do not establish game startup,
loaded-world/save/co-op behavior, native Windows gameplay or measured speedup.


Native v7 host capability admission retains the v6 C startup marker and table
layouts. The plan parser accepts package numbers 1–7, and both v6/v7 packages
use the runtime-services marker and publication checks. Required host adapters
are checked before deployment through SDK `requires_host`/`host_capabilities`;
they do not add special framework IDs or alter owner-scoped service discovery.

The profile-bound v2 plan additionally admits native v8; v1 wire bytes remain
unchanged for legacy callers. V8 uses its distinct broker-only startup context,
the same runtime-services ABI marker, declared framework lookup scope and
typed frame registry. It refuses raw hooks. See [game adapter](game-adapter.md)
for admission, thread rules and current capability limits.

The capability change passes the complete 101-test loader gate with no skips or
exclusions. New checks cover actual v7 archive intake, missing/null/malformed or
incompatible runtime capabilities in both installed/private modes before copying
or deployment, a cached selection after
runtime replacement, and production v7 native provider/consumer calls under
Clang/GCC ASan/UBSan. The new adapter's engine behavior remains separately owned
and must qualify its final runtime bytes.


The separate `interaction.h` adapter and portable SDK interaction core implement
host capability `interaction: 1`. The runtime exports a 32-byte ABI 1 table with
ModStart registration, cached sample and actor-specific take. Coherent held and
pressed input snapshots use render-frame plus InputSystem update-step epochs.
Native interception matches actual keyboard/mouse controls, retaining unrelated
keys and controller input. InputApiV1 remains ABI 1, 64 bytes.

Generic typed frame subscriptions retain each observed walker. Input preflight
runs before Update callbacks, and take validates the local actor; interaction
registration does not filter unrelated frame observers. Unit/Sound frame-latch
admission belongs to their domain implementations. The production regression
executes two distinct walker callbacks with an input adapter active under both
sanitized compilers.

The mirrored SDK contains 37 pinned files; the workshop source pin covers 16
headers with explicit include adaptations. The complete API gate passes 44 tests;
the complete loader gate passes 102, with no skips/exclusions. The new standalone
runtime passes strict freestanding AMD64 compile/link/export checks. Its build
receipt is `artifacts/build-receipt.json`; it is not the older game-qualified
b36 runtime. Its interaction engine/world, native Windows and co-op behavior
require their own exact candidate receipts. Default workshop runtime 51549 is
preserved; no library or seed promotion accompanies this source integration.


SDK 0.6.1 limits the coherent physical snapshot to registered input bindings,
modifier families and latched captures. The native adapter also retains the
original captured control when its action is rebound. A production E-held to
Q-remap fixture fails before the fix under both compilers and passes afterward,
including the original E release epoch. Interaction/Input table ABIs and generic
frame delivery remain unchanged. With the independent native-adapter transfer,
the API snapshot is 38 files and the workshop runtime source pin is 43 files;
the native author SDK remains 37 headers. The expanded full gate passes 113 tests.

### Core cost attribution

`python3 tools/profile_runtime.py` is an explicitly selected CPU-only profile;
ordinary checks run only its small sanitized parity/count fixture. Actual loader
publication, owner commit, sealed lookup, typed Update dispatch and the public
interaction core execute in separate host/consumer translation units without
LTO. Independent digests check every batch, counting builds check actual calls,
and a deliberately wrong cached owner must reject. Timing uses separate clean
builds, one verified warmup, 15 counterbalanced trials, CPU0 affinity and both
thread CPU/monotonic wall clocks with raw p50/p95/p99 samples retained.

The checked i7-6700K/Linux fixture records 255 to 4 physical polls per interaction
epoch for 3, 16 and 128 E-bound actions; query counts stay exactly action-count
per epoch. Its portable mask/alias/release cases pass under both sanitized
compilers. The actual native-adapter fixture records 6 OS polls for its configured
E/mouse/W scenario. These are operation counts, not frame-time percentages.

The before/after clean receipts are `artifacts/runtime-profile/core-sdk06-clean/receipt.json`
and `artifacts/runtime-profile/core-sdk061-clean/receipt.json`. In the cheap
array-poll fixture, the small-case mask can add CPU work: three-action Clang
median 1.139 to 1.427 microseconds, GCC 0.863 to 0.952. At 128 actions the sampled
medians are Clang 14.691 to 8.694 and GCC 20.579 to 15.776 microseconds. These are
scoped host samples with shared-host frequency/load limits, not game speedups.
The new 256-service fixture's cached typed call medians are 1.56/2.09 ns versus
1536/1519 ns for repeated last-entry lookup (Clang/GCC); callers should keep
lookup at binding time rather than replace the bounded startup registry.

This profile omits real Win64 exception trapping/thread checks, Unity/physics,
managed transitions, rendering and display cadence. Domain callbacks use cheap
deterministic data. Publication setup excludes DLL/game startup. No unmodded,
native-only, managed-only or mixed frame-time acceptance is inferred.
