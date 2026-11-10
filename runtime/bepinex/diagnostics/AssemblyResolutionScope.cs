using System;
using System.IO;
using System.Reflection;
using System.Runtime.Loader;

namespace MoonLab.BepInExAdapter;

internal sealed class AssemblyResolutionScope : IDisposable
{
    private readonly Func<AssemblyLoadContext,AssemblyName,Assembly?> resolve;
    internal AssemblyResolutionScope(string core)
    {
        resolve = (context,name) => {
            string path = Path.Combine(core,name.Name + ".dll");
            if (!File.Exists(path)) path = Path.Combine(Path.GetDirectoryName(Path.GetDirectoryName(core))!,"dotnet",name.Name + ".dll");
            return File.Exists(path) ? context.LoadFromAssemblyPath(path) : null;
        };
        AssemblyLoadContext.Default.Resolving += resolve;
    }
    public void Dispose() => AssemblyLoadContext.Default.Resolving -= resolve;
}
