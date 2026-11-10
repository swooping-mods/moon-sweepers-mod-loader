/* Synthetic executable only; no Unity/game or Steam dependency. */
typedef void *PTR;
typedef unsigned int DWORD;
typedef unsigned long long U64;
typedef __WCHAR_TYPE__ WCHAR;
__declspec(dllimport) PTR __stdcall LoadLibraryW(const WCHAR *);
__declspec(dllimport) PTR __stdcall GetProcAddress(PTR,const char *);
__declspec(dllimport) void __stdcall Sleep(DWORD);
__declspec(dllimport) void __stdcall ExitProcess(DWORD);
__declspec(dllimport) PTR __stdcall GetStdHandle(DWORD);
__declspec(dllimport) int __stdcall WriteFile(PTR,const void *,DWORD,DWORD *,PTR);
void mainCRTStartup(void){
    PTR module=LoadLibraryW(L"version.dll");if(!module)ExitProcess(10);
    DWORD (*abi)(void)=(DWORD(*)(void))GetProcAddress(module,"MoonLab_LoaderAbi");
    DWORD (*version)(const WCHAR *,DWORD *)=(DWORD(*)(const WCHAR *,DWORD *))GetProcAddress(module,"GetFileVersionInfoSizeW");
    if(!abi||abi()!=1||!version)ExitProcess(11);
    DWORD ignored=0;version(L"C:\\nonexistent-file.exe",&ignored);
    Sleep(1000);
    const char message[]="synthetic public DLL survived and forwarded version API\n";
    DWORD written=0;WriteFile(GetStdHandle((DWORD)-11),message,sizeof(message)-1,&written,0);
    ExitProcess(written==sizeof(message)-1?0:12);
}
