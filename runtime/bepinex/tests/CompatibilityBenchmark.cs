using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using Il2CppInterop.Runtime.InteropTypes;
using UnityEngine;

namespace MoonLab.WorldProbe;

// Private, opt-in attribution. The baseline below retains our original repair
// algorithm; it is not code from the supplied Mars plugin. Both paths observe
// the same caches on the engine thread, in alternating warmed batches.
internal static class CompatibilityBenchmark
{
    private const BindingFlags Fields = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Static;
    private static Type wind = null!, logo = null!;
    private static object? Get(Type type, string name) => type.GetField(name, Fields)!.GetValue(null);
    private static void Set(Type type, string name, object? value) => type.GetField(name, Fields)!.SetValue(null, value);
    private static bool LegacyDead(object? value) => value is Il2CppObjectBase item &&
        (item.WasCollected || new UnityEngine.Object(item.Pointer) == null);
    private static void LegacyTick()
    {
        if (LegacyDead(Get(wind, "root")))
        {
            Set(wind, "root", null);
            wind.GetMethod("Remove", Fields)!.Invoke(null, null);
        }
        if (LegacyDead(Get(logo, "rawImage")))
        {
            Set(logo, "rawImage", null);
            Set(logo, "overlay", null);
        }
        if (LegacyDead(Get(logo, "overlay"))) Set(logo, "overlay", null);
        if (LegacyDead(Get(logo, "original"))) Set(logo, "original", null);
    }
    private static object?[] Values() => new[] {
        Get(wind, "root"), Get(logo, "rawImage"), Get(logo, "overlay"), Get(logo, "original") };
    private static void Require(bool value, string message)
    { if (!value) throw new InvalidOperationException(message); }

    internal static IEnumerator Run(string output, int id)
    {
        var checks = RunChecks(output, id);
        try
        {
            while (true)
            {
                bool more;
                object? next;
                try { more = checks.MoveNext(); next = more ? checks.Current : null; }
                catch (Exception error)
                {
                    File.WriteAllText(Path.Combine(output, "compatibility-perf-" + id + ".json"),
                        JsonSerializer.Serialize(new { success = false, error = error.ToString() }));
                    File.WriteAllText(Path.Combine(output, "world-observer-error.txt"), error.ToString());
                    throw;
                }
                if (!more) yield break;
                yield return next;
            }
        }
        finally { (checks as IDisposable)?.Dispose(); }
    }

    private static IEnumerator RunChecks(string output, int id)
    {
        var candidate = AppDomain.CurrentDomain.GetAssemblies().Single(a => a.GetName().Name == "MarsMod");
        var companion = AppDomain.CurrentDomain.GetAssemblies().Single(a => a.GetName().Name == "MoonLab.MarsCompatibility");
        var repair = companion.GetType("MoonLab.MarsCompatibility.Compatibility", true)!;
        wind = candidate.GetType("MarsMod.Wind", true)!;
        logo = candidate.GetType("MarsMod.Logo", true)!;
        var windTick = (Action)repair.GetMethod("WindBefore", Fields)!.CreateDelegate(typeof(Action));
        var logoTick = (Action)repair.GetMethod("LogoBefore", Fields)!.CreateDelegate(typeof(Action));
        var dead = (Func<object?, bool>)repair.GetMethod("Dead", Fields)!.CreateDelegate(typeof(Func<object?, bool>));
        Action current = () => { windTick(); logoTick(); };

        // Collection and native destruction are different: retain the wrapper
        // across Destroy's end-of-frame boundary and compare real native truth.
        var control = new GameObject("MoonLab private lifetime control");
        Require(!LegacyDead(null) && !dead(null), "Null lifetime control");
        Require(!LegacyDead(control) && !dead(control), "Live lifetime control");
        UnityEngine.Object.Destroy(control);
        yield return null;
        Require(LegacyDead(control) && dead(control), "Native-destroyed lifetime control");

        current();
        var values = Values();
        Require(!values.Any(LegacyDead), "Benchmark requires settled live or null caches");
        Require(values.Any(value => value is not null), "Live-path benchmark needs at least one live cache");
        const int batches = 21, iterations = 512;
        var healthy = Compare(current, batches, iterations);
        Require(Values().Zip(values, ReferenceEquals).All(equal => equal), "Healthy benchmark changed plugin caches");
        object empty;
        try
        {
            // No game tick can run during this synchronous main-thread fixture.
            // Restore every original reference even if an assertion fails.
            Set(wind, "root", null); Set(logo, "rawImage", null);
            Set(logo, "overlay", null); Set(logo, "original", null);
            empty = Compare(current, batches, iterations);
            Require(Values().All(value => value is null), "Empty benchmark changed plugin caches");
        }
        finally
        {
            Set(wind, "root", values[0]); Set(logo, "rawImage", values[1]);
            Set(logo, "overlay", values[2]); Set(logo, "original", values[3]);
        }
        Require(Values().Zip(values, ReferenceEquals).All(equal => equal), "Empty fixture did not restore original caches");
        File.WriteAllText(Path.Combine(output, "compatibility-perf-" + id + ".json"), JsonSerializer.Serialize(new {
            success = true, scope = "CPU/managed allocation for wind+logo repair prefixes only; not whole-frame FPS",
            runtime = Environment.Version.ToString(), renderer = SystemInfo.graphicsDeviceName,
            lifetime_controls = new[] { "null", "live", "native-destroyed" },
            non_null_caches = values.Count(value => value is not null),
            unchanged_cache_identity = true, empty_fixture_restored = true,
            batches, iterations_per_batch = iterations, healthy, empty
        }));
    }

    private static object Compare(Action current, int batches, int iterations)
    {
        for (int i = 0; i < 1024; i++) { LegacyTick(); current(); }
        var legacyNs = new double[batches]; var currentNs = new double[batches];
        var legacyBytes = new long[batches]; var currentBytes = new long[batches];
        for (int batch = 0; batch < batches; batch++)
        {
            if ((batch & 1) == 0)
            {
                Measure(LegacyTick, iterations, out legacyNs[batch], out legacyBytes[batch]);
                Measure(current, iterations, out currentNs[batch], out currentBytes[batch]);
            }
            else
            {
                Measure(current, iterations, out currentNs[batch], out currentBytes[batch]);
                Measure(LegacyTick, iterations, out legacyNs[batch], out legacyBytes[batch]);
            }
        }
        return new {
            baseline_ns_per_pair = legacyNs, candidate_ns_per_pair = currentNs,
            baseline_bytes_per_pair = legacyBytes.Select(bytes => (double)bytes / iterations).ToArray(),
            candidate_bytes_per_pair = currentBytes.Select(bytes => (double)bytes / iterations).ToArray()
        };
    }

    private static void Measure(Action tick, int count, out double nanoseconds, out long bytes)
    {
        long before = GC.GetAllocatedBytesForCurrentThread();
        long start = Stopwatch.GetTimestamp();
        for (int i = 0; i < count; i++) tick();
        long elapsed = Stopwatch.GetTimestamp() - start;
        bytes = GC.GetAllocatedBytesForCurrentThread() - before;
        nanoseconds = elapsed * (1e9 / Stopwatch.Frequency) / count;
    }
}
