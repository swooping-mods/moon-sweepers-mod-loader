# Bundled managed runtime adapter

Normal source, Windows and Linux distributions include the checked original
adapter and BepInEx host for the `bepinex-il2cpp` /
`BepInEx.IL2CPP/6-be791` backend in **Existing Steam game** and **Private game
copy** modes. This applies to prereleases and full releases alike. Installed
hosting requires runtime `installed_managed_abi: 1` and the checked native
`MoonLab_InstalledManagedState_v1` export. Including the host does not select, acquire or execute a
managed mod; the nine native starter packages retain unchecked defaults.

[Downloaded mod imports](download-imports.md) recognize the complete reviewed
MarsSweepers 0.6.1 folder/ZIP and retain its external metadata and exact hashes.
The import result explains supported deployment and startup requirements.
Installed mode adds owned host/plugin files to the existing Steam installation
without creating a second game copy; Steam uses its normal runtime and saves.
Linux setup requires both `version=n,b` and `winhttp=n,b` overrides. See
[installed deployment](public-deployment.md) for ownership, generation admission,
enable/disable, rollback and removal. The adapter waits for validated native
installed readiness before plugin startup and preserves fatal admission reports.

`loader/moonloader/managed.py` is the canonical deployment implementation. The
workshop consumes an exact hash-pinned copy through its explicit
`tools/sync_managed_runtime.py`; it does not maintain another editable adapter.
The original C# adapter/generator/profile/repair code is singly owned by
this repository's `runtime/bepinex/`; `source-snapshot.json` and
`tools/check_managed_sources.py` bind the transferred sources. The workshop
consumes an explicit pinned source copy for its private harness.
`tools/build_managed_adapter.py --attachment PATH --dotnet PATH --output
artifacts/NEW` compiles the adapter from an existing verified host attachment
and installed SDK, without the workshop. `--target diagnostic` compiles its
original generator/API-check command. Neither command runs a game/plugin,
acquires a runtime or executes generated bindings. Adapter output includes a
fresh hash-checked attachment preserving all supplied upstream notices/sources.

An attachment contains `receipt.json` and `files/`, using
`moonlab-bepinex-build/v1`, exact version `6.0.0-be.791+b782da4`, portable paths
and a complete SHA-256 file table. Required startup files include Doorstop,
CoreCLR, upstream IL2CPP host, original adapter and disabled-download config.
Preparation checks all actual bytes, rejects extra/missing/aliased files and
validates config before changing either deployment target. Declared capability may be
shown in the UI before that full integrity check; preparation repeats it.

`vendored/managed-runtime.lock.json` pins upstream BepInEx, exact upstream source
archives and maintained Windows CoreCLR input bytes. Explicit staging uses
`tools/fetch_windows_inputs.py --lock vendored/managed-runtime.lock.json --output
local/managed-inputs`; offline builders never fetch or install dependencies.
`tools/managed_bundle.py` compiles only this repository's original adapter using
an installed SDK, replaces the entire retired upstream `dotnet/` closure,
retains exact runtime licenses and component sources/notices, and seals a complete
receipt. No plugin, proprietary game binary or generated game binding is shipped.
`tools/build.py --managed-inputs PATH --dotnet PATH` uses this host by default;
Windows packaging forwards those options and Linux consumes the sealed source
archive. Host absence or tampering blocks the build. Package/release gates require
the maintained runtime version and actual member hashes. Receipts omit local
intake/compiler directories. The six existing release assets remain unchanged.

`--with-bepinex ATTACHMENT` remains an explicit development attachment override
producing a separate `*-managed-private-source.zip` and
`SHA256SUMS-managed-private`. Those outputs are not normal release assets.

Private deployment journals immutable host/plugin files and their executable
input allowlist together. A failed commit restores both. Plugins deploy under
`BepInEx/plugins/<package-id>/`; `data/` payloads use the package's validated
`bepinex.data_root` namespace. Mutable config/cache/evidence stays in that
private game tree. Unknown executable inputs or enabled automatic download/
generation settings stop preparation; they are not silently removed/reset.
Installed mode uses its separate owned-file transaction and keeps the generation's
native and managed evidence attributable without redirecting normal Steam saves.

Launch passes only native IDs to ModStart and enables the separate managed
host with its own evidence path and `winhttp` override on Proton. Managed-only
launches have an empty native startup plan and seal the empty native registry.
Private mode retains its synchronous profile guard; installed mode preserves
normal Steam save paths. Native capacity counts only
native entries; total selection capacity remains the package contract's bound.
External provenance is generic metadata and never a native DLL fallback.

The qualified adapter profile is Moon Sweepers Steam 1.0.5 / Unity 6000.6 /
IL2CPP 108. Production packaging replaces upstream CoreCLR 6.0.7 with
maintained CoreCLR 10.0.15. The offline compiler still uses the reviewed upstream
.NET 6 reference assemblies for compatible adapter assembly signatures; the
retired runtime is never copied into normal packages. The maintained host has
its own startup and Mars world qualification below; older retained receipts
qualify only their original runtime. Arbitrary game/Unity profiles remain
unsupported.

Modern HarmonyX 2.16.1 / MonoMod RuntimeDetour 25.3.6 provides .NET 10-aware
managed hooks; its complete dependency/member hash and MIT notice closure is
separately pinned in `modern-harmony.lock.json`. The old backend crashes during
Harmony initialization on .NET 10 and cannot be carried into the maintained
host unchanged. A deterministic offline Cecil transformation preserves the
be.791 host's native-detour interface and MethodBase trampoline proxy in the
isolated original `MoonLab.ManagedHostCompat` assembly. It renames the reviewed
old utilities assembly to `MoonLab.LegacyMonoMod.Utils` and retargets only the
four legacy BepInEx modules to it, preserving their Platform/Reflection/DynDll
APIs. Il2CppInterop/Harmony and modern MonoMod retain modern utility type
identity, including `MonoMod.Cil.ILContext`; the retired native detour backend
is not loaded. Original upstream corresponding sources, the exact patch tool
and helper sources travel in the host. No user plugin is rewritten. Compiler
version/hash and every modified assembly hash are recorded. Real executable
trampoline tests cover zero/eight arguments, by-reference/void, value types,
legacy instance-signature semantics and forced GC; static scope-aware member
and interface checks remain distinct from actual engine qualification.
Managed plugin lifecycle follows BepInEx metadata. Mixed package dependency
ordering establishes package closure. Installed mode also waits for resident
native readiness before managed plugin startup; this does not establish scene
readiness or arbitrary plugin-to-plugin startup ordering.
SDK 0.5 managed consumers may declare native `requires_apis` with
`runtime_api_abi: 1`. Both selection and preparation require readiness ABI 1 in
the native receipt before copying game data. The source C# connector queries the
resident loader's Pending/Ready/Failed export before binding a committed native
table; it never loads or privately starts a provider. This consumer-only bridge
does not sequence arbitrary BepInEx Load methods or admit managed native-table
publication. Each domain owns its typed wrapper and game-thread/object rules.
The separate readiness runtime now passes a headless original managed interop
and independent native-provider/managed-consumer startup diagnostic. It records
Ready, typed result 42, forced GC and 10,000 native calls with zero managed bytes
in that warmed batch. Native startup was already Ready at managed Load; actual
Pending timing remains host-tested. This is not loaded-world/save or Hints UI
qualification. Retained world tests below describe their exact previous runtime
candidate.

Verification: `tests/test_managed_runtime.py` imports unrelated original inert
packages, exercises managed-only and mixed deployment/launch plans, separate
data paths, empty native plans, host absence/version/capability/tamper refusal,
unknown plugins/config and plugin/allowlist transaction rollback. Ordinary
native, installed-mode, GUI, C registry and AMD64 build gates remain required.
Loaded-game qualification of this standalone integration is separate from the
workshop adapter's retained live tests and native Windows/co-op qualification.
The explicitly packaged candidate has now passed its original managed-only
probe and a fresh Mars solo world plus a second-process retained-save replay
through its own Python loader and pinned SDK. Both world runs include movement,
real save files, menu/badge, reload and normal exit; private profiles/prefixes
restore and original game bytes are preserved. Exact inputs and limits are in
the API project's existing
[qualification record](../../moon-sweepers-api/verification/local-preparation.md).
This does not extend support to arbitrary game profiles or qualify every native/
managed combination.
An additional retained-save replay with current native v6 Item Stacking passes
terminal/stacking shortcut arbitration, save/reload and normal exit. This is a
mixed-backend request test, not cargo placement or general hook-composition
qualification. The initial historical-package shortcut timeout is preserved
as a failed attempt in that record.

For v0.2.1, maintained CoreCLR 10.0.15 passes the original managed interop probe
(native object roundtrip, restored Harmony hooks, injected class and natural
component callbacks), and Mars solo movement/save/menu/reload/shutdown in both
private and installed modes. Installed qualification uses standard Steam save
paths in an owned Steam/Proton fixture; preparation creates no game, prefix or
profile copy. Disable, re-enable and uninstall each pass actual startup checks,
with original game hashes preserved and mutable BepInEx caches retained.
The actual Steam handoff is substituted by an authentic private Proton bridge
to avoid personal installation/profile writes. Gamescope segfaults on teardown
after Unity shutdown and runner exit 0; compositor teardown remains a failed
check. Native Windows gameplay and two-account co-op remain unqualified.
Exact test identities/results are in the workshop's existing
[adapter verification record](../../moon-sweepers-modding/verification/2026-11-10-bepinex-adapter.md)
and ignored `.local/release-0.2.1/` receipts.
