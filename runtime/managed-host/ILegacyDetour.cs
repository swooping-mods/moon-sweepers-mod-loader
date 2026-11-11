using System;
using System.Reflection;

namespace MoonLab.ManagedHost;

// The be.791 native Dobby/Funchook wrappers use this contract independently
// of modern MonoMod's managed-detour ordering/configuration interface.
public interface ILegacyDetour : IDisposable
{
    bool IsValid { get; }
    bool IsApplied { get; }
    void Apply();
    void Undo();
    void Free();
    MethodBase GenerateTrampoline(MethodBase? signature = null);
    T GenerateTrampoline<T>() where T : Delegate;
}
