"""Deterministic native startup contracts; no executable payload is inspected."""
import struct

from .interfaces import selection as interface_selection
from .runtimes import NATIVE_ABIS

MAGIC = b"MSAPI\x01\0\0"
MAX_BYTES = 2 * 1024 * 1024
PATH = "MoonLab/runtime-plan.bin"


def encode(manifests, order):
    """Encode an already selected dependency order for the native bootstrap.

    Absent optional providers are omitted; present providers become ordinary
    startup requirements. This is deployed with the same ownership/hash journal
    as the selected DLLs, never written by individual provider packages.
    """
    if len(order) != len(set(order)) or len(order) > 64:
        raise ValueError("Invalid native runtime plan selection")
    edges = interface_selection(manifests, set(order))
    positions = {name: i for i, name in enumerate(order)}
    for name in order:
        for dependency in [*manifests[name].get("requires", []), *edges.get(name, [])]:
            if dependency not in positions or positions[dependency] >= positions[name]:
                raise ValueError("Runtime plan requires dependency-first order")
    native = [manifests[name] for name in order if manifests[name]["kind"] == "native"]
    parts = [MAGIC, struct.pack("<I", len(native))]

    def number(value):
        parts.append(struct.pack("<I", value))

    def string(value):
        data = value.encode("ascii")
        parts.extend((struct.pack("<H", len(data)), data))

    def contract(api, spec, size_key):
        string(api)
        number(spec["abi"])
        number(spec[size_key])
        capacities = spec.get("limits", {})
        number(len(capacities))
        for name, value in sorted(capacities.items()):
            string(name)
            number(value)

    for mod in native:
        abi = mod.get("abi")
        if abi not in NATIVE_ABIS:
            raise ValueError("Invalid native runtime plan ABI")
        string(mod["id"])
        number(NATIVE_ABIS.index(abi) + 1)
        provides = mod.get("provides", {})
        number(len(provides))
        for api, spec in sorted(provides.items()):
            contract(api, spec, "size")
        requirements = [spec for spec in mod.get("requires_apis", [])
                        if spec["api"].split(".", 1)[0] in positions]
        number(len(requirements))
        for spec in sorted(requirements, key=lambda value: value["api"]):
            contract(spec["api"], spec, "min_size")
    data = b"".join(parts)
    if len(data) > MAX_BYTES:
        raise ValueError("Native runtime plan exceeds 2 MiB")
    return data
