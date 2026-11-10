"""Exercise the production launcher's argument/path handling with mocked Win32 APIs."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <setjmp.h>
#include <stdlib.h>
#define __declspec(x)
#include "desktop.c"
static jmp_buf exit_point;
static D exit_code;
static int scenario, message, created;
static int equal(const W *a,const W *b){while(*a && *a==*b){++a;++b;}return *a==*b;}
D GetModuleFileNameW(H h,W *buffer,D capacity){
 (void)h;(void)capacity;
 const W *path=(const W*)L"C:\\Portable tools\\Mod Loader.exe";
 D n=length(path);for(D i=0;i<=n;++i)buffer[i]=path[i];return scenario==3?32768:n;
}
W *GetCommandLineW(void){return (W*)L"\"C:\\Portable tools\\Mod Loader.exe\" --no-launch --data \"C:\\My profiles\\review\"";}
int CreateProcessW(const W *app,W *cmd,void *a,void *b,int inherit,D flags,void *env,const W *cwd,void *si,void *pi){
 (void)a;(void)b;(void)env;
 if(!equal(app,(const W*)L"C:\\Portable tools\\python\\pythonw.exe"))abort();
 if(!equal(cwd,(const W*)L"C:\\Portable tools\\"))abort();
 if(!equal(cmd,(const W*)L"\"C:\\Portable tools\\python\\pythonw.exe\" \"C:\\Portable tools\\loader\\main.py\" --no-launch --data \"C:\\My profiles\\review\""))abort();
 if(inherit || flags || ((START*)si)->cb!=sizeof(START))abort();
 created=1;((PROCESS*)pi)->process=(H)1;((PROCESS*)pi)->thread=(H)2;return scenario!=1;
}
D WaitForSingleObject(H h,D timeout){if(h!=(H)1 || timeout!=0xffffffffUL)abort();return 0;}
int GetExitCodeProcess(H h,D *code){(void)h;*code=scenario==2?5:0;return 1;}
int CloseHandle(H h){(void)h;return 1;}
int MessageBoxW(H h,const W *text,const W *title,unsigned int type){(void)h;(void)text;(void)title;(void)type;++message;return 0;}
void ExitProcess(D code){exit_code=code;longjmp(exit_point,1);}
int main(int argc,char **argv){
 if(argc!=2)return 10;scenario=atoi(argv[1]);
 if(!setjmp(exit_point))mainCRTStartup();
 if(scenario==0)return exit_code==0 && message==0 && created?0:11;
 if(scenario==1)return exit_code==1 && message==1 && created?0:12;
 if(scenario==2)return exit_code==5 && message==1 && created?0:13;
 return exit_code==1 && message==1 && !created?0:14;
}
'''


class DesktopLauncherChecks(unittest.TestCase):
    def test_production_launcher_quotes_paths_and_reports_failures(self):
        compiler = shutil.which('clang')
        self.assertIsNotNone(compiler, 'Installed clang is required for native launcher checks')
        with tempfile.TemporaryDirectory(prefix='moon-desktop-check-') as temporary:
            folder = Path(temporary)
            source = folder / 'check.c'
            source.write_text(HARNESS)
            binary = folder / 'check'
            subprocess.run([compiler, '-std=c11', '-fshort-wchar', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'runtime/loader'), str(source), '-o', str(binary)], check=True)
            for scenario in range(4):
                with self.subTest(scenario=scenario):
                    subprocess.run([str(binary), str(scenario)], check=True, timeout=5)
