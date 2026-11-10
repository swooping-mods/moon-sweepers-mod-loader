using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using Mono.Cecil;
using Mono.Cecil.Cil;
using CAssembly = Mono.Cecil.AssemblyDefinition;
using CFieldAttributes = Mono.Cecil.FieldAttributes;
using CMethodAttributes = Mono.Cecil.MethodAttributes;
using CTypeAttributes = Mono.Cecil.TypeAttributes;

namespace MoonLab.BepInExAdapter;

// Produces metadata declarations from our own live snapshot. None of these
// declarations contains recovered game IL, nor is an input assembly executed.
internal sealed class DeclarationGenerator : IDisposable
{
    private bool used;
    private readonly Dictionary<string,(string Name,IReadOnlyList<string> Arguments)> canonicalNames = new(StringComparer.Ordinal);
    private readonly Dictionary<(TypeDefinition,ModuleDefinition),TypeReference> imports = new();
    private readonly Dictionary<string,List<TypeDefinition>> Types = new();
    private readonly Dictionary<TypeDefinition,JsonElement> Rows = new();
    private readonly Dictionary<string,CAssembly> Assemblies = new();
    private readonly Dictionary<string,Dictionary<string,MethodReference>> Attributes = new();
    private sealed class LiveResolver : IAssemblyResolver
    {
        private readonly IReadOnlyDictionary<string,CAssembly> assemblies;
        internal LiveResolver(IReadOnlyDictionary<string,CAssembly> assemblies) => this.assemblies = assemblies;
        public CAssembly Resolve(AssemblyNameReference name) => assemblies.TryGetValue(name.Name,out var value)
            ? value : throw new AssemblyResolutionException(name);
        public CAssembly Resolve(AssemblyNameReference name,ReaderParameters _) => Resolve(name);
        public void Dispose() { }
    }

    private static string Text(JsonElement value,string name) => value.GetProperty(name).GetString() ?? "";
    private static string NativeName(JsonElement row) => row.GetProperty("Declaring").ValueKind == JsonValueKind.String
        ? Text(row,"Declaring") + "." + Text(row,"Name")
        : (Text(row,"Namespace").Length == 0 ? "" : Text(row,"Namespace") + ".") + Text(row,"Name");

    internal List<AsmResolver.DotNet.AssemblyDefinition> Read(MetadataDocument input, string dummy)
    {
        if (used) throw new InvalidOperationException("A declaration builder belongs to one generation job");
        used = true;
        var snapshot = input.Root;
        foreach (var assembly in snapshot.GetProperty("Assemblies").EnumerateArray())
        {
            string name = Text(assembly,"Name");
            var version = name is "mscorlib" or "System" or "System.Core" ? new Version(4,0,0,0) : new Version(0,0,0,0);
            // Cecil's core-library lookup expects an existing PE image. Use its
            // public reference-based type system while authoring a new corlib,
            // then restore the captured assembly identity before serialization.
            var asm = CAssembly.CreateAssembly(new AssemblyNameDefinition(name == "mscorlib" ? "MoonLab.LiveCorlib" : name,version),name + ".dll",new ModuleParameters { Kind = ModuleKind.Dll, AssemblyResolver = new LiveResolver(Assemblies) });
            _ = asm.MainModule.TypeSystem.Object;
            asm.Name.Name = name;
            Assemblies.Add(name,asm);
            foreach (var row in assembly.GetProperty("Classes").EnumerateArray())
            {
                if (Text(row,"Name") == "<Module>") continue;
                var type = new TypeDefinition(Text(row,"Namespace"),Text(row,"Name"),(CTypeAttributes)row.GetProperty("Flags").GetUInt32());
                string key = Canonical(NativeName(row)).Name;
                if (!Types.TryGetValue(key,out var sameName)) Types[key] = sameName = new();
                if (sameName.Any(t => t.Module.Assembly.Name.Name == name)) throw new InvalidDataException("Duplicate live type in assembly " + name + ": " + key);
                Rows.Add(type,row);
                asm.MainModule.Types.Add(type);
                sameName.Add(type);
                foreach (var generic in row.GetProperty("Generics").EnumerateArray())
                    type.GenericParameters.Add(new GenericParameter(Text(generic,"Name"),type) { Attributes = (Mono.Cecil.GenericParameterAttributes)generic.GetProperty("Flags").GetInt32() });
            }
        }
        foreach (var pair in Rows)
        {
            var type = pair.Key; var row = pair.Value;
            if (row.GetProperty("Declaring").ValueKind == JsonValueKind.String)
            {
                var parent = Definition(Text(row,"Declaring"),type.Module);
                type.Module.Types.Remove(type); type.Namespace = ""; parent.NestedTypes.Add(type);
            }
        }
        // Imported ECMA signatures must retain valuetype/class distinctions
        // even when the referenced declaration is filled later in this pass.
        foreach (var pair in Rows)
            if (pair.Value.GetProperty("Parent").ValueKind == JsonValueKind.String)
                pair.Key.BaseType = Resolve(Text(pair.Value,"Parent"),pair.Key.Module,pair.Key.GenericParameters.ToDictionary(p => p.Name,p => p));
        foreach (var pair in Rows)
        {
            var type = pair.Key; var row = pair.Value; var module = type.Module;
            var context = type.GenericParameters.ToDictionary(p => p.Name,p => p);
            if (row.GetProperty("Parent").ValueKind == JsonValueKind.String)
                type.BaseType = Resolve(Text(row,"Parent"),module,context);
            foreach (var generic in row.GetProperty("Generics").EnumerateArray())
                foreach (var constraint in generic.GetProperty("Constraints").EnumerateArray())
                    context[Text(generic,"Name")].Constraints.Add(new GenericParameterConstraint(Resolve(constraint.GetString()!,module,context)));
            foreach (var iface in row.GetProperty("Interfaces").EnumerateArray())
                type.Interfaces.Add(new InterfaceImplementation(Resolve(iface.GetString()!,module,context)));
            if (row.GetProperty("ValueType").GetBoolean() && row.GetProperty("InstanceSize").GetInt32() > 0 && !row.GetProperty("Enum").GetBoolean() && Text(row,"Namespace") + "." + Text(row,"Name") != "System.Void")
            {
                type.ClassSize = Math.Max(1,row.GetProperty("InstanceSize").GetInt32() - 16);
                type.PackingSize = 0;
            }
            foreach (var field in row.GetProperty("Fields").EnumerateArray())
            {
                var use = field.GetProperty("Type");
                var f = new FieldDefinition(Text(field,"Name"),(CFieldAttributes)field.GetProperty("Flags").GetUInt32(),Resolve(Text(use,"Name"),module,context));
                type.Fields.Add(f);
                long offset = field.GetProperty("Offset").GetInt64();
                // Open generic value types have no instantiated layout yet.
                // Only concrete native object offsets include the 16-byte box.
                if (!f.IsStatic && row.GetProperty("ValueType").GetBoolean() && type.GenericParameters.Count == 0 && row.GetProperty("InstanceSize").GetInt32() > 0) offset -= 16;
                if (offset < 0 && !f.IsStatic) throw new InvalidDataException("Negative instance field offset: " + f.FullName);
                // The generator's offset contract is a 32-bit metadata field;
                // preserve native thread-static -1 as FFFFFFFF, not a 64-bit hex.
                Attribute(f,module,"FieldOffsetAttribute",new Dictionary<string,string> { ["Offset"] = "0x" + unchecked((uint)offset).ToString("X") });
                if (field.GetProperty("Constant").ValueKind == JsonValueKind.String)
                    f.Constant = Constant(field.GetProperty("Constant").GetString()!,f.FieldType);
                else if (f.IsLiteral) f.Constant = null;
                if (type.IsExplicitLayout && !f.IsStatic) f.Offset = checked((int)offset);
            }
            var methods = new Dictionary<uint,MethodDefinition>();
            foreach (var method in row.GetProperty("Methods").EnumerateArray())
            {
                var attrs = (CMethodAttributes)method.GetProperty("Flags").GetUInt32();
                var m = new MethodDefinition(Text(method,"Name"),attrs & ~CMethodAttributes.PInvokeImpl,module.TypeSystem.Void);
                type.Methods.Add(m);
                var local = new Dictionary<string,GenericParameter>(context);
                foreach (var generic in method.GetProperty("Generics").EnumerateArray())
                {
                    var p = new GenericParameter(Text(generic,"Name"),m) { Attributes = (Mono.Cecil.GenericParameterAttributes)generic.GetProperty("Flags").GetInt32() };
                    m.GenericParameters.Add(p); local[p.Name] = p;
                }
                m.ReturnType = Resolve(Text(method.GetProperty("ReturnType"),"Name"),module,local);
                foreach (var parameter in method.GetProperty("Parameters").EnumerateArray())
                {
                    var use = parameter.GetProperty("Type");
                    var t = Resolve(Text(use,"Name"),module,local);
                    if (use.GetProperty("ByRef").GetBoolean() && t is not ByReferenceType) t = new ByReferenceType(t);
                    m.Parameters.Add(new ParameterDefinition(Text(parameter,"Name"),Mono.Cecil.ParameterAttributes.None,t));
                }
                foreach (var generic in method.GetProperty("Generics").EnumerateArray())
                    foreach (var constraint in generic.GetProperty("Constraints").EnumerateArray())
                        local[Text(generic,"Name")].Constraints.Add(new GenericParameterConstraint(Resolve(constraint.GetString()!,module,local)));
                uint token = method.GetProperty("Token").GetUInt32();
                long rva = method.GetProperty("Rva").GetInt64();
                Attribute(m,module,"TokenAttribute",new Dictionary<string,string> { ["Token"] = "0x" + token.ToString("X8") });
                Attribute(m,module,"AddressAttribute",new Dictionary<string,string> { ["RVA"] = "0x" + rva.ToString("X"), ["Offset"] = "0x" + rva.ToString("X") });
                if (!m.IsAbstract)
                {
                    m.ImplAttributes = MethodImplAttributes.IL;
                    m.Body = new MethodBody(m);
                    m.Body.Instructions.Add(Instruction.Create(OpCodes.Ldnull));
                    m.Body.Instructions.Add(Instruction.Create(OpCodes.Throw));
                }
                methods.Add(token,m);
            }
            foreach (var property in row.GetProperty("Properties").EnumerateArray())
            {
                methods.TryGetValue(property.GetProperty("Getter").GetUInt32(),out var get);
                methods.TryGetValue(property.GetProperty("Setter").GetUInt32(),out var set);
                if (get == null && set == null) continue;
                var p = new PropertyDefinition(Text(property,"Name"),Mono.Cecil.PropertyAttributes.None,get?.ReturnType ?? set!.Parameters.Last().ParameterType) { GetMethod = get, SetMethod = set };
                foreach (var parameter in get?.Parameters.AsEnumerable() ?? set!.Parameters.Take(set.Parameters.Count - 1))
                    p.Parameters.Add(new ParameterDefinition(parameter.Name,parameter.Attributes,parameter.ParameterType));
                type.Properties.Add(p);
            }
        }
        var sources = new List<AsmResolver.DotNet.AssemblyDefinition>();
        Directory.CreateDirectory(dummy);
        foreach (var asm in Assemblies.Values)
        {
            using var stream = new MemoryStream(); asm.Write(stream);
            byte[] image = stream.ToArray();
            File.WriteAllBytes(Path.Combine(dummy,asm.Name.Name + ".dll"),image);
            sources.Add(AsmResolver.DotNet.AssemblyDefinition.FromBytes(image));
        }
        return sources;
    }

    public void Dispose()
    {
        used = true;
        foreach (var assembly in Assemblies.Values) assembly.Dispose();
        Assemblies.Clear(); Types.Clear(); Rows.Clear(); Attributes.Clear();
        canonicalNames.Clear(); imports.Clear();
    }

    private TypeDefinition Definition(string name,ModuleDefinition module)
    {
        string key = Canonical(name).Name;
        if (!Types.ContainsKey(key))
        {
            // IL2CPP can print inherited generic arguments on the innermost
            // nested name, while ECMA metadata stores arity on the declaring
            // type. Match the complete name and total arity, never a prefix.
            string plain = System.Text.RegularExpressions.Regex.Replace(key,@"`\d+","");
            int arity = System.Text.RegularExpressions.Regex.Matches(key,@"`(\d+)")
                .Cast<System.Text.RegularExpressions.Match>().Sum(m => int.Parse(m.Groups[1].Value));
            var aliases = Types.Where(p => System.Text.RegularExpressions.Regex.Replace(p.Key,@"`\d+","") == plain)
                .SelectMany(p => p.Value).Distinct().Where(t => t.GenericParameters.Count == arity).ToList();
            if (aliases.Count > 0) Types[key] = aliases;
        }
        if (Types.TryGetValue(key,out var candidates))
        {
            var local = candidates.FirstOrDefault(t => t.Module == module);
            if (local != null) return local;
            if (candidates.Count == 1) return candidates[0];
            throw new InvalidDataException("Ambiguous cross-assembly native type: " + name);
        }
        throw new InvalidDataException("Unresolved native definition: " + name + " => " + key);
    }

    private TypeReference ImportDefinition(string name,ModuleDefinition module)
    {
        var definition = Definition(name,module);
        if (definition.Module == module) return definition;
        var key = (definition,module);
        if (!imports.TryGetValue(key,out var reference))
        {
            reference = module.ImportReference(definition);
            reference.IsValueType = Rows[definition].GetProperty("ValueType").GetBoolean();
            imports.Add(key,reference);
        }
        return reference;
    }

    private TypeReference Resolve(string name,ModuleDefinition module,Dictionary<string,GenericParameter> generics)
    {
        if (generics.TryGetValue(name,out var p)) return p;
        if (name.EndsWith("&")) return new ByReferenceType(Resolve(name[..^1],module,generics));
        if (name.EndsWith("*")) return new PointerType(Resolve(name[..^1],module,generics));
        if (name.EndsWith("]"))
        {
            int start = name.LastIndexOf('[');
            if (start >= 0 && name[(start+1)..^1].All(c => c == ','))
                return new ArrayType(Resolve(name[..start],module,generics),name.Length-start-1);
        }
        var primitive = name switch {
            "System.Void" => module.TypeSystem.Void, "System.Boolean" => module.TypeSystem.Boolean,
            "System.Char" => module.TypeSystem.Char, "System.SByte" => module.TypeSystem.SByte,
            "System.Byte" => module.TypeSystem.Byte, "System.Int16" => module.TypeSystem.Int16,
            "System.UInt16" => module.TypeSystem.UInt16, "System.Int32" => module.TypeSystem.Int32,
            "System.UInt32" => module.TypeSystem.UInt32, "System.Int64" => module.TypeSystem.Int64,
            "System.UInt64" => module.TypeSystem.UInt64, "System.Single" => module.TypeSystem.Single,
            "System.Double" => module.TypeSystem.Double, "System.String" => module.TypeSystem.String,
            "System.IntPtr" => module.TypeSystem.IntPtr, "System.UIntPtr" => module.TypeSystem.UIntPtr,
            "System.Object" => module.TypeSystem.Object, "System.TypedReference" => module.TypeSystem.TypedReference,
            _ => null };
        if (primitive != null) return primitive;
        if (Types.ContainsKey(name)) return ImportDefinition(name,module);
        var canonical = Canonical(name);
        var resolved = ImportDefinition(canonical.Name,module);
        if (canonical.Arguments.Count == 0) return resolved;
        var instance = new GenericInstanceType(resolved);
        foreach (string arg in canonical.Arguments) instance.GenericArguments.Add(Resolve(arg,module,generics));
        return instance;
    }

    private (string Name,IReadOnlyList<string> Arguments) Canonical(string name)
    {
        // Most native names are already canonical. Avoid building another
        // string/list for every ordinary parameter, field and base type.
        if (!name.Contains('<')) return (name.Replace('/','.'),Array.Empty<string>());
        if (!canonicalNames.TryGetValue(name,out var value)) canonicalNames.Add(name,value = ParseCanonical(name));
        return value;
    }

    private static (string Name,IReadOnlyList<string> Arguments) ParseCanonical(string name)
    {
        name = name.Replace('/','.');
        var output = new System.Text.StringBuilder(); var arguments = new List<string>();
        for (int i = 0; i < name.Length; i++)
        {
            if (name[i] != '<' || i == 0 || name[i-1] == '.' || name[i-1] == '<') { output.Append(name[i]); continue; }
            int depth = 1, end = i + 1;
            for (; end < name.Length && depth > 0; end++) { if (name[end] == '<') depth++; else if (name[end] == '>') depth--; }
            if (depth != 0) { output.Append(name[i]); continue; }
            string inner = name[(i+1)..(end-1)];
            if (inner.Length == 0) { output.Append("<>"); i = end-1; continue; }
            var parts = new List<string>(); int start = 0; depth = 0;
            for (int j = 0; j <= inner.Length; j++)
            {
                if (j < inner.Length && inner[j] == '<') depth++;
                if (j < inner.Length && inner[j] == '>') depth--;
                if (j == inner.Length || inner[j] == ',' && depth == 0) { parts.Add(inner[start..j].Trim()); start = j+1; }
            }
            string current = output.ToString(); int segment = current.LastIndexOf('.') + 1;
            if (!current[segment..].Contains('`')) output.Append('`').Append(parts.Count);
            arguments.AddRange(parts); i = end-1;
        }
        return (output.ToString(),arguments);
    }

    private object Constant(string raw,TypeReference type)
    {
        ulong value = ulong.Parse(raw,CultureInfo.InvariantCulture);
        string kind = type.FullName;
        if (Types.ContainsKey(Canonical(kind).Name) && Rows[Definition(kind,type.Module)].GetProperty("Enum").GetBoolean())
        {
            var definition = Definition(kind,type.Module);
            var underlying = Rows[definition].GetProperty("Fields").EnumerateArray().First(f => Text(f,"Name") == "value__");
            kind = Text(underlying.GetProperty("Type"),"Name");
        }
        return kind switch {
            "System.Boolean" => value != 0, "System.Char" => unchecked((char)value),
            "System.Byte" => unchecked((byte)value), "System.SByte" => unchecked((sbyte)value),
            "System.Int16" => unchecked((short)value), "System.UInt16" => unchecked((ushort)value),
            "System.Int32" => unchecked((int)value), "System.UInt32" => unchecked((uint)value),
            "System.Int64" => unchecked((long)value), "System.UInt64" => value,
            "System.Single" => BitConverter.Int32BitsToSingle(unchecked((int)value)),
            "System.Double" => BitConverter.Int64BitsToDouble(unchecked((long)value)),
            _ => throw new InvalidDataException("Unsupported constant type " + kind) };
    }

    private void Attribute(ICustomAttributeProvider owner,ModuleDefinition module,string name,Dictionary<string,string> values)
    {
        string assembly = module.Assembly.Name.Name;
        if (!Attributes.TryGetValue(assembly,out var defs)) Attributes[assembly] = defs = new();
        if (!defs.TryGetValue(name,out var ctor))
        {
            var type = new TypeDefinition("Cpp2ILInjected",name,CTypeAttributes.Public | CTypeAttributes.Class,
                new TypeReference("System","Attribute",module,module.TypeSystem.CoreLibrary));
            module.Types.Add(type);
            foreach (string field in name switch { "TokenAttribute" => new[] { "Token" }, "FieldOffsetAttribute" => new[] { "Offset" }, _ => new[] { "RVA","Offset","VA","Slot" } })
                type.Fields.Add(new FieldDefinition(field,CFieldAttributes.Public,module.TypeSystem.String));
            var constructor = new MethodDefinition(".ctor",CMethodAttributes.Public | CMethodAttributes.SpecialName | CMethodAttributes.RTSpecialName,module.TypeSystem.Void);
            type.Methods.Add(constructor); constructor.Body.Instructions.Add(Instruction.Create(OpCodes.Ret));
            defs[name] = ctor = constructor;
        }
        var attribute = new CustomAttribute(ctor);
        foreach (var pair in values) attribute.Fields.Add(new CustomAttributeNamedArgument(pair.Key,new CustomAttributeArgument(module.TypeSystem.String,pair.Value)));
        owner.CustomAttributes.Add(attribute);
    }
}
