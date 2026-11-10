/* Windows version API forwarding, shared ABI with the diagnostic proxy. */
static PTR real_version;
static PTR self_module;
static PTR version_api(const char *name) {
    if(!real_version){char path[512];DWORD n=GetSystemDirectoryA(path,450);if(!n||n>=450)return 0;append(path+n,"\\version.dll");real_version=LoadLibraryA(path);}
    /* Wine can resolve an absolute system path back to the proxy. A failed
     * version query is valid; recursively calling our own export is not. */
    return real_version && real_version!=self_module?GetProcAddress(real_version,name):0;
}
#define V2(N) DWORD N(PTR a,PTR b){typedef DWORD(*F)(PTR,PTR);F f=(F)version_api(#N);return f?f(a,b):0;}
#define V3(N) DWORD N(PTR a,PTR b,PTR c){typedef DWORD(*F)(PTR,PTR,PTR);F f=(F)version_api(#N);return f?f(a,b,c):0;}
#define V4(N) DWORD N(PTR a,PTR b,PTR c,PTR d){typedef DWORD(*F)(PTR,PTR,PTR,PTR);F f=(F)version_api(#N);return f?f(a,b,c,d):0;}
#define V5(N) DWORD N(PTR a,PTR b,PTR c,PTR d,PTR e){typedef DWORD(*F)(PTR,PTR,PTR,PTR,PTR);F f=(F)version_api(#N);return f?f(a,b,c,d,e):0;}
#define V8(N) DWORD N(PTR a,PTR b,PTR c,PTR d,PTR e,PTR f0,PTR g,PTR h){typedef DWORD(*F)(PTR,PTR,PTR,PTR,PTR,PTR,PTR,PTR);F f=(F)version_api(#N);return f?f(a,b,c,d,e,f0,g,h):0;}
V2(GetFileVersionInfoSizeA) V2(GetFileVersionInfoSizeW)
V3(GetFileVersionInfoSizeExA) V3(GetFileVersionInfoSizeExW)
V4(GetFileVersionInfoA) V4(GetFileVersionInfoW) V5(GetFileVersionInfoExA) V5(GetFileVersionInfoExW)
V4(VerQueryValueA) V4(VerQueryValueW) V3(VerLanguageNameA) V3(VerLanguageNameW)
V8(VerFindFileA) V8(VerFindFileW) V8(VerInstallFileA) V8(VerInstallFileW)
