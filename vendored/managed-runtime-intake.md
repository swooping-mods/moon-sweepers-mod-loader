# Managed distribution input review

`managed-runtime.lock.json` pins the existing reviewed BepInEx be.791 release,
its exact BepInEx and Il2CppInterop source archives, and the Microsoft
`Microsoft.NETCore.App.Runtime.win-x64` 10.0.15 package. Staging is inert and
offline builds reject changed bytes. No package restore, installer or upstream
build hook executes. Original adapter compilation uses the installed SDK and
reviewed reference assemblies; normal packages discard upstream CoreCLR 6.0.7.

Seven separate application libraries from that release remain necessary:
Microsoft.Extensions Logging/Abstractions, Options, Primitives,
DependencyInjection/Abstractions and Microsoft.Bcl.AsyncInterfaces 6.0.0.
Their exact reviewed bytes are retained under `BepInEx/core/`, rather than
mixing retired VM files into the maintained `dotnet/` platform directory.
Each DLL was matched byte-for-byte with its official Microsoft NuGet 6.0.0
member; the exact package metadata, MIT licenses and third-party notices are
retained in `managed-application-notices/`. Official source revision is
`dotnet/runtime` `4822e3c3aa77eb82b2fb33c9321f923cf11ddde6`. On 2026-11-11,
the seven inert source packages passed ClamAV with zero detections; static
review retained 300 expected executable/documentation leads and zero gaps.
Only their notices/metadata were newly integrated; no new package library or
analyzer was executed. Older runtime/debug binaries are excluded.

The BepInEx inputs reuse the exact prior external-intake file receipts described
by the workshop's `vendored/bepinex-adapter.md`. The component inventory and
additional notice/source review are in [managed notices](bepinex-runtime-notices.md).
Source archives are retained as inert corresponding-source distribution data.
They contain no binding generated from the user's game installation. Native
binary/source equivalence has not been established by rebuilding every upstream
library.

The maintained runtime was checked against Microsoft's official 10.0 release
metadata at `https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json`.
Its Windows native and managed DLLs are byte-identical to the full Microsoft
runtime archive verified against the publisher's SHA-512. The official NuGet
package independently declares the MIT license and includes its exact license
and third-party notices; packaging retains those files and the nuspec. No .NET
CLI/SDK is distributed with the managed host.

On 2026-11-11, ClamAV 1.5.4 with database 28179 dated 2026-11-10 scanned all
201 extracted NuGet members with zero detections and no coverage alerts.
Static review recorded 243 expected PE executable and notice/network-link leads
with zero coverage gaps. ZIP paths/types, native Windows/UCRT imports, selected
runtime members, licenses, metadata and the direct CoreCLR hosting entrypoints
were reviewed. No fetched code was activated before this disposition. A bounded
native Windows probe subsequently initialized CoreCLR 6.0.7 and 10.0.15 through
their actual exported hosting API under the existing Wine runner; both returned
success. That probe does not establish BepInEx/game or native Windows behavior.

The lock records every selected CoreCLR member hash. Package gates verify the
actual complete attachment and compare the runtime closure with that lock;
publication requires matching maintained-runtime build/check receipts. Exact
compiler/version and source hashes are retained in the generated host receipt.
The build audits every managed core module's physical AssemblyRef closure,
with only four explicit generated game-reference names admitted. Scoped
detour/member/interface audits resolve type forwarders, generic and function
pointer signatures and explicit interface implementations. Actual negative
controls reject missing assemblies/types/fields, altered signatures and missing
interface getters. The independent trampoline tests execute real unmanaged
function pointers, including reference and value-type signatures and forced GC.
Private game startup, loaded worlds and multiplayer need separate evidence;
package integrity and antivirus results are not those qualifications.
