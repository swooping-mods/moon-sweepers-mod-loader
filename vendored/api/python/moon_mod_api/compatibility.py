"""Requirement-based admission; reviewed targets are supplied by the loader.

No version inference, game inspection, downloading or mod execution happens here.
Qualification records are trusted loader inputs, never author manifest text.
"""
import hashlib
import json
import re

V8 = "MoonLab_ModStart/v8"
GAME_FILES = frozenset(("GameAssembly.dll", "MoonSweepers.exe", "UnityPlayer.dll"))
FIELDS = frozenset(("game_access", "game_api_abi", "requires_game"))
MAX_CAPABILITIES = 64
MAX_TABLE_SIZE = 65536
MAX_EVIDENCE = 128


def _positive(value, maximum=0xffffffff):
    return type(value) is int and 0 < value <= maximum


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _identity(value):
    return (isinstance(value, str) and len(value) <= 160
            and re.fullmatch(r"[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+", value) is not None)


def _profile_id(value):
    return (isinstance(value, str) and len(value) <= 64
            and re.fullmatch(r"[a-z][a-z0-9._-]*", value) is not None)


def _limits(value):
    if (not isinstance(value, dict) or len(value) > 32
            or any(not isinstance(k, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", k)
                   or type(v) is not int or not 0 <= v <= 0xffffffff for k, v in value.items())):
        raise ValueError("Game capability limits must be bounded named nonnegative integers")


def capabilities(value, required=False):
    if not isinstance(value, dict) or len(value) > MAX_CAPABILITIES:
        raise ValueError("Invalid game capability table")
    size = "min_size" if required else "size"
    for name, spec in value.items():
        if not _identity(name):
            raise ValueError("Invalid logical game capability identity")
        if (not isinstance(spec, dict) or not {"abi", size} <= set(spec)
                or set(spec) - {"abi", size, "limits"}
                or not _positive(spec["abi"]) or not _positive(spec[size], MAX_TABLE_SIZE)):
            raise ValueError("Game capabilities require an ABI and bounded table size")
        _limits(spec.get("limits", {}))
    return value


def validate_manifest(manifest):
    modern = manifest.get("kind") == "native" and manifest.get("abi") == V8
    if not modern:
        if FIELDS.intersection(manifest):
            raise ValueError("Game adapter contracts require native v8")
        return
    if (manifest.get("game_access") != "adapter" or type(manifest.get("game_api_abi")) is not int
            or manifest["game_api_abi"] != 1 or "requires_game" not in manifest):
        raise ValueError("Native v8 requires adapter game access, game API ABI 1 and explicit requires_game")
    capabilities(manifest["requires_game"], required=True)
    if (manifest.get("claims") or manifest.get("shared_claims")
            or any(k in manifest for k in ("vehicle_hook", "late_update_hook", "hook_framework_abi"))):
        raise ValueError("Native v8 cannot declare raw game hooks or machine-context claims")


def _canonical(value):
    try:
        result = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                            allow_nan=False).encode("ascii")
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("Compatibility identity must contain finite JSON data") from error
    if len(result) > 256 * 1024:
        raise ValueError("Compatibility identity exceeds 256 KiB")
    return result


def content_digest(manifest):
    """Identity includes the complete manifest and its revalidated payload hashes."""
    return hashlib.sha256(_canonical(manifest)).hexdigest()


def profile_digest(profile):
    """Bind every reviewed field, including physical bindings and layouts."""
    if not isinstance(profile, dict):
        raise ValueError("Invalid reviewed game profile")
    return hashlib.sha256(_canonical({k: v for k, v in profile.items() if k != "digest"})).hexdigest()


def validate_profile(profile):
    if not isinstance(profile, dict) or not _profile_id(profile.get("id")):
        raise ValueError("Invalid reviewed game profile identity")
    hashes = profile.get("hashes")
    if (not isinstance(hashes, dict) or set(hashes) != GAME_FILES
            or any(not _digest(v) for v in hashes.values())):
        raise ValueError("Reviewed game profiles require all three exact game hashes")
    capabilities(profile.get("capabilities"))
    if not _digest(profile.get("digest")) or profile_digest(profile) != profile["digest"]:
        raise ValueError("Reviewed game profile digest does not match its complete content")
    return profile


def _adapter_capabilities(profile, game_adapter):
    if not isinstance(game_adapter, dict) or type(game_adapter.get("abi")) is not int or game_adapter["abi"] != 1:
        raise ValueError("Game adapter ABI 1 is unavailable")
    profiles = game_adapter.get("profiles")
    if not isinstance(profiles, dict) or len(profiles) > 128:
        raise ValueError("Invalid runtime game adapter profile table")
    actual = profiles.get(profile["id"])
    if not isinstance(actual, dict) or actual.get("digest") != profile["digest"]:
        raise ValueError("Runtime game adapter does not support the reviewed profile digest")
    table = capabilities(actual.get("capabilities"))
    if table != profile["capabilities"]:
        raise ValueError("Runtime game capabilities differ from the reviewed profile")
    return table


def require_game(manifest, game_hashes, game_profile=None, game_adapter=None, legacy_profile_ids=None):
    """Runtime selection rechecks exactly the same contract as player inspection."""
    validate_manifest(manifest)
    if not isinstance(game_hashes, dict):
        raise ValueError("Observed game hashes must be a dictionary")
    modern = manifest.get("kind") == "native" and manifest.get("abi") == V8
    if modern:
        if game_profile is None:
            raise ValueError("Unknown game build: a reviewed game adapter profile is required")
        validate_profile(game_profile)
        if game_hashes != game_profile["hashes"]:
            raise ValueError("Unknown game build: observed hashes do not match the reviewed profile")
        offered = _adapter_capabilities(game_profile, game_adapter)
        for name, requirement in manifest["requires_game"].items():
            actual = offered.get(name)
            if actual is None:
                raise ValueError("Game capability " + name + " is unavailable for " + manifest["id"])
            if actual["abi"] != requirement["abi"] or actual["size"] < requirement["min_size"]:
                raise ValueError("Incompatible game capability ABI/size: " + name + " for " + manifest["id"])
            for key, minimum in requirement.get("limits", {}).items():
                if actual.get("limits", {}).get(key, -1) < minimum:
                    raise ValueError("Insufficient game capability limit " + key + ": " + name + " for " + manifest["id"])
    elif legacy_profile_ids is not None:
        if (not isinstance(legacy_profile_ids, dict)
                or any(not isinstance(v, (list, tuple, set, frozenset))
                       or any(not _profile_id(p) for p in v) for v in legacy_profile_ids.values())):
            raise ValueError("Invalid legacy runtime profile support table")
        if not isinstance(game_profile, dict) or game_profile.get("id") not in legacy_profile_ids.get(manifest.get("kind"), ()):
            raise ValueError("Legacy runtime profile is unavailable for " + manifest["id"])
    # Optional v8 pins remain an additional restriction, never a tested-on hint.
    for name, expected in manifest.get("game", {}).get("hashes", {}).items():
        if game_hashes.get(name) != expected:
            raise ValueError(manifest["name"] + " does not support this game build")


def selection_digest(manifests, selected):
    return hashlib.sha256(_canonical({name: content_digest(manifests[name])
                                     for name in sorted(set(selected))})).hexdigest()


def _reason(code, message, **context):
    return {"code": code, "message": message, **context}


def _satisfies(actual, required):
    return (actual is not None and actual["abi"] == required["abi"]
            and actual["size"] >= required["min_size"]
            and all(actual.get("limits", {}).get(k, -1) >= v
                    for k, v in required.get("limits", {}).items()))


def evaluate(manifests, selected, game_hashes, *, game_profile=None, game_adapter=None,
             available_runtimes=None, runtime_api_abi=None, runtime_readiness_abi=None,
             host_capabilities=None, native_package_abis=None, legacy_profile_ids=None,
             runtime_sha256=None, evidence=()):
    """Explain a complete effective base without executing any package.

    The loader owns target discovery, integrity checks and evidence trust. A
    requirements match is admission evidence, not proof of gameplay behavior.
    """
    from . import packages
    if (not isinstance(selected, (list, tuple, set, frozenset))
            or any(not isinstance(n, str) for n in selected) or not isinstance(manifests, dict)):
        return {"status": "incompatible", "allowed": False, "profile": None,
                "mods": {}, "reasons": [_reason("selection-invalid", "Invalid package selection.")],
                "order": [], "selection_digest": None, "verification": []}
    chosen = sorted(set(selected))
    reasons, unknown, mods = [], [], {}
    if not isinstance(game_hashes, dict):
        game_hashes = {}
        reasons.append(_reason("game-identity-invalid", "Observed game hashes must be a dictionary."))
    if available_runtimes is None:
        unknown.append(_reason("runtime-target-unknown", "Available target runtimes were not supplied."))
    valid = set()
    validation = {}

    def package_error(name):
        if name not in validation:
            try:
                packages.validate(manifests.get(name))
                validation[name] = None
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                validation[name] = str(error)
        return validation[name]
    profile = None
    if game_profile is None:
        unknown.append(_reason("game-build-unknown", "This game build has no reviewed adapter profile."))
    else:
        try:
            validate_profile(game_profile)
            if game_hashes != game_profile["hashes"]:
                unknown.append(_reason("game-build-unknown", "The game hashes do not match the reviewed profile."))
            else:
                profile = {"id": game_profile["id"], "digest": game_profile["digest"]}
        except (ValueError, TypeError) as error:
            reasons.append(_reason("game-profile-invalid", str(error)))
    for name in chosen:
        mod = manifests.get(name)
        item = {"status": "requirements-matched", "allowed": True, "reasons": [], "requirements": []}
        mods[name] = item
        if mod is None:
            item["reasons"].append(_reason("package-missing", "Required package is not installed.", package=name))
            continue
        invalid = package_error(name)
        if invalid is not None:
            item["reasons"].append(_reason("package-invalid", invalid, package=name))
            continue
        valid.add(name)
        if mod.get("runtime_api_abi") is not None and runtime_api_abi != mod["runtime_api_abi"]:
            item["reasons"].append(_reason("runtime-api-unavailable", "Required public runtime API ABI is unavailable.", package=name))
        if mod.get("kind") == "native" and mod.get("abi") == V8:
            supported = (isinstance(native_package_abis, (tuple, list, set, frozenset))
                         and V8 in native_package_abis)
            item["requirements"].append({"kind": "native-package-abi", "required": V8, "available": supported})
            if not supported:
                item["reasons"].append(_reason("native-package-abi-unavailable", "The runtime does not advertise native v8 support.", package=name))
        try:
            require_game(mod, game_hashes, game_profile, game_adapter, legacy_profile_ids)
        except (ValueError, TypeError) as error:
            code = ("game-api-unavailable" if mod.get("abi") == V8 else
                    "legacy-runtime-profile-unavailable" if "Legacy runtime profile" in str(error) else "game-pin-mismatch")
            if profile is not None or mod.get("abi") != V8:
                item["reasons"].append(_reason(code, str(error), package=name))
        offered = {}
        if profile is not None:
            try:
                offered = _adapter_capabilities(game_profile, game_adapter)
            except (ValueError, TypeError):
                pass
        for api, required in sorted(mod.get("requires_game", {}).items()):
            actual = offered.get(api)
            item["requirements"].append({"kind": "game-api", "api": api, "optional": False,
                "required_abi": required["abi"], "required_min_size": required["min_size"],
                "required_limits": required.get("limits", {}), "actual": actual, "available": actual is not None,
                "satisfied": _satisfies(actual, required)})
        for required in mod.get("requires_apis", []):
            api = required["api"]; owner = api.split(".", 1)[0]
            provider = manifests.get(owner) if owner in chosen else None
            if not isinstance(provider, dict) or package_error(owner) is not None: provider = None
            actual = provider.get("provides", {}).get(api) if provider else None
            satisfied = (owner not in chosen and required.get("optional", False)
                         or _satisfies(actual, required))
            item["requirements"].append({"kind": "framework-api", "api": api, "provider": owner,
                "provider_version": provider.get("version") if provider else None,
                "optional": required.get("optional", False), "required_abi": required["abi"],
                "required_min_size": required["min_size"], "required_limits": required.get("limits", {}),
                "actual": actual, "available": actual is not None, "satisfied": satisfied})
            if not satisfied:
                item["reasons"].append(_reason("framework-api-incompatible", "Selected framework does not satisfy the API requirement.", package=name, provider=owner, api=api))
        for capability, required in sorted(mod.get("requires_host", {}).items()):
            actual = host_capabilities.get(capability) if isinstance(host_capabilities, dict) else None
            matched = type(actual) is int and actual == required
            item["requirements"].append({"kind": "host-api", "api": capability,
                "required_abi": required, "actual_abi": actual, "satisfied": matched,
                "optional": False, "available": actual is not None})
            if not matched:
                item["reasons"].append(_reason("host-capability-unavailable", "Required host adapter capability is unavailable.", package=name, api=capability))
    # Explain an incompatible provider through every selected dependent, even
    # when the consumer itself uses no vanilla game capability.
    for _ in chosen:
        changed = False
        for name in chosen:
            mod = manifests.get(name, {})
            if name not in valid:
                continue
            dependencies = set(mod.get("requires", []))
            dependencies.update(r["api"].split(".", 1)[0] for r in mod.get("requires_apis", [])
                                if isinstance(r, dict) and isinstance(r.get("api"), str)
                                and r["api"].split(".", 1)[0] in chosen)
            known = {r.get("provider") for r in mods[name]["reasons"] if r["code"] == "dependency-incompatible"}
            for dependency in sorted(dependencies):
                if dependency in mods and mods[dependency]["reasons"] and dependency not in known:
                    mods[name]["reasons"].append(_reason("dependency-incompatible", "Selected provider cannot run on this effective base.", package=name, provider=dependency))
                    changed = True
        if not changed:
            break
    order = []
    try:
        order = packages.resolve(manifests, chosen, game_hashes,
            available_runtimes=available_runtimes, runtime_api_abi=runtime_api_abi,
            runtime_readiness_abi=runtime_readiness_abi, host_capabilities=host_capabilities,
            native_package_abis=native_package_abis, game_profile=game_profile,
            game_adapter=game_adapter, legacy_profile_ids=legacy_profile_ids)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        # The unknown profile is already reported accurately above; do not
        # reclassify that one missing target as an incompatibility.
        if not unknown or any(item["reasons"] for item in mods.values()):
            reasons.append(_reason("selection-incompatible", str(error)))
    incompatible = bool(reasons or any(item["reasons"] for item in mods.values()))
    status = "incompatible" if incompatible else "unknown" if unknown else "requirements-matched"
    allowed = status == "requirements-matched"
    try:
        digest = selection_digest(manifests, chosen)
    except (KeyError, ValueError, TypeError):
        digest = None
    verified = []
    if (allowed and _digest(runtime_sha256) and isinstance(evidence, (list, tuple))
            and len(evidence) <= MAX_EVIDENCE):
        identities = {name: content_digest(manifests[name]) for name in chosen}
        for record in evidence:
            if (isinstance(record, dict) and record.get("success") is True
                    and record.get("selection_digest") == digest
                    and record.get("mod_digests") == identities
                    and record.get("profile_digest") == profile["digest"]
                    and record.get("runtime_sha256") == runtime_sha256
                    and record.get("scope") in ("startup", "world", "co-op")
                    and isinstance(record.get("record"), str) and 0 < len(record["record"]) <= 160):
                verified.append({"scope": record["scope"], "record": record["record"]})
    if verified:
        status = "verified"
    for item in mods.values():
        item["allowed"] = not item["reasons"] and allowed
        item["status"] = "incompatible" if item["reasons"] else status
    return {"status": status, "allowed": allowed, "profile": profile, "mods": mods,
            "reasons": [*reasons, *unknown], "order": order,
            "selection_digest": digest, "verification": verified}
