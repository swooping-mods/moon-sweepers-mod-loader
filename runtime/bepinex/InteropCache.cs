using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace MoonLab.BepInExAdapter;

internal sealed record CacheIdentity(string GameHash, string ProfileId,
    IReadOnlyList<string> Repairs, string GeneratorHash);

internal static class InteropCache
{
    internal const string ReceiptName = "moonlab-interop.json";

    // False means an owned, unmodified cache needs regeneration. An unknown
    // identity or changed file set is an error, never permission to retire it.
    internal static bool Verify(string directory, CacheIdentity identity)
    {
        FileIntegrity.RegularPath(directory);
        string path = Path.Combine(directory,ReceiptName);
        FileIntegrity.RegularPath(path);
        if (new FileInfo(path).Length > 1024 * 1024) throw new InvalidDataException("Oversized interop receipt");
        using var doc = JsonDocument.Parse(File.ReadAllBytes(path));
        var receipt = doc.RootElement;
        string? schema = receipt.GetProperty("schema").GetString();
        if (schema is not ("moonlab-interop/v2" or "moonlab-interop/v3") ||
            receipt.GetProperty("game_sha256").GetString() != identity.GameHash)
            throw new InvalidDataException("Unowned or different-build interop cache; preserve it before retrying");
        var expected = new Dictionary<string,string?>(StringComparer.OrdinalIgnoreCase);
        foreach (var row in receipt.GetProperty("files").EnumerateObject())
            if (!expected.TryAdd(FileIntegrity.Relative(row.Name),row.Value.GetString()))
                throw new InvalidDataException("Duplicate interop receipt path");
        var actual = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (string file in FileIntegrity.Files(directory))
        {
            string relative = Path.GetRelativePath(directory,file).Replace('\\','/');
            if (relative == ReceiptName || relative == "assembly-hash.txt") continue;
            if (!actual.Add(relative) || !expected.TryGetValue(relative,out var hash) || FileIntegrity.Hash(file) != hash)
                throw new InvalidDataException("Interop cache file set or bytes changed; preserving cache");
        }
        if (!actual.SetEquals(expected.Keys)) throw new InvalidDataException("Missing interop cache file");
        return schema == "moonlab-interop/v3" &&
            receipt.GetProperty("profile").GetString() == identity.ProfileId &&
            receipt.GetProperty("repairs").EnumerateArray().Select(p => p.GetString()).SequenceEqual(identity.Repairs) &&
            receipt.GetProperty("generator_sha256").GetString() == identity.GeneratorHash;
    }
}
