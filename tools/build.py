#!/usr/bin/env python3
"""Build the native loader and curated portable source bundle, entirely offline."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "loader"))
from moonloader import __version__ as VERSION
from moonloader.discovery import PIN
from pe import PE


def find_tools():
    tools = {}
    for tool in ("clang", "lld-link", "llvm-dlltool"):
        installed = shutil.which(tool) or next((path for major in range(30, 13, -1)
            if (path := shutil.which(tool + "-" + str(major)))), None)
        if not installed:
            raise ValueError("Missing installed tool: " + tool + "; no download attempted")
        tools[tool] = installed
    return tools


def source_payload():
    from moonloader.downloads import profiles
    profiles()
    files = {}
    for folder in ('loader', 'vendored', 'sdk', 'runtime', 'tools', 'tests', 'specs', '.github'):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_symlink():
                raise ValueError('Source alias refused: '+str(path))
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                if path.is_relative_to(ROOT/'loader/runtime/bepinex'):
                    continue
                if path.is_relative_to(ROOT/'vendored/mod-bundle/packages') or path.is_relative_to(ROOT/'loader/packages'):
                    continue
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    from mod_bundle import payload
    files.update(payload())
    for name in ('README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', '.gitignore', 'run.sh', 'Start-Mod-Loader.cmd'):
        files[name] = (ROOT/name).read_bytes()
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts')
    parser.add_argument('--with-bepinex', type=Path, metavar='ATTACHMENT',
                        help='Explicit checked runtime attachment containing receipt.json and files/; private mode only')
    parser.add_argument('--managed-inputs', type=Path, default=ROOT/'local/managed-inputs',
                        help='Reviewed hash-locked BepInEx/CoreCLR inputs; required for normal distributions')
    parser.add_argument('--dotnet', type=Path, help='Existing .NET SDK executable for the original adapter build')
    args = parser.parse_args(argv)
    from check_native_sdk import check as check_native_sdk
    check_native_sdk()
    from check_managed_sources import check as check_managed_sources
    check_managed_sources()
    sources = source_payload()
    managed_payload = {}; managed_receipt = None
    if args.with_bepinex:
        from moonloader.managed import artifact_files
        host_receipt, host_files = artifact_files(args.with_bepinex)
        # Keep portable provenance and original notices/source archives without
        # disclosing the author's intake or build directories in a distribution.
        public_receipt = {key: value for key, value in host_receipt.items() if key in
                          ('schema', 'version', 'files', 'inputs', 'adapter_sha256', 'builder_sha256', 'limits', 'coreclr_version')}
        managed_payload = {'loader/runtime/bepinex/files/' + name: data for name, data in host_files.items()}
        managed_payload['loader/runtime/bepinex/receipt.json'] = (json.dumps(public_receipt, indent=2) + '\n').encode()
    tools = find_tools()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT/'artifacts'):
        raise ValueError('Build outputs belong under this project artifacts/')
    work = out / "build"
    work.mkdir(parents=True, exist_ok=True)
    if not args.with_bepinex:
        from managed_bundle import payload
        managed_payload, managed_receipt = payload(args.managed_inputs, args.dotnet, work/'managed')
    runtime = ROOT / "runtime/loader"
    for name in ("kernel32", "ole32", "shell32", "bcrypt"):
        subprocess.run([tools["llvm-dlltool"], "-m", "i386:x86-64", "-d", str(runtime / (name + ".def")), "-l", str(work / (name + ".lib"))], check=True)
    for source in ("proxy", "check"):
        subprocess.run([tools["clang"], "--target=x86_64-pc-windows-msvc", "-O2", "-Wall", "-Wextra", "-Werror", "-ffreestanding", "-fno-builtin", "-fno-stack-protector", "-funwind-tables", "-c", str(runtime / (source + ".c")), "-o", str(work / (source + ".obj"))], check=True)
    subprocess.run([tools["lld-link"], "/dll", "/entry:DllMain", "/nodefaultlib", "/machine:x64", "/timestamp:0", "/def:" + str(ROOT / "runtime/native/version.def"), "/out:" + str(work / "version.dll"), str(work / "proxy.obj"), str(work / "kernel32.lib"), str(work / "ole32.lib"), str(work / "bcrypt.lib")], check=True)
    subprocess.run([tools["lld-link"], "/entry:mainCRTStartup", "/subsystem:console", "/nodefaultlib", "/machine:x64", "/timestamp:0", "/out:" + str(work / "MoonLab.LoaderCheck.exe"), str(work / "check.obj"), str(work / "kernel32.lib"), str(work / "ole32.lib"), str(work / "shell32.lib")], check=True)
    image = PE(work / "version.dll")
    expected = set((ROOT / "runtime/native/version.def").read_text().splitlines()[2:]) | {
        "MoonLab_LoaderAbi", "MoonLab_RegisterUpdate_v1", "MoonLab_RegisterVehicle_v1",
        "MoonLab_RegisterLateUpdate_v1", "MoonLab_CameraOverrideActive_v1", "MoonLab_GetHookApi_v1",
        "MoonLab_GetRuntimeApi_v1", "MoonLab_RuntimeState_v1", "MoonLab_GetInputApi_v1", "MoonLab_GetCameraApi_v1", "MoonLab_GetInteractionApi_v1",
        "MoonLab_InstalledManagedState_v1"}
    if image.machine != 0x8664 or not expected.issubset({e["name"] for e in image.exports()}):
        raise ValueError("Loader PE/export surface is incomplete")
    diagnostic = PE(work / "MoonLab.LoaderCheck.exe")
    if diagnostic.machine != 0x8664:
        raise ValueError("Diagnostic must be AMD64")
    receipt = {"schema": "moon-loader-runtime/v1", "sha256": hashlib.sha256((work / "version.dll").read_bytes()).hexdigest(),
               "game_pins": PIN, "abi": "MoonLab_ModStart/v7", "hook_framework_abi": 1,
               "runtime_api_abi": 1, "input_api_abi": 1, "camera_api_abi": 1,
               "runtime_readiness_abi": 1, "host_capabilities": {"interaction": 1},
               "runtime_plan_schema": "moon-runtime-plan/v1",
               "late_update_abi": 1, "shared_update_abi": 1, "vehicle_dispatch_abi": 1,
               "managed_profile_guard_abi": 1,
               "max_native_mods": 64, "public_bootstrap_abi": 1, "installed_managed_abi": 1,
               "runtime_replay": "Installed-game replay requires separate qualification"}
    if sources != source_payload():
        raise ValueError('Loader source changed during compilation; candidate not sealed')
    files = dict(sources)
    files.update(managed_payload)
    files["loader/runtime/windows-x64/version.dll"] = (work / "version.dll").read_bytes()
    files["loader/runtime/windows-x64/MoonLab.LoaderCheck.exe"] = (work / "MoonLab.LoaderCheck.exe").read_bytes()
    files["loader/runtime/receipt.json"] = (json.dumps(receipt, indent=2) + "\n").encode()
    suffix = '-managed-private' if args.with_bepinex else ''
    archive = out / f"moon-sweepers-mod-loader-{VERSION}{suffix}-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            target.writestr(info, data)
    checksums = 'SHA256SUMS-managed-private' if args.with_bepinex else 'SHA256SUMS'
    (out / checksums).write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")
    (out / ("build" + suffix + "-receipt.json")).write_text(json.dumps({"version": VERSION, "runtime": receipt, "pe_exports_valid": True,
        "source_files": {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()},
        "managed_attachment": bool(managed_payload),
        "managed_coreclr_version": managed_receipt.get('coreclr_version') if managed_receipt else public_receipt.get('coreclr_version'),
        "archive": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "limits": ["Host Python/PySide6 required", "No game, Wine or native Windows execution"]}, indent=2) + "\n")
    print(archive)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
