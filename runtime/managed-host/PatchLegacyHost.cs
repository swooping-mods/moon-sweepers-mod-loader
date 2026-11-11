using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Offline compatibility transformation of the exact reviewed be.791 assemblies.
// Corresponding upstream source and this tool accompany the modified LGPL host.
internal static class PatchLegacyHost
{
    private static void Main(string[] arguments)
    {
        if (arguments.Length != 3) throw new ArgumentException("host, original Utils, output required");
        using var host = AssemblyDefinition.ReadAssembly(arguments[0]);
        var module = host.MainModule;
        if (module.Name == "MonoMod.Utils.dll")
        {
            host.Name.Name = "MoonLab.LegacyMonoMod.Utils";
            module.Name = "MoonLab.LegacyMonoMod.Utils.dll";
            host.Write(arguments[2], new WriterParameters { DeterministicMvid = true, Timestamp = 0 });
            Console.WriteLine("Isolated original MonoMod utilities; no legacy detour backend");
            return;
        }
        if (!new[] {"BepInEx.Core.dll", "BepInEx.Preloader.Core.dll", "BepInEx.Unity.Common.dll", "BepInEx.Unity.IL2CPP.dll"}.Contains(module.Name))
            throw new InvalidOperationException("Unexpected legacy host module " + module.Name);
        foreach (var reference in module.AssemblyReferences.Where(reference => reference.Name == "MonoMod.Utils"))
            reference.Name = "MoonLab.LegacyMonoMod.Utils";

        var helperAssembly = new AssemblyNameReference("MoonLab.ManagedHostCompat", new Version(1, 0, 0, 0));
        module.AssemblyReferences.Add(helperAssembly);
        var helper = new TypeReference("MoonLab.ManagedHost", "LegacyDetourCompatibility", module, helperAssembly);
        foreach (var reference in module.GetTypeReferences())
        {
            if (reference.FullName != "MonoMod.RuntimeDetour.IDetour") continue;
            reference.Name = "ILegacyDetour";
            reference.Namespace = "MoonLab.ManagedHost";
            reference.Scope = helperAssembly;
        }
        var changed = 0;
        foreach (var type in module.Types.SelectMany(type => type.NestedTypes.Prepend(type)))
        foreach (var method in type.Methods.Where(method => method.HasBody))
        foreach (var instruction in method.Body.Instructions)
        {
            if (instruction.Operand is not MethodReference old ||
                old.DeclaringType.FullName != "MonoMod.RuntimeDetour.DetourHelper" || old.Name != "GenerateNativeProxy") continue;
            if (old.Parameters.Count != 2) throw new InvalidOperationException("Unexpected legacy proxy signature");
            var replacement = new MethodReference("GenerateNativeProxy", old.ReturnType, helper);
            foreach (var parameter in old.Parameters) replacement.Parameters.Add(new ParameterDefinition(parameter.ParameterType));
            instruction.Operand = replacement;
            changed++;
        }
        if (module.Name == "BepInEx.Unity.IL2CPP.dll" && changed != 1)
            throw new InvalidOperationException("Unexpected legacy host: expected one trampoline compatibility change, found " + changed);
        host.Write(arguments[2], new WriterParameters { DeterministicMvid = true, Timestamp = 0 });
        Console.WriteLine("Legacy BepInEx host compatibility: " + module.Name + ", trampoline changes=" + changed);
    }
}
