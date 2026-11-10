using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace MoonLab.BepInExAdapter;

internal static unsafe class Native
{
    internal static IntPtr Domain;
    internal static IntPtr Module;
    internal static void Initialize(string path)
    {
        Module = NativeLibrary.Load(path);
        NativeLibrary.SetDllImportResolver(typeof(Native).Assembly, (name, _, _) => name == "GameAssembly" ? Module : IntPtr.Zero);
        Domain = domain_get();
        if (Domain == IntPtr.Zero) throw new InvalidOperationException("Live IL2CPP domain is not ready");
        if (thread_current() == IntPtr.Zero) thread_attach(Domain);
    }
    internal static string Text(IntPtr p) => p == IntPtr.Zero ? "" : Marshal.PtrToStringUTF8(p)!;
    internal static string TypeName(IntPtr p)
    {
        IntPtr name = type_get_name(p);
        try { return Text(name); } finally { free(name); }
    }
    internal static IEnumerable<IntPtr> Iterate(IntPtr owner, Func<IntPtr, IntPtr, (IntPtr Value, IntPtr Next)> read)
    {
        IntPtr iterator = IntPtr.Zero;
        for (int n = 0; n < 100000; n++)
        {
            var row = read(owner, iterator); iterator = row.Next;
            if (row.Value == IntPtr.Zero) yield break;
            yield return row.Value;
        }
        throw new InvalidOperationException("Native metadata iterator exceeded its bound");
    }
    [DllImport("GameAssembly", EntryPoint="il2cpp_domain_get")] internal static extern IntPtr domain_get();
    [DllImport("GameAssembly", EntryPoint="il2cpp_thread_current")] internal static extern IntPtr thread_current();
    [DllImport("GameAssembly", EntryPoint="il2cpp_thread_attach")] internal static extern IntPtr thread_attach(IntPtr domain);
    [DllImport("GameAssembly", EntryPoint="il2cpp_domain_get_assemblies")] internal static extern IntPtr domain_get_assemblies(IntPtr domain, out nuint count);
    [DllImport("GameAssembly", EntryPoint="il2cpp_assembly_get_image")] internal static extern IntPtr assembly_get_image(IntPtr assembly);
    [DllImport("GameAssembly", EntryPoint="il2cpp_image_get_name")] internal static extern IntPtr image_get_name(IntPtr image);
    [DllImport("GameAssembly", EntryPoint="il2cpp_image_get_class_count")] internal static extern nuint image_get_class_count(IntPtr image);
    [DllImport("GameAssembly", EntryPoint="il2cpp_image_get_class")] internal static extern IntPtr image_get_class(IntPtr image, nuint index);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_name")] internal static extern IntPtr class_get_name(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_namespace")] internal static extern IntPtr class_get_namespace(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_declaring_type")] internal static extern IntPtr class_get_declaring_type(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_parent")] internal static extern IntPtr class_get_parent(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_type")] internal static extern IntPtr class_get_type(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_flags")] internal static extern uint class_get_flags(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_type_token")] internal static extern uint class_get_type_token(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_instance_size")] internal static extern int class_instance_size(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_is_valuetype")] [return: MarshalAs(UnmanagedType.I1)] internal static extern bool class_is_valuetype(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_is_enum")] [return: MarshalAs(UnmanagedType.I1)] internal static extern bool class_is_enum(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_fields")] internal static extern IntPtr class_get_fields(IntPtr klass, ref IntPtr iterator);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_methods")] internal static extern IntPtr class_get_methods(IntPtr klass, ref IntPtr iterator);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_properties")] internal static extern IntPtr class_get_properties(IntPtr klass, ref IntPtr iterator);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_interfaces")] internal static extern IntPtr class_get_interfaces(IntPtr klass, ref IntPtr iterator);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_from_name")] internal static extern IntPtr class_from_name(IntPtr image, string ns, string name);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_get_method_from_name")] internal static extern IntPtr class_get_method_from_name(IntPtr klass, string name, int args);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_from_type")] internal static extern IntPtr class_from_type(IntPtr type);
    [DllImport("GameAssembly", EntryPoint="il2cpp_type_get_name")] internal static extern IntPtr type_get_name(IntPtr type);
    [DllImport("GameAssembly", EntryPoint="il2cpp_type_get_type")] internal static extern int type_get_type(IntPtr type);
    [DllImport("GameAssembly", EntryPoint="il2cpp_type_is_byref")] [return: MarshalAs(UnmanagedType.I1)] internal static extern bool type_is_byref(IntPtr type);
    [DllImport("GameAssembly", EntryPoint="il2cpp_field_get_name")] internal static extern IntPtr field_get_name(IntPtr field);
    [DllImport("GameAssembly", EntryPoint="il2cpp_field_get_type")] internal static extern IntPtr field_get_type(IntPtr field);
    [DllImport("GameAssembly", EntryPoint="il2cpp_field_get_flags")] internal static extern uint field_get_flags(IntPtr field);
    [DllImport("GameAssembly", EntryPoint="il2cpp_field_get_offset")] internal static extern nuint field_get_offset(IntPtr field);
    [DllImport("GameAssembly", EntryPoint="il2cpp_field_static_get_value")] internal static extern void field_static_get_value(IntPtr field, void* value);
    [DllImport("GameAssembly", EntryPoint="il2cpp_method_get_name")] internal static extern IntPtr method_get_name(IntPtr method);
    [DllImport("GameAssembly", EntryPoint="il2cpp_method_get_token")] internal static extern uint method_get_token(IntPtr method);
    [DllImport("GameAssembly", EntryPoint="il2cpp_method_get_flags")] internal static extern uint method_get_flags(IntPtr method, out uint implementation);
    [DllImport("GameAssembly", EntryPoint="il2cpp_method_get_param_count")] internal static extern uint method_get_param_count(IntPtr method);
    [DllImport("GameAssembly", EntryPoint="il2cpp_method_get_param")] internal static extern IntPtr method_get_param(IntPtr method, uint index);
    [DllImport("GameAssembly", EntryPoint="il2cpp_method_get_param_name")] internal static extern IntPtr method_get_param_name(IntPtr method, uint index);
    [DllImport("GameAssembly", EntryPoint="il2cpp_method_get_return_type")] internal static extern IntPtr method_get_return_type(IntPtr method);
    [DllImport("GameAssembly", EntryPoint="il2cpp_method_is_generic")] [return: MarshalAs(UnmanagedType.I1)] internal static extern bool method_is_generic(IntPtr method);
    [DllImport("GameAssembly", EntryPoint="il2cpp_property_get_name")] internal static extern IntPtr property_get_name(IntPtr property);
    [DllImport("GameAssembly", EntryPoint="il2cpp_property_get_get_method")] internal static extern IntPtr property_get_get_method(IntPtr property);
    [DllImport("GameAssembly", EntryPoint="il2cpp_property_get_set_method")] internal static extern IntPtr property_get_set_method(IntPtr property);
    [DllImport("GameAssembly", EntryPoint="il2cpp_free")] internal static extern void free(IntPtr pointer);
    [DllImport("GameAssembly", EntryPoint="il2cpp_method_get_object")] internal static extern IntPtr method_get_object(IntPtr method, IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_type_get_object")] internal static extern IntPtr type_get_object(IntPtr type);
    [DllImport("GameAssembly", EntryPoint="il2cpp_object_get_class")] internal static extern IntPtr object_get_class(IntPtr obj);
    [DllImport("GameAssembly", EntryPoint="il2cpp_object_unbox")] internal static extern IntPtr object_unbox(IntPtr obj);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_from_system_type")] internal static extern IntPtr class_from_system_type(IntPtr obj);
    [DllImport("GameAssembly", EntryPoint="il2cpp_class_is_generic")] [return: MarshalAs(UnmanagedType.I1)] internal static extern bool class_is_generic(IntPtr klass);
    [DllImport("GameAssembly", EntryPoint="il2cpp_runtime_invoke")] internal static extern IntPtr runtime_invoke(IntPtr method, IntPtr self, IntPtr args, out IntPtr exception);
    [DllImport("GameAssembly", EntryPoint="il2cpp_array_length")] internal static extern nuint array_length(IntPtr array);
    [DllImport("GameAssembly", EntryPoint="il2cpp_array_object_header_size")] internal static extern uint array_object_header_size();
    [DllImport("GameAssembly", EntryPoint="il2cpp_gchandle_new")] internal static extern uint gchandle_new(IntPtr obj, [MarshalAs(UnmanagedType.I1)] bool pinned);
    [DllImport("GameAssembly", EntryPoint="il2cpp_gchandle_free")] internal static extern void gchandle_free(uint handle);
    [DllImport("GameAssembly", EntryPoint="il2cpp_string_chars")] internal static extern IntPtr string_chars(IntPtr text);
    [DllImport("GameAssembly", EntryPoint="il2cpp_string_length")] internal static extern int string_length(IntPtr text);

    internal sealed class Root : IDisposable
    {
        internal readonly IntPtr Pointer;
        private readonly uint handle;
        internal Root(IntPtr pointer)
        {
            Pointer = pointer;
            if (pointer != IntPtr.Zero) handle = gchandle_new(pointer,false);
        }
        public void Dispose() { if (handle != 0) gchandle_free(handle); }
    }
    internal static Root Reflect(IntPtr obj, string method)
    {
        IntPtr target = class_get_method_from_name(object_get_class(obj),method,0);
        if (target == IntPtr.Zero) throw new MissingMethodException("Native reflection metadata: " + method);
        IntPtr value = runtime_invoke(target,obj,IntPtr.Zero,out IntPtr error);
        if (error != IntPtr.Zero) throw new InvalidOperationException("Native reflection failed: " + method);
        return new Root(value);
    }
    internal static string ManagedText(IntPtr text) => text == IntPtr.Zero ? "" : Marshal.PtrToStringUni(string_chars(text),string_length(text))!;
}
