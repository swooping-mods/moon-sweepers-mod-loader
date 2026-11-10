# Mod-provided interfaces

Every framework is an ordinary mod. Any game mod may declare interfaces in its
own namespace; consumers name the actual provider rather than selecting an
arbitrary implementation with a similar feature label.

```json
{
  "id": "another-authors-library",
  "kind": "native",
  "abi": "MoonLab_ModStart/v6",
  "runtime_api_abi": 1,
  "provides": {
    "another-authors-library.building": {
      "abi": 7,
      "size": 64,
      "limits": {"build_menu_max_kind": 384}
    }
  }
}
```

This is a fragment of the normal manifest, not a separate package kind. A
consumer explicitly selects the package dependency and declares its interface:

```json
{
  "id": "independent-feature",
  "kind": "native",
  "abi": "MoonLab_ModStart/v6",
  "requires": ["another-authors-library"],
  "runtime_api_abi": 1,
  "requires_apis": [{
    "api": "another-authors-library.building",
    "abi": 7,
    "min_size": 32,
    "limits": {"build_menu_max_kind": 384}
  }]
}
```

API ABI must match exactly. Provider size must cover the requested prefix;
integer limits must be present and at least the requested values. These are
author declarations, not proof that the DLL implements them. The runtime must
validate actual tables before calls. API version is independent of mod package,
SDK, backend and game versions.

An optional requirement uses `optional: true` and need not appear in `requires`.
It does not auto-select the provider. When that provider is selected, its API
must satisfy the requirement and it starts before the consumer. An incompatible
selected provider is an error. Required/optional API dependency cycles reject.
No automatic replacement provider or network acquisition occurs.

IDs use lowercase owner-qualified names, at most 160 characters. The owner is
the ordinary package ID, including valid digit-leading IDs such as `3d-tools`;
service-name segments begin with a letter. A package may
publish 64 APIs and require 64; a selected set may publish 256. ABI values are
positive uint32; table sizes are 1–65536 bytes. Each limit dictionary has at most
32 lowercase identifiers and nonnegative uint32 capacities. Booleans are not
integers for this contract. Duplicate requirements and foreign API namespaces
reject. Interface-aware native packages require native ABI v6 so older loaders
reject them rather than ignoring new metadata. Companion tools cannot declare these interfaces. SDK 0.5 permits managed
consumers to declare native API requirements with `runtime_api_abi: 1`; they
cannot publish native tables. Such consumers require readiness ABI 1 on the
target runtime. See the [managed client guide](managed-services.md).

New building providers choose `build_api` naming their required interface and
retain ordinary `build_items`. The selected provider must advertise the
`build_menu_max_kind` limit in the implemented 193–384 range. All providers still
share the game's numeric saved-kind space: using different framework APIs does
not make duplicate saved kinds compatible. Existing packages without
`build_api` retain the Build Menu Framework dependency and 224 historical
capacity fallback. No saved identity is reallocated.

SDK 0.5 supplies the [native runtime protocol](runtime-services.md). A matching
runtime receipt is required before deployment. Actual tables must match these
declarations during dependency-ordered startup; a successful provider becomes
visible before its consumer starts. Domain headers and implementations remain
with their owning frameworks. Each framework owns its typed managed wrapper; loaded-world qualification
remains separate from these package and runtime checks.
