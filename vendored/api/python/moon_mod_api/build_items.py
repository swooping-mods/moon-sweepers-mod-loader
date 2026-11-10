"""Stable saved building identities shared by tooling and package resolvers."""
import argparse
import json
from pathlib import Path
import re

NATIVE_LAST_KIND = 192
FIRST_KIND = 193
LAST_KIND = 384
CAPACITY = LAST_KIND - FIRST_KIND + 1
REGISTRY_SCHEMA = "moon-build-registry/v1"


def validate_items(owner, items):
    if not isinstance(owner, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", owner):
        raise ValueError("Invalid building owner mod ID")
    if not isinstance(items, list) or not items or len(items) > CAPACITY:
        raise ValueError("build_items must contain 1–192 building definitions")
    ids, keys = set(), set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"kind", "key"}:
            raise ValueError("A build item requires exactly kind and key")
        kind, key = item["kind"], item["key"]
        if type(kind) is not int or not FIRST_KIND <= kind <= LAST_KIND:
            raise ValueError("Choose a stable build kind from 193 through 384")
        if (not isinstance(key, str) or len(key) >= 96 or
                not re.fullmatch(r"[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+", key) or
                not key.startswith(owner + ".")):
            raise ValueError("Building key must be a stable namespaced key under " + owner + ".")
        if kind in ids or key in keys:
            raise ValueError("Duplicate building kind or key")
        ids.add(kind)
        keys.add(key)
    return items


def validate_manifest(manifest):
    if "build_menu_max_kind" in manifest:
        limit = manifest["build_menu_max_kind"]
        if (manifest.get("id") != "build-menu-framework" or manifest.get("kind") != "native" or
                type(limit) is not int or not FIRST_KIND <= limit <= LAST_KIND):
            raise ValueError("Only Build Menu Framework may declare its supported kind range")
    if "build_api" in manifest:
        api = manifest["build_api"]
        if (not isinstance(api, str) or api.count(".") < 1 or
                not any(isinstance(spec, dict) and spec.get("api") == api and not spec.get("optional", False)
                        for spec in manifest.get("requires_apis", []))):
            raise ValueError("build_api needs an explicit required API dependency")
        if "build_items" not in manifest:
            raise ValueError("build_api requires building definitions")
    if "build_items" not in manifest:
        return
    validate_items(manifest["id"], manifest["build_items"])
    if "build_api" in manifest:
        provider = manifest["build_api"].split(".", 1)[0]
        if provider not in manifest.get("requires", []):
            raise ValueError("Build items need the selected API provider dependency")
    elif manifest.get("kind") != "native" or "build-menu-framework" not in manifest.get("requires", []):
        raise ValueError("Build items require the native build-menu-framework dependency")


def validate_selection(manifests, selected):
    selected = set(selected)
    ids, keys = {}, {}
    for name in sorted(set(selected)):
        manifest = manifests.get(name)
        if manifest is None:
            continue  # The package resolver owns missing dependency diagnostics.
        validate_manifest(manifest)
        for item in manifest.get("build_items", []):
            kind, key = item["kind"], item["key"]
            if kind in ids:
                raise ValueError("Building kind " + str(kind) + " is claimed by " + ids[kind] + " and " + name)
            if key in keys:
                raise ValueError("Building key " + key + " is claimed more than once")
            ids[kind], keys[key] = name, name
        if manifest.get("build_items") and "build_api" in manifest:
            api = manifest["build_api"]
            provider = api.split(".", 1)[0]
            framework = manifests.get(provider, {}) if provider in selected else {}
            spec = framework.get("provides", {}).get(api, {})
            available = spec.get("limits", {}).get("build_menu_max_kind")
            required = max(item["kind"] for item in manifest["build_items"])
            if type(available) is not int or not FIRST_KIND <= available <= LAST_KIND or required > available:
                raise ValueError("Building API " + api + " does not support kinds through " + str(required))
    framework = manifests.get("build-menu-framework") if "build-menu-framework" in selected else None
    legacy_ids = [item["kind"] for name in selected for item in manifests.get(name, {}).get("build_items", [])
                  if "build_api" not in manifests.get(name, {})]
    if legacy_ids and framework is not None:
        # Existing released framework manifests predate capability metadata and
        # support only the original extension through kind 224.
        available = framework.get("build_menu_max_kind", 224)
        if max(legacy_ids) > available:
            raise ValueError("Build Menu Framework supports kinds through " + str(available) +
                             "; selected providers require " + str(max(legacy_ids)))


def validate_registry(registry):
    if (not isinstance(registry, dict) or registry.get("schema") != REGISTRY_SCHEMA or
            registry.get("native_last_kind") != NATIVE_LAST_KIND or
            registry.get("first_kind") != FIRST_KIND or registry.get("last_kind") != LAST_KIND):
        raise ValueError("Unsupported building registry or range")
    entries = registry.get("entries")
    if not isinstance(entries, list) or len(entries) > CAPACITY:
        raise ValueError("Invalid building registry entries")
    ids, keys = set(), set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"mod", "kind", "key", "status"}:
            raise ValueError("Registry entry requires mod, kind, key and status")
        owner = entry["mod"]
        if not isinstance(owner, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", owner):
            raise ValueError("Invalid registry mod ID")
        validate_items(owner, [{"kind": entry["kind"], "key": entry["key"]}])
        if entry["status"] not in ("reserved", "active", "retired"):
            raise ValueError("Invalid building reservation status")
        if entry["kind"] in ids or entry["key"] in keys:
            raise ValueError("Duplicate building reservation; retired IDs stay occupied")
        ids.add(entry["kind"])
        keys.add(entry["key"])
    return registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    args = parser.parse_args()
    registry = validate_registry(json.loads(args.registry.read_text()))
    print(json.dumps({"first_kind": FIRST_KIND, "last_kind": LAST_KIND,
                      "reserved": len(registry["entries"]),
                      "unreserved": CAPACITY - len(registry["entries"])}, indent=2))


if __name__ == "__main__":
    main()
