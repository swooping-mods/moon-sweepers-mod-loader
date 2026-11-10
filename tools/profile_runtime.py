#!/usr/bin/env python3
"""Opt-in CPU profile of the real registry/dispatch and portable interaction core.

No game, Wine, renderer, native exception trap or engine query is executed.
Sanitized/counting verification is separate from clean timing binaries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tools/fixtures"
SCALES = (4, 64, 256)
MODES = ("cached_typed_call", "lookup_and_typed_call", "typed_update_dispatch", "interaction_epoch")


def compile_fixture(directory, compiler, *, verify):
    binary = Path(directory) / (compiler + ("-verify" if verify else "-clean"))
    command = [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-fno-lto",
               "-O1" if verify else "-O2", "-I", str(ROOT / "vendored/api/include")]
    if verify:
        command += ["-DPROFILE_VERIFY", "-fsanitize=address,undefined", "-fno-sanitize-recover=all"]
    command += [str(FIXTURES / "runtime_profile.c"), str(FIXTURES / "runtime_profile_host.c"),
                "-o", str(binary)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Profile compilation failed:\n" + result.stdout + result.stderr)
    return binary, command


def run_fixture(binary, services, iterations, trials, *, wrong_cache=False, cpu=None):
    command = [str(binary), str(services), str(iterations), str(trials)]
    if wrong_cache:
        command.append("wrong-cache")
    setup = (lambda: os.sched_setaffinity(0, {cpu})) if cpu is not None else None
    return subprocess.run(command, capture_output=True, text=True, preexec_fn=setup)


def checked_result(result):
    if result.returncode:
        raise ValueError("Profile parity/execution failed:\n" + result.stdout + result.stderr)
    value = json.loads(result.stdout)
    if value.get("parity") is not True:
        raise ValueError("Profile did not prove output parity")
    return value


def percentile(values, fraction):
    values = sorted(values)
    at = (len(values) - 1) * fraction
    left = int(at)
    return values[left] + (values[min(left + 1, len(values) - 1)] - values[left]) * (at - left)


def fingerprints():
    files = [Path(__file__), *FIXTURES.glob("runtime_profile*"), ROOT / "vendored/api/snapshot.json"]
    files += list((ROOT / "runtime").rglob("*.h"))
    files += list((ROOT / "vendored/api/include").rglob("*.h"))
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 1000000 or not 1 <= args.trials <= 51:
        parser.error("iterations must be 1–1000000 and trials 1–51")
    if any(shutil.which(c) is None for c in ("clang", "gcc")):
        parser.error("installed clang and gcc are required; nothing is downloaded")
    output = args.output or ROOT / "artifacts/runtime-profile" / str(time.time_ns()) / "receipt.json"
    output = output.absolute()
    if output != output.resolve() or not output.is_relative_to(ROOT / "artifacts") or output.exists():
        parser.error("choose a fresh output beneath this project's artifacts/")
    if any(p.is_symlink() for p in (output, *output.parents)):
        parser.error("output aliases are refused")
    cpu = min(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    versions = {c: subprocess.run([c, "--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
                for c in ("clang", "gcc")}
    initial_load = os.getloadavg() if hasattr(os, "getloadavg") else None
    before = fingerprints()
    verification, builds, measured = [], [], []
    with tempfile.TemporaryDirectory(prefix="moon-runtime-profile-") as directory:
        for compiler in ("clang", "gcc"):
            binary, command = compile_fixture(directory, compiler, verify=True)
            builds.append({"compiler": compiler, "instrumented": True, "command": command})
            for services in SCALES:
                value = checked_result(run_fixture(binary, services, 128, 1, cpu=cpu))
                sample = next(s for s in value["samples"] if s["mode"] == 3)
                verification.append({"compiler": compiler, "services": services, "parity_and_counts": True,
                                     "physical_polls_per_epoch": sample["verified_polls"] / sample["ops"],
                                     "queries_per_epoch": sample["verified_queries"] / sample["ops"]})
            bad = run_fixture(binary, 4, 128, 1, wrong_cache=True, cpu=cpu)
            if bad.returncode != 3 or "wrong cached owner" not in bad.stderr:
                raise ValueError("Wrong-owner cache negative control did not reject")
            verification.append({"compiler": compiler, "wrong_cached_owner_rejected": True})
            if args.verify_only:
                continue
            binary, command = compile_fixture(directory, compiler, verify=False)
            builds.append({"compiler": compiler, "instrumented": False, "command": command})
            for services in SCALES:
                value = checked_result(run_fixture(binary, services, args.iterations, args.trials, cpu=cpu))
                value["compiler"] = compiler
                value["summary"] = {}
                for mode, name in enumerate(MODES):
                    samples = [s for s in value["samples"] if s["mode"] == mode]
                    value["summary"][name] = {
                        clock: {"p50_ns": percentile([s[clock] / s["ops"] for s in samples], .5),
                                "p95_ns": percentile([s[clock] / s["ops"] for s in samples], .95),
                                "p99_ns": percentile([s[clock] / s["ops"] for s in samples], .99)}
                        for clock in ("cpu_ns", "wall_ns")}
                measured.append(value)
    if fingerprints() != before:
        raise ValueError("Profile inputs changed; results are not a coherent source checkpoint")
    models = [line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
              if line.startswith("model name")] if Path("/proc/cpuinfo").exists() else []
    receipt = {"schema": "moon-runtime-core-profile/v1", "success": True,
               "scope": "Linux host C core attribution; not Win64/game or display performance",
               "hardware": {"cpu": models[0] if models else platform.processor(), "logical_cpu": cpu,
                            "os": platform.system(), "kernel": platform.release()},
               "compilers": versions,
               "load_average": {"before": initial_load,
                                "after": os.getloadavg() if hasattr(os, "getloadavg") else None},
               "inputs": before, "builds": builds, "verification": verification, "measurements": measured,
               "sampling": {"discarded_warmup_trials": 1, "trials": args.trials,
                            "cpu_clock": "CLOCK_THREAD_CPUTIME_ID", "wall_clock": "CLOCK_MONOTONIC",
                            "alternating_lookup_cached_order": True, "iterations": args.iterations,
                            "percentiles": "linear interpolation of per-batch per-operation values"},
               "limits": ["No native exception trapping or real OS thread query cost",
                          "No Unity calls, physics, UI, managed runtime, rendering, saves or co-op",
                          "Cheap deterministic domain/query fixture; actual domain work has separate cost",
                          "Setup is core publication/registration only, not DLL/game startup",
                          "Sanitizer/counting builds are verification only; timings come from clean builds",
                          "Shared-host frequency/load can affect timings; CPU and wall clocks are separate"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(output)
    for value in measured:
        medians = {k: round(v["cpu_ns"]["p50_ns"], 2) for k, v in value["summary"].items()}
        print(value["compiler"], value["services"], medians)


if __name__ == "__main__":
    main()
