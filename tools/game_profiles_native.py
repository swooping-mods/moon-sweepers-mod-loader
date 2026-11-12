#!/usr/bin/env python3
"""Check the reviewed profile catalog and generate its compiled native identity."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CATALOG = 'loader/moonloader/game_profiles.json'
HEADER = 'runtime/loader/game_profiles.generated.h'
CURRENT = 'moon-sweepers.steam.1.0.5.il2cpp108.win-x64'
# Legacy binaries embed addresses and field layouts, so this ID must never be
# repurposed for new code bytes. New builds require a distinct reviewed profile.
LEGACY_HASHES = {
    'GameAssembly.dll': '14f711a6a3b1b7cd803a03f85cc6c6201c5b546ab9b90329533f5cb8ae2e7f13',
    'MoonSweepers.exe': '0e780f8e8d4bf26ed6bdd8a4068ac42a18846a66a80da7ba5c78f1917a093901',
    'UnityPlayer.dll': 'bfafc49b185eb8427ad75e3648bcba3bf5b07455567ca05ae2b2e23bc1646c0c',
}
FILES = ('GameAssembly.dll', 'MoonSweepers.exe', 'UnityPlayer.dll')
NATIVE_FIELDS = ('domain_rva', 'domain_ready_offset', 'image_min_rva', 'image_max_rva',
                 'update_token', 'late_update_token', 'late_update_rva',
                 'vehicle_fixed_token', 'vehicle_fixed_rva')
# Source candidates do not advertise support until added to a reviewed row.
IMPLEMENTED_CAPABILITIES = {'unity.clock': {'abi': 1, 'size': 16, 'limits': {}},
                          'unity.time-scale': {'abi': 1, 'size': 16, 'limits': {}}}
CAPABILITY_BITS = {'unity.clock': 1, 'unity.time-scale': 2}


def digest(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest()


def unique_object(pairs):
    result = {}
    for name,value in pairs:
        if name in result: raise ValueError('Duplicate profile catalog key: '+name)
        result[name] = value
    return result


def profiles(root=ROOT):
    path = Path(root)/CATALOG
    if path.is_symlink() or path.stat().st_size>256*1024: raise ValueError('Profile catalog alias/size refused')
    document = json.loads(path.read_text(),object_pairs_hook=unique_object)
    if set(document) != {'schema', 'profiles'} or document['schema'] != 'moon-game-profiles/v1':
        raise ValueError('Unsupported game profile catalog')
    rows = document['profiles']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 16:
        raise ValueError('Invalid compiled profile count')
    seen = set(); identities = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'id','version','backend','metadata_version','architecture','hashes','adapter','capabilities','native'}:
            raise ValueError('Incomplete native profile contract')
        name = row['id']
        if not isinstance(name,str) or not re.fullmatch('[a-z][a-z0-9._-]{0,63}',name) or name in seen:
            raise ValueError('Invalid/duplicate native profile identity')
        seen.add(name)
        if type(row['metadata_version']) is not int or (row['backend'],row['metadata_version'],row['architecture']) != ('il2cpp',108,'win-x64'):
            raise ValueError('Unsupported native backend/layout family')
        if row['adapter'] != {'id':'moon-sweepers.native.il2cpp108/v1','abi':1,'layout':'steam105-unity6000.6/v1'} or type(row['adapter']['abi']) is not int:
            raise ValueError('Unsupported native adapter/layout family')
        caps = row['capabilities']
        if (not isinstance(caps, dict) or 'unity.clock' not in caps
                or any(name not in IMPLEMENTED_CAPABILITIES or cap != IMPLEMENTED_CAPABILITIES[name]
                       or type(cap['abi']) is not int or type(cap['size']) is not int
                       for name, cap in caps.items())):
            raise ValueError('Profile capability differs from implemented native tables')
        if not isinstance(row['version'],str) or len(row['version'])>32 or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}',row['version']):
            raise ValueError('Invalid game version label')
        hashes = row['hashes']
        if not isinstance(hashes,dict) or set(hashes)!=set(FILES) or any(not isinstance(hashes[n],str) or not re.fullmatch('[a-f0-9]{64}',hashes[n]) for n in FILES):
            raise ValueError('Invalid complete game identity')
        if name == CURRENT and (row['version'] != '1.0.5' or hashes != LEGACY_HASHES):
            raise ValueError('Legacy profile identity is frozen; use a distinct profile for another build')
        identity = tuple(hashes[n] for n in FILES)
        if identity in identities: raise ValueError('Ambiguous native game identity')
        identities.add(identity)
        native = row['native']
        if not isinstance(native,dict) or set(native)!=set(NATIVE_FIELDS) or any(type(native[n]) is not int or not 0<native[n]<2**32 for n in NATIVE_FIELDS):
            raise ValueError('Invalid native profile bounds')
        if not native['image_min_rva']<native['late_update_rva']<native['image_max_rva'] or not native['image_min_rva']<native['vehicle_fixed_rva']<native['image_max_rva'] or native['domain_rva']%8 or native['domain_ready_offset']%8:
            raise ValueError('Invalid native address/layout bounds')
        if native['domain_ready_offset']!=24:
            raise ValueError('Unsupported domain layout for this adapter family')
    if CURRENT not in seen: raise ValueError('Legacy current-build profile must remain explicit')
    return rows


def generate(root=ROOT):
    rows = profiles(root)
    out = ['/* Generated by tools/game_profiles_native.py; edit the reviewed catalog. */',
           '#ifndef MOON_GAME_PROFILES_GENERATED_H', '#define MOON_GAME_PROFILES_GENERATED_H',
           '#define MOON_GAME_LEGACY_PROFILE_ID "'+CURRENT+'"',
           'static const MoonNativeGameProfile moon_native_game_profiles[] = {']
    for row in rows:
        values = [json.dumps(row['id']), json.dumps(digest(row)),
                  '{'+','.join(json.dumps(row['hashes'][n]) for n in FILES)+'}',
                  *[str(row['native'][n])+'u' for n in NATIVE_FIELDS],
                  str(sum(CAPABILITY_BITS[name] for name in row['capabilities']))+'u']
        out.append('    {'+','.join(values)+'},')
    out += ['};', '#define MOON_NATIVE_GAME_PROFILE_COUNT '+str(len(rows))+'u', '#endif', '']
    return '\n'.join(out)


def check(root=ROOT):
    root = Path(root); header = root/HEADER
    if header.is_symlink() or not header.is_file() or header.read_text()!=generate(root):
        raise ValueError('Compiled native profiles differ from the reviewed catalog; run explicit --write')
    return {'abi':1,'profiles':{p['id']:{'digest':digest(p),'capabilities':p['capabilities']} for p in profiles(root)}}


def legacy_profile_ids(root=ROOT):
    profiles(root)
    return [CURRENT]


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    if args.write:(ROOT/HEADER).write_text(generate())
    print(json.dumps(check(),indent=2))
