#!/usr/bin/env python3
"""Inspect the produced Windows bundle without executing foreign binaries."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import zipfile
from pe import PE
from build import VERSION
from mod_bundle import payload as bundled_payload

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT/'artifacts'):
        raise ValueError('Bundle outputs must belong to this project artifacts/')
    folder = out / 'moon-sweepers-mod-loader-windows-x64'
    lock = json.loads((ROOT / 'vendored/windows-runtime.lock.json').read_text())
    archive = out / f'moon-sweepers-mod-loader-{VERSION}-windows-x64.zip'
    required = ['Mod Loader.exe', 'python/pythonw.exe', 'python/python.exe',
                'loader/main.py', 'loader/runtime/windows-x64/version.dll',
                'loader/runtime/windows-x64/MoonLab.LoaderCheck.exe',
                'LICENSES/Python/LICENSE.txt', 'LICENSES/README.md',
                'THIRD_PARTY_NOTICES.md', 'vendored/api/python/moon_mod_api/__init__.py']
    required += ['python/' + name for name in lock['wheel_members']]
    bundled = bundled_payload(folder / 'loader/packages')
    required += list(bundled) + ['vendored/mod-bundle.json', 'vendored/mod-bundle/README.md']
    for name in required:
        assert (folder / name).is_file(), name
    from managed_bundle import verify_bundle
    managed_receipt = verify_bundle(folder/'loader')
    with zipfile.ZipFile(archive) as z:
        assert not any(name.startswith('vendored/managed-build-inputs/') for name in z.namelist()), 'Upstream build input leaked into desktop bundle'
        for name in required:
            assert z.read(name) == (folder / name).read_bytes(), name
        assert {name for name in z.namelist() if name.startswith('loader/packages/')} == set(bundled)
        managed_prefix = 'loader/runtime/bepinex/files/'
        assert {name[len(managed_prefix):] for name in z.namelist() if name.startswith(managed_prefix)} == set(managed_receipt['files'])
        for name, expected in managed_receipt['files'].items():
            assert hashlib.sha256(z.read(managed_prefix + name)).hexdigest() == expected, name
        for item in lock['files']:
            if item['role'] in ('source', 'license'):
                data = z.read('LICENSES/' + item['name'])
                assert hashlib.sha256(data).hexdigest() == item['sha256'], item['name']
    launcher = PE(folder / 'Mod Loader.exe')
    assert launcher.machine == 0x8664
    launcher_headers = subprocess.check_output(['objdump', '-p', str(folder / 'Mod Loader.exe')], text=True)
    assert '(Windows GUI)' in launcher_headers
    assert (folder / 'python/qt.conf').read_text() == '[Paths]\nPrefix=PySide6\nPlugins=plugins\n'
    native = sorted(p for p in (folder / 'python').rglob('*') if p.suffix.lower() in ('.dll', '.exe', '.pyd'))
    available = {p.name.lower() for p in native}
    system = set('advapi32 authz bcrypt comdlg32 crypt32 d3d9 d3d11 d3d12 dwmapi dwrite dxgi gdi32 imm32 iphlpapi kernel32 mpr netapi32 ole32 oleaut32 propsys rpcrt4 setupapi shell32 shlwapi uiautomationcore user32 userenv uxtheme version winmm ws2_32 wtsapi32'.split())
    import re
    for p in native:
        assert PE(p).machine == 0x8664, str(p)
        text = subprocess.check_output(['objdump', '-p', str(p)], text=True)
        for dependency in re.findall(r'DLL Name: (.*)', text):
            name = dependency.lower()
            assert name in available or name.removesuffix('.dll') in system or name.startswith(('api-ms-', 'ext-ms-')), (p, dependency)
    assert (folder / 'python/python313._pth').read_text().splitlines() == ['python313.zip', '.', '../loader', '../vendored/api/python']
    assert not list((folder / 'python').rglob('Qt6Qml.dll'))
    licenses = list((folder / 'LICENSES/upstream').rglob('LGPL-3.0-only.txt'))
    assert len(licenses) == 3
    receipt = {'success': True, 'required_files': len(required), 'amd64_runtime_images': len(native),
               'bundled_mods_checked': len(bundled),
               'library_source_hashes_verified': True, 'runtime_import_closure': 'Windows system libraries plus bundled DLLs',
               'managed_coreclr_version': managed_receipt['coreclr_version'],
               'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
               'limits': ['Static package verification; Windows GUI and launcher execution not tested']}
    (out / 'windows-checks.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
