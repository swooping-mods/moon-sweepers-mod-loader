using System;
using System.Runtime.InteropServices;
using Il2CppInterop.Runtime;
using Il2CppInterop.Runtime.InteropTypes.Arrays;

namespace MoonLab.BepInExAdapter;

// Original wrappers for engine APIs whose native calls survived managed
// stripping. The supported engine identity is checked before these are used.
public static class UnityShims
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int PropertyTypeCall(IntPtr nativeShader, int index);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int PropertyCountCall(IntPtr nativeShader);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate void MaskCall(IntPtr nativeCamera, int mask);
    private static readonly MaskCall SetMask = IL2CPP.ResolveICall<MaskCall>("UnityEngine.Camera::set_cullingMask_Injected");
    private static readonly PropertyCountCall Count = IL2CPP.ResolveICall<PropertyCountCall>("UnityEngine.Shader::GetPropertyCount_Injected");
    private static readonly PropertyTypeCall PropertyType =
        IL2CPP.ResolveICall<PropertyTypeCall>("UnityEngine.Shader::GetPropertyType_Injected");
    public static int ShaderPropertyType(IntPtr nativeShader, int index)
    {
        if (nativeShader == IntPtr.Zero || index < 0 || index >= Count(nativeShader)) throw new ArgumentOutOfRangeException(nameof(index));
        int result = PropertyType(nativeShader,index);
        if (result < 0 || result > 5) throw new InvalidOperationException("Unqualified shader property kind");
        return result;
    }
    public static void CameraCullingMask(IntPtr nativeCamera, int mask)
    {
        if (nativeCamera == IntPtr.Zero) throw new ArgumentNullException(nameof(nativeCamera));
        SetMask(nativeCamera,mask);
    }
    public static Il2CppStructArray<TTarget> ConvertColors<TSource,TTarget>(Il2CppStructArray<TSource> source)
        where TSource : unmanaged where TTarget : unmanaged
    {
        if (Marshal.SizeOf<TSource>() != 16 || Marshal.SizeOf<TTarget>() != 4 || source.Length > 16 * 1024 * 1024)
            throw new ArgumentException("Color pixel conversion layout/budget mismatch");
        var result = new Il2CppStructArray<TTarget>(source.Length);
        var floats = MemoryMarshal.Cast<TSource,float>(source.AsSpan());
        var bytes = MemoryMarshal.AsBytes(result.AsSpan());
        for (int i = 0; i < bytes.Length; i++)
            bytes[i] = (byte)MathF.Round(Math.Clamp(floats[i],0f,1f) * 255f);
        return result;
    }
}
