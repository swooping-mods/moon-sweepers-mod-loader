# Forward compatibility

## Human input

The 2026-11-11 request treats the vanilla game and selected mod frameworks as
one base that feature mods build on. An unchanged mod should be able to work
on another known game build when its actual requirements remain compatible.
The loader should explain this to a player before preparation or launch.

## Architecture

Build identity, adapter support, dependency contracts and execution evidence are
separate facts. A hash identifies bytes; a version label explains them. Neither
alone proves that a mod works. The loader evaluates the entire selected closure,
including ordinary framework packages, against a reviewed exact-hash game
profile and the actual runtime's supported adapter profiles.

The core API owns the package/ABI contracts and pure evaluator. The loader owns
reviewed game profiles, native implementations of semantic game services,
deployment admission and player reports. Frameworks remain independently owned
mods that publish versioned domain interfaces. A feature can depend only on a
framework, with no direct vanilla-game requirements: the framework's dependency
closure supplies the game requirements. Optional framework integrations retain
the existing explicit selected-provider rules.

New native v8 packages opt into an adapter-only context, receiving a game-service
broker and the existing runtime registry rather than game module/domain pointers.
Logical game capabilities specify ABI, minimum table size and capacities;
framework interfaces retain their provider-qualified requirements. Providers and
consumers bind once, cache typed tables and respect thread/object lifetimes.
The v8 broker admits only declared game/framework lookups during startup; raw
machine-hook subscriptions remain on the legacy path. This is an enforceable
contract on the supplied interfaces, not a sandbox for arbitrary native code.
The initial game service is a typed Unity clock. Additional domain services
require their own explicit semantics and implementation/qualification.

The runtime selects a compiled reviewed profile from actual original binary
hashes before build-relative pointer reads. Its receipt and profile-bound startup
plan must agree on the complete profile digest, including physical bindings and
layout assumptions. Adding a display catalog row cannot make an older runtime
support that build. Unknown hashes and unsupported profiles remain blocked.
Initially these profile implementations ship inside the loader runtime;
support for another reviewed build requires an adapter/runtime update, while a
compatible feature or framework binary can remain unchanged.
Version ranges, similar addresses and successful Steam requests are not admission
or verification evidence.

## Migration and bounds

Existing native v1-v7 binaries and current managed plugins remain pinned. Many
contain direct RVAs, field offsets or version-specific layout repairs; changing
manifest text cannot make those binaries portable. Their current execution
path stays available. Authors must migrate a framework's game-facing operations
to typed adapter capabilities and rebuild once before its binary can rely on
future adapter substitution. Feature mods using stable framework APIs can then
stay unchanged when only the lower game adapter needs an update.

Sound is a plausible early domain migration because much of its binding is
already reflective, but its local-actor and token assumptions still need
explicit adapter ownership. Hints and Vehicles have additional raw layout/RVA
requirements. These migrations are planned work, not implied by opting into
v8 or changing a package's declared ABI. Managed-host forwarding needs a
separate plugin/binding contract and qualified engine layouts; it remains
outside the initial native v8 path.

Only one real game version is presently available. Independent synthetic profile
adapters can prove that identical compiled provider and consumer code survives
changed physical implementation, including a feature that depends only on a
framework. They cannot qualify an actual future Moon Sweepers build.

## Player interpretation

The report distinguishes unknown targets, incompatible requirements and matching
requirements. Verified execution additionally needs loader-owned evidence bound
to immutable package identity, selected providers, game profile, runtime binary
and an explicit scope such as menu startup or world/save replay. Author-written
verification descriptions are informational and grant no verified status.
A blocked framework must explain why dependent features cannot currently run.
A new valid profile or changed provider invalidates stale verification evidence.
