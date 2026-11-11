using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Runtime.InteropServices;
using System.Threading;
using BepInEx;
using BepInEx.Preloader.Core.Patching;

namespace MoonLab.BepInExAdapter;

[PatcherPluginInfo("moonlab.il2cpp.adapter", "MoonLab IL2CPP Adapter", "0.1.0")]
public sealed class Adapter : BasePatcher
{
    [DllImport("version.dll", EntryPoint="MoonLab_InstalledManagedState_v1", CallingConvention=CallingConvention.Cdecl)]
    private static extern uint InstalledManagedState();
    public override void Initialize()
    {
        string? output = null;
        try
        {
            // Until installed admission succeeds, inherited evidence variables
            // are untrusted. Keep fatal startup reports in this host's folder.
            output = AdapterFailure.Fallback(Paths.BepInExRootPath);
            // Installed mode relies on the resident bootstrap's exact enabled
            // generation/inventory validation. Private mode retains its existing
            // synchronous save guard and independent allowlist validation.
            string gameRoot = Path.GetDirectoryName(Paths.ExecutablePath)!;
            if (File.Exists(Path.Combine(gameRoot,"MoonLab","owner.json")))
            {
                InstalledSelection.RequireReady(InstalledManagedState, () => Thread.Sleep(25));
            }
            var measurements = Environment.GetEnvironmentVariable("MOONLAB_ADAPTER_PROFILE") == "1"
                ? new StartupMeasurements() : null;
            output = Environment.GetEnvironmentVariable("MOONLAB_BEPINEX_EVIDENCE")
                ?? output;
            Directory.CreateDirectory(output);
            string game = Path.Combine(Path.GetDirectoryName(Paths.ExecutablePath)!, "GameAssembly.dll");
            var profile = GameProfiles.Match(new(Paths.ExecutablePath,
                Path.Combine(Path.GetDirectoryName(game)!,"UnityPlayer.dll"),game));
            measurements?.Mark("game_identity");
            string actual = profile.GameAssemblyHash;
            ManagedInputs.Verify(Path.GetDirectoryName(Paths.ExecutablePath)!,
                Path.Combine(Paths.BepInExRootPath,"MoonLab","allowed-inputs.json"));
            measurements?.Mark("managed_input_verification");
            Native.Initialize(game);
            measurements?.Mark("native_api_initialization");
            Log.LogInfo("MoonLab adapter: pinned live IL2CPP domain " + Native.Domain);
            if (Environment.GetEnvironmentVariable("MOONLAB_BEPINEX_SNAPSHOT") == "1")
            {
                var snapshot = MetadataSnapshot.Capture(actual);
                File.WriteAllText(Path.Combine(output, "metadata.json"), JsonSerializer.Serialize(snapshot));
                Log.LogInfo("MoonLab live metadata snapshot complete: " + snapshot.Assemblies.Length + " assemblies");
                File.WriteAllText(Path.Combine(output, "snapshot-complete.json"), JsonSerializer.Serialize(new { success = true, game_sha256 = actual, assemblies = snapshot.Assemblies.Length }));
                // This explicit diagnostic mode stops before any plug-in is loaded.
                Environment.Exit(0);
            }
            Interop153Bridge.InstallProfile(profile);
            measurements?.Mark("native_layout_validation");
            string interop = Path.Combine(Paths.BepInExRootPath, "interop");
            var identity = new CacheIdentity(actual,profile.Id,profile.Repairs.Select(p => p.Id).ToArray(),
                FileIntegrity.Hash(typeof(Adapter).Assembly.Location));
            bool cacheReady = File.Exists(Path.Combine(interop,InteropCache.ReceiptName)) && InteropCache.Verify(interop,identity);
            if (File.Exists(Path.Combine(interop,InteropCache.ReceiptName)) && !cacheReady)
            {
                string retired = Path.Combine(Paths.BepInExRootPath,"MoonLab","retired-interop",Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(Path.GetDirectoryName(retired)!);
                Directory.Move(interop,retired);
                Directory.CreateDirectory(interop);
            }
            measurements?.Mark("initial_cache_verification");
            if (!File.Exists(Path.Combine(interop, "moonlab-interop.json")))
            {
                if (Directory.EnumerateFileSystemEntries(interop).Any())
                    throw new InvalidOperationException("Unowned interop files must be preserved and reviewed");
                string job = Path.Combine(Paths.BepInExRootPath,"MoonLab","generation",Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(Path.GetDirectoryName(job)!);
                string metadata = Path.Combine(output,"metadata.json");
                using var document = MetadataDocument.FromValue(MetadataSnapshot.Capture(actual));
                using (var evidence = File.Create(metadata)) document.WriteTo(evidence);
                measurements?.Mark("live_metadata_capture_and_serialization");
                Log.LogInfo("Generating source-pinned bindings from original live metadata");
                new InteropGeneration().Run(new(document,job,game,profile.Id,profile.Repairs));
                measurements?.Mark("declaration_and_binding_generation");
                string generated = Path.Combine(job,"interop");
                string emptyBackup = interop + ".empty-" + Guid.NewGuid().ToString("N");
                Directory.Move(interop,emptyBackup);
                try { Directory.Move(generated,interop); }
                catch { Directory.Move(emptyBackup,interop); throw; }
                Directory.Delete(emptyBackup);
                measurements?.Mark("cache_publication");
            }
            if (!cacheReady && !InteropCache.Verify(interop,identity)) throw new InvalidOperationException("Generated cache identity mismatch");
            measurements?.Mark("final_cache_verification");
            File.WriteAllText(Path.Combine(output, "adapter-ready.json"), JsonSerializer.Serialize(new { success = true, game_sha256 = actual, profile = profile.Id, repairs = profile.Repairs.Select(p => p.Id).ToArray(), startup = measurements?.Snapshot(), native_classes = measurements == null ? null : StartupMeasurements.MeasureNativeClasses() }));
            Log.LogInfo("MoonLab independent adapter ready");
        }
        catch (Exception error)
        {
            AdapterFailure.Stop(error,output,failure=>Log.LogError(failure));
        }
    }
}

internal static class AdapterFailure
{
    internal static string Fallback(string bepinexRoot) => Path.Combine(bepinexRoot,"MoonLab","evidence");

    internal static void Stop(Exception error, string? output, Action<Exception> log)
    {
        // Reporting must never turn a fatal adapter error into a caught patcher
        // exception that lets upstream continue loading managed plugins.
        try { log(error); } catch { }
        try
        {
            if (output != null)
            {
                Directory.CreateDirectory(output);
                File.WriteAllText(Path.Combine(output,"adapter-failure.txt"),error.ToString());
            }
        }
        catch { }
        Environment.Exit(23);
    }
}


internal static class InstalledSelection
{
    internal static void RequireReady(Func<uint> read, Action pause, int attempts=1200)
    {
        for (int attempt=0; attempt<attempts; attempt++)
        {
            uint state = read();
            if (state == 1) return;
            if (state != 0) throw new InvalidDataException("Installed managed selection was rejected by the native bootstrap");
            pause();
        }
        throw new InvalidDataException("Installed managed selection did not become ready before the timeout");
    }
}
