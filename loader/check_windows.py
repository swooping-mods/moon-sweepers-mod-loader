"""Native Windows, non-game DLL/profile diagnostic. No Python GUI required."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from moonloader import packages


def main():
    if sys.platform != 'win32': raise ValueError('Run on Windows. On Linux use tools/loader_wine_check.py in the source project.')
    bundle=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='MoonLab-check-') as temporary:
        location,_=packages.install(bundle/'packages/electricity-toggle-0.2.0.msmod',Path(temporary))
        env={key:value for key,value in os.environ.items() if not key.startswith('MOONLAB_')}
        env['MOONLAB_CHECK_LOADER']=str(bundle/'runtime/windows-x64/version.dll')
        env['MOONLAB_CHECK_MOD']=str(Path(temporary)/'library'/location/'mod.dll')
        result=subprocess.run([str(bundle/'runtime/windows-x64/MoonLab.LoaderCheck.exe')],env=env,capture_output=True,text=True,timeout=30)
        print(result.stdout.strip());print(result.stderr.strip(),file=sys.stderr)
        report=json.loads(result.stdout.strip().splitlines()[-1])
        if result.returncode or not report.get('success') or report.get('game_started') or report.get('unity_loaded'):return 1
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as error:print(str(error),file=sys.stderr);raise SystemExit(1)
