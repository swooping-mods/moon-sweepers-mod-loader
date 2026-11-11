#!/usr/bin/env python3
"""Execute the actual installed adapter gate with an explicitly installed SDK."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dotnet', type=Path, required=True)
    args = parser.parse_args()
    dotnet = args.dotnet.resolve()
    compiler = max((dotnet.parent/'sdk').glob('*/Roslyn/bincore/csc.dll'), key=lambda p: tuple(map(int,p.parents[2].name.split('-')[0].split('.'))))
    runtime = max((dotnet.parent/'shared/Microsoft.NETCore.App').iterdir(), key=lambda p: tuple(map(int,p.name.split('-')[0].split('.'))))
    output = ROOT/'artifacts/installed-managed-gate'; output.mkdir(parents=True, exist_ok=True)
    source = (ROOT/'runtime/bepinex/Adapter.cs').read_text()
    actual_gate = source[source.index('internal static class AdapterFailure'):]
    checks = '''
internal static class Checks {
 static void Main(string[] args) {
  if(args.Length!=0) {
   string output=AdapterFailure.Fallback(args[1]);
   try {
    if(args[0]=="--blocked-output")Directory.CreateDirectory(output);
    InstalledSelection.RequireReady(()=>2u,()=>throw new Exception("must not wait"),2);
   }
   catch(Exception error) { AdapterFailure.Stop(error,output,_=>throw new IOException("controlled logger failure")); }
   throw new Exception("fatal gate returned");
  }
  int reads=0,waits=0;
  InstalledSelection.RequireReady(()=>++reads<3?0u:1u,()=>waits++,4);
  if(reads!=3||waits!=2)throw new Exception("pending/ready sequencing");
  foreach(uint state in new uint[]{2,9}) {
   bool rejected=false;
   try{InstalledSelection.RequireReady(()=>state,()=>throw new Exception("must not wait"),2);}
   catch(InvalidDataException){rejected=true;}
   if(!rejected)throw new Exception("rejected state admitted");
  }
  waits=0;bool timeout=false;
  try{InstalledSelection.RequireReady(()=>0u,()=>waits++,2);}
  catch(InvalidDataException){timeout=true;}
  if(!timeout||waits!=2)throw new Exception("pending timeout");
  bool forwarded=false;
  try{InstalledSelection.RequireReady(()=>throw new IOException("native admission unavailable"),()=>{},2);}
  catch(IOException){forwarded=true;}
  if(!forwarded)throw new Exception("native error concealed");
  Console.WriteLine("Installed gate: pending/ready, reject, unknown, timeout and native failure passed");
 }
}
'''
    file = output/'GateChecks.cs'; file.write_text('using System; using System.IO;\n'+actual_gate+checks)
    binary = output/'GateChecks.dll'
    subprocess.run([str(dotnet),str(compiler),'/nologo','/noconfig','/nostdlib+','/nullable:enable','/target:exe','/out:'+str(binary),
                    *['/reference:'+str(p) for p in runtime.glob('*.dll')],str(file)],check=True,timeout=60)
    (output/'GateChecks.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'tfm':'net'+runtime.name.split('.')[0]+'.0','framework':{'name':'Microsoft.NETCore.App','version':runtime.name}}}))
    run=subprocess.run([str(dotnet),str(binary)],capture_output=True,text=True,check=True,timeout=20)
    fallback=output/'writable-host'; expected=fallback/'MoonLab/evidence/adapter-failure.txt'
    env=__import__('os').environ.copy(); unrelated=output/'untrusted-inherited-evidence';env['MOONLAB_BEPINEX_EVIDENCE']=str(unrelated)
    failure=subprocess.run([str(dotnet),str(binary),'--admission-failure',str(fallback)],env=env,capture_output=True,text=True,timeout=20)
    if failure.returncode!=23 or not expected.is_file() or 'selection was rejected' not in expected.read_text() or unrelated.exists():
        raise ValueError('Fatal admission must exit 23 and preserve the known fallback report despite failed logging')
    blocked=output/'blocked-host/MoonLab/evidence';blocked.parent.mkdir(parents=True,exist_ok=True);blocked.write_text('preserve blocking file')
    no_report=subprocess.run([str(dotnet),str(binary),'--blocked-output',str(output/'blocked-host')],env=env,capture_output=True,text=True,timeout=20)
    if no_report.returncode!=23 or blocked.read_text()!='preserve blocking file':
        raise ValueError('Unwritable fallback or failed logger must not prevent fatal exit 23')
    record={'success':True,'adapter_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'runtime':runtime.name,'stdout':run.stdout,
            'fatal_admission_exit_code':failure.returncode,'fatal_admission_report':str(expected.relative_to(output)),
            'unwritable_fallback_exit_code':no_report.returncode,'inherited_evidence_ignored':True,'game_started':False}
    (output/'result.json').write_text(json.dumps(record,indent=2)+'\n'); print(run.stdout.strip())


if __name__=='__main__': main()
