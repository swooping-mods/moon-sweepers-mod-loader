# BepInEx runtime component notices

The managed host contains upstream BepInEx components and an original Moon
Sweepers adapter. Component terms apply independently. This file adds no license
to the loader, adapter, game or third-party mods.

The adjacent `components.json` in a packaged host records the original be.791
non-CoreCLR runtime DLLs, their SHA-256 identity, observed version, owner, license
and corresponding notice. The source repository keeps the same manifest at
`vendored/bepinex-notices/manifest.json`. Versions were read from the actual
be.791 DLL resources and upstream project pins, rather than inferred from a
current repository default branch.

The production host replaces the original Harmony/MonoMod/Cecil dependency
assemblies with the versions and exact hashes in
`modern-detours/components.json`; their retained notices take precedence for
those runtime files. The original inventory remains useful provenance for
the archived upstream corresponding source. The original BepInEx modules are
adapted by the accompanying `managed-host-compat/PatchLegacyHost.cs` tool;
the complete attachment receipt records their final modified hashes. Its
compatibility modifications retain BepInEx's LGPL terms. The independent host
compatibility helper and its source are also included.

| Component | Bundled version | Terms | Retained notice/source |
|---|---|---|---|
| BepInEx | 6.0.0-be.791, b782da4 | LGPL-2.1-or-later | `BepInEx-LICENSE`, exact source ZIP |
| Il2CppInterop | 1.5.3, dbda1cb | LGPL-3.0 | `Il2CppInterop-LICENSE`, `GPL-3.0.txt`, exact source ZIP |
| Unity Doorstop | 4.6.0, 1c3ece1 | LGPL-2.1 | `UnityDoorstop-LICENSE`, exact source ZIP |
| Dobby | 1.0.5 | Apache-2.0 | `Dobby-LICENSE` |
| HarmonyX | 2.10.2 | MIT | `HarmonyX-LICENSE` |
| AsmResolver | 6.0.0-beta.5, 124e161 | MIT | `AsmResolver-LICENSE` |
| AssetRipper.CIL | 1.2.2, 06216e6 | MIT | `AssetRipper-CIL-LICENSE` |
| AssetRipper.Primitives | 3.2.0, d759b3d | MIT | `AssetRipper-Primitives-LICENSE`, `uTinyRipper-LICENSE` |
| Cpp2IL, LibCpp2IL, StableNameDotNet, WasmDisassembler | development.1452, 558ddd9 | MIT | `Cpp2IL-LICENSE` |
| Disarm | master.99, 8574010 | MIT | `Disarm-LICENSE` |
| Capstone.NET managed wrapper | 2.3.2, b90e380 | MIT | `Capstone-NET-LICENSE` |
| Iced | 1.21.0, 601c405 | MIT | `Iced-LICENSE` |
| Mono.Cecil and extensions | 0.11.4 | MIT | `Mono-Cecil-LICENSE` |
| MonoMod RuntimeDetour/Utils | 22.07.31.01 | MIT | `MonoMod-LICENSE` |
| MonoMod.Backports and ILHelpers | Backports 1.1.2, a1b82852b | MIT | `MonoMod-Backports-LICENSE` |
| SemanticVersioning | 2.0.2, c52c9d4 | MIT | `SemanticVersioning-LICENSE` |

The Windows CoreCLR runtime has its own Microsoft NuGet MIT license and third-party
notices in the pinned runtime payload. Its selected version and archive identity
are recorded by the managed bundle builder. This inventory does not authorize
shipping the older development-only CoreCLR 6.0.7 closure.

Unmodified corresponding-source archives for BepInEx, Il2CppInterop and Doorstop
travel with the binaries, alongside their complete license texts. They retain
upstream build instructions and reference libraries as inert source-distribution
data. No upstream build script runs while packaging. They contain no bindings
generated from the user's Moon Sweepers installation. The current adapter sources
and build tools are included in the loader source distribution.

Recipients may inspect, modify, replace and debug the LGPL libraries. Rebuilding
or intentionally replacing a library requires updating the local attachment's
hash receipt; deployment verifies that receipt to reject accidental or unowned
changes. Upstream rights are preserved; these checks do not grant rights to the
game or to a separately downloaded mod.

Original binaries were not rebuilt to establish complete binary/source
equivalence. Windows/native-game, loaded-world and multiplayer qualification
are separate from the notice inventory and package-integrity checks.
