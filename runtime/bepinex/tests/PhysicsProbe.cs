using System;
using System.Linq;
using System.Reflection;
using UnityEngine;

namespace MoonLab.ManagedProbe;

internal static class PhysicsProbe
{
    internal static void Run()
    {
        // Match the external mod's reflection selector, then exercise boxed
        // out-parameter writeback rather than only compiling a direct call.
        var raycast = typeof(Physics).GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(m => m.Name == "Raycast" && m.GetParameters().Length == 4 &&
                m.GetParameters()[0].ParameterType == typeof(Vector3) &&
                m.GetParameters()[1].ParameterType == typeof(Vector3) &&
                m.GetParameters()[2].ParameterType.IsByRef &&
                m.GetParameters()[3].ParameterType == typeof(float));
        if (raycast.ReturnType != typeof(bool) ||
            raycast.GetParameters()[2].ParameterType != typeof(RaycastHit).MakeByRefType() ||
            !raycast.GetParameters()[2].IsOut)
            throw new InvalidOperationException("Raycast reflection/out metadata mismatch");
        var origin = new Vector3(12345f, 12345f, 12345f);
        var direction = new Vector3(0f, 0f, 1f);
        GameObject? fixture = null;
        try
        {
            fixture = new GameObject("MoonLab isolated Physics translation control");
            fixture.layer = 0;
            fixture.transform.position = new Vector3(origin.x, origin.y, origin.z + 5f);
            var collider = fixture.AddComponent<BoxCollider>();
            collider.size = new Vector3(1f, 1f, 1f);
            Physics.SyncTransforms();

            bool Check(Vector3 rayDirection, float maxDistance, bool? expected)
            {
                var nativeHit = default(RaycastHit);
                bool direct = Physics.Raycast(origin, rayDirection, ref nativeHit,
                    maxDistance, -5, QueryTriggerInteraction.UseGlobal);
                object[] arguments = { origin, rayDirection, Activator.CreateInstance(typeof(RaycastHit))!, maxDistance };
                bool reflected = (bool)raycast.Invoke(null, arguments)!;
                if (direct != reflected || (expected.HasValue && reflected != expected.Value))
                    throw new InvalidOperationException("Raycast forwarding result mismatch");
                if (reflected)
                {
                    var hit = (RaycastHit)arguments[2];
                    if (nativeHit.collider != collider || hit.collider != collider ||
                        Math.Abs(hit.distance - nativeHit.distance) > .001f ||
                        Math.Abs(hit.distance - 4.5f) > .01f ||
                        Math.Abs(hit.point.x - nativeHit.point.x) > .001f ||
                        Math.Abs(hit.point.y - nativeHit.point.y) > .001f ||
                        Math.Abs(hit.point.z - nativeHit.point.z) > .001f)
                        throw new InvalidOperationException("Raycast boxed hit writeback mismatch");
                }
                return reflected;
            }

            Check(direction, 10f, true);
            Check(direction, 1f, false);
            Check(new Vector3(0f, 1f, 0f), 10f, false);
            fixture.layer = 2; // Ignore Raycast must be excluded by the default mask.
            Physics.SyncTransforms();
            Check(direction, 10f, false);
            var controlHit = default(RaycastHit);
            if (!Physics.Raycast(origin, direction, ref controlHit, 10f, ~0, QueryTriggerInteraction.UseGlobal))
                throw new InvalidOperationException("Ignored-layer collider control was absent");
            fixture.layer = 0;
            collider.isTrigger = true;
            Physics.SyncTransforms();
            if (Physics.Raycast(origin, direction, ref controlHit, 10f, -5, QueryTriggerInteraction.Ignore) ||
                !Physics.Raycast(origin, direction, ref controlHit, 10f, -5, QueryTriggerInteraction.Collide))
                throw new InvalidOperationException("Trigger controls did not distinguish query modes");
            // The global setting is untouched. Its current value must be
            // observed identically by the wrapper and the retained overload.
            bool globalTriggerHit = Check(direction, 10f, null);
            TestPlugin.Step("native-raycast-reflection-out-hit-miss-distance-layer-trigger-parity; global_trigger_hit=" + globalTriggerHit);
        }
        finally
        {
            if (fixture != null)
            {
                fixture.SetActive(false);
                UnityEngine.Object.Destroy(fixture);
                Physics.SyncTransforms();
            }
        }
    }
}
