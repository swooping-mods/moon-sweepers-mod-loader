# Native runtime services

Native startup accepts package IDs using the SDK's lowercase alphanumeric groups separated by single hyphens, including numeric prefixes. API owner prefixes use the same package grammar; service names keep their separate letter-leading grammar.

The pinned SDK 0.4 owns public C tables, interface/package validation and
`runtime_plan.encode`. This loader owns the executable implementation. Domain
framework APIs remain ordinary independent mod packages with opaque tables.

`services.h` extends the existing owner/thread-scoped hook registry rather than
creating another callback scheduler. `MoonLab_GetRuntimeApi_v1` exposes publish,
find, typed Update subscribe and unsubscribe. V6 DLLs export
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

`tools/build.py` verifies the three new exports and records runtime/input/camera
ABI 1 and native v6 capability in the hashed runtime receipt. Preparation
refuses a distribution without the required capability before deployment.

Verification: `tests/test_service_plan.py` builds the production C registry and
parser with separate public-SDK provider/consumer translation units under
Clang and GCC ASan/UBSan. Checks include actual typed calls, compatible prefixes,
wrong ABI/size/capacities, borrowed publication storage, duplicate/missing tables,
thread boundaries, callback rollback, sealing, 256 APIs/32 limits, every truncated
prefix and trailing bytes. `tests/test_runtime_contracts.py` exercises actual
v6 archives, deterministic plan deployment and preservation of unknown edits.
The full check gate and AMD64 cross-build remain required.

Limits: no managed host or native/managed service bridge is implied. The
workshop pins/synchronizes the reviewed core separately; its framework migration
has independent qualification. These host checks do not establish game startup,
loaded-world/save/co-op behavior, native Windows gameplay or measured speedup.
