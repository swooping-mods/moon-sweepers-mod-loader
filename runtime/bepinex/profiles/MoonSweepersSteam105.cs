using System.Collections.Generic;

namespace MoonLab.BepInExAdapter;

internal sealed class MoonSweepersSteam105 : IGameProfile
{
    public string Id => "moon-sweepers/steam-1.0.5-unity-6000.6.0f1";
    public string NativeLayoutId => "unity-6000.6-class/v1";
    public string GameAssemblyHash => "14f711a6a3b1b7cd803a03f85cc6c6201c5b546ab9b90329533f5cb8ae2e7f13";
    public IReadOnlyList<IBindingRepair> Repairs { get; } = System.Array.AsReadOnly<IBindingRepair>(new IBindingRepair[] {
        new ShaderPropertiesRepair(), new UnityRetainedApiRepair(), new UnityPhysicsRaycastRepair()
    });

    public bool Matches(GameFiles files) => FileIntegrity.Hash(files.GameAssembly) == GameAssemblyHash &&
        FileIntegrity.Hash(files.Player) == "bfafc49b185eb8427ad75e3648bcba3bf5b07455567ca05ae2b2e23bc1646c0c" &&
        FileIntegrity.Hash(files.Executable) == "0e780f8e8d4bf26ed6bdd8a4068ac42a18846a66a80da7ba5c78f1917a093901";
}
