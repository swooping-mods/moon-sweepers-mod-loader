/* Host-only checks: synthetic PE import tables and private shell paths.
 * No Windows process, Unity or proprietary game instructions are executed. */
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <stddef.h>
#include <string.h>
typedef void *PTR;typedef uint32_t DWORD;typedef uint64_t U64;typedef wchar_t WCHAR;
#define __stdcall
static int protect_ok=1;
static int VirtualProtect(PTR p,U64 n,DWORD flags,DWORD *old){(void)p;(void)n;(void)flags;*old=4;return protect_ok;}
static PTR CoTaskMemAlloc(U64 n){return malloc((size_t)n);}
static int equal(const char *a,const char *b){return !strcmp(a,b);}
#include "../runtime/loader/profile.h"
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}}while(0)
static int delegated;
static long fallback_known(const Guid *id,DWORD f,PTR t,WCHAR **out){(void)id;(void)f;(void)t;(void)out;delegated++;return 17;}
static long fallback_folder(PTR w,int id,PTR t,DWORD f,WCHAR *out){(void)w;(void)id;(void)t;(void)f;(void)out;delegated++;return 19;}
static int wequal(const WCHAR *a,const WCHAR *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static void setroot(const WCHAR *value){int n=0;while(value[n]){profile_root[n]=value[n];n++;}profile_root[n]=0;}
int main(void){
 real_known=fallback_known;real_folder=fallback_folder;setroot(L"C:\\MoonLab\\profile");WCHAR *out=0;
 CHECK(private_known(&local_low,0,0,&out)==0);CHECK(wequal(out,L"C:\\MoonLab\\profile\\AppData\\LocalLow"));free(out);
 CHECK(private_known(&local_app,0,0,&out)==0);CHECK(wequal(out,L"C:\\MoonLab\\profile\\AppData\\Local"));free(out);
 CHECK(private_known(&roaming_app,0,0,&out)==0);CHECK(wequal(out,L"C:\\MoonLab\\profile\\AppData\\Roaming"));free(out);
 CHECK(private_known(&user_profile,0,0,&out)==0);CHECK(wequal(out,profile_root));free(out);
 Guid unknown={0};CHECK(private_known(&unknown,0,0,&out)==17);CHECK(delegated==1);
 CHECK(private_known(&local_low,0,(PTR)1,&out)!=0);CHECK(delegated==1);
 WCHAR legacy[260];CHECK(private_folder(0,0x801c,0,0,legacy)==0);CHECK(wequal(legacy,L"C:\\MoonLab\\profile\\AppData\\Local"));
 CHECK(private_folder(0,0x1a,0,0,legacy)==0);CHECK(wequal(legacy,L"C:\\MoonLab\\profile\\AppData\\Roaming"));
 CHECK(private_folder(0,0x28,0,0,legacy)==0);CHECK(wequal(legacy,profile_root));
 CHECK(private_folder(0,1,0,0,legacy)==19);
 for(int i=0;i<300;i++)profile_root[i]='x';profile_root[300]=0;CHECK(private_folder(0,0x1c,0,0,legacy)!=0);
 unsigned char *module=calloc(1,4096);*(DWORD *)(module+0x3c)=0x80;*(DWORD *)(module+0x80)=0x4550;
 *(unsigned short *)(module+0x80+24)=0x20b;*(DWORD *)(module+0x80+24+56)=4096;*(DWORD *)(module+0x80+24+120)=0x200;
 *(DWORD *)(module+0x200)=0x300;*(DWORD *)(module+0x20c)=0x250;*(DWORD *)(module+0x210)=0x400;
 *(U64 *)(module+0x300)=0x500;*(U64 *)(module+0x308)=0x540;
 strcpy((char *)module+0x502,"SHGetKnownFolderPath");strcpy((char *)module+0x542,"SHGetFolderPathW");
 *(PTR *)(module+0x400)=(PTR)fallback_known;*(PTR *)(module+0x408)=(PTR)fallback_folder;
 CHECK(protect_profile(module,1));CHECK(*(PTR *)(module+0x400)==(PTR)private_known);CHECK(*(PTR *)(module+0x408)==(PTR)private_folder);
 protect_ok=0;CHECK(!protect_profile(module,1));protect_ok=1;
 *(U64 *)(module+0x308)=0;CHECK(!protect_profile(module,1));CHECK(protect_profile(module,0));
 CHECK(!protect_profile(0,1));CHECK(protect_profile(0,0));free(module);
 puts("private known-folder mappings and required PE import guards passed");return 0;
}
