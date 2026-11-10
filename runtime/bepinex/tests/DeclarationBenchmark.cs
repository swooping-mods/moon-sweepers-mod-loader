using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mono.Cecil;

namespace MoonLab.BepInExAdapter;

internal static class DeclarationBenchmark
{
    private static string Hash(string path)
    {
        using var file=File.OpenRead(path);using var hash=SHA256.Create();
        return Convert.ToHexString(hash.ComputeHash(file));
    }
    private static IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> types)
    {
        foreach(var type in types) { yield return type;foreach(var nested in Types(type.NestedTypes))yield return nested; }
    }
    private static string Signature(string folder)
    {
        var lines=new List<string>();
        foreach(string path in Directory.GetFiles(folder,"*.dll").OrderBy(p=>p,StringComparer.Ordinal))
        {
            using var assembly=AssemblyDefinition.ReadAssembly(path);
            foreach(var type in Types(assembly.MainModule.Types).OrderBy(p=>p.FullName,StringComparer.Ordinal))
            {
                lines.Add("T|"+assembly.Name.Name+"|"+type.FullName+"|"+type.Attributes+"|"+type.BaseType?.FullName+"|"+type.ClassSize);
                foreach(var field in type.Fields)lines.Add("F|"+field.FullName+"|"+field.Attributes+"|"+field.FieldType.IsValueType+"|"+field.Constant);
                foreach(var method in type.Methods)lines.Add("M|"+method.FullName+"|"+method.Attributes+"|"+method.ReturnType.IsValueType+"|"+string.Join(",",method.Parameters.Select(p=>p.ParameterType.IsValueType+":"+p.Attributes)));
            }
        }
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n",lines))));
    }

    public static int Main(string[] args)
    { using var resolver=new AssemblyResolutionScope(args[0]);return Run(args); }

    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static int Run(string[] args)
    {
        var samples=new List<object>();string? signature=null;
        for(int sample=-1;sample<5;sample++)
        {
            string output=Path.Combine(args[1],"declarations-"+(sample+1));
            GC.Collect();GC.WaitForPendingFinalizers();GC.Collect();
            long retained=GC.GetTotalMemory(false);
            long allocated=GC.GetTotalAllocatedBytes(true),start=Stopwatch.GetTimestamp();
#if BASELINE_CORE
            using(var metadata=JsonDocument.Parse(File.ReadAllBytes(args[2])))
            using(var builder=new DeclarationGenerator())
            { _=metadata.RootElement.GetProperty("GameHash").GetString();builder.Read(args[2],output);_=Hash(args[2]); }
#else
            using(var metadata=MetadataDocument.Load(args[2]))
            using(var builder=new DeclarationGenerator())builder.Read(metadata,output);
#endif
            double elapsed=(Stopwatch.GetTimestamp()-start)*1000d/Stopwatch.Frequency;
            long bytes=GC.GetTotalAllocatedBytes(true)-allocated;
            string actual=Signature(output);
            if(signature!=null && actual!=signature)throw new InvalidOperationException("Declaration semantics changed between jobs");
            signature=actual;
            if(sample>=0)samples.Add(new{elapsed_ms=elapsed,managed_bytes=bytes,retained_before=retained});
            Console.WriteLine("job="+sample+" ms="+elapsed+" managed="+bytes+" signature="+actual);
            Directory.Delete(output,true);
        }
        File.WriteAllText(Path.Combine(args[1],"result.json"),JsonSerializer.Serialize(new{success=true,scope="Offline declaration authoring including snapshot parse/hash and dummy PE output; excludes upstream interop generation and game runtime",warmup_jobs=1,samples,signature}));
        return 0;
    }
}
