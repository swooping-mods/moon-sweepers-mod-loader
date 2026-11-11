using System;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.InteropServices;

[assembly: AssemblyVersion("1.0.0.0")]

namespace MoonLab.ManagedHost;

public static class LegacyDetourCompatibility
{
    // be.791 exposes MethodBase trampolines through MonoMod's retired helper.
    // Windows x64 has one native calling convention; the generic delegate path
    // still uses Marshal.GetDelegateForFunctionPointer in the original host.
    public static MethodInfo GenerateNativeProxy(IntPtr address, MethodBase signature)
    {
        if (address == IntPtr.Zero) throw new ArgumentException("A native trampoline is required", nameof(address));
        if (signature == null) throw new ArgumentNullException(nameof(signature));
        var arguments = signature.GetParameters().Select(parameter => parameter.ParameterType).ToArray();
        var result = signature is MethodInfo method ? method.ReturnType : typeof(void);
        var proxy = new DynamicMethod("MoonLabNativeTrampoline", result, arguments,
                                      typeof(LegacyDetourCompatibility).Module, true);
        var il = proxy.GetILGenerator();
        for (var index = 0; index < arguments.Length; index++) il.Emit(OpCodes.Ldarg, checked((short)index));
        il.Emit(OpCodes.Ldc_I8, address.ToInt64());
        il.Emit(OpCodes.Conv_I);
        il.EmitCalli(OpCodes.Calli, CallingConvention.Cdecl, result, arguments);
        il.Emit(OpCodes.Ret);
        return proxy;
    }
}
