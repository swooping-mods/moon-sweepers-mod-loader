# Conventions for shared APIs and future mods

Keep stable public contracts here and feature behavior in its owning mod. A
shared framework owns each common game integration and multiplexes registered
providers. Providers use that framework's API instead of independently patching
the same reader, catalog or definition array. Keep dependencies explicit and
allow unrelated features to remain independently selectable.

Preserve published C symbol names and layouts. Every API table/definition carries
an ABI and size where its existing contract requires them. Extend with a checked
optional tail or introduce a new ABI; never reinterpret old fields. Document
whether pointers are borrowed or owned, who releases objects, callback thread,
registration lifetime and ordering. Provider strings/callbacks in the current
building ABI remain valid for the process lifetime; configure/release/update
callbacks run through its main-thread owner.

Use stable namespaced definition keys and explicit saved IDs. Separate definition
identity, placed-object identity and translated display names. Preserve old keys
when categories or appearances change. Reserve before sharing and retain retired
identities. Save values and references with defined ownership; never persist
process pointers. See [building conventions](building-api.md) for the implemented
193–384 range and the registry.

Declare package dependencies and capabilities. Optional manifest additions must
have documented behavior with older packages; reject incompatible selections
before loading when metadata permits it. Still validate at the runtime boundary.
A package version or valid checksum does not establish game, ABI or multiplayer
compatibility. Every peer that uses saved native kinds needs matching definitions.

Use explicit reviewed SDK snapshots with recorded file hashes. Keep installed
game data, extracted assets, personal saves, credentials and downloaded dependency
runtimes out of this repository. First-party snapshot updates are local explicit
operations; do not fetch new code during mod startup or silently track branches.

Verify actual production helpers and public consumers. Cover old saved IDs and
ABI prefixes, new boundaries, collisions, incompatible capabilities and refusal
paths. Distinguish source/host/compiler checks, native loaded-world save/reload,
and co-op qualification. Record untested behavior explicitly. The existing hook
and building contracts provide the first shared surfaces; other domain APIs stay
with their owning frameworks until deliberately migrated here.
