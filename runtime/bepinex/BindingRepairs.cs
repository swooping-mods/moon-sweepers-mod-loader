using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Mono.Cecil;

namespace MoonLab.BepInExAdapter;

internal interface IBindingRepair
{
    string Id { get; }
    string TargetAssembly { get; }
    void Apply(ModuleDefinition module);
}

internal sealed class BindingRepairRollbackException : AggregateException
{
    internal string RecoveryDirectory { get; }
    internal BindingRepairRollbackException(string directory, IEnumerable<Exception> errors)
        : base("Repair rollback incomplete; preserve " + directory,errors) => RecoveryDirectory = directory;
}

internal static class BindingRepairs
{
    internal static void Validate(IReadOnlyList<IBindingRepair> repairs)
    {
        if (repairs == null) throw new ArgumentNullException(nameof(repairs));
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var repair in repairs)
        {
            if (repair == null || string.IsNullOrWhiteSpace(repair.Id) || !ids.Add(repair.Id))
                throw new ArgumentException("Empty or duplicate binding repair identity");
            string target = FileIntegrity.Relative(repair.TargetAssembly);
            if (target.Contains('/') || !target.EndsWith(".dll",StringComparison.Ordinal) || target.Length <= 4)
                throw new ArgumentException("Repair target must be an assembly filename");
        }
    }

    internal static void Apply(string directory, IReadOnlyList<IBindingRepair> repairs)
    {
        Validate(repairs);
        if (repairs.Count == 0) return;
        FileIntegrity.RegularPath(directory);
        string stage = Path.Combine(directory,".moonlab-repairs-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(stage);
        var files = new List<(string Original, string Prepared, string Backup)>();
        bool preserveStage = false;
        try
        {
            // Prepare the complete set before changing any input assembly.
            foreach (var group in repairs.GroupBy(p => p.TargetAssembly,StringComparer.OrdinalIgnoreCase))
            {
                string path = Path.Combine(directory,group.Key);
                FileIntegrity.RegularPath(path);
                using var input = new MemoryStream(File.ReadAllBytes(path));
                using var assembly = AssemblyDefinition.ReadAssembly(input);
                foreach (var repair in group)
                {
                    try { repair.Apply(assembly.MainModule); }
                    catch (Exception error) when (error is not BindingRepairRollbackException) { throw new InvalidOperationException("Binding repair " + repair.Id + " failed for " + group.Key,error); }
                }
                string prepared = Path.Combine(stage,files.Count + ".new");
                assembly.Write(prepared);
                files.Add((path,prepared,Path.Combine(stage,files.Count + ".old")));
            }
            foreach (var file in files)
            {
                File.Move(file.Original,file.Backup);
                File.Move(file.Prepared,file.Original);
            }
        }
        catch (Exception failure)
        {
            var errors = new List<Exception> { failure };
            foreach (var file in files.AsEnumerable().Reverse())
            {
                if (!File.Exists(file.Backup)) continue;
                try
                {
                    if (File.Exists(file.Original)) File.Delete(file.Original);
                    File.Move(file.Backup,file.Original);
                }
                catch (Exception error) { errors.Add(error); }
            }
            if (errors.Count > 1)
            {
                preserveStage = true;
                throw new BindingRepairRollbackException(stage,errors);
            }
            preserveStage = failure is BindingRepairRollbackException;
            throw;
        }
        finally { if (!preserveStage) Directory.Delete(stage,true); }
    }
}
