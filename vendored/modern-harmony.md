# Modern managed detours

The maintained CoreCLR host needs the .NET 10-aware detour implementation:
HarmonyX 2.16.1, MonoMod.RuntimeDetour 25.3.6, MonoMod.Core 1.3.6,
MonoMod.Utils 25.0.14, MonoMod.Backports 1.1.2, MonoMod.ILHelpers 1.1.0 and
Mono.Cecil 0.11.6. Exact NuGet publisher URLs, archive/member SHA-256 hashes,
selected framework members and source revisions are in
`modern-harmony.lock.json`. No package installation, restore or build hooks run.

The selected MonoMod implementation targets .NET 6 and includes runtime-specific
.NET 10 detection/JIT support. HarmonyX and Cecil use their .NET Standard 2.0
assemblies. System.Text.Json and Reflection.Emit resolve from the maintained
.NET 10 platform, rather than copying older platform-library packages. All
selected components use MIT licenses; the embedded MonoMod.Iced decoder retains
the Iced project notice supplied in the Core package. Original license/copyright
texts and NuGet metadata are retained under `modern-harmony-notices/` and copied
into `BepInEx/third-party-sources/modern-detours/`.

This overlay replaces only the named dependency assemblies. BepInEx's older
IL2CPP native-detour classes need a separate compatibility port for the new
`IDetour.Config` contract and removed `DetourHelper.GenerateNativeProxy` API.
Overlay presence alone does not establish BepInEx/game startup compatibility.

Bounded inspection on 2026-11-11 checked portable archive members, declared
dependencies, selected PE surfaces, and the exact Harmony patcher and
MonoMod `Core100Runtime`/platform source entry points. Selected assembly static
inspection reported 11 expected executable-content leads and zero coverage
gaps. ClamAV 1.5.4 database 28179 dated 2026-11-10 scanned the complete seven
NuGet inputs and eleven selected DLLs with zero detections. Archive static
prefix limits affected ten long Iced XML documentation files that are neither
selected nor executed. Source/binary equivalence was not established by
rebuilding third-party libraries.

An original synthetic host running installed Linux .NET 10.0.14 in a rootless,
network-disabled container passed a real Harmony prefix/postfix installation,
1,000 patched calls, forced GC, and unpatch/restored behavior. Reflection of the
unmodified older BepInEx IL2CPP assembly correctly exposed its missing
`IDetour.Config` implementations. This host check is distinct from native
Windows, Unity/IL2CPP, multiplayer or user-mod qualification.
