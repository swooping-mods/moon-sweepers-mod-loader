using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

namespace MoonLab.BepInExAdapter;

internal static class UnityRepairReferences
{
    internal static TypeReference Shims(ModuleDefinition module)
    {
        var adapter = module.AssemblyReferences.SingleOrDefault(p => p.Name == "MoonLab.BepInExAdapter");
        if (adapter == null)
        {
            adapter = new AssemblyNameReference("MoonLab.BepInExAdapter",new Version(0,0,0,0));
            module.AssemblyReferences.Add(adapter);
        }
        return new TypeReference("MoonLab.BepInExAdapter","UnityShims",module,adapter);
    }
}

internal sealed class ShaderPropertiesRepair : IBindingRepair
{
    public string Id => "unity.shader-properties/v1";
    public string TargetAssembly => "UnityEngine.CoreModule.dll";
    public void Apply(ModuleDefinition module)
    {
        if (module.GetType("UnityEngine.Rendering.ShaderPropertyType") != null)
            throw new InvalidOperationException("Shader shim is no longer needed; requalify this game");
        // Public API identifiers and numeric values, independently declared.
        var kind = new TypeDefinition("UnityEngine.Rendering","ShaderPropertyType",
            TypeAttributes.Public | TypeAttributes.Sealed,
            new TypeReference("System","Enum",module,module.TypeSystem.Object.Scope));
        kind.Fields.Add(new FieldDefinition("value__",FieldAttributes.Public | FieldAttributes.SpecialName | FieldAttributes.RTSpecialName,module.TypeSystem.Int32));
        string[] names = { "Color","Vector","Float","Range","Texture","Int" };
        for (int i = 0; i < names.Length; i++) kind.Fields.Add(new FieldDefinition(names[i],
            FieldAttributes.Public | FieldAttributes.Static | FieldAttributes.Literal | FieldAttributes.HasDefault,kind) { Constant = i });
        module.Types.Add(kind);
        var shader = module.GetType("UnityEngine.Shader");
        var obj = module.GetType("UnityEngine.Object");
        var helper = UnityRepairReferences.Shims(module);
        var call = new MethodReference("ShaderPropertyType",module.TypeSystem.Int32,helper) { HasThis = false };
        call.Parameters.Add(new ParameterDefinition(module.TypeSystem.IntPtr));
        call.Parameters.Add(new ParameterDefinition(module.TypeSystem.Int32));
        var type = new MethodDefinition("GetPropertyType",MethodAttributes.Public | MethodAttributes.HideBySig,kind);
        type.Parameters.Add(new ParameterDefinition("index",ParameterAttributes.None,module.TypeSystem.Int32));
        shader.Methods.Add(type);
        var il = type.Body.GetILProcessor();
        il.Emit(OpCodes.Ldarg_0);
        il.Emit(OpCodes.Call,obj.Methods.Single(m => m.Name == "get_m_CachedPtr"));
        il.Emit(OpCodes.Ldarg_1); il.Emit(OpCodes.Call,call); il.Emit(OpCodes.Ret);

        // Names can be recovered through the retained ID and reverse-lookup
        // APIs, avoiding a second string-marshalling implementation.
        var name = new MethodDefinition("GetPropertyName",MethodAttributes.Public | MethodAttributes.HideBySig,module.TypeSystem.String);
        name.Parameters.Add(new ParameterDefinition("index",ParameterAttributes.None,module.TypeSystem.Int32));
        shader.Methods.Add(name);
        var text = new VariableDefinition(module.TypeSystem.String);
        name.Body.Variables.Add(text); name.Body.InitLocals = true;
        il = name.Body.GetILProcessor();
        il.Emit(OpCodes.Ldarg_0); il.Emit(OpCodes.Ldarg_1);
        il.Emit(OpCodes.Call,shader.Methods.Single(m => m.Name == "GetPropertyNameId" && !m.IsStatic));
        il.Emit(OpCodes.Ldloca,text);
        il.Emit(OpCodes.Call,shader.Methods.Single(m => m.Name == "TryConvertPropertyIDToName"));
        il.Emit(OpCodes.Pop); il.Emit(OpCodes.Ldloc,text); il.Emit(OpCodes.Ret);
    }
}

internal sealed class UnityRetainedApiRepair : IBindingRepair
{
    public string Id => "unity.retained-convenience/v1";
    public string TargetAssembly => "UnityEngine.CoreModule.dll";
    private static TypeReference InteropType(ModuleDefinition m,string ns,string name)
    {
        // Import public signatures explicitly. Reflection-importing these from
        // an offline .NET 10 host would accidentally raise the target CLR ABI.
        var scope=m.AssemblyReferences.Single(p=>p.Name=="Il2CppInterop.Runtime");
        var type=new TypeReference(ns,name,m,scope);
        if (name.EndsWith("`1")) type.GenericParameters.Add(new GenericParameter("T",type));
        return type;
    }
    private static MethodDefinition Add(TypeDefinition owner,string name,TypeReference result,bool isStatic,params TypeReference[] parameters)
    {
        var method = new MethodDefinition(name,MethodAttributes.Public | MethodAttributes.HideBySig |
            (isStatic ? MethodAttributes.Static : 0),result);
        foreach (var parameter in parameters) method.Parameters.Add(new ParameterDefinition(parameter));
        owner.Methods.Add(method);
        return method;
    }
    private static void Setter(TypeDefinition owner,MethodDefinition setter)
    {
        setter.IsSpecialName = true;
        owner.Properties.Single(p => p.Name == setter.Name[4..]).SetMethod = setter;
    }
    public void Apply(ModuleDefinition m)
    {
        var helper = UnityRepairReferences.Shims(m);
        var obj = m.GetType("UnityEngine.Object");
        var material=m.GetType("UnityEngine.Material");var texture=m.GetType("UnityEngine.Texture");
        var shader=m.GetType("UnityEngine.Shader");var renderer=m.GetType("UnityEngine.Renderer");
        var setter=Add(renderer,"set_material",m.TypeSystem.Void,false,material);
        var il=setter.Body.GetILProcessor();il.Emit(OpCodes.Ldarg_0);il.Emit(OpCodes.Ldarg_1);
        il.Emit(OpCodes.Call,renderer.Methods.Single(p => p.Name=="SetMaterial"));il.Emit(OpCodes.Ret);Setter(renderer,setter);

        setter=Add(material,"set_mainTexture",m.TypeSystem.Void,false,texture);
        var id=new VariableDefinition(m.TypeSystem.Int32);setter.Body.Variables.Add(id);setter.Body.InitLocals=true;
        il=setter.Body.GetILProcessor();il.Emit(OpCodes.Ldarg_0);il.Emit(OpCodes.Ldc_I4,128);
        il.Emit(OpCodes.Call,material.Methods.Single(p => p.Name=="GetFirstPropertyNameIdByAttribute"));il.Emit(OpCodes.Stloc,id);
        var ready=Instruction.Create(OpCodes.Nop);il.Emit(OpCodes.Ldloc,id);il.Emit(OpCodes.Ldc_I4_M1);il.Emit(OpCodes.Bne_Un,ready);
        il.Emit(OpCodes.Ldstr,"_MainTex");il.Emit(OpCodes.Call,shader.Methods.Single(p => p.Name=="PropertyToID"));il.Emit(OpCodes.Stloc,id);
        il.Append(ready);il.Emit(OpCodes.Ldarg_0);il.Emit(OpCodes.Ldloc,id);il.Emit(OpCodes.Ldarg_1);
        il.Emit(OpCodes.Call,material.Methods.Single(p => p.Name=="SetTexture" && p.Parameters[0].ParameterType.FullName=="System.Int32"));
        il.Emit(OpCodes.Ret);Setter(material,setter);

        var camera=m.GetType("UnityEngine.Camera");setter=Add(camera,"set_cullingMask",m.TypeSystem.Void,false,m.TypeSystem.Int32);
        var mask=new MethodReference("CameraCullingMask",m.TypeSystem.Void,helper) { HasThis=false };
        mask.Parameters.Add(new ParameterDefinition(m.TypeSystem.IntPtr));mask.Parameters.Add(new ParameterDefinition(m.TypeSystem.Int32));
        il=setter.Body.GetILProcessor();il.Emit(OpCodes.Ldarg_0);il.Emit(OpCodes.Call,obj.Methods.Single(p=>p.Name=="get_m_CachedPtr"));
        il.Emit(OpCodes.Ldarg_1);il.Emit(OpCodes.Call,mask);il.Emit(OpCodes.Ret);Setter(camera,setter);

        var rt=m.GetType("UnityEngine.RenderTexture");var temporary=Add(rt,"GetTemporary",rt,true,m.TypeSystem.Int32,m.TypeSystem.Int32,m.TypeSystem.Int32);
        var five=rt.Methods.Single(p=>p.Name=="GetTemporary" && p.Parameters.Count==5);
        il=temporary.Body.GetILProcessor();il.Emit(OpCodes.Ldarg_0);il.Emit(OpCodes.Ldarg_1);il.Emit(OpCodes.Ldarg_2);
        il.Emit(OpCodes.Ldc_I4,Convert.ToInt32(m.GetType("UnityEngine.RenderTextureFormat").Fields.Single(p=>p.Name=="Default").Constant));
        il.Emit(OpCodes.Ldc_I4_0);il.Emit(OpCodes.Call,five);il.Emit(OpCodes.Ret);

        var transform=m.GetType("UnityEngine.Transform");var quaternion=m.GetType("UnityEngine.Quaternion");
        var rotate=Add(transform,"Rotate",m.TypeSystem.Void,false,m.TypeSystem.Single,m.TypeSystem.Single,m.TypeSystem.Single,m.GetType("UnityEngine.Space"));
        var q=new VariableDefinition(quaternion);rotate.Body.Variables.Add(q);rotate.Body.InitLocals=true;
        il=rotate.Body.GetILProcessor();il.Emit(OpCodes.Ldarg_1);il.Emit(OpCodes.Ldarg_2);il.Emit(OpCodes.Ldarg_3);
        il.Emit(OpCodes.Call,quaternion.Methods.Single(p=>p.Name=="Euler" && p.Parameters.Count==3));il.Emit(OpCodes.Stloc,q);
        var world=Instruction.Create(OpCodes.Nop);il.Emit(OpCodes.Ldarg,rotate.Parameters[3]);il.Emit(OpCodes.Ldc_I4_1);il.Emit(OpCodes.Bne_Un,world);
        var multiply=quaternion.Methods.Single(p=>p.Name=="op_Multiply" && p.Parameters[1].ParameterType.FullName==quaternion.FullName);
        il.Emit(OpCodes.Ldarg_0);il.Emit(OpCodes.Ldarg_0);il.Emit(OpCodes.Call,transform.Methods.Single(p=>p.Name=="get_localRotation"));
        il.Emit(OpCodes.Ldloc,q);il.Emit(OpCodes.Call,multiply);il.Emit(OpCodes.Call,transform.Methods.Single(p=>p.Name=="set_localRotation"));il.Emit(OpCodes.Ret);
        il.Append(world);il.Emit(OpCodes.Ldarg_0);il.Emit(OpCodes.Ldloc,q);il.Emit(OpCodes.Ldarg_0);
        il.Emit(OpCodes.Call,transform.Methods.Single(p=>p.Name=="get_rotation"));il.Emit(OpCodes.Call,multiply);
        il.Emit(OpCodes.Call,transform.Methods.Single(p=>p.Name=="set_rotation"));il.Emit(OpCodes.Ret);

        var array=InteropType(m,"Il2CppInterop.Runtime.InteropTypes.Arrays","Il2CppStructArray`1");
        var color=m.GetType("UnityEngine.Color");var color32=m.GetType("UnityEngine.Color32");
        var result=new GenericInstanceType(array);result.GenericArguments.Add(color32);
        var convert=new MethodReference("ConvertColors",m.TypeSystem.Void,helper) { HasThis=false };
        var inputType=new GenericParameter("TSource",convert);var outputType=new GenericParameter("TTarget",convert);
        convert.GenericParameters.Add(inputType);convert.GenericParameters.Add(outputType);
        var sourceArray=new GenericInstanceType(array);sourceArray.GenericArguments.Add(inputType);
        var targetArray=new GenericInstanceType(array);targetArray.GenericArguments.Add(outputType);
        convert.Parameters.Add(new ParameterDefinition(sourceArray));convert.ReturnType=targetArray;
        var conversion=new GenericInstanceMethod(convert);conversion.GenericArguments.Add(color);conversion.GenericArguments.Add(color32);
        var tex=m.GetType("UnityEngine.Texture2D");var pixels=Add(tex,"GetPixels32",result,false);
        il=pixels.Body.GetILProcessor();il.Emit(OpCodes.Ldarg_0);il.Emit(OpCodes.Call,tex.Methods.Single(p=>p.Name=="GetPixels" && p.Parameters.Count==0));
        il.Emit(OpCodes.Call,conversion);il.Emit(OpCodes.Ret);

        AddComponentQueries(m);
    }
    private static void AddComponentQueries(ModuleDefinition m)
    {
        var component=m.GetType("UnityEngine.Component");var go=m.GetType("UnityEngine.GameObject");
        var native=go.Methods.Single(p=>p.Name=="GetComponentsInternal" && !p.HasGenericParameters);
        var type=native.Parameters[0].ParameterType;
        var array=InteropType(m,"Il2CppInterop.Runtime.InteropTypes.Arrays","Il2CppReferenceArray`1");
        var result=new GenericInstanceType(array);result.GenericArguments.Add(component);
        var ctor=new MethodReference(".ctor",m.TypeSystem.Void,result) { HasThis=true };
        ctor.Parameters.Add(new ParameterDefinition(m.TypeSystem.IntPtr));
        var pointer=new MethodReference("Il2CppObjectBaseToPtr",m.TypeSystem.IntPtr,InteropType(m,"Il2CppInterop.Runtime","IL2CPP")) { HasThis=false };
        pointer.Parameters.Add(new ParameterDefinition(InteropType(m,"Il2CppInterop.Runtime.InteropTypes","Il2CppObjectBase")));
        void Body(MethodDefinition method,bool recursive,bool hasInactive)
        {
            var il=method.Body.GetILProcessor();il.Emit(OpCodes.Ldarg_0);
            if (method.DeclaringType==component) il.Emit(OpCodes.Call,component.Methods.Single(p=>p.Name=="get_gameObject"));
            il.Emit(OpCodes.Ldarg_1);il.Emit(OpCodes.Ldc_I4_0);il.Emit(recursive?OpCodes.Ldc_I4_1:OpCodes.Ldc_I4_0);
            il.Emit(hasInactive?OpCodes.Ldarg_2:OpCodes.Ldc_I4_0);il.Emit(OpCodes.Ldc_I4_0);il.Emit(OpCodes.Ldnull);
            il.Emit(OpCodes.Call,native);il.Emit(OpCodes.Call,pointer);il.Emit(OpCodes.Newobj,ctor);il.Emit(OpCodes.Ret);
        }
        Body(Add(go,"GetComponentsInChildren",result,false,type,m.TypeSystem.Boolean),true,true);
        Body(Add(go,"GetComponentsInChildren",result,false,type),true,false);
        Body(Add(component,"GetComponents",result,false,type),false,false);
    }
}
