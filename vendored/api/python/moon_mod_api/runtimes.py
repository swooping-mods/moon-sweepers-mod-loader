"""Package backend contracts; hosting and deployment belong to the loader."""
import re
from urllib.parse import urlsplit
from .storage import relative

NATIVE_ABIS = tuple("MoonLab_ModStart/v" + str(version) for version in range(1, 7))
MANAGED_KIND = "bepinex-il2cpp"
MANAGED_ABI = "BepInEx.IL2CPP/6-be791"
RUNTIMES = frozenset([*(('native', abi) for abi in NATIVE_ABIS),
                      (MANAGED_KIND, MANAGED_ABI), ('companion', 'PythonZipApp/v1')])


def game_mod(manifest):
    return manifest.get("kind") in ("native", MANAGED_KIND)


def validate(manifest):
    runtime = (manifest.get("kind"), manifest.get("abi"))
    if not all(isinstance(value, str) for value in runtime) or runtime not in RUNTIMES:
        raise ValueError("Unsupported mod runtime")
    if "mode" in manifest or "external" in manifest:
        external = manifest.get("external")
        if manifest.get("mode") != "external" or manifest["kind"] != MANAGED_KIND:
            raise ValueError("External mode requires a managed adapter, never a native mod ABI")
        if not isinstance(external, dict) or set(external) != {"adapter", "repository", "revision"}:
            raise ValueError("External mode requires adapter and source provenance")
        if external["adapter"] != MANAGED_KIND:
            raise ValueError("External adapter does not match the package runtime")
        try:
            source = urlsplit(external["repository"]) if isinstance(external["repository"], str) else None
            valid = (source and source.scheme == "https" and source.hostname and not source.username
                     and not source.password and not source.query and not source.fragment
                     and source.path.strip("/"))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("External source must be an HTTPS repository URL")
        if not isinstance(external["revision"], str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}", external["revision"]):
            raise ValueError("External source requires a revision")
    if manifest["kind"] != MANAGED_KIND:
        if "bepinex" in manifest:
            raise ValueError("BepInEx settings require the managed runtime")
        return
    host = manifest.get("bepinex")
    if not isinstance(host, dict) or set(host) != {"guid", "data_root"}:
        raise ValueError("Managed mods require explicit BepInEx identity and data namespace")
    if not isinstance(host["guid"], str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{2,127}", host["guid"]):
        raise ValueError("Invalid BepInEx plugin GUID")
    namespace = host["data_root"]
    reserved = {"core", "patchers", "plugins", "interop", "config", "cache", "unity-libs",
                "moonlab", "third-party-sources", "unhollowed"}
    if (not isinstance(namespace, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", namespace)
            or namespace.casefold() in reserved):
        raise ValueError("Reserved or invalid managed data namespace")
    relative(namespace)
    if "/" in manifest["entry"]:
        raise ValueError("Managed entry must be a root DLL")


def selection(manifests, chosen):
    identities, namespaces = {}, {}
    for name in sorted(chosen):
        mod = manifests.get(name, {})
        if mod.get("kind") != MANAGED_KIND:
            continue
        # Recheck identity fields here too: callers may construct a selection
        # directly rather than obtaining every descriptor from archive intake.
        validate(mod)
        for value, owners in ((mod["bepinex"]["guid"].casefold(), identities),
                              (mod["bepinex"]["data_root"].casefold(), namespaces)):
            if value in owners:
                raise ValueError("Managed plugin identity/data collision: " + name + " and " + owners[value])
            owners[value] = name


def require_available(manifest, available, runtime_api_abi=None, runtime_readiness_abi=None):
    """An SDK can inspect a backend without promising that a target hosts it."""
    if available is not None and (manifest.get("kind"), manifest.get("abi")) not in available:
        raise ValueError("Runtime is unavailable for " + manifest["id"] + ": " +
                         str(manifest.get("kind")) + " / " + str(manifest.get("abi")))
    if (manifest.get("runtime_api_abi") is not None and runtime_api_abi is not None
            and (type(runtime_api_abi) is not int or runtime_api_abi != manifest["runtime_api_abi"])):
        raise ValueError("Public runtime API ABI is unavailable for " + manifest["id"])
    if (manifest.get("kind") == MANAGED_KIND and manifest.get("runtime_api_abi") is not None
            and runtime_readiness_abi is not None
            and (type(runtime_readiness_abi) is not int or runtime_readiness_abi != 1)):
        raise ValueError("Native runtime readiness ABI is unavailable for " + manifest["id"])
