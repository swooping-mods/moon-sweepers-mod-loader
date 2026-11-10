using System;
using System.IO;

namespace MoonLab.BepInExAdapter;

internal static class GenerateCommand
{
    public static int Main(string[] args)
    {
        if (args.Length != 4) throw new ArgumentException("Generate SNAPSHOT OUTPUT BUNDLE_CORE GAME_ASSEMBLY or --check-api PLUGIN INTEROP BUNDLE_CORE");
        bool checkApi = args[0] == "--check-api";
        string core = Path.GetFullPath(checkApi ? args[3] : args[2]);
        using var resolver = new AssemblyResolutionScope(core);
        return Run(args,checkApi);
    }

    // Delay dependency resolution until the explicit resolver scope exists.
    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static int Run(string[] args, bool checkApi)
    {
        if (checkApi) return ApiCheck.Run(args[1],args[2],args[3]);
        using var snapshot = MetadataDocument.Load(args[0]);
        var profile = GameProfiles.ForSnapshot(snapshot.GameHash);
        new InteropGeneration().Run(new(snapshot,args[1],args[3],profile.Id,profile.Repairs));
        return 0;
    }
}
