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
    private static readonly HashSet<string> GeneratedGameAssemblies = new(StringComparer.OrdinalIgnoreCase) {
        "Il2Cppmscorlib", "Unity.InputSystem", "UnityEngine.CoreModule", "UnityEngine.InputLegacyModule"
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
        return FindForwarded(Scope(type), type.FullName, new HashSet<string>());
    }
    private static TypeDefinition FindForwarded(string scope, string name, HashSet<string> seen)
    {
        if (!seen.Add(scope + ":" + name) || !Assemblies.TryGetValue(scope, out var assembly)) return null;
        var found = Types(assembly.MainModule.Types).FirstOrDefault(candidate => candidate.FullName == name);
        if (found != null) return found;
        var forwarded = assembly.MainModule.ExportedTypes.FirstOrDefault(candidate => candidate.FullName == name);
        return forwarded?.Scope is AssemblyNameReference target ? FindForwarded(target.Name, name, seen) : null;
    }
    private static string Normal(TypeReference type, GenericInstanceType declaring = null)
    {
        if (type is GenericParameter parameter) {
            if (parameter.Type == GenericParameterType.Type && declaring != null && parameter.Position < declaring.GenericArguments.Count)
                return Normal(declaring.GenericArguments[parameter.Position]);
            return (parameter.Type == GenericParameterType.Method ? "!!" : "!") + parameter.Position;
        }
        if (type is GenericInstanceType generic)
            return Identity(generic.ElementType) + "<" + string.Join(",", generic.GenericArguments.Select(argument => Normal(argument, declaring))) + ">";
        if (type is FunctionPointerType pointerSignature)
            return "fnptr:" + pointerSignature.CallingConvention + ":" + pointerSignature.HasThis + ":" +
                Normal(pointerSignature.ReturnType, declaring) + "(" +
                string.Join(",", pointerSignature.Parameters.Select(parameter => Normal(parameter.ParameterType, declaring))) + ")";
        if (type is ByReferenceType reference) return Normal(reference.ElementType, declaring) + "&";
        if (type is PointerType pointer) return Normal(pointer.ElementType, declaring) + "*";
        if (type is ArrayType array) return Normal(array.ElementType, declaring) + "[" + new string(',', array.Rank - 1) + "]";
        if (type is OptionalModifierType optional) return Normal(optional.ElementType, declaring);
        if (type is RequiredModifierType required) return Normal(required.ElementType, declaring);
        return Identity(type);
    }
    // Equal names in modern and isolated legacy Utils are distinct CLR types.
    // Framework forwards remain name-normalized; detour dependency scopes do not.
    private static string Identity(TypeReference type) =>
        (Targets.Contains(Scope(type)) ? Scope(type) + "::" : "") + type.FullName;
    private static IEnumerable<TypeDefinition> Hierarchy(TypeDefinition type)
    {
        var seen = new HashSet<string>();
        while (type != null && seen.Add(type.FullName)) {
            yield return type;
            type = type.BaseType == null ? null : Find(type.BaseType);
        }
    }
    private static TypeReference Substitute(TypeReference type, GenericInstanceType context)
    {
        if (context != null && type is GenericParameter parameter && parameter.Type == GenericParameterType.Type)
            return context.GenericArguments[parameter.Position];
        if (type is GenericInstanceType generic) {
            var result = new GenericInstanceType(generic.ElementType);
            foreach (var argument in generic.GenericArguments) result.GenericArguments.Add(Substitute(argument, context));
            return result;
        }
        return type;
    }
    private static IEnumerable<(TypeDefinition Type, GenericInstanceType Context)> Interfaces(TypeDefinition type, HashSet<string> seen, GenericInstanceType context = null)
    {
        foreach (var current in Hierarchy(type))
        foreach (var implemented in current.Interfaces) {
            var reference = Substitute(implemented.InterfaceType, context);
            var contract = Find(reference);
            if (contract == null || !seen.Add(Scope(reference) + ":" + reference.FullName)) continue;
            var bound = reference as GenericInstanceType;
            yield return (contract, bound);
            foreach (var parent in Interfaces(contract, seen, bound)) yield return parent;
        }
    }
    private static bool MethodMatches(MethodReference reference, MethodDefinition candidate, GenericInstanceType context = null, bool explicitName = false)
    {
        reference = reference.GetElementMethod();
        var declaring = context ?? reference.DeclaringType as GenericInstanceType;
        return (explicitName || candidate.Name == reference.Name) && candidate.HasThis == reference.HasThis &&
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
            var missingAssemblies = input.assembly.MainModule.AssemblyReferences
                .Where(reference => !Assemblies.ContainsKey(reference.Name) && !GeneratedGameAssemblies.Contains(reference.Name))
                .Select(reference => reference.FullName).ToArray();
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
            foreach (var requirement in contract.Type.Methods.Where(method => method.IsAbstract)) {
                if (!Targets.Contains(contract.Type.Module.Assembly.Name.Name)) continue;
                var methods = Hierarchy(type).SelectMany(current => current.Methods).ToList();
                if (methods.Any(candidate => MethodMatches(requirement, candidate, contract.Context) ||
                    candidate.Overrides.Any(overridden => overridden.Name == requirement.Name &&
                        overridden.DeclaringType.GetElementType().FullName == contract.Type.FullName &&
                        MethodMatches(overridden, candidate, contract.Context, true)))) continue;
                missingImplementations.Add(type.FullName + " does not implement " + requirement.FullName);
            }
            failures += missingAssemblies.Length + missingTypes.Count + missingMembers.Count + signatures.Count + missingImplementations.Count;
            results.Add(new { assembly = assembly.Name.Name, path = Path.GetFullPath(path), checkedTypes, checkedMembers,
                missingTypes = missingTypes.OrderBy(value => value).ToArray(), missingMembers = missingMembers.OrderBy(value => value).ToArray(),
                signatureMismatches = signatures, missingImplementations, missingAssemblies });
        }
        var json = JsonSerializer.Serialize(results, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(arguments[1], json + Environment.NewLine);
        Console.WriteLine(json);
        return failures == 0 ? 0 : 1;
    }
}
