/* Resolve the runtime beside this launcher; never use a host Python or PATH. */
typedef unsigned short W;
typedef unsigned int D;
typedef void *H;
#define API __declspec(dllimport)
API D GetModuleFileNameW(H,W*,D);
API W *GetCommandLineW(void);
API int CreateProcessW(const W*,W*,void*,void*,int,D,void*,const W*,void*,void*);
API D WaitForSingleObject(H,D);
API int GetExitCodeProcess(H,D*);
API int CloseHandle(H);
API int MessageBoxW(H,const W*,const W*,unsigned int);
API void ExitProcess(D);
typedef struct { D cb; W *reserved,*desktop,*title; D x,y,xsize,ysize,xchars,ychars,fill,flags; unsigned short show,reserved2; void *reserved3; H in,out,err; } START;
typedef struct {H process,thread; D pid,tid;} PROCESS;
_Static_assert(sizeof(START)==104, "Windows x64 STARTUPINFOW layout");
_Static_assert(sizeof(PROCESS)==24, "Windows x64 PROCESS_INFORMATION layout");
static W root[32768],python[32768],command[32768];
static D length(const W *s){D n=0;while(s[n])++n;return n;}
static int append(W *to,const W *s){D a=length(to),b=length(s);if(a+b>=32767)return 0;for(D i=0;i<=b;++i)to[a+i]=s[i];return 1;}
void mainCRTStartup(void){
 D n=GetModuleFileNameW(0,root,32768),code=1;
 START startup={0}; PROCESS process={0};
 if(!n||n>=32768)goto fail;
 while(n && root[n-1]!='\\')--n;
 if(!n)goto fail;
 root[n]=0;
 if(!append(python,root)||!append(python,(const W*)L"python\\pythonw.exe"))goto fail;
 if(!append(command,(const W*)L"\"")||!append(command,python)||!append(command,(const W*)L"\" \"")||!append(command,root)||!append(command,(const W*)L"loader\\main.py\""))goto fail;
 /* Windows executable token uses quotes for spaces; preserve the remaining args verbatim. */
 W *args=GetCommandLineW();
 if(*args=='"'){++args;while(*args && *args!='"')++args;if(*args)++args;}
 else while(*args && *args!=' ' && *args!='\t')++args;
 if(!append(command,args))goto fail;
 startup.cb=sizeof(startup);
 if(!CreateProcessW(python,command,0,0,0,0,0,root,&startup,&process))goto fail;
 WaitForSingleObject(process.process,0xffffffffUL);
 GetExitCodeProcess(process.process,&code);
 CloseHandle(process.thread);CloseHandle(process.process);
 if(code)goto fail;
 ExitProcess(0);
fail:
 MessageBoxW(0,(const W*)L"The Mod Loader could not start. Extract the entire ZIP before running. For diagnostics, run python\\python.exe loader\\main.py from this folder.",(const W*)L"Moon Sweepers Mod Loader",0x10);
 ExitProcess(code);
}
