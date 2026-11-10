# MoonLab hook SDK v1

The desktop loader hosts this framework. Include `hooks.h` and resolve
`MoonLab_GetHookApi_v1` from the loaded `version.dll` during `MoonLab_ModStart`.
Check the returned table with `moon_hook_api_valid`. These headers are C11,
Windows AMD64 and independent of Unity headers or downloaded dependencies.

```c
static int update(int local_id, MoonHookContext *context) {
    (void)local_id;
    void *walker = (void *)context->rcx;
    /* Validate ownership/world state before using this borrowed instance. */
    return tick(walker);
}

/* Inside ModStart, after resolving and validating api: */
MoonHookSubscriptionV1 sub = {
    sizeof(sub), MOON_HOOK_UPDATE, MOON_ROLE_OBSERVER,
    MOON_PHASE_NORMAL, 0, 7, update, 0
};
unsigned int handle = api->subscribe(&sub);
if (!handle) return 0;
```

| Hook | Allowed roles | Behavior |
|---|---|---|
| `MOON_HOOK_UPDATE` | Observer | All observers run; vanilla continues once |
| `MOON_HOOK_LATE_UPDATE` | One override, observers | Camera override runs first, then all observers; only override can skip vanilla |
| `MOON_HOOK_VEHICLE_FIXED` | One input, one physics | Fresh validated input snapshot, then physics; only physics can skip vanilla |

Observer order is phase Early/Normal/Late, ascending signed priority, then
registration order. All phases run **before** the native method. Default phase
and priority preserve the loader's dependency-first, ID-ordered startup order.
Override/input/physics require Normal and priority zero; their role order is fixed.
Choose a non-default priority only for a documented ordering requirement. Domain
frameworks should multiplex their own providers behind a single subscription.

Observers, camera override and input callbacks receive isolated context copies.
Their register edits cannot affect another callback or native continuation.
Observer/input return values are ignored. Camera override returns nonzero to skip
the void native method. Physics receives the live context and may set a return
register when it replaces physics. Callbacks may mutate validated game objects;
this ABI does not sandbox code or catch native faults.

The loader owns each registration on behalf of the mod currently starting.
Subscribe/remove calls are accepted only on that bootstrap worker thread; a
mod-created worker cannot register into another mod's startup scope.
`subscribe` copies the descriptor and returns a nonzero handle, or zero on an
invalid ABI/role, duplicate callback, occupied exclusive role or exhausted table.
`unsubscribe(handle)` only removes this mod's registration during the same
ModStart. Failed startup rolls back that mod's shared subscriptions. A failure
still aborts game startup because exclusive feature hooks may already exist.
The loader publishes one breakpoint per used hook only after all mods succeed.
Registration/removal after publication rejects. DLLs and callbacks remain
resident until process exit; hot reload, scene callbacks and dynamic unload are
not supported. Feature mods own their world/scene pointer cleanup and authority.

`camera_override_active()` reports the most recent LateUpdate override result,
not a camera pointer or a prediction of the next frame. Use it on the Unity thread.
Contexts and per-tick vehicle input are borrowed; never retain them.

A mod using the SDK directly must also export
`int MoonLab_HookFrameworkAbi(void) { return 1; }` from its client DLL.
The common native gameplay adapter already provides this marker.

New catalog builds using this SDK declare `MoonLab_ModStart/v5` and
`hook_framework_abi: 1` alongside the
existing shared claims and roles. Older package loaders reject v5. Preparation requires the matching runtime
receipt before copying game files. The native gameplay/vehicle adapters export
`MoonLab_HookFrameworkAbi` so package production adds that requirement. Legacy
`MoonLab_RegisterUpdate_v1`, `MoonLab_RegisterLateUpdate_v1` and
`MoonLab_RegisterVehicle_v1` exports remain binary-compatible shims into this
registry. There is no second hook installation path inside a packaged game.

Add a new hook only after inspecting its current-build method identity and
establishing its cancellation/ownership contract. Raw arbitrary detours, feature
logic, domain catalogs, input arbitration and HUD allocation are outside SDK v1.
