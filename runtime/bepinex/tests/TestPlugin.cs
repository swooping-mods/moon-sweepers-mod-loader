using System;
using System.IO;
using System.Reflection;
using System.Text.Json;
using BepInEx;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;
using Il2CppInterop.Runtime.Injection;
using MoonCleaners;
using UnityEngine;

namespace MoonLab.ManagedProbe;

public sealed class ProbeBehaviour : MonoBehaviour
{
    public ProbeBehaviour(IntPtr pointer) : base(pointer) { }
    internal static bool AwakeSeen;
    internal static bool MessageSeen;
    public void Awake() { AwakeSeen = true; TestPlugin.Step("awake-callback"); }
    public void ProbeMessage() { MessageSeen = true; TestPlugin.Step("native-message-callback"); }
    public void Update() { TestPlugin.Complete(); }
}

[BepInPlugin("moonlab.managed.probe", "MoonLab Managed Probe", "0.1.0")]
public sealed class TestPlugin : BasePlugin
{
    private static int prefixes, postfixes;
    private static GameObject? probeObject;
    private static string folder = "";
    private static bool loaded, completed;
    internal static void Step(string text) => File.AppendAllText(Path.Combine(folder,"test-steps.log"),text + "\n");
    internal static void Complete()
    {
        if (!loaded || completed) return;
        completed = true;
        Step("injected-update-callback");
        File.WriteAllText(Path.Combine(folder,"test-plugin.json"),JsonSerializer.Serialize(new {
            success=ProbeBehaviour.AwakeSeen && ProbeBehaviour.MessageSeen,
            native_object_roundtrip=true, prefixes, postfixes, native_getter_restored=true,
            class_injection=true, awake_callback=ProbeBehaviour.AwakeSeen,
            native_message_callback=ProbeBehaviour.MessageSeen, update_callback=true,
            game_version=Application.version, scope="Original managed interop/native-hook/component diagnostic; no world/co-op claim"
        }));
        if (probeObject != null) UnityEngine.Object.Destroy(probeObject);
    }
    private static void Prefix() { prefixes++; }
    private static void Postfix(ref string __result) { postfixes++; __result += "/MoonLabHookProbe"; }
    public override void Load()
    {
        folder = Environment.GetEnvironmentVariable("MOONLAB_BEPINEX_EVIDENCE")!;
        var harmony = new Harmony("moonlab.managed.probe");
        GameObject? go = null;
        try
        {
            Step("plugin-load");
            go = new GameObject("MoonLab original managed interop probe");
            UnityEngine.Object.DontDestroyOnLoad(go);
            go.transform.position = new Vector3(1.25f,2.5f,-3.75f);
            var value = go.transform.position;
            if (Math.Abs(value.x-1.25f) > .001f || Math.Abs(value.y-2.5f) > .001f || Math.Abs(value.z+3.75f) > .001f)
                throw new InvalidOperationException("Native value/object call did not round-trip");
            Step("native-object-and-vector-roundtrip");
            var originalColor = MoonMapScreen.Backdrop;
            try
            {
                MoonMapScreen.Backdrop = new Color(.25f,.5f,.75f,1f);
                var color = MoonMapScreen.Backdrop;
                if (Math.Abs(color.r-.25f)>.001f || Math.Abs(color.b-.75f)>.001f)
                    throw new InvalidOperationException("Static Color field did not round-trip");
                Step("native-static-color-field-roundtrip");
            }
            finally { MoonMapScreen.Backdrop = originalColor; }
            int shaderProperties = 0;
            foreach (var shader in Resources.FindObjectsOfTypeAll<Shader>())
            {
                if (shader == null) continue;
                int count = Math.Min(shader.GetPropertyCount(),24);
                for (int i = 0; i < count; i++)
                {
                    int kind = (int)shader.GetPropertyType(i);
                    string name = shader.GetPropertyName(i);
                    if (kind < 0 || kind > 5 || string.IsNullOrEmpty(name) || Shader.PropertyToID(name) != shader.GetPropertyNameId(i))
                        throw new InvalidOperationException("Independent shader API shim did not round-trip");
                    shaderProperties++;
                }
                if (shaderProperties > 0) break;
            }
            if (shaderProperties == 0) throw new InvalidOperationException("No live shader properties qualified");
            Step("native-shader-property-type-name-roundtrip: " + shaderProperties);
            go.transform.rotation = Quaternion.identity;
            go.transform.Rotate(0f,90f,0f,Space.Self);
            if (go.transform.forward.x < .99f) throw new InvalidOperationException("Local Euler rotation shim failed");
            go.transform.Rotate(0f,-90f,0f,Space.World);
            if (go.transform.forward.z < .99f) throw new InvalidOperationException("World Euler rotation shim failed");
            var transformType = Il2CppInterop.Runtime.Il2CppType.Of<Transform>();
            if (go.GetComponentsInChildren(transformType,true).Length < 1 || go.GetComponentsInChildren(transformType).Length < 1 || go.transform.GetComponents(transformType).Length < 1)
                throw new InvalidOperationException("Dynamic component query shim failed");
            var camera = go.AddComponent<Camera>();
            camera.cullingMask = 32;
            if (camera.cullingMask != 32) throw new InvalidOperationException("Camera culling mask shim failed");
            var pixelsTexture = new Texture2D(2,2);
            try
            {
                var pixels = pixelsTexture.GetPixels32();
                if (pixels.Length != 4) throw new InvalidOperationException("Pixel array shim returned the wrong size");
            }
            finally { UnityEngine.Object.Destroy(pixelsTexture); }
            Step("native-rotation-components-camera-pixels-shims");
            PhysicsProbe.Run();
            var iterator = new BepInEx.Unity.IL2CPP.Utils.Collections.Il2CppManagedEnumerator(new[] { 7 }.GetEnumerator());
            var nativeIterator = iterator.Cast<Il2CppSystem.Collections.IEnumerator>();
            if (!nativeIterator.MoveNext() || nativeIterator.MoveNext())
                throw new InvalidOperationException("Injected interface virtual dispatch failed");
            Step("native-injected-interface-virtual-dispatch");
            string original = MoonSaveSlots.Folder;
            MethodBase target = AccessTools.PropertyGetter(typeof(MoonSaveSlots),"Folder");
            harmony.Patch(target,new HarmonyMethod(typeof(TestPlugin),nameof(Prefix)),new HarmonyMethod(typeof(TestPlugin),nameof(Postfix)));
            if (MoonSaveSlots.Folder != original + "/MoonLabHookProbe" || prefixes != 1 || postfixes != 1)
                throw new InvalidOperationException("Native Harmony prefix/postfix return handling failed");
            harmony.UnpatchSelf();
            if (MoonSaveSlots.Folder != original) throw new InvalidOperationException("Native getter not restored after unpatch");
            Step("native-harmony-prefix-postfix-and-unpatch");
            ClassInjector.RegisterTypeInIl2Cpp<ProbeBehaviour>();
            var component = go.AddComponent<ProbeBehaviour>();
            if (component == null) throw new InvalidOperationException("Injected component was null");
            Step("class-injection; awake=" + ProbeBehaviour.AwakeSeen + "; active=" + go.activeInHierarchy + "; playing=" + Application.isPlaying);
            go.SendMessage("ProbeMessage", null, SendMessageOptions.RequireReceiver);
            if (!ProbeBehaviour.MessageSeen) throw new InvalidOperationException("Native message did not reach injected component");
            probeObject = go;
            go = null;
            loaded = true;
            Step("awaiting-natural-update");
        }
        catch (Exception error)
        {
            Step("failed: " + error);
            File.WriteAllText(Path.Combine(folder,"test-plugin.json"),JsonSerializer.Serialize(new { success=false, error=error.ToString() }));
            Log.LogError(error);
        }
        finally
        {
            harmony.UnpatchSelf();
            if (go != null) UnityEngine.Object.Destroy(go);
        }
    }
}
