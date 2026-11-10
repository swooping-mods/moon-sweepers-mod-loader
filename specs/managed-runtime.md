# Optional managed runtime adapter

The default distribution hosts native mods. A checked BepInEx runtime attachment
adds the existing `bepinex-il2cpp` / `BepInEx.IL2CPP/6-be791` backend in **Private
game copy** mode. Installed-game mode continues to refuse managed selections.
Importing a package never downloads, attaches or executes a host.

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
validates config before making a private game copy. Declared capability may be
shown in the UI before that full integrity check; preparation repeats it.

`tools/build.py --with-bepinex ATTACHMENT` explicitly packages the attachment
in a separate `*-managed-private-source.zip`. It never executes or downloads
the input. Default builds exclude an attached managed folder unless the flag
is supplied. Its separate `SHA256SUMS-managed-private` preserves the default
source/Windows checksum manifest. Portable receipts retain file/source hashes and bounded limits,
omitting local intake/build directories. The normal Windows portable build
remains native-only unless a separate managed packaging path is requested.

Private deployment journals immutable host/plugin files and their executable
input allowlist together. A failed commit restores both. Plugins deploy under
`BepInEx/plugins/<package-id>/`; `data/` payloads use the package's validated
`bepinex.data_root` namespace. Mutable config/cache/evidence stays in that
private game tree. Unknown executable inputs or enabled automatic download/
generation settings stop preparation; they are not silently removed/reset.

Launch passes only native IDs to ModStart and enables the separate managed
host with its own evidence path and `winhttp` override on Proton. Managed-only
launches have an empty native startup plan, retain the synchronous private
profile guard and seal the empty native registry. Native capacity counts only
native entries; total selection capacity remains the package contract's bound.
External provenance is generic metadata and never a native DLL fallback.

The qualified adapter profile is Moon Sweepers Steam 1.0.5 / Unity 6000.6 /
IL2CPP 108. Its upstream .NET 6.0.7 closure is development-only; attaching it
does not qualify a public runtime release or arbitrary game/Unity profiles.
Managed plugin lifecycle follows BepInEx metadata. Mixed package dependency
ordering establishes package closure, not a native/managed startup rendezvous.
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
