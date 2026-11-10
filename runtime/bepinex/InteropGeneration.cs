using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Text.Json;
using Il2CppInterop.Generator;
using Il2CppInterop.Generator.Runners;

namespace MoonLab.BepInExAdapter;

internal sealed record GenerationRequest(MetadataDocument Snapshot, string OutputDirectory,
    string GameAssemblyPath, string ProfileId, IReadOnlyList<IBindingRepair> Repairs);

internal sealed class InteropGeneration
{
    [MethodImpl(MethodImplOptions.NoInlining)]
    internal void Run(GenerationRequest request)
    {
        BindingRepairs.Validate(request.Repairs);
        if (string.IsNullOrWhiteSpace(request.ProfileId)) throw new ArgumentException("Generation requires a profile identity");
        string gameHash = request.Snapshot.GameHash;
        if (FileIntegrity.Hash(request.GameAssemblyPath) != gameHash)
            throw new InvalidDataException("Generator GameAssembly differs from live snapshot");
        string output = Path.GetFullPath(request.OutputDirectory);
        if (Directory.Exists(output) || File.Exists(output)) throw new IOException("Preserve existing generator output");
        FileIntegrity.WritablePath(output);
        string stage = output + ".stage-" + Guid.NewGuid().ToString("N");
        Directory.CreateDirectory(stage);
        bool preserveStage = false;
        try
        {
            using var declarations = new DeclarationGenerator();
            var sources = declarations.Read(request.Snapshot,Path.Combine(stage,"dummy"));
            string interop = Path.Combine(stage,"interop");
            var options = new GeneratorOptions { Source = sources, OutputDir = interop,
                UnityBaseLibsDir = null, GameAssemblyPath = Path.GetFullPath(request.GameAssemblyPath),
                NoXrefCache = true, PassthroughNames = true, Parallel = false };
            Il2CppInteropGenerator.Create(options).AddInteropAssemblyGenerator().Run();
            BindingRepairs.Apply(interop,request.Repairs);
            File.WriteAllText(Path.Combine(interop,"moonlab-interop.json"),JsonSerializer.Serialize(new {
                schema = "moonlab-interop/v3", game_sha256 = gameHash, profile = request.ProfileId,
                repairs = request.Repairs.Select(p => p.Id).ToArray(),
                generator_sha256 = FileIntegrity.Hash(typeof(InteropGeneration).Assembly.Location),
                files = FileIntegrity.Files(interop).ToDictionary(
                    p => Path.GetRelativePath(interop,p).Replace('\\','/'), p => FileIntegrity.Hash(p)),
                snapshot_sha256 = request.Snapshot.Hash, assemblies = sources.Count,
                generator = "Il2CppInterop 1.5.3; original live-metadata declarations",
                limits = new[] { "General unstripping not performed", "No game/plugin execution in generation" }
            }));
            Directory.Move(stage,output);
            Console.WriteLine("Generated " + sources.Count + " independently captured interop assemblies");
        }
        catch (BindingRepairRollbackException) { preserveStage = true; throw; }
        finally { if (!preserveStage && Directory.Exists(stage)) Directory.Delete(stage,true); }
    }
}
