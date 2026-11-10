using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

namespace MoonLab.BepInExAdapter;

internal sealed class UnityPhysicsRaycastRepair : IBindingRepair
{
    public string Id => "unity.physics-raycast-convenience/v1";
    public string TargetAssembly => "UnityEngine.PhysicsModule.dll";

    public void Apply(ModuleDefinition module)
    {
        var physics = module.GetType("UnityEngine.Physics") ??
            throw new InvalidOperationException("Physics type is missing");
        string[] signature = {
            "UnityEngine.Vector3", "UnityEngine.Vector3", "UnityEngine.RaycastHit&",
            "System.Single", "System.Int32", "UnityEngine.QueryTriggerInteraction"
        };
        bool Matches(MethodDefinition method, int count) => method.Name == "Raycast" &&
            method.IsPublic && method.IsStatic && !method.HasGenericParameters &&
            method.ReturnType.FullName == "System.Boolean" && method.Parameters.Count == count &&
            method.Parameters.Select(p => p.ParameterType.FullName).SequenceEqual(signature.Take(count));
        if (physics.Methods.Any(p => Matches(p, 4)))
            throw new InvalidOperationException("Physics Raycast convenience repair is no longer needed; requalify this profile");
        var retained = physics.Methods.Single(p => Matches(p, 6));
        int useGlobal = Convert.ToInt32(module.GetType("UnityEngine.QueryTriggerInteraction")
            .Fields.Single(p => p.Name == "UseGlobal" && p.IsLiteral).Constant);
        var wrapper = new MethodDefinition("Raycast",
            MethodAttributes.Public | MethodAttributes.Static | MethodAttributes.HideBySig,
            retained.ReturnType);
        for (int i = 0; i < 4; i++)
            wrapper.Parameters.Add(new ParameterDefinition(retained.Parameters[i].Name,
                i == 2 ? ParameterAttributes.Out : ParameterAttributes.None,
                retained.Parameters[i].ParameterType));

        // Unity's default excludes the Ignore Raycast layer and observes the
        // current global trigger setting. Forward to the retained binding so
        // native invocation, value layout and out writeback have one owner.
        // https://docs.unity.com/en-us/engine/6000.6/script-reference/unityengine/physics/defaultraycastlayers
        var il = wrapper.Body.GetILProcessor();
        il.Emit(OpCodes.Ldarg_0); il.Emit(OpCodes.Ldarg_1);
        il.Emit(OpCodes.Ldarg_2); il.Emit(OpCodes.Ldarg_3);
        il.Emit(OpCodes.Ldc_I4, -5); il.Emit(OpCodes.Ldc_I4, useGlobal);
        il.Emit(OpCodes.Call, retained); il.Emit(OpCodes.Ret);
        physics.Methods.Add(wrapper);
    }
}
