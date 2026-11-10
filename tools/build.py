#!/usr/bin/env python3
"""Build the native loader and a mod-free portable source bundle, entirely offline."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "loader"))
from moonloader.discovery import PIN
from pe import PE


def main():
    tools = {}
    for tool in ("clang", "lld-link", "llvm-dlltool"):
        installed = shutil.which(tool) or next((path for major in range(30, 13, -1)
            if (path := shutil.which(tool + "-" + str(major)))), None)
        if not installed:
            raise ValueError("Missing installed tool: " + tool + "; no download attempted")
        tools[tool] = installed
    out = ROOT / "artifacts"
    work = out / "build"
    work.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / "runtime/loader"
    for name in ("kernel32", "ole32", "shell32"):
        subprocess.run([tools["llvm-dlltool"], "-m", "i386:x86-64", "-d", str(runtime / (name + ".def")), "-l", str(work / (name + ".lib"))], check=True)
    for source in ("proxy", "check"):
        subprocess.run([tools["clang"], "--target=x86_64-pc-windows-msvc", "-O2", "-Wall", "-Wextra", "-Werror", "-ffreestanding", "-fno-builtin", "-fno-stack-protector", "-funwind-tables", "-c", str(runtime / (source + ".c")), "-o", str(work / (source + ".obj"))], check=True)
    subprocess.run([tools["lld-link"], "/dll", "/entry:DllMain", "/nodefaultlib", "/machine:x64", "/timestamp:0", "/def:" + str(ROOT / "runtime/native/version.def"), "/out:" + str(work / "version.dll"), str(work / "proxy.obj"), str(work / "kernel32.lib"), str(work / "ole32.lib")], check=True)
    subprocess.run([tools["lld-link"], "/entry:mainCRTStartup", "/subsystem:console", "/nodefaultlib", "/machine:x64", "/timestamp:0", "/out:" + str(work / "MoonLab.LoaderCheck.exe"), str(work / "check.obj"), str(work / "kernel32.lib"), str(work / "ole32.lib"), str(work / "shell32.lib")], check=True)
    image = PE(work / "version.dll")
    expected = set((ROOT / "runtime/native/version.def").read_text().splitlines()[2:]) | {
        "MoonLab_LoaderAbi", "MoonLab_RegisterUpdate_v1", "MoonLab_RegisterVehicle_v1",
        "MoonLab_RegisterLateUpdate_v1", "MoonLab_CameraOverrideActive_v1", "MoonLab_GetHookApi_v1"}
    if image.machine != 0x8664 or not expected.issubset({e["name"] for e in image.exports()}):
        raise ValueError("Loader PE/export surface is incomplete")
    diagnostic = PE(work / "MoonLab.LoaderCheck.exe")
    if diagnostic.machine != 0x8664:
        raise ValueError("Diagnostic must be AMD64")
    receipt = {"schema": "moon-loader-runtime/v1", "sha256": hashlib.sha256((work / "version.dll").read_bytes()).hexdigest(),
               "game_pins": PIN, "abi": "MoonLab_ModStart/v5", "hook_framework_abi": 1,
               "late_update_abi": 1, "shared_update_abi": 1, "vehicle_dispatch_abi": 1,
               "max_native_mods": 64, "runtime_replay": "Not rerun for repository extraction"}
    files = {}
    for folder in ("loader", "vendored"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ("README.md", "run.sh", "Start-Mod-Loader.cmd"):
        files[name] = (ROOT / name).read_bytes()
    files["loader/runtime/windows-x64/version.dll"] = (work / "version.dll").read_bytes()
    files["loader/runtime/windows-x64/MoonLab.LoaderCheck.exe"] = (work / "MoonLab.LoaderCheck.exe").read_bytes()
    files["loader/runtime/receipt.json"] = (json.dumps(receipt, indent=2) + "\n").encode()
    archive = out / "moon-sweepers-mod-loader-0.1.0-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            target.writestr(info, data)
    (out / "SHA256SUMS").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")
    (out / "build-receipt.json").write_text(json.dumps({"runtime": receipt, "pe_exports_valid": True,
        "archive": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "limits": ["Host Python/PySide6 required", "No mod binaries bundled", "No game, Wine or native Windows execution"]}, indent=2) + "\n")
    print(archive)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
