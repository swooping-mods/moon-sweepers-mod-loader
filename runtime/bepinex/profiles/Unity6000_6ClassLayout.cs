using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using Il2CppInterop.Runtime.Runtime;
using Il2CppInterop.Runtime.Runtime.VersionSpecific.Class;
using Il2CppInterop.Runtime.Runtime.VersionSpecific.Type;

namespace MoonLab.BepInExAdapter;

// This is an original handler for the pinned game's measured layout. Offsets
// are accepted only after comparison with the game's own exported producers.
internal sealed unsafe class Unity6000_6ClassLayout : INativeClassStructHandler, IDisposable
{
    private const int HeaderSize = 0x130;
    private readonly NativeAllocationArena memory = new();
    private readonly Dictionary<IntPtr,View> views = new();
    private readonly object gate = new();
    private bool installed, disposed;
    internal long AllocatedBytes => memory.Bytes;
    internal int CachedClasses => views.Count;
    internal void Install()
    {
        try { Validate(); Interop153Bridge.Install(this); installed = true; }
        catch { Dispose(); throw; }
    }
    private void Validate()
    {
        int checkedClasses = 0;
        IntPtr assemblies = Native.domain_get_assemblies(Native.Domain, out nuint count);
        for (nuint i = 0; i < count && checkedClasses < 128; i++)
        {
            IntPtr image = Native.assembly_get_image(Marshal.ReadIntPtr(assemblies, checked((int)i * 8)));
            nuint classes = Native.image_get_class_count(image);
            for (nuint j = 0; j < classes && checkedClasses < 128; j++)
            {
                IntPtr klass = Native.image_get_class(image,j);
                var view = (View)Wrap((Il2CppClass*)klass);
                if (view.Flags != (Il2CppClassAttributes)Native.class_get_flags(klass) ||
                    view.InstanceSize != Native.class_instance_size(klass) ||
                    view.Parent != (Il2CppClass*)Native.class_get_parent(klass) ||
                    view.DeclaringType != (Il2CppClass*)Native.class_get_declaring_type(klass) ||
                    view.EnumType != Native.class_is_enum(klass) || view.ValueType != Native.class_is_valuetype(klass) ||
                    Native.Text(view.Name) != Native.Text(Native.class_get_name(klass)))
                    throw new InvalidOperationException("Measured class layout does not match public native APIs");
                IntPtr iterator = IntPtr.Zero;
                int methods = 0;
                for (IntPtr method; (method = Native.class_get_methods(klass, ref iterator)) != IntPtr.Zero; methods++)
                    if (methods >= 65535 || view.Methods[methods] != (Il2CppMethodInfo*)method)
                        throw new InvalidOperationException("Measured method table does not match native iteration");
                if (methods != view.MethodCount) throw new InvalidOperationException("Native method count mismatch");
                iterator = IntPtr.Zero;
                int interfaces = 0;
                for (IntPtr iface; (iface = Native.class_get_interfaces(klass,ref iterator)) != IntPtr.Zero; interfaces++)
                    if (interfaces >= view.InterfaceCount || view.ImplementedInterfaces[interfaces] != (Il2CppClass*)iface)
                        throw new InvalidOperationException("Native interface projection mismatch");
                if (interfaces != view.InterfaceCount) throw new InvalidOperationException("Native interface count mismatch");
                IntPtr ancestor = klass;
                int depth = 0;
                while (ancestor != IntPtr.Zero && depth < 256) { depth++; ancestor = Native.class_get_parent(ancestor); }
                // Some lazy classes have not built a hierarchy yet; only compare
                // initialized native tables, never force a guessed pointer read.
                if (view.TypeHierarchy != null && (view.TypeHierarchyDepth != depth || view.TypeHierarchy[depth-1] != (Il2CppClass*)klass))
                    throw new InvalidOperationException("Native inheritance table mismatch");
                checkedClasses++;
            }
        }
        if (checkedClasses < 32) throw new InvalidOperationException("Insufficient class-layout controls");
    }
    public void Dispose()
    {
        lock (gate)
        {
            if (installed) throw new InvalidOperationException("Published IL2CPP descriptors have process lifetime");
            if (disposed) return;
            memory.Dispose(); views.Clear(); disposed = true;
        }
    }
    public int Size() => HeaderSize;
    public INativeClassStruct CreateNewStruct(int slots)
    {
        if (slots < 0 || slots > 65535) throw new ArgumentOutOfRangeException(nameof(slots));
        lock (gate)
        {
            if (disposed) throw new ObjectDisposedException(nameof(Unity6000_6ClassLayout));
            IntPtr p = memory.Allocate(checked(HeaderSize + slots * 16));
            var view = new View(p,memory,true);
            views.Add(p,view);
            return view;
        }
    }
    public INativeClassStruct Wrap(Il2CppClass* pointer)
    {
        if (pointer == null) return null!;
        lock (gate)
        {
            if (disposed) throw new ObjectDisposedException(nameof(Unity6000_6ClassLayout));
            IntPtr p = (IntPtr)pointer;
            if (!views.TryGetValue(p,out var view)) views.Add(p,view = new View(p,memory));
            return view;
        }
    }

    private sealed class View : INativeClassStruct, Interop153Bridge.IPendingClass
    {
        public IntPtr Pointer { get; }
        private readonly bool injected;
        private readonly NativeAllocationArena memory;
        private bool projected;
        private bool published;
        private IntPtr projectedRows;
        private ushort projectedTotal, projectedOffsets;
        private readonly object projectionGate = new();
        private ushort interfaceCount, offsetsCount;
        private Il2CppClass** interfaces;
        private Il2CppRuntimeInterfaceOffsetPair* offsets;
        internal View(IntPtr pointer, NativeAllocationArena memory, bool injected = false)
        { Pointer = pointer; this.memory = memory; this.injected = injected; }
        // Unity 6000.6 stores a single 16-byte interface/offset/flags table.
        // Present the older split API to upstream without changing native data.
        private void ProjectInterfaces()
        {
            lock (projectionGate)
            {
                if (injected) return;
                ushort total = At<ushort>(0x124), usable = At<ushort>(0x126);
                IntPtr table = At<IntPtr>(0x90);
                if (projected && projectedRows == table && projectedTotal == total && projectedOffsets == usable) return;
                if (usable > total) throw new InvalidOperationException("Native interface counts disagree");
                if (total != 0 && table == IntPtr.Zero) throw new InvalidOperationException("Missing native interface table");
                // Lazy native initialization can replace an initially empty
                // table. Keep old buffers alive for any escaped upstream refs.
                var nextInterfaces = (Il2CppClass**)memory.Allocate(total * 8);
                var nextOffsets = (Il2CppRuntimeInterfaceOffsetPair*)memory.Allocate(usable * 16);
                ushort declared = 0;
                var rows = (byte*)table;
                for (int i = 0; i < total; i++)
                {
                    if (i < usable)
                    {
                        *(IntPtr*)((byte*)nextOffsets + i * 16) = *(IntPtr*)(rows + i * 16);
                        *(int*)((byte*)nextOffsets + i * 16 + 8) = *(int*)(rows + i * 16 + 8);
                    }
                    if (*(int*)(rows + i * 16 + 12) == 0)
                        nextInterfaces[declared++] = *(Il2CppClass**)(rows + i * 16);
                }
                interfaces = nextInterfaces; offsets = nextOffsets;
                interfaceCount = declared; offsetsCount = usable;
                projectedRows = table; projectedTotal = total; projectedOffsets = usable; projected = true;
            }
        }
        // Tiny interface lists use their existing native rows without managed
        // allocations. Larger lists build one sized index to keep merging
        // linear; striding supports both declarations and offset-prefix rows.
        private readonly struct InterfaceSet
        {
            private readonly byte* rows;
            private readonly int count, stride;
            private readonly HashSet<IntPtr>? index;
            internal InterfaceSet(void* rows, int count, int stride, bool distinct)
            {
                this.rows = (byte*)rows; this.count = count; this.stride = stride;
                index = count > 8 ? new HashSet<IntPtr>(count) : null;
                if (count != 0 && rows == null) throw new InvalidOperationException("Incomplete injected interface inputs");
                for (int i = 0; i < count; i++)
                {
                    IntPtr value = *(IntPtr*)(this.rows + i * stride);
                    if (value == IntPtr.Zero) throw new InvalidOperationException("Null injected interface");
                    bool duplicate = index != null ? !index.Add(value) : false;
                    if (index == null && distinct)
                        for (int j = 0; j < i; j++) if (*(IntPtr*)(this.rows + j * stride) == value) duplicate = true;
                    if (distinct && duplicate) throw new InvalidOperationException("Duplicate injected interface");
                }
            }
            internal bool Contains(IntPtr value)
            {
                if (index != null) return index.Contains(value);
                for (int i = 0; i < count; i++) if (*(IntPtr*)(rows + i * stride) == value) return true;
                return false;
            }
        }

        public void CompleteIfReady()
        {
            // Native views never publish. Avoid taking the construction lock
            // for ordinary type reads or already completed injected classes.
            if (!injected || Volatile.Read(ref published)) return;
            lock (projectionGate)
            {
                if (published || TypeHierarchy == null) return;
                if (At<IntPtr>(0x90) != IntPtr.Zero) throw new InvalidOperationException("Injected table was published outside its owner");
                var declared = new InterfaceSet(interfaces,interfaceCount,IntPtr.Size,true);
                var inherited = new InterfaceSet(offsets,offsetsCount,16,false);
                int total = offsetsCount;
                for (int i = 0; i < interfaceCount; i++) if (!inherited.Contains((IntPtr)interfaces[i])) total++;
                // Validate the complete count before allocating or publishing.
                // A checked conversion after writing the pointer is too late.
                ushort count = checked((ushort)total);
                var rows = (byte*)memory.Allocate(total * 16);
                for (int i = 0; i < offsetsCount; i++)
                {
                    IntPtr klass = *(IntPtr*)((byte*)offsets + i * 16);
                    *(IntPtr*)(rows + i * 16) = klass;
                    *(int*)(rows + i * 16 + 8) = *(int*)((byte*)offsets + i * 16 + 8);
                    *(int*)(rows + i * 16 + 12) = declared.Contains(klass) ? 0 : 1;
                }
                int next = offsetsCount;
                for (int i = 0; i < interfaceCount; i++)
                    if (!inherited.Contains((IntPtr)interfaces[i])) *(Il2CppClass**)(rows + next++ * 16) = interfaces[i];
                At<ushort>(0x124) = count;
                At<ushort>(0x126) = offsetsCount;
                At<IntPtr>(0x90) = (IntPtr)rows;
                Volatile.Write(ref published,true);
            }
        }
        private ref T At<T>(int offset) where T : unmanaged => ref *(T*)((byte*)Pointer + offset);
        private bool Bit(int offset,int mask) => (At<byte>(offset) & mask) != 0;
        private void Bit(int offset,int mask,bool value)
        {
            ref byte b = ref At<byte>(offset); b = (byte)(value ? b | mask : b & ~mask);
        }
        public Il2CppClass* ClassPointer => (Il2CppClass*)Pointer;
        public IntPtr VTable => Pointer + HeaderSize;
        public ref uint InstanceSize => ref At<uint>(0xf0);
        public ref ushort VtableCount => ref At<ushort>(0x122);
        public ref ushort InterfaceCount { get { ProjectInterfaces(); return ref interfaceCount; } }
        public ref ushort InterfaceOffsetsCount { get { ProjectInterfaces(); return ref offsetsCount; } }
        public ref byte TypeHierarchyDepth => ref At<byte>(0x128);
        public ref int NativeSize => ref At<int>(0x100);
        public ref uint ActualSize => ref At<uint>(0xf8);
        public ref ushort MethodCount => ref At<ushort>(0x118);
        public ref ushort FieldCount => ref At<ushort>(0x11c);
        public ref Il2CppClassAttributes Flags => ref At<Il2CppClassAttributes>(0x110);
        public ref IntPtr Name => ref At<IntPtr>(0x10);
        public ref IntPtr Namespace => ref At<IntPtr>(0x18);
        public INativeTypeStruct ByValArg { get { Interop153Bridge.BeforeByValArgAccess(this); return UnityVersionHandler.Wrap((Il2CppTypeStruct*)((byte*)Pointer + 0x20)); } }
        public INativeTypeStruct ThisArg => UnityVersionHandler.Wrap((Il2CppTypeStruct*)((byte*)Pointer + 0x30));
        public ref Il2CppImage* Image => ref *(Il2CppImage**)Pointer;
        public ref Il2CppClass* Parent => ref *(Il2CppClass**)((byte*)Pointer + 0x58);
        public ref Il2CppClass* ElementClass => ref *(Il2CppClass**)((byte*)Pointer + 0x40);
        public ref Il2CppClass* CastClass => ref *(Il2CppClass**)((byte*)Pointer + 0x48);
        public ref Il2CppClass* DeclaringType => ref *(Il2CppClass**)((byte*)Pointer + 0x50);
        public ref Il2CppClass* Class => ref *(Il2CppClass**)((byte*)Pointer + 0x78);
        public ref Il2CppFieldInfo* Fields => ref *(Il2CppFieldInfo**)((byte*)Pointer + 0x80);
        public ref Il2CppMethodInfo** Methods => ref *(Il2CppMethodInfo***)((byte*)Pointer + 0x88);
        public ref Il2CppClass** ImplementedInterfaces { get { ProjectInterfaces(); return ref interfaces; } }
        public ref Il2CppRuntimeInterfaceOffsetPair* InterfaceOffsets { get { ProjectInterfaces(); return ref offsets; } }
        public ref Il2CppClass** TypeHierarchy => ref *(Il2CppClass***)((byte*)Pointer + 0xa8);
        public bool ValueType { get => ByValArg.ValueType; set => ByValArg.ValueType = value; }
        public bool EnumType { get => Bit(0x12d,4); set => Bit(0x12d,4,value); }
        public bool IsGeneric { get => Bit(0x12d,16); set => Bit(0x12d,16,value); }
        public bool Initialized { get => Bit(0x12d,2); set => Bit(0x12d,2,value); }
        public bool InitializedAndNoError { get => Bit(0x12d,1); set => Bit(0x12d,1,value); }
        public bool SizeInited { get => Bit(0x12e,1); set => Bit(0x12e,1,value); }
        public bool HasFinalize { get => Bit(0x12e,2); set => Bit(0x12e,2,value); }
        public bool IsVtableInitialized { get => Bit(0x12e,32); set => Bit(0x12e,32,value); }
    }
}
