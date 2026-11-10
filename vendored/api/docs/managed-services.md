# Managed consumers of native frameworks

SDK 0.5 supplies source-only `managed/MoonSweepers.Api/RuntimeClient.cs` for
Windows AMD64 BepInEx IL2CPP plugins targeting the qualified host. Compile it
with your plugin, or build and reference your own SDK assembly. No runtime,
plugin, dependency download or generated game binding is bundled with it.

Declare ordinary package dependencies and explicit table requirements:

```json
{
  "kind": "bepinex-il2cpp",
  "abi": "BepInEx.IL2CPP/6-be791",
  "runtime_api_abi": 1,
  "requires": ["hints-framework"],
  "requires_apis": [
    {"api": "hints-framework.hints", "abi": 1, "min_size": 24}
  ]
}
```

The remaining ordinary package fields, game pins and BepInEx GUID/data namespace
are still required. Managed consumers cannot advertise native `provides` tables.
The loader validates required ABI/size/capacity before copying a game and requires
native readiness ABI 1. Old SDK validators reject this opt-in metadata rather
than silently pretending to provide a bridge. Existing plugins need no changes.

`RuntimeClient.TryConnect(out client)` only queries the already loaded
`version.dll` and checks the loader/table/export ABIs. It never loads a DLL,
starts a dependency or uses a private fallback. The frozen runtime table remains
40 bytes. The separate `MoonLab_RuntimeState_v1` export reports Pending (0),
Ready (1) or Failed (2). Ready is published only after every native owner commits
and all shared hooks install. Failure is terminal for that startup.

Wait without blocking Unity or BepInEx Load: retry from your normal admitted
game-thread lifecycle, apply a bounded failure policy and report a missing
required provider. Then call `TryFind(owner, service, abi, minimumSize, out table)`
once and cache your domain's typed delegates. Pending returns false without
performing lookup; failed/unknown states throw. An absent or incompatible
committed provider returns false. This is a native-before-managed-use contract,
not ordering of arbitrary BepInEx plugin Load methods or support for managed
providers. Keep normal BepInDependency attributes for managed dependencies.

Each framework owns its own typed wrapper. Hints Framework, for example, owns
`sdk/managed/HintsClient.cs`; it is not a list of privileged APIs in this core.
That wrapper binds ABI 1 / 24 bytes, owns one stable plugin-prefixed key, copies
changed controls into bounded UTF-8 buffers and makes direct repeated calls.
Publishing still requires its observed native Update thread, a genuine live
borrowed walker/world and the same frame as the native legend. Runtime readiness
does not establish any of those conditions. An arbitrary MonoBehaviour Update
order is not a guarantee of same-frame legend delivery. Clear on disable/world
change on the admitted thread; a cleared key slot is not reclaimed.

The framework's separate 0.2 candidate also owns `HintsPresentation.cs` and
the `hints-framework.presentation` ABI 1 / 24-byte service. Its late callback
runs immediately before the native legend selects current hints, after the
provider admits its Unity thread and live world. This is an ordinary optional
domain service, not an extension to core startup registration. Consumers bind
once, retry subscription on that component thread, publish synchronously with
the callback's borrowed walker, and unsubscribe before disposing callback state.
Active subscriptions explicitly root their managed delegate and closure until
successful unsubscribe; a refusal must retain those roots. Host reverse-call,
GC, exception and allocation checks pass. The candidate's loaded-world legend
proof remains separate; existing Hints consumers require only the original API.

Native table/code storage lasts until process exit. Do not unload a native
module, retain borrowed Unity pointers, assume a table is thread-safe, pass
unrooted delegates or marshal raw managed object references as native objects.
The core RuntimeClient only binds and calls; framework wrappers own any late
callback contract. Such a service does not reopen the native startup transaction.

With an installed SDK/runtime, the optional compiled FFI checks are included in
`MOON_API_DOTNET=/absolute/path/to/dotnet python3 tools/check.py`. They compile
original C and C# fixtures, exercise actual native calls, readiness/ABI refusal,
name bounds and delegate lifetime through forced GC. Without that tool the
managed check reports a skip; it never downloads a compiler. Loaded-game and
individual framework presentation tests remain separate qualification.
