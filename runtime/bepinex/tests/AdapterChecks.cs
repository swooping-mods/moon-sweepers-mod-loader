using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading.Tasks;
using Mono.Cecil;
using Il2CppInterop.Runtime.Runtime;
using Il2CppInterop.Runtime.Runtime.VersionSpecific.Class;

namespace MoonLab.BepInExAdapter;

internal static unsafe class AdapterChecks
{
    private static void Require(bool value, string message)
    { if (!value) throw new InvalidOperationException(message); }
    private static void Reject<T>(Action action) where T : Exception
    {
        try { action(); } catch (T) { return; }
        throw new InvalidOperationException("Expected " + typeof(T).Name);
    }

    private static void ProjectionOwnership()
    {
        using var fixture = new NativeAllocationArena();
        using var layout = new Unity6000_6ClassLayout();
        IntPtr pointer = fixture.Allocate(0x130);
        var view = layout.Wrap((Il2CppClass*)pointer);
        Require(view.InterfaceCount == 0,"Empty lazy native class");
        IntPtr rows = fixture.Allocate(32);
        Marshal.WriteIntPtr(pointer,0x90,rows);
        Marshal.WriteInt16(pointer,0x124,2); Marshal.WriteInt16(pointer,0x126,1);
        Marshal.WriteIntPtr(rows,0,(IntPtr)1234); Marshal.WriteInt32(rows,8,7);
        Marshal.WriteInt32(rows,12,1); // inherited offset, not a declared interface
        Marshal.WriteIntPtr(rows,16,(IntPtr)5678);
        Require(view.InterfaceCount == 1 && view.InterfaceOffsetsCount == 1,"Refresh after native lazy initialization");
        Require((IntPtr)view.ImplementedInterfaces[0] == (IntPtr)5678,"Declared interface projection");
        Require(*(int*)((byte*)view.InterfaceOffsets + 8) == 7,"Usable offset projection");
        long bytes = layout.AllocatedBytes;
        Parallel.For(0,10000,_ => {
            var again = layout.Wrap((Il2CppClass*)pointer);
            Require(ReferenceEquals(view,again) && again.InterfaceCount == 1,"Shared projection view");
        });
        Require(layout.AllocatedBytes == bytes && layout.CachedClasses == 1,"Wrapping must not grow native allocations");
        Marshal.WriteInt16(pointer,0x126,3);
        Reject<InvalidOperationException>(() => { _ = view.InterfaceCount; });
        Marshal.WriteInt16(pointer,0x126,1);
        Require(view.InterfaceCount == 1,"Rejected projection cannot poison the cached view");
        layout.Dispose();
        Require(layout.AllocatedBytes == 0 && layout.CachedClasses == 0,"Unpublished layout releases all owned storage");
        Reject<ObjectDisposedException>(() => layout.Wrap((Il2CppClass*)pointer));
    }

    private static void InjectionPublication()
    {
        using var fixture = new NativeAllocationArena();
        using var layout = new Unity6000_6ClassLayout();
        var view = layout.CreateNewStruct(2);
        Require(ReferenceEquals(view,layout.Wrap(view.ClassPointer)),"Injected wrapper identity must survive Wrap");
        var declared = (Il2CppClass**)fixture.Allocate(16);
        declared[0] = (Il2CppClass*)1234; declared[1] = (Il2CppClass*)5678;
        view.ImplementedInterfaces = declared; view.InterfaceCount = 2;
        view.InterfaceOffsets = (Il2CppRuntimeInterfaceOffsetPair*)fixture.Allocate(16);
        *(IntPtr*)view.InterfaceOffsets = (IntPtr)1234;
        *(int*)((byte*)view.InterfaceOffsets + 8) = 9;
        view.InterfaceOffsetsCount = 1;
        var pending = (Interop153Bridge.IPendingClass)view;
        Interop153Bridge.BeforeByValArgAccess(pending);
        Require(Marshal.ReadIntPtr(view.Pointer,0x90) == IntPtr.Zero,"Do not publish an unfinished hierarchy");
        view.TypeHierarchy = (Il2CppClass**)fixture.Allocate(8);
        Interop153Bridge.BeforeByValArgAccess(pending);
        IntPtr rows = Marshal.ReadIntPtr(view.Pointer,0x90);
        Require(rows != IntPtr.Zero && Marshal.ReadInt16(view.Pointer,0x124) == 2 && Marshal.ReadInt16(view.Pointer,0x126) == 1,"Unified table counts");
        Require(Marshal.ReadIntPtr(rows) == (IntPtr)1234 && Marshal.ReadInt32(rows,8) == 9 && Marshal.ReadIntPtr(rows,16) == (IntPtr)5678,"Unified table contents");
        long bytes = layout.AllocatedBytes;
        Interop153Bridge.BeforeByValArgAccess(pending);
        Require(layout.AllocatedBytes == bytes && Marshal.ReadIntPtr(view.Pointer,0x90) == rows,"Publish once");
        Reject<ArgumentOutOfRangeException>(() => layout.CreateNewStruct(-1));
    }

    private static void PublicationFailureSafety()
    {
        using var fixture=new NativeAllocationArena();
        using var layout=new Unity6000_6ClassLayout();
        var view=layout.CreateNewStruct(0);
        view.TypeHierarchy=(Il2CppClass**)fixture.Allocate(8);
        view.InterfaceCount=40000; view.InterfaceOffsetsCount=40000;
        view.ImplementedInterfaces=(Il2CppClass**)fixture.Allocate(40000*8);
        view.InterfaceOffsets=(Il2CppRuntimeInterfaceOffsetPair*)fixture.Allocate(40000*16);
        for (int i=0;i<40000;i++)
        {
            view.ImplementedInterfaces[i]=(Il2CppClass*)(i+1);
            *(IntPtr*)((byte*)view.InterfaceOffsets+i*16)=(IntPtr)(i+40001);
        }
        long before=layout.AllocatedBytes;
        Reject<OverflowException>(()=>((Interop153Bridge.IPendingClass)view).CompleteIfReady());
        Require(Marshal.ReadIntPtr(view.Pointer,0x90)==IntPtr.Zero && Marshal.ReadInt16(view.Pointer,0x124)==0 && layout.AllocatedBytes==before,"Overflow must not publish or allocate native output");
        view.InterfaceCount=2;view.InterfaceOffsetsCount=0;
        view.ImplementedInterfaces[1]=view.ImplementedInterfaces[0];
        Reject<InvalidOperationException>(()=>((Interop153Bridge.IPendingClass)view).CompleteIfReady());
        Require(Marshal.ReadIntPtr(view.Pointer,0x90)==IntPtr.Zero,"Duplicate input must not publish");
        view.InterfaceCount=0;
        var pending=(Interop153Bridge.IPendingClass)view;
        pending.CompleteIfReady();pending.CompleteIfReady();
        Require(layout.AllocatedBytes==before,"An empty interface table completes without native allocations");
    }

    private static void SnapshotOwnership(string folder)
    {
        string path=Path.Combine(folder,"immutable-snapshot.json");
        File.WriteAllText(path,Snapshot("Original"));
        using var snapshot=MetadataDocument.Load(path);
        string hash=snapshot.Hash;
        File.WriteAllText(path,Snapshot("Changed"));
        using var declarations=new DeclarationGenerator();
        string output=Path.Combine(folder,"immutable-declarations");
        declarations.Read(snapshot,output);
        using var assembly=AssemblyDefinition.ReadAssembly(Path.Combine(output,"Example.dll"));
        Require(assembly.MainModule.GetType("Example.Original")!=null && snapshot.Hash==hash && FileIntegrity.Hash(path)!=hash,"Metadata identity must describe exactly the bytes used");
        using (var source=JsonDocument.Parse(Snapshot("Owned")))
        using (var captured=MetadataDocument.FromValue(source.RootElement))
        {
            using var stream=new MemoryStream();captured.WriteTo(stream);
            Require(captured.Hash==Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(stream.ToArray())).ToLowerInvariant(),"Captured evidence must be exactly the generated input");
            captured.Dispose();
            Reject<ObjectDisposedException>(()=>captured.WriteTo(stream));
        }
        File.WriteAllText(path,Snapshot("Invalid").Replace("Example","../outside"));
        Reject<InvalidDataException>(()=>MetadataDocument.Load(path));
        using(var stream=File.Create(path)) stream.SetLength(256L*1024*1024+1);
        Reject<InvalidDataException>(()=>MetadataDocument.Load(path));
    }

    private static void AliasRejection(string folder)
    {
        foreach(string path in new[]{"../x","/root","foo\\bar","C:x","NUL.dll","a.","a/CON","a//b"})
            Reject<InvalidDataException>(()=>FileIntegrity.Relative(path));
        string root=Path.Combine(folder,"alias-inputs"),core=Path.Combine(root,"BepInEx","core");
        Directory.CreateDirectory(core);
        string file=Path.Combine(core,"Checked.dll"); File.WriteAllText(file,"checked bytes");
        string manifest=Path.Combine(root,"inputs.json");
        File.WriteAllText(manifest,JsonSerializer.Serialize(new{schema="moonlab-managed-inputs/v1",files=new Dictionary<string,string>{{"BepInEx/core/Checked.dll",FileIntegrity.Hash(file)}}}));
        ManagedInputs.Verify(root,manifest);
        string outside=Path.Combine(folder,"outside-input");Directory.CreateDirectory(outside);
        string linked=Path.Combine(core,"linked");Directory.CreateSymbolicLink(linked,outside);
        Reject<InvalidDataException>(()=>ManagedInputs.Verify(root,manifest));
        Directory.Delete(linked);
        string alias=Path.Combine(folder,"alias-parent");Directory.CreateSymbolicLink(alias,root);
        Reject<InvalidDataException>(()=>ManagedInputs.Verify(alias,Path.Combine(alias,"inputs.json")));
        Directory.Delete(alias);
    }

    private static string Snapshot(string name) => JsonSerializer.Serialize(new {
        Schema="moonlab-live-metadata/v1", GameHash="test", Assemblies=new[] {
            new { Name="Example", Classes=new[] { new {
                Name=name, Namespace="Example", Flags=1, Parent=(string?)null, Declaring=(string?)null,
                ValueType=false, Enum=false, InstanceSize=16, Generics=Array.Empty<object>(),
                Interfaces=Array.Empty<string>(), Fields=Array.Empty<object>(), Methods=Array.Empty<object>(), Properties=Array.Empty<object>()
            } } }
        }
    });

    private static void IndependentDeclarations(string folder)
    {
        for (int job=0; job<2; job++)
        {
            string snapshot=Path.Combine(folder,"snapshot-"+job+".json"), output=Path.Combine(folder,"declarations-"+job);
            File.WriteAllText(snapshot,Snapshot("Type"+job));
            using var document=MetadataDocument.Load(snapshot);
            using var builder=new DeclarationGenerator();
            var result=builder.Read(document,output);
            Require(result.Count==1,"One job's assembly set");
            using var assembly=AssemblyDefinition.ReadAssembly(Path.Combine(output,"Example.dll"));
            Require(assembly.MainModule.GetType("Example.Type"+job)!=null,"Independent declaration identity");
            Reject<InvalidOperationException>(() => builder.Read(document,output));
        }
    }

    private sealed class TestRepair : IBindingRepair
    {
        public string Id { get; }
        public string TargetAssembly { get; }
        private readonly bool fail;
        internal TestRepair(string id, string target="Fixture.dll", bool fail=false)
        { Id=id; TargetAssembly=target; this.fail=fail; }
        public void Apply(ModuleDefinition module)
        {
            if (fail) throw new InvalidOperationException("Controlled repair failure");
            module.Types.Add(new TypeDefinition("Fixture",Id,TypeAttributes.Public,module.TypeSystem.Object));
        }
    }

    private static void RepairIsolation(string folder)
    {
        string file=Path.Combine(folder,"Fixture.dll");
        using (var assembly=AssemblyDefinition.CreateAssembly(new AssemblyNameDefinition("Fixture",new Version(1,0)),"Fixture.dll",ModuleKind.Dll)) assembly.Write(file);
        string before=FileIntegrity.Hash(file);
        BindingRepairs.Apply(folder,Array.Empty<IBindingRepair>());
        Require(FileIntegrity.Hash(file)==before,"An empty repair set changes no bindings");
        Reject<ArgumentException>(() => BindingRepairs.Apply(folder,new IBindingRepair[] { new TestRepair("A"),new TestRepair("A") }));
        Reject<InvalidDataException>(() => BindingRepairs.Apply(folder,new[] { new TestRepair("A","../Fixture.dll") }));
        Reject<InvalidOperationException>(() => BindingRepairs.Apply(folder,new[] { new TestRepair("A"),new TestRepair("B",fail:true) }));
        Require(FileIntegrity.Hash(file)==before,"Failed module repairs preserve the original binding");
        string other=Path.Combine(folder,"Other.dll");File.Copy(file,other);
        Reject<InvalidOperationException>(()=>BindingRepairs.Apply(folder,new[]{new TestRepair("First"),new TestRepair("Second","Other.dll",true)}));
        Require(FileIntegrity.Hash(file)==before && FileIntegrity.Hash(other)==before,"A later assembly failure must preserve every original");
        Require(!Directory.EnumerateDirectories(folder,".moonlab-repairs-*").Any(),"Failed repairs leave no unpublished stage");
        BindingRepairs.Apply(folder,new[] { new TestRepair("Chosen") });
        using var changed=AssemblyDefinition.ReadAssembly(file);
        Require(changed.MainModule.GetType("Fixture.Chosen")!=null && changed.MainModule.GetType("Fixture.A")==null,"Only selected repairs apply");
    }

    private static void CacheIdentity(string folder)
    {
        string cache=Path.Combine(folder,"cache");Directory.CreateDirectory(cache);
        string binding=Path.Combine(cache,"Fixture.dll");File.WriteAllText(binding,"original");
        var profile=new MoonSweepersSteam105();
        string receipt=Path.Combine(cache,"moonlab-interop.json");
        void Write(string schema, string id, string[] repairs, string generator) => File.WriteAllText(receipt,JsonSerializer.Serialize(new {
            schema,profile=id,repairs,generator_sha256=generator,game_sha256=profile.GameAssemblyHash,
            files=new Dictionary<string,string> { ["Fixture.dll"]=FileIntegrity.Hash(binding) }
        }));
        string generator=FileIntegrity.Hash(typeof(Adapter).Assembly.Location);
        var identity=new CacheIdentity(profile.GameAssemblyHash,profile.Id,profile.Repairs.Select(p=>p.Id).ToArray(),generator);
        string[] modules=profile.Repairs.Select(p=>p.Id).ToArray();
        Write("moonlab-interop/v3",profile.Id,modules,generator);
        Require(InteropCache.Verify(cache,identity),"Current cache reused");
        Write("moonlab-interop/v3",profile.Id,Array.Empty<string>(),generator);
        Require(!InteropCache.Verify(cache,identity),"Changed repair selection requires regeneration");
        Write("moonlab-interop/v3","different-profile",modules,generator);
        Require(!InteropCache.Verify(cache,identity),"Changed profile requires regeneration");
        Write("moonlab-interop/v2",profile.Id,modules,generator);
        Require(!InteropCache.Verify(cache,identity),"Verified legacy cache is retired");
        File.AppendAllText(binding,"modified");
        Reject<InvalidDataException>(() => InteropCache.Verify(cache,identity));
        File.WriteAllText(binding,"original");
        Reject<InvalidOperationException>(() => GameProfiles.Match(new(binding,binding,binding)));
        Reject<InvalidDataException>(() => GameProfiles.ForSnapshot("unknown"));
    }

    private sealed class RecoveryRepair : IBindingRepair
    {
        public string Id => "test.rollback-evidence/v1";
        public string TargetAssembly => "UnityEngine.CoreModule.dll";
        private readonly string output;
        internal string? Recovery;
        internal RecoveryRepair(string output) => this.output=output;
        public void Apply(ModuleDefinition module)
        {
            string stage=Directory.GetDirectories(Path.GetDirectoryName(output)!,Path.GetFileName(output)+".stage-*").Single();
            Recovery=Path.Combine(stage,"interop",".rollback-recovery");Directory.CreateDirectory(Recovery);
            File.WriteAllText(Path.Combine(Recovery,"original"),"preserve original");
            throw new BindingRepairRollbackException(Recovery,new[]{new IOException("Controlled rollback failure")});
        }
    }

    public static int Main(string[] args)
    {
        if (args[0]=="--fail-closed")
        {
            AdapterFailure.Stop(new IOException("Controlled adapter failure"),args[1],_=>throw new IOException("Controlled logger failure"));
            return 1;
        }
        using var resolver=new AssemblyResolutionScope(args[0]);
        return Run(args);
    }
    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    private static int Run(string[] args)
    {
        string folder=args[1];Directory.CreateDirectory(folder);
        var cases=new Dictionary<string,Action> {
            ["compiled-host-boundaries"]=()=> {
                using var assembly=AssemblyDefinition.ReadAssembly(args[2]);
                Require(assembly.Name.Name=="MoonLab.BepInExAdapter","Compiler staging must preserve assembly identity");
                var debugging=assembly.CustomAttributes.SingleOrDefault(p=>p.AttributeType.FullName=="System.Diagnostics.DebuggableAttribute");
                Require(debugging==null || (Convert.ToInt32(debugging.ConstructorArguments[0].Value)&256)==0,"Runtime must permit optimized JIT code");
                var names=assembly.MainModule.Types.Select(p=>p.FullName).ToArray();
                Require(!names.Any(p=>p.Contains("MarsCompatibility") || p.EndsWith("ApiCheck") || p.EndsWith("GenerateCommand") || p.EndsWith("AssemblyResolutionScope")),"Host contains an optional plugin or diagnostic");
            },
            ["projection-owner-cache-and-lazy-initialization"]=ProjectionOwnership,
            ["injection-identity-and-publication"]=InjectionPublication,
            ["publication-overflow-and-duplicate-safety"]=PublicationFailureSafety,
            ["snapshot-identity-paths-and-bounds"]=()=>SnapshotOwnership(folder),
            ["linked-directory-rejection"]=()=>AliasRejection(folder),
            ["independent-declaration-jobs"]=()=>IndependentDeclarations(folder),
            ["optional-repairs-and-failure-isolation"]=()=>RepairIsolation(folder),
            ["profile-cache-identity-and-tamper-rejection"]=()=>CacheIdentity(folder)
        };
        foreach (var test in cases) { test.Value(); Console.WriteLine("PASS "+test.Key); }
        if (args.Length==5)
        {
            using var snapshot=MetadataDocument.Load(args[3]);
            var profile=GameProfiles.ForSnapshot(snapshot.GameHash);
            var service=new InteropGeneration();
            for (int i=0;i<2;i++) service.Run(new(snapshot,Path.Combine(folder,"generation-"+i),args[4],profile.Id,profile.Repairs));
            string failed=Path.Combine(folder,"rollback-generation");
            var recovery=new RecoveryRepair(failed);
            Reject<BindingRepairRollbackException>(()=>service.Run(new(snapshot,failed,args[4],profile.Id,new[]{recovery})));
            Require(!Directory.Exists(failed) && recovery.Recovery!=null && File.ReadAllText(Path.Combine(recovery.Recovery,"original"))=="preserve original","Generation cleanup must preserve incomplete rollback evidence");
            Console.WriteLine("PASS nested-generation-rollback-evidence");
            Console.WriteLine("PASS repeated-full-generation-in-one-process");
        }
        File.WriteAllText(Path.Combine(folder,"result.json"),JsonSerializer.Serialize(new { success=true,checks=cases.Keys,repeated_generation=args.Length==5 }));
        return 0;
    }
}
