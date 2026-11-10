using System;
using System.Runtime.InteropServices;

namespace MoonSweepers.Api;

public enum NativeRuntimeState : uint { Pending = 0, Ready = 1, Failed = 2 }

/// <summary>A non-owning connection to the resident native loader. Bind tables
/// once after Ready; each provider still defines its own thread/object rules.</summary>
public sealed class RuntimeClient
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate uint StateCall();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate uint AbiCall();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate IntPtr GetCall();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate IntPtr FindCall(
        [MarshalAs(UnmanagedType.LPUTF8Str)] string provider,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string service, uint abi, uint size);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    private static extern IntPtr GetModuleHandleW(string name);
    [DllImport("kernel32.dll", CharSet = CharSet.Ansi, ExactSpelling = true)]
    private static extern IntPtr GetProcAddress(IntPtr module, string name);

    private readonly StateCall state;
    private readonly FindCall find;
    private RuntimeClient(StateCall state, FindCall find) { this.state = state; this.find = find; }

    public NativeRuntimeState State
    {
        get
        {
            uint value = state();
            if (value > (uint)NativeRuntimeState.Failed)
                throw new InvalidOperationException("Unknown native runtime state");
            return (NativeRuntimeState)value;
        }
    }

    /// <summary>Never loads a DLL or starts another mod. False means no compatible
    /// loader; Pending is a separate state. Do not block the game thread waiting.</summary>
    public static bool TryConnect(out RuntimeClient? client)
    {
        client = null;
        if (IntPtr.Size != 8 || !OperatingSystem.IsWindows()) return false;
        IntPtr module = GetModuleHandleW("version.dll");
        return module != IntPtr.Zero && TryConnect(name => GetProcAddress(module, name), out client);
    }

    // The same connector is compiled with a native fixture on non-Windows hosts.
    internal static bool TryConnect(Func<string, IntPtr> resolve, out RuntimeClient? client)
    {
        client = null;
        if (IntPtr.Size != 8) return false;
        IntPtr abi = resolve("MoonLab_LoaderAbi"), query = resolve("MoonLab_RuntimeState_v1"),
            get = resolve("MoonLab_GetRuntimeApi_v1");
        if (abi == IntPtr.Zero || query == IntPtr.Zero || get == IntPtr.Zero ||
            Marshal.GetDelegateForFunctionPointer<AbiCall>(abi)() != 1) return false;
        IntPtr table = Marshal.GetDelegateForFunctionPointer<GetCall>(get)();
        if (table == IntPtr.Zero || (uint)Marshal.ReadInt32(table) < 40 || Marshal.ReadInt32(table, 4) != 1)
            return false;
        for (int offset = 8; offset < 40; offset += 8)
            if (Marshal.ReadIntPtr(table, offset) == IntPtr.Zero) return false;
        client = new RuntimeClient(Marshal.GetDelegateForFunctionPointer<StateCall>(query),
            Marshal.GetDelegateForFunctionPointer<FindCall>(Marshal.ReadIntPtr(table, 16)));
        return true;
    }

    /// <summary>False while startup is Pending or the committed provider is absent/
    /// incompatible. Failed startup throws. Returned storage has process lifetime.</summary>
    public bool TryFind(string provider, string service, uint abi, uint minimumSize, out IntPtr table)
    {
        ValidateName(provider, false, 64);
        ValidateName(service, true, 160);
        if (provider.Length + service.Length + 1 > 160 || abi == 0 || minimumSize == 0 || minimumSize > 65536)
            throw new ArgumentException("Invalid native service contract");
        table = IntPtr.Zero;
        NativeRuntimeState current = State;
        if (current == NativeRuntimeState.Failed) throw new InvalidOperationException("Native startup failed");
        if (current != NativeRuntimeState.Ready) return false;
        table = find(provider, service, abi, minimumSize);
        return table != IntPtr.Zero;
    }

    private static void ValidateName(string value, bool service, int maximum)
    {
        if (string.IsNullOrEmpty(value) || value.Length > maximum)
            throw new ArgumentException("Invalid native service identity");
        bool start = true;
        foreach (char c in value)
        {
            bool letter = c >= 'a' && c <= 'z', digit = c >= '0' && c <= '9';
            if (start && !(letter || (!service && digit))) throw new ArgumentException("Invalid native service identity");
            if (letter || digit) start = false;
            else if (c == '-') { if (!service) start = true; }
            else if (service && c == '.') start = true;
            else throw new ArgumentException("Invalid native service identity");
        }
        if (start) throw new ArgumentException("Invalid native service identity");
    }
}
