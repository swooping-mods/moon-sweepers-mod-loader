using System;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;

public static class ModernHarmonyProbe
{
    [MethodImpl(MethodImplOptions.NoInlining | MethodImplOptions.NoOptimization)]
    public static int Target(int value) => value + 1;
    public static void Prefix(ref int value) => value += 10;
    public static void Postfix(ref int __result) => __result += 100;

    public static int Main()
    {
        try
        {
            Console.WriteLine("runtime=" + Environment.Version);
            Func<int, int> call = Target;
            if (call(1) != 2) throw new Exception("Baseline behavior changed");
            var owner = new Harmony("moonlab.synthetic.net10");
            Console.WriteLine("patch-start"); Console.Out.Flush();
            owner.Patch(typeof(ModernHarmonyProbe).GetMethod(nameof(Target)),
                new HarmonyMethod(typeof(ModernHarmonyProbe).GetMethod(nameof(Prefix))),
                new HarmonyMethod(typeof(ModernHarmonyProbe).GetMethod(nameof(Postfix))));
            Console.WriteLine("patch-installed"); Console.Out.Flush();
            for (int value = 0; value < 1000; ++value)
                if (call(value) != value + 111) throw new Exception("Patched behavior changed");
            GC.Collect(); GC.WaitForPendingFinalizers();
            if (call(2) != 113) throw new Exception("Patch did not survive GC");
            owner.UnpatchSelf();
            if (call(1) != 2) throw new Exception("Unpatch did not restore behavior");
            Console.WriteLine("patch-roundtrip-passed");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
