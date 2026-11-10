using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Il2CppInterop.Runtime.Runtime;
using Il2CppInterop.Runtime.Runtime.VersionSpecific.Class;

namespace MoonLab.BepInExAdapter;

// Explicit attribution workload, never compiled into the host or normal probe.
internal static unsafe class AdapterBenchmark
{
    private static object Measure(Action operation, int iterations, int samples=21)
    {
        for (int i=0;i<3;i++) operation();
        var times=new double[samples]; var allocations=new long[samples];
        for (int sample=0;sample<samples;sample++)
        {
            long bytes=GC.GetAllocatedBytesForCurrentThread(),start=Stopwatch.GetTimestamp();
            for (int i=0;i<iterations;i++) operation();
            times[sample]=(Stopwatch.GetTimestamp()-start)*1000d/Stopwatch.Frequency;
            allocations[sample]=GC.GetAllocatedBytesForCurrentThread()-bytes;
        }
        var sorted=times.OrderBy(x=>x).ToArray();
        return new { iterations,samples,milliseconds=times,managed_bytes=allocations,
            median_ms=sorted[samples/2],p95_ms=sorted[(int)Math.Ceiling(samples*.95)-1],
            median_managed_bytes=allocations.OrderBy(x=>x).ElementAt(samples/2) };
    }

    private static void Publish(int count)
    {
        using var fixture=new NativeAllocationArena();
        using var layout=new Unity6000_6ClassLayout();
        var view=layout.CreateNewStruct(0);
        view.TypeHierarchy=(Il2CppClass**)fixture.Allocate(8);
        view.InterfaceOffsets=(Il2CppRuntimeInterfaceOffsetPair*)fixture.Allocate(count*16);
        view.InterfaceOffsetsCount=(ushort)count;
        view.ImplementedInterfaces=(Il2CppClass**)fixture.Allocate(count*8);
        view.InterfaceCount=(ushort)count;
        for (int i=0;i<count;i++)
        {
            IntPtr klass=(IntPtr)(i+1);
            *(IntPtr*)((byte*)view.InterfaceOffsets+i*16)=klass;
            view.ImplementedInterfaces[i]=(Il2CppClass*)klass;
        }
        ((Interop153Bridge.IPendingClass)view).CompleteIfReady();
        if (Marshal.ReadInt16(view.Pointer,0x124)!=count || Marshal.ReadInt16(view.Pointer,0x126)!=count)
            throw new InvalidOperationException("Publication changed counts");
    }

    public static int Main(string[] args)
    {
        using var resolver=new AssemblyResolutionScope(args[0]);
        return Run(args);
    }

    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static int Run(string[] args)
    {
        using var fixture=new NativeAllocationArena();
        using var layout=new Unity6000_6ClassLayout();
        var native=layout.Wrap((Il2CppClass*)fixture.Allocate(0x130));
        var pending=(Interop153Bridge.IPendingClass)native;
        var result=new Dictionary<string,object> {
            ["native_type_access_guard"]=Measure(pending.CompleteIfReady,1000000),
            ["publish_2"]=Measure(()=>Publish(2),100),
            ["publish_512"]=Measure(()=>Publish(512),5),
            ["publish_8192"]=Measure(()=>Publish(8192),1,11)
        };
        File.WriteAllText(args[1],JsonSerializer.Serialize(new { success=true,scope="Offline native class publication attribution; no game/frame timing",runtime=Environment.Version.ToString(),processor_count=Environment.ProcessorCount,results=result }));
        return 0;
    }
}
