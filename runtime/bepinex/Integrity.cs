using System;
using System.IO;
using System.Collections.Generic;
using System.Text.Json;

namespace MoonLab.BepInExAdapter;

internal static class ManagedInputs
{
    internal static void Verify(string root, string manifestPath)
    {
        FileIntegrity.RegularPath(manifestPath);
        if (new FileInfo(manifestPath).Length > 256 * 1024) throw new InvalidDataException("Oversized managed input manifest");
        using var doc = JsonDocument.Parse(File.ReadAllBytes(manifestPath));
        if (doc.RootElement.GetProperty("schema").GetString() != "moonlab-managed-inputs/v1")
            throw new InvalidDataException("Unknown managed input manifest");
        var expected = new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
        foreach (var row in doc.RootElement.GetProperty("files").EnumerateObject())
            if (!expected.TryAdd(FileIntegrity.Relative(row.Name),row.Value.GetString()!))
                throw new InvalidDataException("Duplicate managed input path");
        var actual = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (string name in new[] { "BepInEx/core", "BepInEx/patchers", "BepInEx/plugins", "dotnet" })
        {
            string directory = Path.Combine(root,name);
            if (!Directory.Exists(directory)) continue;
            foreach (string file in FileIntegrity.Files(directory))
            {
                string relative = Path.GetRelativePath(root,file).Replace('\\','/');
                if (!actual.Add(relative) || !expected.TryGetValue(relative,out string? hash) || FileIntegrity.Hash(file) != hash)
                    throw new InvalidDataException("Changed or unowned managed input: " + relative);
            }
        }
        if (!actual.SetEquals(expected.Keys)) throw new InvalidDataException("Missing managed input");
    }
}
