/* Exercise actual bootstrap parser and guard ordering with synthetic Win32 IO.
 * Crypto is mocked here; Windows/Wine smoke uses the real BCrypt provider. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#define __declspec(x)
#define __stdcall
typedef void *PTR;
typedef unsigned int DWORD;
typedef unsigned long long U64;
typedef int BOOL;
typedef __WCHAR_TYPE__ WCHAR;
#define MOONLAB_MAX_NATIVE_MODS 64
static PTR self_module;
static char *append(char *out,const char *s){while(*s)*out++=*s++;*out=0;return out;}
static int equal(const char *a,const char *b){return strcmp(a,b)==0;}
DWORD GetModuleFileNameW(PTR,WCHAR *,DWORD);
PTR CreateFileW(const WCHAR *,DWORD,DWORD,PTR,DWORD,DWORD,PTR);
BOOL CloseHandle(PTR);
#include "../runtime/loader/public.h"

static const char *pins[]={
    "14f711a6a3b1b7cd803a03f85cc6c6201c5b546ab9b90329533f5cb8ae2e7f13",
    "0e780f8e8d4bf26ed6bdd8a4068ac42a18846a66a80da7ba5c78f1917a093901",
    "bfafc49b185eb8427ad75e3648bcba3bf5b07455567ca05ae2b2e23bc1646c0c"};
static const char *mod_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
static char configuration[6000], inventory[2000];
static const char *file_data;
static unsigned int file_position, hashing_file, hashes, environments;
static int wrong_hash;
static const char *generation="0123456789abcdef0123456789abcdef";
static void reset(const char *enabled,const char *mods){
    snprintf(configuration,sizeof(configuration),"MOONLAB-PUBLIC-1\ninstallation=0123456789abcdef\ngeneration=%s\nenabled=%s\nmods=%s\n",generation,enabled,mods);
    snprintf(inventory,sizeof(inventory),"%s MoonLab/mods/test-mod/mod.dll\n%s MoonLab/runtime-plan.bin\n",mod_hash,mod_hash);
    hashes=environments=0;wrong_hash=0;public_mode=1;
}
DWORD GetModuleFileNameW(PTR module,WCHAR *out,DWORD capacity){
    const char *s=module?"C:\\game\\version.dll":"C:\\game\\MoonSweepers.exe";unsigned int i=0;
    for(;s[i]&&i+1<capacity;i++)out[i]=s[i];out[i]=0;return i;
}
PTR CreateFileW(const WCHAR *path,DWORD access,DWORD share,PTR security,DWORD mode,DWORD flags,PTR template){
    (void)access;(void)security;(void)mode;(void)flags;(void)template;assert(share==1);
    char name[1600];unsigned int i=0;for(;path[i]&&i+1<sizeof(name);i++)name[i]=(char)path[i];name[i]=0;
    file_position=0;
    if(strstr(name,"active.txt"))file_data=configuration;
    else if(strstr(name,"files.txt"))file_data=inventory;
    else {
        const char *names[]={"GameAssembly.dll","MoonSweepers.exe","UnityPlayer.dll","mod.dll","runtime-plan.bin"};
        hashing_file=5;for(unsigned int j=0;j<5;j++)if(strstr(name,names[j]))hashing_file=j;
        if(hashing_file==5)return (PTR)(U64)-1;
        file_data="synthetic file";
    }
    return (PTR)(uintptr_t)(hashing_file+1);
}
BOOL ReadFile(PTR file,void *out,DWORD capacity,DWORD *size,PTR overlap){
    (void)file;(void)overlap;unsigned int n=(unsigned int)strlen(file_data)-file_position;if(n>capacity)n=capacity;
    memcpy(out,file_data+file_position,n);file_position+=n;*size=n;return 1;
}
BOOL CloseHandle(PTR file){(void)file;return 1;}
BOOL SetEnvironmentVariableW(const WCHAR *name,const WCHAR *value){(void)name;(void)value;environments++;return 1;}
void OutputDebugStringA(const char *text){(void)text;}
DWORD GetFileAttributesW(const WCHAR *path){(void)path;return 0x80;}
BOOL CreateDirectoryW(const WCHAR *path,PTR security){(void)path;(void)security;return 1;}
U64 GetTickCount64(void){return 42;}
DWORD GetCurrentProcessId(void){return 99;}
int BCryptOpenAlgorithmProvider(PTR *out,const WCHAR *name,const WCHAR *provider,DWORD flags){(void)name;(void)provider;(void)flags;*out=(PTR)1;hashes++;return 0;}
int BCryptCreateHash(PTR alg,PTR *out,void *obj,DWORD size,void *secret,DWORD count,DWORD flags){(void)alg;(void)obj;(void)size;(void)secret;(void)count;(void)flags;*out=(PTR)1;return 0;}
int BCryptHashData(PTR hash,void *bytes,DWORD size,DWORD flags){(void)hash;(void)bytes;(void)size;(void)flags;return 0;}
static unsigned char hex_digit(char c){return (unsigned char)(c<='9'?c-'0':c-'a'+10);}
int BCryptFinishHash(PTR hash,void *bytes,DWORD size,DWORD flags){
    (void)hash;(void)flags;assert(size==32);const char *expected=hashing_file<3?pins[hashing_file]:mod_hash;
    for(int i=0;i<32;i++)((unsigned char *)bytes)[i]=(unsigned char)((hex_digit(expected[i*2])<<4)|hex_digit(expected[i*2+1]));
    if(wrong_hash)((unsigned char *)bytes)[0]^=1;return 0;
}
int BCryptDestroyHash(PTR hash){(void)hash;return 0;}
int BCryptCloseAlgorithmProvider(PTR alg,DWORD flags){(void)alg;(void)flags;return 0;}

int main(void){
    assert(valid_id(L"3d-tools"));assert(valid_id(L"test-3d"));assert(valid_id(L"123"));
    assert(!valid_id(L"-test"));assert(!valid_id(L"test-"));assert(!valid_id(L"test--mod"));
    assert(public_same_path(L"C:\\Game\\MoonSweepers.exe",L"c:/game/moonsweepers.exe"));
    assert(!public_same_path(L"C:\\Game\\MoonSweepers.exe",L"C:\\Elsewhere\\MoonSweepers.exe"));
    self_module=(PTR)1;assert(public_installed_marker());assert(!public_game_module((PTR)1));
    reset("1","test-mod");assert(public_startup());assert(hashes==5);assert(environments>2);public_release_inputs();
    reset("1","3d-tools");snprintf(inventory,sizeof(inventory),"%s MoonLab/mods/3d-tools/mod.dll\n%s MoonLab/runtime-plan.bin\n",mod_hash,mod_hash);
    assert(public_startup());assert(hashes==5);public_release_inputs();
    reset("1","test-mod");strchr(inventory,'\n')[1]=0;
    assert(!public_startup());assert(environments==0);public_release_inputs();
    reset("1","test-mod");size_t used=strlen(inventory);
    snprintf(inventory+used,sizeof(inventory)-used,"%s MoonLab/runtime-plan.bin\n",mod_hash);
    assert(!public_startup());assert(environments==0);public_release_inputs();
    reset("1","test-mod");size_t config_length=strlen(configuration), inventory_length=strlen(inventory);
    for(size_t length=0;length<config_length;length++){
        reset("1","test-mod");configuration[length]=0;
        assert(!public_startup());assert(hashes==0);assert(environments==0);public_release_inputs();
    }
    for(size_t length=0;length<inventory_length;length++){
        reset("1","test-mod");inventory[length]=0;
        assert(!public_startup());assert(environments==0);public_release_inputs();
    }
    reset("0","test-mod");assert(!public_startup());assert(hashes==0);assert(environments==0);
    reset("1","");assert(!public_startup());assert(hashes==0);
    reset("1","../escape");assert(!public_startup());assert(hashes==0);
    reset("1","test-mod;");assert(!public_startup());assert(hashes==0);
    reset("1","test-mod;test-mod");assert(!public_startup());assert(hashes==0);
    reset("1","test-mod");configuration[0]='X';assert(!public_startup());assert(hashes==0);
    reset("1","test-mod");strcat(configuration,"unexpected=1\n");assert(!public_startup());assert(hashes==0);
    reset("1","test-mod");wrong_hash=1;assert(!public_startup());assert(hashes==1);assert(environments==0);public_release_inputs();
    reset("1","missing-mod");assert(!public_startup());assert(environments==0);public_release_inputs();
    reset("1","test-mod");strcpy(inventory+65,"MoonLab/mods/../escape.dll\n");assert(!public_startup());assert(environments==0);public_release_inputs();
    assert(!public_relative("/absolute"));assert(!public_relative("x//y"));assert(!public_relative("x/.."));
    assert(!public_relative("x/space "));assert(!public_relative("x:stream"));
    assert(public_relative("MoonLab/mods/test-mod/.asset"));assert(public_relative("MoonLab/mods/test-mod/.data/file.bin"));
    puts("public bootstrap parsing, inventory and build-guard ordering passed");return 0;
}
