using System;
using System.Collections;
using System.Reflection;
using Il2CppInterop.Runtime.Runtime;
using Il2CppInterop.Runtime.Runtime.VersionSpecific.Class;

namespace MoonLab.BepInExAdapter;

// All reliance on the pinned upstream's private registration/lifecycle contract
// belongs here. This is deliberately not presented as a stable upstream API.
internal static class Interop153Bridge
{
    internal static Unity6000_6ClassLayout? InstalledLayout { get; private set; }
    internal interface IPendingClass { void CompleteIfReady(); }

    internal static void InstallProfile(IGameProfile profile)
    {
        switch (profile.NativeLayoutId)
        {
            case "unity-6000.6-class/v1":
                var layout = new Unity6000_6ClassLayout();
                layout.Install(); InstalledLayout = layout; break;
            default: throw new InvalidOperationException("Unqualified native layout: " + profile.NativeLayoutId);
        }
    }

    internal static void Install(INativeClassStructHandler handler)
    {
        var version = typeof(UnityVersionHandler).Assembly.GetName().Version;
        if (version != new Version(1,5,3,0))
            throw new InvalidOperationException("Unsupported Il2CppInterop handler contract: " + version);
        var flags = BindingFlags.Static | BindingFlags.NonPublic;
        var field = typeof(UnityVersionHandler).GetField("classStructHandler",flags)
            ?? throw new MissingFieldException("Il2CppInterop class handler contract changed");
        var all = (IDictionary)(typeof(UnityVersionHandler).GetField("Handlers",flags)?.GetValue(null)
            ?? throw new MissingFieldException("Il2CppInterop handler registry changed"));
        object? previousField = field.GetValue(null);
        object key = typeof(INativeClassStructHandler);
        bool hadKey = all.Contains(key);
        object? previousEntry = all[key];
        try { field.SetValue(null,handler); all[key] = handler; }
        catch
        {
            field.SetValue(null,previousField);
            if (hadKey) all[key] = previousEntry; else all.Remove(key);
            throw;
        }
    }

    // 1.5.3 finishes the class hierarchy immediately before accessing
    // ByValArg.Data. There is no public completion callback in this contract.
    internal static void BeforeByValArgAccess(IPendingClass pending) => pending.CompleteIfReady();
}
