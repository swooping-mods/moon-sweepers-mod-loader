using System;
using System.Collections.Generic;
using System.IO;

namespace MoonLab.BepInExAdapter;

internal sealed record GameFiles(string Executable, string Player, string GameAssembly);

// Profiles describe qualified inputs and choose repairs. Generic generation
// takes the chosen repair list explicitly and does not discover profiles.
internal interface IGameProfile
{
    string Id { get; }
    string GameAssemblyHash { get; }
    string NativeLayoutId { get; }
    IReadOnlyList<IBindingRepair> Repairs { get; }
    bool Matches(GameFiles files);
}

internal static class GameProfiles
{
    // Registration is explicit: a plugin cannot silently replace a profile.
    private static readonly IGameProfile[] Supported = { new MoonSweepersSteam105() };
    internal static IGameProfile Match(GameFiles files)
    {
        foreach (var profile in Supported) if (profile.Matches(files)) return profile;
        throw new InvalidOperationException("Unqualified game/engine identity");
    }

    internal static IGameProfile ForSnapshot(string hash)
    {
        foreach (var profile in Supported) if (profile.GameAssemblyHash == hash) return profile;
        throw new InvalidDataException("No qualified profile for snapshot");
    }
}
