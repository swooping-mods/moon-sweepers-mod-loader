"""Explicit compilation boundaries for the adapter and optional tooling/plugins."""
from pathlib import Path

BASE = Path('runtime/bepinex')
GENERATION = (
    'Generate.cs', 'InteropGeneration.cs', 'BindingRepairs.cs',
    'FileIntegrity.cs', 'MetadataDocument.cs',
)
PROFILES = (
    'profiles/GameProfile.cs', 'profiles/MoonSweepersSteam105.cs', 'repairs/UnityCoreRepairs.cs',
    'repairs/UnityPhysicsRepairs.cs',
)
ADAPTER = GENERATION + PROFILES + (
    'Adapter.cs', 'Integrity.cs', 'InteropCache.cs', 'Native.cs', 'MetadataSnapshot.cs', 'StartupMeasurements.cs',
    'profiles/Unity6000_6ClassLayout.cs', 'Interop153Bridge.cs', 'NativeAllocationArena.cs', 'UnityShims.cs',
)
DIAGNOSTIC = GENERATION + PROFILES + ('ApiCheck.cs', 'diagnostics/AssemblyResolutionScope.cs', 'diagnostics/GenerateCommand.cs')
PLUGINS = {
    'test': ('tests/TestPlugin.cs', 'tests/PhysicsProbe.cs'),
    'world': ('tests/WorldProbe.cs', 'tests/CompatibilityBenchmark.cs'),
}


def sources(root, target):
    names = {'adapter': ADAPTER, 'diagnostic': DIAGNOSTIC, 'engine': GENERATION,
             'checks': ADAPTER + ('diagnostics/AssemblyResolutionScope.cs', 'tests/AdapterChecks.cs'), **PLUGINS}[target]
    result = [Path(root) / BASE / name for name in names]
    if len(set(result)) != len(result):
        raise ValueError('Duplicate compilation input: ' + target)
    for path in result:
        if not path.is_file():
            raise ValueError('Missing compilation input: ' + str(path))
    return result
