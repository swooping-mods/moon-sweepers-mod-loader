#!/usr/bin/env python3
"""Execute original immutable v8 modules against production native broker code."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]


def check(api, output):
    api=Path(api).resolve();output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'artifacts'):
        raise ValueError('Diagnostic outputs must belong to this project artifacts/')
    output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(api/'python'))
    from moon_mod_api.compatibility import profile_digest
    from moon_mod_api.runtime_plan import encode
    from game_profiles_native import check as check_profiles
    check_profiles()
    compiler=shutil.which('clang')
    if not compiler:raise ValueError('Use an existing clang compiler; none is downloaded')
    profiles=[]
    for index,key in enumerate(('a','b')):
        profile={'id':'synthetic.profile-'+key,
                 'hashes':{name:str(index*3+i+1)*64 for i,name in enumerate(('GameAssembly.dll','MoonSweepers.exe','UnityPlayer.dll'))},
                 'capabilities':{'unity.clock':{'abi':1,'size':16,'limits':{}},
                                 'unity.time-scale':{'abi':1,'size':16,'limits':{}}},
                 'native':{'domain_rva':16 if key=='a' else 128,'test_only_relocated_state':key}}
        profile['digest']=profile_digest(profile);profiles.append(profile)
    header=output/'profile-identities.h'
    lines=[]
    for key,p in zip(('A','B'),profiles):
        for name,value in [('DIGEST',p['digest']),('GAME',p['hashes']['GameAssembly.dll']),('EXE',p['hashes']['MoonSweepers.exe']),('PLAYER',p['hashes']['UnityPlayer.dll'])]:
            lines.append('#define PROBE_PROFILE_'+key+'_'+name+' '+json.dumps(value))
    header.write_text('\n'.join(lines)+'\n')
    common=[compiler,'-std=c11','-Wall','-Wextra','-Werror','-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(api/'include')]
    commands=[]
    def run(command):
        commands.append([str(p) for p in command]);result=subprocess.run(command,capture_output=True,text=True,timeout=60)
        (output/('compile-'+str(len(commands))+'.log')).write_text(result.stdout+result.stderr)
        if result.returncode:raise ValueError('Diagnostic compilation failed\n'+result.stdout+result.stderr)
    for name in ('framework','consumer'):
        run(common+['-fPIC','-shared',str(ROOT/'tests/fixtures'/('game_clock_'+name+'.c')),'-o',str(output/(name+'.so'))])
    run(common+['-fPIC','-shared',str(ROOT/'tests/fixtures/game_time_scale_consumer.c'),'-o',str(output/'time-scale-consumer.so')])
    variants={'legacy-entry':('game_legacy_entry.c',[]),
              'wrong-runtime':('game_clock_consumer.c',['-DPROBE_RUNTIME_MARKER=2']),
              'missing-runtime':('game_clock_consumer.c',['-DPROBE_OMIT_RUNTIME_MARKER=1'])}
    for name,(source,defines) in variants.items():
        run(common+defines+['-fPIC','-shared',str(ROOT/'tests/fixtures'/source),'-o',str(output/(name+'.so'))])
    binary=output/'native-game-adapter'
    run(common+['-include',str(api/'include/moon_sweepers/game_adapter.h'),'-include',str(header),str(ROOT/'tests/native_game_adapter_checks.c'),'-ldl','-pthread','-o',str(binary)])
    manifests={}
    for name in ('clock-framework','clock-feature'):
        manifests[name]={'id':name,'kind':'native','abi':'MoonLab_ModStart/v8','runtime_api_abi':1,
                         'game_access':'adapter','game_api_abi':1,'requires_game':{},'requires':[],
                         'game':{'id':'moon-sweepers','appid':'5335510','hashes':profiles[0]['hashes']},
                         'provides':{},'requires_apis':[],'claims':[]}
    manifests['clock-framework'].update(requires_game={'unity.clock':{'abi':1,'min_size':16}},
        provides={'clock-framework.elapsed':{'abi':1,'size':16},'clock-framework.hidden':{'abi':1,'size':16}})
    manifests['clock-feature'].update(requires=['clock-framework'],requires_apis=[{'api':'clock-framework.elapsed','abi':1,'min_size':16,'optional':False}])
    order=['clock-framework','clock-feature'];cases=[]
    immutable={name:hashlib.sha256((output/(name+'.so')).read_bytes()).hexdigest() for name in ('framework','consumer','time-scale-consumer')}
    def scenario(name,profile,records=None,mode='accept',adapter=None,mutate=None,consumer='consumer',framework='framework'):
        data=encode(records or manifests,order,game_profile=profile)
        if mutate:data=mutate(data)
        path=output/(name+'.bin');path.write_bytes(data)
        result=subprocess.run([str(binary),str(path),adapter or ('b' if profile['id'].endswith('-b') else 'a'),str(output/(framework+'.so')),str(output/(consumer+'.so')),mode],capture_output=True,text=True,timeout=30)
        (output/(name+'.log')).write_text(result.stdout+result.stderr)
        if result.returncode:raise ValueError('Native game adapter check failed: '+name+'\n'+result.stdout+result.stderr)
        cases.append({'case':name,'success':True,'mode':mode,'profile':profile['id']})
    scenario('profile-a',profiles[0]);scenario('profile-b',profiles[1])
    scenario('all-plan-truncations',profiles[0],mode='truncations')
    scenario('stale-selected-profile',profiles[0],mode='profile-reject',adapter='b')
    stale=copy.deepcopy(profiles[0]);stale['native']['domain_rva']+=8;stale['digest']=profile_digest(stale)
    scenario('stale-profile-digest',stale,mode='profile-reject')
    for name,requirement in [('unsupported',{'unity.unsupported':{'abi':1,'min_size':16}}),
                             ('wrong-abi',{'unity.clock':{'abi':2,'min_size':16}}),
                             ('oversize',{'unity.clock':{'abi':1,'min_size':32}}),
                             ('missing-limit',{'unity.clock':{'abi':1,'min_size':16,'limits':{'max_reads':1}}})]:
        records=copy.deepcopy(manifests);records['clock-framework']['requires_game']=requirement
        scenario(name,profiles[0],records,mode='profile-reject')
    legacy=copy.deepcopy(manifests);legacy['clock-framework']['abi']='MoonLab_ModStart/v6'
    for name in ('game_access','game_api_abi','requires_game'):legacy['clock-framework'].pop(name)
    scenario('legacy-refuses-other-profile',profiles[1],legacy,mode='profile-reject')
    scenario('trailing-bytes',profiles[0],mode='parser-reject',mutate=lambda b:b+b'\0')
    scenario('unsupported-plan-version',profiles[0],mode='parser-reject',mutate=lambda b:b[:5]+b'\3'+b[6:])
    scenario('missing-v8-entry-no-legacy-fallback',profiles[0],mode='entry-missing',consumer='legacy-entry')
    scenario('wrong-runtime-marker',profiles[0],mode='entry-runtime',consumer='wrong-runtime')
    scenario('missing-runtime-marker',profiles[0],mode='entry-runtime',consumer='missing-runtime')
    scale=copy.deepcopy(manifests)
    scale['clock-framework']['requires_game']={'unity.time-scale':{'abi':1,'min_size':16}}
    for profile in profiles:
        key=profile['id'].rsplit('-',1)[-1]
        scenario('time-scale-only-'+key,profile,scale,mode='time-scale-only',framework='time-scale-consumer')
        both=copy.deepcopy(scale);both['clock-framework']['requires_game']['unity.clock']={'abi':1,'min_size':16}
        scenario('time-scale-both-'+key,profile,both,mode='time-scale-both',framework='time-scale-consumer')
    scenario('time-scale-unadvertised-profile',profiles[0],scale,mode='time-scale-profile-reject')
    for name,requirement in [('time-scale-wrong-abi',{'abi':2,'min_size':16}),
                             ('time-scale-oversize',{'abi':1,'min_size':32}),
                             ('time-scale-missing-limit',{'abi':1,'min_size':16,'limits':{'max_reads':1}})]:
        records=copy.deepcopy(scale);records['clock-framework']['requires_game']['unity.time-scale']=requirement
        scenario(name,profiles[0],records,mode='profile-reject')
    assert immutable=={name:hashlib.sha256((output/(name+'.so')).read_bytes()).hexdigest() for name in immutable},'Diagnostic modules changed during proof'
    receipt={'success':True,'cases':cases,'immutable_binaries':immutable,
             'compiler':compiler,'commands':commands,'profiles':profiles,
             'limits':['Synthetic relocated adapters only; neither is a supported game profile','No game/Wine/Steam execution or later Moon Sweepers version qualification']}
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--api',type=Path,default=ROOT/'vendored/api');parser.add_argument('--output',type=Path)
    args=parser.parse_args();out=args.output or ROOT/'artifacts/game-adapter-checks'/uuid.uuid4().hex
    result=check(args.api,out);print(json.dumps({'success':result['success'],'cases':len(result['cases']),'receipt':str(out/'result.json')},indent=2))
