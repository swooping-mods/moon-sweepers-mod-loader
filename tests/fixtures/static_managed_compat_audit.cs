using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Mono.Cecil;

internal static class StaticManagedCompatAudit
{
    private static readonly Dictionary<string, AssemblyDefinition> Assemblies = new(StringComparer.OrdinalIgnoreCase);
    private static readonly HashSet<string> Targets = new(StringComparer.OrdinalIgnoreCase) {
        "MonoMod.Utils", "MonoMod.RuntimeDetour", "MonoMod.Backports", "MonoMod.Core",
        "MonoMod.ILHelpers", "Mono.Cecil", "0Harmony", "MoonLab.ManagedHostCompat",
        "MoonLab.LegacyMonoMod.Utils"
    };
    private static IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> types) =>
        types.SelectMany(type => new[] { type }.Concat(Types(type.NestedTypes)));
    private static string Scope(TypeReference type)
    {
        type = type.GetElementType();
        return type.Scope is AssemblyNameReference reference ? reference.Name :
               type.Scope is ModuleDefinition module ? module.Assembly.Name.Name : "";
    }
    private static TypeDefinition Find(TypeReference type)
    {
        type = type.GetElementType();
        if (!Assemblies.TryGetValue(Scope(type), out var assembly)) return null;
        return Types(assembly.MainModule.Types).FirstOrDefault(candidate => candidate.FullName == type.FullName);
    }
    private static string Normal(TypeReference type, GenericInstanceType declaring = null)
    {
        if (type is GenericParameter parameter) {
            if (parameter.Type == GenericParameterType.Type && declaring != null && parameter.Position < declaring.GenericArguments.Count)
                return Normal(declaring.GenericArguments[parameter.Position]);
            return (parameter.Type == GenericParameterType.Method ? "!!" : "!") + parameter.Position;
        }
        if (type is GenericInstanceType generic)
            return generic.ElementType.FullName + "<" + string.Join(",", generic.GenericArguments.Select(argument => Normal(argument, declaring))) + ">";
        if (type is ByReferenceType reference) return Normal(reference.ElementType, declaring) + "&";
        if (type is PointerType pointer) return Normal(pointer.ElementType, declaring) + "*";
        if (type is ArrayType array) return Normal(array.ElementType, declaring) + "[" + new string(',', array.Rank - 1) + "]";
        if (type is OptionalModifierType optional) return Normal(optional.ElementType, declaring);
        if (type is RequiredModifierType required) return Normal(required.ElementType, declaring);
        return type.FullName;
    }
    private static IEnumerable<TypeDefinition> Hierarchy(TypeDefinition type)
    {
        var seen = new HashSet<string>();
        while (type != null && seen.Add(type.FullName)) {
            yield return type;
            type = type.BaseType == null ? null : Find(type.BaseType);
        }
    }
    private static IEnumerable<TypeDefinition> Interfaces(TypeDefinition type, HashSet<string> seen)
    {
        foreach (var current in Hierarchy(type))
        foreach (var implemented in current.Interfaces) {
            var contract = Find(implemented.InterfaceType);
            if (contract == null || !seen.Add(contract.FullName)) continue;
            yield return contract;
            foreach (var parent in Interfaces(contract, seen)) yield return parent;
        }
    }
    private static bool MethodMatches(MethodReference reference, MethodDefinition candidate)
    {
        reference = reference.GetElementMethod();
        var declaring = reference.DeclaringType as GenericInstanceType;
        return candidate.Name == reference.Name && candidate.HasThis == reference.HasThis &&
            candidate.GenericParameters.Count == reference.GenericParameters.Count &&
            candidate.Parameters.Count == reference.Parameters.Count &&
            Normal(candidate.ReturnType, declaring) == Normal(reference.ReturnType, declaring) &&
            candidate.Parameters.Select(parameter => Normal(parameter.ParameterType, declaring))
                .SequenceEqual(reference.Parameters.Select(parameter => Normal(parameter.ParameterType, declaring)));
    }
    private static int Main(string[] arguments)
    {
        if (arguments.Length < 3) throw new ArgumentException("modern dependency folder, report path and input modules required");
        var dependencies = Path.GetFullPath(arguments[0]);
        foreach (var path in Directory.EnumerateFiles(dependencies, "*.dll")) {
            try {
                var assembly = AssemblyDefinition.ReadAssembly(path);
                Assemblies[assembly.Name.Name] = assembly;
            } catch (BadImageFormatException) { }
        }
        var results = new List<object>();
        int failures = 0;
        var inputs = arguments.Skip(2).Select(path => (path, assembly: AssemblyDefinition.ReadAssembly(path))).ToArray();
        foreach (var input in inputs) Assemblies[input.assembly.Name.Name] = input.assembly;
        foreach (var input in inputs) {
            var path = input.path;
            var assembly = input.assembly;
            var missingTypes = new HashSet<string>();
            var missingMembers = new HashSet<string>();
            var signatures = new List<object>();
            var missingImplementations = new List<string>();
            int checkedTypes = 0, checkedMembers = 0;
            foreach (var reference in assembly.MainModule.GetTypeReferences()) {
                if (!Targets.Contains(Scope(reference))) continue;
                checkedTypes++;
                if (Find(reference) == null) missingTypes.Add(Scope(reference) + ": " + reference.FullName);
            }
            foreach (var member in assembly.MainModule.GetMemberReferences()) {
                if (!Targets.Contains(Scope(member.DeclaringType))) continue;
                checkedMembers++;
                var type = Find(member.DeclaringType);
                if (type == null) { missingMembers.Add("missing-type: " + member.FullName); continue; }
                if (member is MethodReference method) {
                    var candidates = Hierarchy(type).SelectMany(current => current.Methods).Where(candidate => candidate.Name == method.Name).ToList();
                    if (candidates.Any(candidate => MethodMatches(method, candidate))) continue;
                    if (candidates.Count == 0) missingMembers.Add("missing-name: " + member.FullName);
                    else signatures.Add(new { reference = member.FullName, candidates = candidates.Select(candidate => candidate.FullName).ToArray() });
                } else if (member is FieldReference field) {
                    var candidates = Hierarchy(type).SelectMany(current => current.Fields).Where(candidate => candidate.Name == field.Name).ToList();
                    if (!candidates.Any(candidate => Normal(candidate.FieldType, field.DeclaringType as GenericInstanceType) == Normal(field.FieldType, field.DeclaringType as GenericInstanceType)))
                        missingMembers.Add("missing-field: " + member.FullName);
                }
            }
            foreach (var type in Types(assembly.MainModule.Types).Where(type => !type.IsInterface && !type.IsAbstract))
            foreach (var contract in Interfaces(type, new HashSet<string>()))
            foreach (var requirement in contract.Methods.Where(method => method.IsAbstract)) {
                if (!Targets.Contains(contract.Module.Assembly.Name.Name)) continue;
                var methods = Hierarchy(type).SelectMany(current => current.Methods).ToList();
                if (methods.Any(candidate => MethodMatches(requirement, candidate) ||
                    candidate.Overrides.Any(overridden => overridden.FullName == requirement.FullName))) continue;
                missingImplementations.Add(type.FullName + " does not implement " + requirement.FullName);
            }
            failures += missingTypes.Count + missingMembers.Count + signatures.Count + missingImplementations.Count;
            results.Add(new { assembly = assembly.Name.Name, path = Path.GetFullPath(path), checkedTypes, checkedMembers,
                missingTypes = missingTypes.OrderBy(value => value).ToArray(), missingMembers = missingMembers.OrderBy(value => value).ToArray(),
                signatureMismatches = signatures, missingImplementations });
        }
        var json = JsonSerializer.Serialize(results, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(arguments[1], json + Environment.NewLine);
        Console.WriteLine(json);
        return failures == 0 ? 0 : 1;
    }
}
