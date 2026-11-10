using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Il2CppInterop.Runtime.Runtime;

namespace MoonLab.BepInExAdapter;

// Created only by the explicitly requested private profiling route. Phase
// attribution includes verification and preparation, never just generation.
internal sealed class StartupMeasurements
{
    private readonly long started = Stopwatch.GetTimestamp();
    private readonly long initialBytes = System.GC.GetAllocatedBytesForCurrentThread();
    private long previous, previousBytes;
    private readonly List<Phase> phases = new();
    internal sealed record Phase(string Name, double Milliseconds, long ManagedBytes);

    internal StartupMeasurements() { previous = started; previousBytes = initialBytes; }
    internal void Mark(string name)
    {
        long now = Stopwatch.GetTimestamp(), bytes = System.GC.GetAllocatedBytesForCurrentThread();
        phases.Add(new(name, (now - previous) * (1000d / Stopwatch.Frequency), bytes - previousBytes));
        previous = now; previousBytes = bytes;
    }
    internal object Snapshot() => new {
        elapsed_ms = (Stopwatch.GetTimestamp() - started) * (1000d / Stopwatch.Frequency),
        managed_bytes = System.GC.GetAllocatedBytesForCurrentThread() - initialBytes,
        phases = phases.ToArray(),
        scope = "Adapter initialization elapsed time; current-thread managed bytes exclude native and worker allocations; recorder overhead included"
    };

    internal static unsafe object MeasureNativeClasses()
    {
        var layout = Interop153Bridge.InstalledLayout
            ?? throw new InvalidOperationException("Expected the installed profile's class handler");
        IntPtr assemblies = Native.domain_get_assemblies(Native.Domain, out nuint count);
        var classes = new List<IntPtr>(128);
        for (nuint i = 0; i < count && classes.Count < 128; i++)
        {
            IntPtr image = Native.assembly_get_image(Marshal.ReadIntPtr(assemblies, checked((int)i * IntPtr.Size)));
            nuint total = Native.image_get_class_count(image);
            for (nuint j = 0; j < total && classes.Count < 128; j++)
                classes.Add(Native.image_get_class(image, j));
        }
        if (classes.Count < 32) throw new InvalidOperationException("Insufficient live class controls");
        var pointers = classes.ToArray();
        long checksum = 0;
        void Exercise(int calls)
        {
            for (int i = 0; i < calls; i++)
            {
                var view = layout.Wrap((Il2CppClass*)pointers[i % pointers.Length]);
                ((Interop153Bridge.IPendingClass)view).CompleteIfReady();
                checksum = unchecked(checksum + (long)view.Flags + view.InstanceSize + view.InterfaceCount);
            }
        }
        Exercise(8192);
        long nativeBefore = layout.AllocatedBytes;
        int cachedBefore = layout.CachedClasses;
        var batches = new object[21];
        for (int i = 0; i < batches.Length; i++)
        {
            long bytes = GC.GetAllocatedBytesForCurrentThread(), started = Stopwatch.GetTimestamp();
            Exercise(4096);
            long ended = Stopwatch.GetTimestamp(), allocated = GC.GetAllocatedBytesForCurrentThread() - bytes;
            if (allocated != 0 || layout.AllocatedBytes != nativeBefore || layout.CachedClasses != cachedBefore)
                throw new InvalidOperationException("Warmed live class wrapping grew allocation or cached views");
            batches[i] = new { calls = 4096, elapsed_ms = (ended - started) * (1000d / Stopwatch.Frequency), managed_bytes = allocated };
        }
        return new {
            success = true, classes = pointers.Length, warmup_calls = 8192, batches,
            native_bytes_before = nativeBefore, native_bytes_after = layout.AllocatedBytes,
            cached_classes_before = cachedBefore, cached_classes_after = layout.CachedClasses, checksum,
            scope = "Warmed live native class wrapping, native completion guard and Flags/InstanceSize/InterfaceCount getters; excludes injected completion, generated plugin calls, first-use growth and whole-game frame time"
        };
    }
}
