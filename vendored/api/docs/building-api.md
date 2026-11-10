# Building API and saved-ID conventions

The public C contract is `include/moon_sweepers/build_menu/`. It preserves
`MoonLab_BuildMenu_v1` and the existing structure layout, including the legacy
definition prefix. Its implementation currently lives in the development
project's `mods/build-menu-framework/`; publishing headers does not supply a
runtime DLL. Providers require Build Menu Framework **0.2.0 or newer** to use
kinds above 224. Native game/build qualification remains the runtime owner's job.

Kinds 0–192 belong to the original pinned game. Provider kinds are **193–384**,
giving 192 additional definitions. These are type IDs, not placed-object limits.
The current kind-193 Power Pole retains both its numeric kind and its existing
`manual-power-poles.power-pole` key. Existing IDs and keys are never renumbered to
match load order or a changed menu category.

## Stable identity

Use `modid.category.item` for new definition keys, with lowercase letters,
digits and hyphens in each segment. The first segment must equal the package's
mod ID. The category segment is a permanent namespace chosen when the key is
created; changing a display category or translation does not change the key.
Existing two-segment keys remain valid. Keep each placed building's instance ID
separate from its definition key and numeric kind.

Reserve kinds in [the registry](registries/buildings.json) before sharing a new
mod. `active`, `reserved` and `retired` entries all occupy their IDs and keys.
Retire removed definitions rather than reusing their identities. Breaking identity
changes require an explicit, separately qualified save migration. A registry
reservation is a coordination contract, not proof of gameplay compatibility.

The canonical Python validator is `moon_mod_api.build_items`. Check the registry:

```sh
PYTHONPATH=python python3 -m moon_mod_api.build_items docs/registries/buildings.json
```

Packages declare the exact saved identity and framework dependency:

```json
{
  "id": "utility-relay",
  "kind": "native",
  "requires": ["build-menu-framework"],
  "build_items": [{"kind": 194, "key": "utility-relay.power.relay"}]
}
```

This is a fragment of the full package manifest. The package validator checks
ownership, range, dependency and duplicates; the resolver rejects overlapping
numeric kinds before launch. The framework declares `build_menu_max_kind: 384`;
older framework manifests default to 224 and cannot satisfy higher provider IDs.
Older packages without this optional declaration
still rely on runtime registry/slot rejection. There is no automatic assignment
from load order, hashing or whichever mod starts first.

## Shared ownership and saves

One Build Menu Framework owns the native catalog, definition arrays and reader
range patch. Providers register definitions through its versioned API; they must
not patch the reader or replace these arrays independently. One fixed shared
range replaces competing higher-wins patches. Unknown code bytes are rejected.

The game writes ordinary native records with stable numeric kinds. Matching
framework/provider definitions are required on every machine that loads those
records. Expanding to 384 preserves the existing format and kinds 193–224; it
does not promise loading with providers removed, arbitrary game-version upgrades
or mismatched multiplayer peers. Save pairing, sidecars and missing-mod recovery
are not introduced by this contract.

The API repository owns public declarations, validation and reservations. The
loader owns hosting, package selection and private launch. Feature repositories
own gameplay implementation/assets. Use explicit checked snapshots rather than
symlinks or imports into a developer's neighbouring checkout. ABI shape changes
need a new ABI or a size-checked appended extension. No game code, metadata,
binaries or proprietary extracted content belongs in this SDK.
