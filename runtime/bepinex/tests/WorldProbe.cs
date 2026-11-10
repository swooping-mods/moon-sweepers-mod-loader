using System;
using System.IO;
using System.Text.Json;
using BepInEx;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;
using System.Collections;
using System.Linq;
using System.Reflection;
using BepInEx.Unity.IL2CPP.Utils;
using Il2CppInterop.Runtime.Injection;
using MoonCleaners;
using UnityEngine;

namespace MoonLab.WorldProbe;

public sealed class FrameCapture : MonoBehaviour
{
    public FrameCapture(IntPtr pointer) : base(pointer) { }
    private float nextScan;
    public void Update()
    {
        if (Time.realtimeSinceStartup < nextScan) return;
        nextScan = Time.realtimeSinceStartup + 1f;
        var sessions=Resources.FindObjectsOfTypeAll(Il2CppInterop.Runtime.Il2CppType.Of<MoonCrewSession>());
        for (int i=0;i<sessions.Length;i++)
        {
            var session=sessions[i].Cast<MoonCrewSession>();
            if (session != null && session.isActiveAndEnabled && session.local != null && session.local.world != null)
            {
                WorldProbe.Observe(session.local);
                return;
            }
        }
    }
    internal IEnumerator Capture(string folder,int id)
    {
        yield return new WaitForEndOfFrame();
        Texture2D? texture = null;
        try
        {
            texture = new Texture2D(Screen.width,Screen.height,TextureFormat.RGBA32,false);
            texture.ReadPixels(new Rect(0,0,Screen.width,Screen.height),0,0);
            texture.Apply();
            File.WriteAllBytes(Path.Combine(folder,"unity-frame-"+id+".png"),ImageConversion.EncodeToPNG(texture).AsSpan().ToArray());
        }
        catch (Exception error) { File.WriteAllText(Path.Combine(folder,"world-observer-error.txt"),error.ToString()); }
        finally { if (texture != null) UnityEngine.Object.Destroy(texture); }
    }
}

[BepInPlugin("moonlab.world.observer", "MoonLab private world observer", "0.1.0")]
public sealed class WorldProbe : BasePlugin
{
    private static string output = "";
    private static FrameCapture runner = null!;
    private static float next;
    private static int lastCommand;
    internal static void Observe(MoonWalker __instance)
    {
        if (Time.realtimeSinceStartup < next) return;
        next = Time.realtimeSinceStartup + 1;
        try
        {
            var world = __instance.world;
            if (world == null) return;
            var point = __instance.transform.position;
            string path = world.SaveDirectory;
            var direction=__instance.MoveDirection;
            string observation=JsonSerializer.Serialize(new {
                success=true, world=true, terrain=world.Terrain != null,
                loading=MoonSession.Loading, held=__instance.Held, blocked=__instance.uiBlocked, focused=Application.isFocused,
                save_directory=path, folder=MoonSaveSlots.Folder,
                gravity=world.settings.gravity, seed=world.settings.seed,
                pending_save=world.PendingSave != null && !world.PendingSave.IsCompleted, save_status=MoonWorld.SaveStatus, x=point.x,y=point.y,z=point.z,
                graphics=SystemInfo.graphicsDeviceName,
                move_x=direction.x, move_y=direction.y, move_z=direction.z,
                walker_name=__instance.gameObject.name, body=__instance.body != null, seated=__instance.vehicleSeat != null,
                terminal_open=TerminalOpen(), typing=MoonInput.Typing, input_blocked=__instance.UIBlocked, menu_blocked=__instance.MenuBlocked,
                shelter_api=ShelterState(),
                timestamp=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
            });
            File.WriteAllText(Path.Combine(output,"world-observer.json"),observation);
            File.AppendAllText(Path.Combine(output,"motion-samples.jsonl"),observation+"\n");
            string control = Path.Combine(output,"world-control.json");
            if (File.Exists(control))
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(control));
                int id = doc.RootElement.GetProperty("id").GetInt32();
                if (id <= lastCommand) return;
                lastCommand = id;
                switch (doc.RootElement.GetProperty("action").GetString())
                {
                    case "capture": runner.StartCoroutine(runner.Capture(output,id)); break;
                    case "compat-profile": runner.StartCoroutine(CompatibilityBenchmark.Run(output,id)); break;
                    case "save": world.RequestSave(); break;
                    case "outside":
                        // Diagnostic staging beside the starter base. Physics
                        // and subsequent movement remain owned by the game.
                        var before=__instance.transform.position;
                        var destination=new Vector3(80f,2010f,-18f);
                        __instance.Teleport(destination,true);
                        var after=__instance.transform.position;
                        var physical=__instance.body.position;
                        File.WriteAllText(Path.Combine(output,"teleport-evidence.json"),JsonSerializer.Serialize(new {
                            before=new {before.x,before.y,before.z},
                            destination=new {destination.x,destination.y,destination.z},
                            after=new {after.x,after.y,after.z},body=new {physical.x,physical.y,physical.z}}));
                        break;
                    case "menu": MoonSession.ReturnToMenu(); break;
                    case "quit": MoonSession.QuitGame(); break;
                    default: throw new InvalidOperationException("Unknown private world diagnostic action");
                }
                File.WriteAllText(Path.Combine(output,"world-action.json"),JsonSerializer.Serialize(new {success=true,id}));
            }
        }
        catch (Exception error)
        {
            File.WriteAllText(Path.Combine(output,"world-observer-error.txt"),error.ToString());
        }
    }
    private static bool TerminalOpen()
    {
        var mars = AppDomain.CurrentDomain.GetAssemblies().Single(a => a.GetName().Name == "MarsMod");
        return (bool)mars.GetType("MarsMod.Terminal",true)!.GetProperty("Open",BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!;
    }
    private sealed record ShelterApi(bool looked, bool bound, bool broken, int rays_per_second, float ray_window);
    private static ShelterApi ShelterState()
    {
        var mars = AppDomain.CurrentDomain.GetAssemblies().Single(a => a.GetName().Name == "MarsMod");
        var shelter = mars.GetType("MarsMod.Shelter",true)!;
        const BindingFlags fields = BindingFlags.Static | BindingFlags.NonPublic;
        return new((bool)shelter.GetField("looked",fields)!.GetValue(null)!,
            shelter.GetField("raycast",fields)!.GetValue(null) is MethodInfo,
            (bool)shelter.GetField("broken",fields)!.GetValue(null)!,
            (int)shelter.GetProperty("RaysPerSecond",BindingFlags.Static | BindingFlags.Public)!.GetValue(null)!,
            (float)shelter.GetField("rayWindow",fields)!.GetValue(null)!);
    }
    public override void Load()
    {
        output = Environment.GetEnvironmentVariable("MOONLAB_BEPINEX_EVIDENCE")
            ?? throw new InvalidOperationException("Private observer requires an owned evidence path");
        ClassInjector.RegisterTypeInIl2Cpp<FrameCapture>();
        var captures = new GameObject("MoonLab private frame evidence");
        UnityEngine.Object.DontDestroyOnLoad(captures);
        runner = captures.AddComponent<FrameCapture>();
        Log.LogInfo("Original private world observer ready");
    }
}
