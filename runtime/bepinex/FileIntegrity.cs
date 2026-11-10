using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;

namespace MoonLab.BepInExAdapter;

internal static class FileIntegrity
{
    internal static string Hash(string path)
    {
        using var input = File.OpenRead(path);
        using var hasher = SHA256.Create();
        return Convert.ToHexString(hasher.ComputeHash(input)).ToLowerInvariant();
    }

    internal static string Relative(string name)
    {
        if (string.IsNullOrEmpty(name) || name.Any(c => c < 32 || "\\:\"<>|?*".Contains(c)))
            throw new InvalidDataException("Invalid integrity manifest path");
        foreach (string part in name.Split('/'))
        {
            string device = part.Split('.')[0].ToUpperInvariant();
            if (part.Length == 0 || part is "." or ".." || part.EndsWith('.') || part.EndsWith(' ') ||
                device is "CON" or "PRN" or "AUX" or "NUL" ||
                device.Length == 4 && (device.StartsWith("COM",StringComparison.Ordinal) || device.StartsWith("LPT",StringComparison.Ordinal)) && device[3] is >= '1' and <= '9')
                throw new InvalidDataException("Aliased or invalid manifest path: " + name);
        }
        return name;
    }

    internal static void RegularPath(string path) => CheckPath(path,false);
    internal static void WritablePath(string path) => CheckPath(path,true);

    private static void CheckPath(string path, bool allowMissing)
    {
        // Check every existing ancestor, not only the leaf: enumerating through
        // a linked directory would otherwise appear to return regular files.
        for (string? current = Path.GetFullPath(path); current != null; current = Path.GetDirectoryName(current))
        {
            FileAttributes attributes;
            try { attributes = File.GetAttributes(current); }
            catch (FileNotFoundException) when (allowMissing) { continue; }
            catch (DirectoryNotFoundException) when (allowMissing) { continue; }
            if ((attributes & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Linked integrity input: " + current);
        }
    }

    internal static IEnumerable<string> Files(string root)
    {
        RegularPath(root);
        var pending = new Stack<string>(); pending.Push(root);
        while (pending.Count != 0)
        {
            foreach (string entry in Directory.EnumerateFileSystemEntries(pending.Pop()))
            {
                var attributes = File.GetAttributes(entry);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidDataException("Linked integrity input: " + entry);
                if ((attributes & FileAttributes.Directory) != 0) pending.Push(entry);
                else yield return entry;
            }
        }
    }
}
