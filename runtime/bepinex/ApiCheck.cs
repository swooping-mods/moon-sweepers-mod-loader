using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
using Mono.Cecil;

internal static class ApiCheck
{
    internal static int Run(string candidate, string interop, string core)
    {
        using var resolver = new DefaultAssemblyResolver();
        foreach (string directory in new[] { interop, core, Path.GetFullPath(Path.Combine(core,"..","..","dotnet")) })
            resolver.AddSearchDirectory(directory);
        using var assembly = AssemblyDefinition.ReadAssembly(candidate,new ReaderParameters { AssemblyResolver=resolver });
        var missing = new List<string>();
        var references = assembly.MainModule.GetMemberReferences().ToArray();
        if (references.Length > 20000) throw new InvalidDataException("Plugin API inventory exceeds bound");
        int checkedCount = 0;
        foreach (var member in references)
        {
            // Engine/game contracts are the adapter boundary; framework and
            // generic CLR resolution use the separately screened host closure.
            string owner = member.DeclaringType.Scope.Name;
            if (!owner.StartsWith("UnityEngine.") && owner != "Assembly-CSharp" && owner != "com.rlabrecque.steamworks.net") continue;
            checkedCount++;
            try
            {
                bool found = member switch { MethodReference m => m.Resolve() != null, FieldReference f => f.Resolve() != null, _ => true };
                if (!found) missing.Add(member.FullName);
            }
            catch (Exception error) { missing.Add(member.FullName + " [" + error.GetType().Name + "]"); }
        }
        Console.WriteLine(JsonSerializer.Serialize(new { success=missing.Count==0, total_references=references.Length, checked_references=checkedCount, missing }));
        return missing.Count == 0 ? 0 : 2;
    }
}
