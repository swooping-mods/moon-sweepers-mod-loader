using System;
using System.Reflection;
using System.Runtime.InteropServices;
using MoonLab.ManagedHost;

internal static class ManagedHostCompatibilityChecks
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int Zero();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int One(int value);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int Many(int a, int b, int c, int d, int e, int f, int g, int h);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate void Ref(ref int value, int delta);
    [StructLayout(LayoutKind.Sequential)] private struct Pair { public long X, Y; }
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate Pair Structure(Pair value);
    private sealed class InstanceSignature { public int Invoke(int value) => value; }

    private static T Proxy<T>(T target, MethodBase? signature = null) where T : Delegate
    {
        var method = LegacyDetourCompatibility.GenerateNativeProxy(Marshal.GetFunctionPointerForDelegate(target),
            signature ?? typeof(T).GetMethod("Invoke")!);
        return (T)method.CreateDelegate(typeof(T));
    }

    private static void Require(bool value, string name)
    {
        if (!value) throw new InvalidOperationException(name);
        Console.WriteLine("passed=" + name);
    }

    private static void Main()
    {
        Zero zero = () => 71;
        var zeroProxy = Proxy(zero);
        Require(zeroProxy() == 71, "zero-argument native call");
        Many many = (a,b,c,d,e,f,g,h) => a+2*b+3*c+4*d+5*e+6*f+7*g+8*h;
        var manyProxy = Proxy(many);
        Require(manyProxy(1,2,3,4,5,6,7,8) == 204, "eight arguments including stack arguments");
        Ref reference = (ref int value, int delta) => value += delta;
        var refProxy = Proxy(reference); var count = 17;
        refProxy(ref count, 8);
        Require(count == 25, "by-reference argument and void return");
        Structure structure = value => new Pair { X = value.Y + 2, Y = value.X + 3 };
        var structProxy = Proxy(structure);
        var pair = structProxy(new Pair { X = 11, Y = 29 });
        Require(pair.X == 31 && pair.Y == 14, "value type argument and return");
        One one = value => value*3;
        // Legacy MonoMod uses only GetParameters even for instance MethodBase
        // signatures. A delegate Invoke method itself is an instance method.
        var instanceProxy = Proxy(one, typeof(InstanceSignature).GetMethod("Invoke"));
        Require(instanceProxy(7) == 21, "legacy instance-signature parameter semantics");
        GC.Collect(); GC.WaitForPendingFinalizers(); GC.Collect();
        Require(zeroProxy() == 71 && manyProxy(1,2,3,4,5,6,7,8) == 204 && instanceProxy(9) == 27,
                "generated proxies survive forced collection while owned");
        try { LegacyDetourCompatibility.GenerateNativeProxy(IntPtr.Zero, typeof(Zero).GetMethod("Invoke")!); throw new Exception("zero pointer admitted"); }
        catch (ArgumentException) { Console.WriteLine("passed=invalid pointer rejected"); }
        GC.KeepAlive(zero); GC.KeepAlive(many); GC.KeepAlive(reference); GC.KeepAlive(structure); GC.KeepAlive(one);
        Console.WriteLine("Managed native trampoline checks passed");
    }
}
