# Interaction adapter

`interaction.h` defines a separate opt-in interaction table. `InputApiV1` keeps
its existing layout and observational actions. An interaction adapter can select
one eligible action and mask its captured physical key from native input and
other registered actions. Domain eligibility and gameplay stay in each mod.

An ordinary native consumer declares:

```json
{
  "kind": "native",
  "abi": "MoonLab_ModStart/v7",
  "runtime_api_abi": 1,
  "requires_host": {"interaction": 1}
}
```

Its DLL exports `MoonLab_RuntimeServicesAbi` and `MoonLab_InteractionApiAbi`,
both returning 1. A matching runtime advertises `host_capabilities.interaction`
as 1. Older loaders reject v7; a target missing this adapter rejects before
preparation. Validate the actual `MoonLab_GetInteractionApi_v1` result too:
ABI 1, exact 32-byte table and all three nonnull function pointers. The adapter
is resident in the loader; do not privately load or start a second registry.
See the [package contract](packages.md) for target admission.

Register `MoonInteractionActionV1` during the owning ModStart scope. Use a stable
action name beginning with the package ID and a dot, an explicit default binding,
a resident query and a resident context. Names/bindings are copied; callback code
and context remain valid until exit. Failed startup rolls back its queries, and
registration is sealed before gameplay. Registration returns zero on refusal.

The query receives a borrowed local actor and writes a target identity, distance,
priority and domain token. It checks world, focus, text input, menus, authority,
reach and occlusion through the owning game/domain adapter. It must be read-only
and must not retain the borrowed actor without an engine root. A target identity
is a live domain identity, not permission to dereference an unrooted pointer.
The portable registry accepts nonzero identities, finite distances in 0–100 and
priorities in -1000–1000. Shared keys resolve by active input, priority, shorter
distance, then stable action name; distinct physical keys remain independent.

`sample(handle)` is a repeatable cached read for prompts. `take(handle, actor)`
authorizes the selected pressed edge once per input epoch and requires the
matching local actor. Reading a prompt does not consume an action; another actor
cannot consume the local edge. The handler must still validate any
domain state that could have changed since the query before mutating it.

```c
/* Called from an admitted game-thread callback with its borrowed actor. */
MoonInteractionState state = interaction->sample(handle);
if (state.selected && interaction->take(handle, actor)) {
    /* Revalidate state.target/state.token through the owning domain, then act. */
}
```

All access is serialized on the game thread. The current loader uses both the
render-frame counter and the InputSystem update step as its epoch: fixed and
dynamic input updates may occur within one rendered frame. Queries and coherent
held/pressed snapshots run once per epoch. This is separate from the general
borrowed-walker Update callback, which may be observed for different actors.

`MOON_INTERACTION_EXCLUSIVE` latches the winning physical base key through its
release epoch, including short taps and modifier-key aliases. Losing focus or a
target while held does not hand a stale press to another action. Ordinary input
sampling still observes physical edges internally while masking delivery; it
does not invent a new press when capture ends. The native adapter matches actual
keyboard/mouse controls and leaves unrelated alternate keys and controller
controls available. No action consumes an unrelated physical key.

`interaction_registry.h` supplies the bounded portable core: 128 interactions
sharing the 512-action input registry. Its implementation structures are source
helpers, not binary tables. Hosts supply input snapshots, lifecycle/thread gates
and native interception. Another adapter can reuse that core without using the
Moon Sweepers engine binding. Domain raycasts, purchases, carrying and other
gameplay remain independently owned; this contract does not grant world,
save, multiplayer or presentation compatibility to arbitrary mods.
