# Using the native runtime

Include `moon_sweepers/services.h` and your provider's separately versioned domain
header. Resolve `MoonLab_GetRuntimeApi_v1` from the loaded `version.dll`, call it
once and validate the result with `moon_runtime_api_valid`. Both provider and
consumer packages use native v6 and `runtime_api_abi: 1`; their DLLs export
`MoonLab_RuntimeServicesAbi` returning 1. Keep ordinary ModStart entrypoints.
Declare [provided/required interfaces](interfaces.md) in the normal manifest.
`services_client.h` supplies this connection and the v6 marker export after
your native adapter's Win32 types/functions are declared. Include it in exactly
one bootstrap translation unit; other files use `services.h`. It never loads another
mod or calls its ModStart. The Build Menu compatibility client uses the same
connector; a recognized loader with an unavailable table fails closed.

A provider publishes its resident table during its own ModStart. For the
`another-authors-library.building` declaration in the interface guide:

```c
MoonServiceLimitV1 limit = {"build_menu_max_kind", 384};
MoonServicePublicationLimitsV1 publication = {
    {sizeof(publication), "building", 7, sizeof(building_api), &building_api},
    1, 0, &limit
};
if (!runtime->publish(&publication.base)) return 0;
```

The table's ABI, size and all capacities must exactly match its declaration.
The runtime supplies the provider identity; another mod cannot publish in that
namespace. The descriptor, names and capacity array may be stack-local. The
table, its function pointers and any storage it references must remain valid
through process exit. A successful ModStart commits visibility only when all
advertised tables were published. Failure rolls back APIs and callbacks.

A consumer binds the selected provider during its ModStart and caches the
result using that provider's own header:

```c
const BuildingApi *building = runtime->find(
    "another-authors-library", "building", 7, sizeof(BuildingApi));
if (!building) return 0;
```

ABI must match exactly; a larger provider table can satisfy an older prefix.
Lookup does not select a replacement provider. Required providers start and
commit before consumers. Optional providers are used only when selected and
compatible. Domain functions define their own thread/ownership rules; lookup
availability does not make arbitrary calls thread-safe. Cache pointers instead
of resolving names on every tick.

For an Update observer, initialize `MoonFrameSubscriptionV1` with its exact
size, phase, priority, callback and resident user pointer, then call
`subscribe_frame`. The callback receives a borrowed walker for each observed
Update. It must check relevant world/authority state before acting. Phase and
priority order observers before the original game Update; “Late” is not a
postfix. Unsubscribe is available only within the owning startup scope. Runtime
subscriptions remain fixed after startup; disable behavior through provider
state instead of unloading callback code.

Shared local input uses `input.h` and `MoonLab_GetInputApi_v1`. Call it on the
game thread, register stable namespaced actions once, then sample with a gate
covering world, focus, text input, menus and authority. It does not consume game
input itself. The separate [interaction adapter](interaction.md) can mask keys
that an exclusive action captures. The portable registry/host headers let another
adapter supply key polling without a Windows dependency.

Shared camera ownership uses `camera.h` and
`MoonLab_GetCameraApi_v1(MOON_CAMERA_ABI, sizeof(MoonCameraApiV1))`. Claims start
only after the loader has observed the game thread. Root the world/walker/camera
and capture a snapshot when `moon_camera_begin` acquires the needed pose/FOV/mode
resources. `moon_camera_finish` restores while ownership is exclusive, then
releases. If restoration fails, retain the rooted targets/session and retry.
Never discard a live claim merely because a scene changed.

The runtime retains modules and API tables until exit. The optional [C# consumer client](managed-services.md) binds these tables after
native readiness; each framework owns its domain wrapper and call admission.
Managed publication, hot unload and automatic save/network conversion are not
part of this ABI. See the
[runtime spec](https://github.com/swooping-mods/moon-sweepers-api/blob/main/specs/runtime-services.md) for startup-plan and verification
boundaries.
