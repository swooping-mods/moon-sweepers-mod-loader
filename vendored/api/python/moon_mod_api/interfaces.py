"""Owner-qualified public interfaces, independent of particular framework IDs."""
import re
from .storage import key
from .runtimes import MANAGED_KIND, MANAGED_ABI, host_requirements

MAX_APIS = 256
MAX_MOD_APIS = 64
MAX_API_SIZE = 65536


def owner(api):
    if not isinstance(api, str) or len(api) > 160 or '.' not in api:
        raise ValueError("API identity must be owner-qualified")
    provider, suffix = api.split('.', 1)
    try:
        key(provider)
    except ValueError:
        raise ValueError("API identity must be owner-qualified") from None
    if not re.fullmatch(r"[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)*", suffix):
        raise ValueError("API identity must be owner-qualified")
    return provider


def positive(value, maximum=0xffffffff):
    return type(value) is int and 0 < value <= maximum


def limits(value):
    if (not isinstance(value, dict) or len(value) > 32 or
            any(not isinstance(k, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", k)
                or type(v) is not int or not 0 <= v <= 0xffffffff for k, v in value.items())):
        raise ValueError("API limits must be bounded named nonnegative integers")


def validate_manifest(manifest):
    host_requirements(manifest)
    fields = {"provides", "requires_apis", "runtime_api_abi"}
    native = manifest.get("kind") == "native" and manifest.get("abi") in (
        "MoonLab_ModStart/v6", "MoonLab_ModStart/v7", "MoonLab_ModStart/v8")
    if not fields.intersection(manifest) and not native:
        return
    managed = manifest.get("kind") == MANAGED_KIND and manifest.get("abi") == MANAGED_ABI
    if (not (native or managed) or type(manifest.get("runtime_api_abi")) is not int
            or manifest["runtime_api_abi"] != 1):
        raise ValueError("Public interfaces require native v6/v7/v8 or a managed consumer and runtime API ABI 1")
    if managed and manifest.get("provides"):
        raise ValueError("Managed consumers cannot publish native API tables")
    provides = manifest.get("provides", {})
    if not isinstance(provides, dict) or len(provides) > MAX_MOD_APIS:
        raise ValueError("Invalid provided API table")
    for api, spec in provides.items():
        if owner(api) != manifest["id"]:
            raise ValueError("A mod may only publish APIs in its own namespace")
        if (not isinstance(spec, dict) or not {"abi", "size"} <= set(spec)
                or set(spec) - {"abi", "size", "limits"}
                or not positive(spec["abi"]) or not positive(spec["size"], MAX_API_SIZE)):
            raise ValueError("Provided APIs require an ABI and bounded table size")
        limits(spec.get("limits", {}))
    requirements = manifest.get("requires_apis", [])
    if not isinstance(requirements, list) or len(requirements) > MAX_MOD_APIS:
        raise ValueError("Invalid required API table")
    seen = set()
    for spec in requirements:
        if (not isinstance(spec, dict) or not {"api", "abi", "min_size"} <= set(spec)
                or set(spec) - {"api", "abi", "min_size", "optional", "limits"}):
            raise ValueError("Required APIs need an identity, ABI and minimum size")
        provider = owner(spec["api"])
        if spec["api"] in seen:
            raise ValueError("Duplicate API requirement")
        seen.add(spec["api"])
        if (not positive(spec["abi"]) or not positive(spec["min_size"], MAX_API_SIZE)
                or type(spec.get("optional", False)) is not bool):
            raise ValueError("Invalid API ABI, minimum size or optional flag")
        if provider == manifest["id"]:
            raise ValueError("A mod cannot depend on its own API")
        if not spec.get("optional", False) and provider not in manifest.get("requires", []):
            raise ValueError("Required APIs need an explicit package dependency: " + provider)
        limits(spec.get("limits", {}))


def selection(manifests, chosen):
    """Return selected API dependency edges; no implicit provider substitution."""
    published, edges = {}, {}
    for name in sorted(chosen):
        mod = manifests.get(name)
        if mod is None:
            continue
        validate_manifest(mod)
        for api, spec in mod.get("provides", {}).items():
            if name != owner(api):
                raise ValueError("Selected API owner does not match package identity")
            published[api] = spec
    if len(published) > MAX_APIS:
        raise ValueError("Selected mods exceed the public API registry capacity")
    for name in sorted(chosen):
        mod = manifests.get(name, {})
        edges[name] = []
        for requirement in mod.get("requires_apis", []):
            api = requirement["api"]
            provider = owner(api)
            if provider not in chosen and requirement.get("optional", False):
                continue
            actual = published.get(api)
            # An installed optional provider must satisfy the advertised contract.
            # Silently ignoring an incompatible installed version hides updates.
            if actual is None:
                raise ValueError("Required API is unavailable: " + api + " for " + name)
            if actual["abi"] != requirement["abi"] or actual["size"] < requirement["min_size"]:
                raise ValueError("Incompatible API ABI/size: " + api + " for " + name)
            for capacity, minimum in requirement.get("limits", {}).items():
                if actual.get("limits", {}).get(capacity, -1) < minimum:
                    raise ValueError("Insufficient API limit " + capacity + ": " + api + " for " + name)
            edges[name].append(provider)
    return edges
