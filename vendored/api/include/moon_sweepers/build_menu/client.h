#ifndef MOON_BUILD_MENU_CLIENT_H
#define MOON_BUILD_MENU_CLIENT_H
#include "build_menu.h"
__declspec(dllimport) DWORD __stdcall GetModuleFileNameA(PTR, char *, DWORD);
static const MoonBuildMenu *mb_connect(PTR domain, PTR game) {
    char path[1200];DWORD n=GetModuleFileNameA(0,path,1000);
    if(!n||n>=1000)return 0;
    while(n&&path[n-1]!='\\'&&path[n-1]!='/')n--;
    if(!n)return 0;cat(path+n,"MoonLab\\mods\\build-menu-framework\\mod.dll");
    PTR module=LoadLibraryA(path);if(!module)return 0;
    int (*start)(PTR,PTR)=(int(*)(PTR,PTR))GetProcAddress(module,"MoonLab_ModStart");
    MoonBuildMenuGet get=(MoonBuildMenuGet)GetProcAddress(module,"MoonLab_BuildMenu_v1");
    if(!start||!get||!start(domain,game))return 0;
    return get(MB_ABI,sizeof(MoonBuildMenu));
}
#endif
