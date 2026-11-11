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
    actual_gate = source[source.index('internal static class InstalledSelection'):]
    checks = '''
internal static class Checks {
 static void Main() {
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
    subprocess.run([str(dotnet),str(compiler),'/nologo','/noconfig','/nostdlib+','/target:exe','/out:'+str(binary),
                    *['/reference:'+str(p) for p in runtime.glob('*.dll')],str(file)],check=True,timeout=60)
    (output/'GateChecks.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'tfm':'net'+runtime.name.split('.')[0]+'.0','framework':{'name':'Microsoft.NETCore.App','version':runtime.name}}}))
    run=subprocess.run([str(dotnet),str(binary)],capture_output=True,text=True,check=True,timeout=20)
    record={'success':True,'adapter_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'runtime':runtime.name,'stdout':run.stdout,'game_started':False}
    (output/'result.json').write_text(json.dumps(record,indent=2)+'\n'); print(run.stdout.strip())


if __name__=='__main__': main()
