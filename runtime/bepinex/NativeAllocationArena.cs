using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace MoonLab.BepInExAdapter;

// One owner for native descriptors and projection buffers. Once installed,
// IL2CPP can retain their addresses until process exit; a GC finalizer must
// never free them. Unpublished handlers/tests can explicitly release them.
internal sealed unsafe class NativeAllocationArena : IDisposable
{
    private readonly List<IntPtr> allocations = new();
    internal long Bytes { get; private set; }
    private bool disposed;
    private readonly object gate = new();
    internal IntPtr Allocate(int bytes)
    {
        lock (gate)
        {
            if (disposed) throw new ObjectDisposedException(nameof(NativeAllocationArena));
            if (bytes < 0) throw new ArgumentOutOfRangeException(nameof(bytes));
            if (bytes == 0) return IntPtr.Zero;
            IntPtr pointer = Marshal.AllocHGlobal(bytes);
            try { new Span<byte>((void*)pointer, bytes).Clear(); allocations.Add(pointer); }
            catch { Marshal.FreeHGlobal(pointer); throw; }
            Bytes += bytes;
            return pointer;
        }
    }
    public void Dispose()
    {
        lock (gate)
        {
            if (disposed) return;
            foreach (var pointer in allocations) Marshal.FreeHGlobal(pointer);
            allocations.Clear(); Bytes = 0; disposed = true;
        }
    }
}
