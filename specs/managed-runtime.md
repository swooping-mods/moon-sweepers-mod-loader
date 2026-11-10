# Optional managed runtime adapter

The default distribution hosts native mods. A checked BepInEx runtime attachment
adds the existing `bepinex-il2cpp` / `BepInEx.IL2CPP/6-be791` backend in **Private
game copy** mode. Installed-game mode continues to refuse managed selections.
Importing a package never downloads, attaches or executes a host.

`loader/moonloader/managed.py` is the canonical deployment implementation. The
workshop consumes an exact hash-pinned copy through its explicit
`tools/sync_managed_runtime.py`; it does not maintain another editable adapter.
The original C# adapter/generator/profile/repair code remains singly owned by
the workshop's `runtime/bepinex/` and its checked builder. This loader consumes
that builder's artifact and preserves its upstream notices/source archives.

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
is supplied. Portable receipts retain file/source hashes and bounded limits,
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
Native service bridging and cross-backend startup dependencies need their own
readiness/lifetime contract and qualification.

Verification: `tests/test_managed_runtime.py` imports unrelated original inert
packages, exercises managed-only and mixed deployment/launch plans, separate
data paths, empty native plans, host absence/version/capability/tamper refusal,
unknown plugins/config and plugin/allowlist transaction rollback. Ordinary
native, installed-mode, GUI, C registry and AMD64 build gates remain required.
Loaded-game qualification of this standalone integration is separate from the
workshop adapter's retained live tests and native Windows/co-op qualification.
