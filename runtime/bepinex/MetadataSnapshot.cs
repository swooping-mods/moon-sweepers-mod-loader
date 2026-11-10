using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;

namespace MoonLab.BepInExAdapter;

internal sealed record TypeUse(string Name, int Kind, bool ByRef);
internal sealed record ParameterRow(string Name, TypeUse Type);
internal sealed record FieldRow(string Name, TypeUse Type, uint Flags, long Offset, string? Constant);
internal sealed record GenericRow(string Name, int Flags, string[] Constraints);
internal sealed record MethodRow(string Name, uint Token, uint Flags, uint Implementation, long Rva, bool Generic, GenericRow[] Generics, TypeUse ReturnType, ParameterRow[] Parameters);
internal sealed record PropertyRow(string Name, uint Getter, uint Setter);
internal sealed record ClassRow(string Name, string Namespace, uint Token, uint Flags, string? Parent, string? Declaring, bool ValueType, bool Enum, int InstanceSize, GenericRow[] Generics, string[] Interfaces, FieldRow[] Fields, MethodRow[] Methods, PropertyRow[] Properties);
internal sealed record AssemblyRow(string Name, ClassRow[] Classes);
internal sealed record Snapshot(string Schema, string GameHash, AssemblyRow[] Assemblies);

internal static unsafe class MetadataSnapshot
{
    private static GenericRow[] Generics(IntPtr reflected)
    {
        using var owner = new Native.Root(reflected);
        using var args = Native.Reflect(reflected,"GetGenericArguments");
        int count = checked((int)Native.array_length(args.Pointer));
        if (count > 128) throw new InvalidOperationException("Generic argument budget exceeded");
        int header = checked((int)Native.array_object_header_size());
        if (header != 32) throw new InvalidOperationException("Unexpected reflection array ABI");
        var rows = new List<GenericRow>();
        for (int i = 0; i < count; i++)
        {
            IntPtr arg = Marshal.ReadIntPtr(args.Pointer,header + i * IntPtr.Size);
            using var name = Native.Reflect(arg,"get_Name");
            using var attributes = Native.Reflect(arg,"get_GenericParameterAttributes");
            using var constraints = Native.Reflect(arg,"GetGenericParameterConstraints");
            int flags = Marshal.ReadInt32(Native.object_unbox(attributes.Pointer));
            int length = checked((int)Native.array_length(constraints.Pointer));
            if (length > 128) throw new InvalidOperationException("Constraint budget exceeded");
            var types = new List<string>();
            for (int j = 0; j < length; j++)
            {
                IntPtr c = Marshal.ReadIntPtr(constraints.Pointer,header + j * IntPtr.Size);
                IntPtr klass = Native.class_from_system_type(c);
                if (klass != IntPtr.Zero) types.Add(TypeName(klass)!);
                else
                {
                    using var constraintName = Native.Reflect(c,"get_Name");
                    types.Add(Native.ManagedText(constraintName.Pointer));
                }
            }
            rows.Add(new(Native.ManagedText(name.Pointer),flags,types.ToArray()));
        }
        return rows.ToArray();
    }
    internal static TypeUse Use(IntPtr type) => new(Native.TypeName(type), Native.type_get_type(type), Native.type_is_byref(type));
    internal static string? TypeName(IntPtr klass) => klass == IntPtr.Zero ? null : Native.TypeName(Native.class_get_type(klass));
    internal static Snapshot Capture(string hash)
    {
        IntPtr list = Native.domain_get_assemblies(Native.Domain, out nuint count);
        if (count == 0 || count > 512) throw new InvalidOperationException("Invalid live assembly count");
        var assemblies = new List<AssemblyRow>();
        long total = 0;
        for (nuint i = 0; i < count; i++)
        {
            IntPtr image = Native.assembly_get_image(Marshal.ReadIntPtr(list, checked((int)i * IntPtr.Size)));
            nuint classes = Native.image_get_class_count(image);
            total += (long)classes;
            if (total > 100000) throw new InvalidOperationException("Metadata class budget exceeded");
            var rows = new List<ClassRow>();
            for (nuint j = 0; j < classes; j++)
            {
                IntPtr klass = Native.image_get_class(image, j);
                var fields = new List<FieldRow>();
                IntPtr iterator = IntPtr.Zero, member;
                while ((member = Native.class_get_fields(klass, ref iterator)) != IntPtr.Zero)
                {
                    if (fields.Count >= 100000) throw new InvalidOperationException("Field budget exceeded");
                    var type = Use(Native.field_get_type(member));
                    uint flags = Native.field_get_flags(member);
                    string? constant = null;
                    if ((flags & 0x40) != 0 && (type.Kind is >= 2 and <= 13 ||
                        type.Kind == 17 && Native.class_is_enum(Native.class_from_type(Native.field_get_type(member)))))
                    {
                        ulong value = 0; Native.field_static_get_value(member, &value);
                        constant = value.ToString(System.Globalization.CultureInfo.InvariantCulture);
                    }
                    fields.Add(new(Native.Text(Native.field_get_name(member)), type, flags, (long)Native.field_get_offset(member), constant));
                }
                var methods = new List<MethodRow>(); iterator = IntPtr.Zero;
                while ((member = Native.class_get_methods(klass, ref iterator)) != IntPtr.Zero)
                {
                    if (methods.Count >= 100000) throw new InvalidOperationException("Method budget exceeded");
                    uint n = Native.method_get_param_count(member);
                    if (n > 1024) throw new InvalidOperationException("Parameter budget exceeded");
                    var parameters = new List<ParameterRow>();
                    for (uint p = 0; p < n; p++) parameters.Add(new(Native.Text(Native.method_get_param_name(member,p)), Use(Native.method_get_param(member,p))));
                    uint flags = Native.method_get_flags(member,out uint impl);
                    long address = Marshal.ReadIntPtr(member).ToInt64();
                    long rva = address == 0 ? 0 : address - Native.Module.ToInt64();
                    if (rva < 0 || rva >= 0x3000000) rva = 0;
                    bool generic = Native.method_is_generic(member);
                    var generics = generic ? Generics(Native.method_get_object(member,klass)) : Array.Empty<GenericRow>();
                    methods.Add(new(Native.Text(Native.method_get_name(member)),Native.method_get_token(member),flags,impl,rva,generic,generics,Use(Native.method_get_return_type(member)),parameters.ToArray()));
                }
                var properties = new List<PropertyRow>(); iterator = IntPtr.Zero;
                while ((member = Native.class_get_properties(klass,ref iterator)) != IntPtr.Zero)
                {
                    IntPtr get = Native.property_get_get_method(member), set = Native.property_get_set_method(member);
                    properties.Add(new(Native.Text(Native.property_get_name(member)),get == IntPtr.Zero ? 0 : Native.method_get_token(get),set == IntPtr.Zero ? 0 : Native.method_get_token(set)));
                }
                var interfaces = new List<string>(); iterator = IntPtr.Zero;
                while ((member = Native.class_get_interfaces(klass,ref iterator)) != IntPtr.Zero) interfaces.Add(TypeName(member)!);
                var classGenerics = Native.class_is_generic(klass) ? Generics(Native.type_get_object(Native.class_get_type(klass))) : Array.Empty<GenericRow>();
                rows.Add(new(Native.Text(Native.class_get_name(klass)),Native.Text(Native.class_get_namespace(klass)),Native.class_get_type_token(klass),Native.class_get_flags(klass),TypeName(Native.class_get_parent(klass)),TypeName(Native.class_get_declaring_type(klass)),Native.class_is_valuetype(klass),Native.class_is_enum(klass),Native.class_instance_size(klass),classGenerics,interfaces.ToArray(),fields.ToArray(),methods.ToArray(),properties.ToArray()));
            }
            assemblies.Add(new(Path.GetFileNameWithoutExtension(Native.Text(Native.image_get_name(image))),rows.ToArray()));
        }
        return new("moonlab-live-metadata/v1",hash,assemblies.ToArray());
    }
}
