using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;

namespace MoonLab.BepInExAdapter;

// One immutable input identity and one parse per generation job. Builders borrow
// Root only while this owner is alive; they never reopen the snapshot path.
internal sealed class MetadataDocument : IDisposable
{
    private const int MaximumBytes = 256 * 1024 * 1024;
    private readonly JsonDocument document;
    private byte[]? serialized;
    internal JsonElement Root => document.RootElement;
    internal string Hash { get; }
    internal string GameHash { get; }

    private MetadataDocument(byte[] bytes)
    {
        Hash = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        document = JsonDocument.Parse(bytes);
        serialized = bytes;
        try
        {
            if (Root.GetProperty("Schema").GetString() != "moonlab-live-metadata/v1")
                throw new InvalidDataException("Unknown live metadata schema");
            GameHash = Root.GetProperty("GameHash").GetString() ?? throw new InvalidDataException("Missing game hash");
            var assemblies = Root.GetProperty("Assemblies");
            if (assemblies.GetArrayLength() is < 1 or > 512) throw new InvalidDataException("Invalid snapshot assembly count");
            var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var row in assemblies.EnumerateArray())
            {
                string name = row.GetProperty("Name").GetString() ?? "";
                FileIntegrity.Relative(name);
                if (name.Contains('/') || !names.Add(name)) throw new InvalidDataException("Invalid or duplicate snapshot assembly: " + name);
            }
        }
        catch { document.Dispose(); throw; }
    }

    internal static MetadataDocument FromValue<T>(T value)
    {
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(value);
        if (bytes.Length > MaximumBytes) throw new InvalidDataException("Snapshot exceeds generation budget");
        return new MetadataDocument(bytes);
    }

    internal void WriteTo(Stream output)
    {
        byte[] bytes = serialized ?? throw new ObjectDisposedException(nameof(MetadataDocument));
        output.Write(bytes,0,bytes.Length);
    }

    internal static MetadataDocument Load(string path)
    {
        FileIntegrity.RegularPath(path);
        using var input = File.OpenRead(path);
        if (input.Length > MaximumBytes) throw new InvalidDataException("Snapshot exceeds generation budget");
        var bytes = new byte[checked((int)input.Length)];
        int offset = 0;
        while (offset < bytes.Length)
        {
            int count = input.Read(bytes,offset,bytes.Length-offset);
            if (count == 0) throw new EndOfStreamException("Snapshot changed during read");
            offset += count;
        }
        if (input.ReadByte() != -1) throw new InvalidDataException("Snapshot grew during read");
        return new MetadataDocument(bytes);
    }

    public void Dispose() { document.Dispose(); serialized = null; }
}
