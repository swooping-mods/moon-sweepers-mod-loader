/* Standalone Windows ABI diagnostic. Never loads Unity or starts a game.
 * Exercise real Win32 allocation, import-table protection and DLL resolution. */
typedef void *PTR;typedef unsigned int DWORD;typedef unsigned long long U64;
typedef __WCHAR_TYPE__ WCHAR;typedef int BOOL;
__declspec(dllimport) int __stdcall VirtualProtect(PTR,U64,DWORD,DWORD *);
__declspec(dllimport) PTR __stdcall CoTaskMemAlloc(U64);
__declspec(dllimport) void __stdcall CoTaskMemFree(PTR);
__declspec(dllimport) PTR __stdcall GetModuleHandleW(const WCHAR *);
__declspec(dllimport) DWORD __stdcall GetEnvironmentVariableW(const WCHAR *,WCHAR *,DWORD);
__declspec(dllimport) PTR __stdcall LoadLibraryW(const WCHAR *);
__declspec(dllimport) PTR __stdcall GetProcAddress(PTR,const char *);
__declspec(dllimport) PTR __stdcall GetStdHandle(DWORD);
__declspec(dllimport) int __stdcall WriteFile(PTR,const void *,DWORD,DWORD *,PTR);
__declspec(dllimport) void __stdcall ExitProcess(DWORD);
static int equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
#include "profile.h"
#include "dispatch.h"
int _fltused=0;
__declspec(dllimport) PTR __stdcall VirtualAlloc(PTR,U64,DWORD,DWORD);
__declspec(dllimport) long __stdcall SHGetKnownFolderPath(const Guid *,DWORD,PTR,WCHAR **);
__declspec(dllimport) long __stdcall SHGetFolderPathW(PTR,int,PTR,DWORD,WCHAR *);
static int wide_equal(const WCHAR *a,const WCHAR *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static void report(const char *text,DWORD code){DWORD n=0,written;while(text[n])n++;WriteFile(GetStdHandle((DWORD)-11),text,n,&written,0);ExitProcess(code);}
static int callback_calls,callback_order_ok=1;
static U64 *expected_counter;
static int synthetic_first(int id,Context *context){
    if(id!=7||callback_calls%2||context->rcx!=(U64)expected_counter)callback_order_ok=0;
    callback_calls++;context->rcx=0;return 1;
}
static int synthetic_second(int id,Context *context){
    if(id!=8||callback_calls%2!=1||context->rcx!=(U64)expected_counter)callback_order_ok=0;
    callback_calls++;return 0;
}
static int vehicle_live=1,vehicle_flying,vehicle_stage,vehicle_order_ok=1,vehicle_flight_calls;
static float vehicle_observed;
static int diagnostic_input(int id,Context *c,MoonVehicleInput *input){
    if(id!=12||vehicle_stage||c->rcx!=(U64)expected_counter)vehicle_order_ok=0;
    vehicle_stage=1;c->rcx=0;
    if(vehicle_live){input->valid=1;input->throttle=.75f;input->steer=.5f;input->boost=1;}
    return 1;
}
static int diagnostic_physics(int id,Context *c,MoonVehicleInput *input){
    if(id!=13||vehicle_stage!=1||c->rcx!=(U64)expected_counter)vehicle_order_ok=0;
    vehicle_stage=0;vehicle_observed=input->valid?input->throttle:0;
    if(vehicle_flying){vehicle_flight_calls++;c->rax=900;return 1;}
    return 0;
}
static int late_active,late_observed,late_order_ok=1;
static int diagnostic_camera(int id,Context *c){if(id!=21||c->rcx!=(U64)expected_counter)late_order_ok=0;c->rcx=0;return late_active;}
static int diagnostic_lines(int id,Context *c){if(id!=22||c->rcx!=(U64)expected_counter)late_order_ok=0;late_observed++;return 1;}
static int check_shared_execution(void){
    /* Original AMD64 function: mov rax,rsp; inc qword [rcx]; mov rax,[rcx]; ret.
     * All instructions and writable state are synthetic, owned by this process. */
    static const unsigned char bytes[]={0x48,0x8b,0xc4,0x48,0xff,0x01,0x48,0x8b,0x01,0xc3};
    unsigned char *code=VirtualAlloc(0,4096,0x3000,0x40);if(!code)return 0;
    for(U64 i=0;i<sizeof(bytes);i++)code[i]=bytes[i];
    if(!FlushInstructionCache(GetCurrentProcess(),code,sizeof(bytes)))return 0;
    unsigned char *fixed=VirtualAlloc(0,4096,0x3000,0x40);if(!fixed)return 0;
    for(U64 i=0;i<sizeof(bytes);i++)fixed[i]=bytes[i];
    if(!FlushInstructionCache(GetCurrentProcess(),fixed,sizeof(bytes)))return 0;
    vehicle_address=fixed;
    unsigned char *late=code+128;
    for(U64 i=0;i<sizeof(bytes);i++)late[i]=bytes[i];
    if(!FlushInstructionCache(GetCurrentProcess(),late,sizeof(bytes)))return 0;
    late_update_address=late;
    if(!begin_hook_registration(1))return 0;
    if(!MoonLab_RegisterLateUpdate_v1(late,100671741,1,22,diagnostic_lines)
       ||!MoonLab_RegisterLateUpdate_v1(late,100671741,2,21,diagnostic_camera))return 0;
    /* Deliberately register physics first; input must execute first. */
    if(!MoonLab_RegisterVehicle_v1(fixed,100669323,2,13,diagnostic_physics)
       ||!MoonLab_RegisterVehicle_v1(fixed,100669323,1,12,diagnostic_input))return 0;
    update_address=code;
    const MoonHookApiV1 *api=MoonLab_GetHookApi_v1();
    MoonHookSubscriptionV1 spec={sizeof(spec),MOON_HOOK_UPDATE,MOON_ROLE_OBSERVER,MOON_PHASE_NORMAL,0,7,synthetic_first,0};
    if(!moon_hook_api_valid(api)||!api->subscribe(&spec)
       ||!MoonLab_RegisterUpdate_v1(code,100671733,8,synthetic_second))return 0;
    finish_hook_registration(1);
    if(!seal_updates())return 0;
    U64 counter=0;expected_counter=&counter;
    U64 (*function)(U64 *)=(U64(*)(U64 *))code;
    for(U64 i=1;i<=3;i++)if(function(&counter)!=i||counter!=i)return 0;
    U64 (*physics)(U64 *)=(U64(*)(U64 *))fixed;
    counter=0;
    if(physics(&counter)!=1||counter!=1||vehicle_observed!=.75f)return 0;
    vehicle_flying=1;
    if(physics(&counter)!=900||counter!=1||vehicle_observed!=.75f)return 0;
    vehicle_live=0;
    if(physics(&counter)!=900||counter!=1||vehicle_observed!=0)return 0;
    vehicle_flying=0;
    if(physics(&counter)!=2||counter!=2||vehicle_observed!=0)return 0;
    U64 other=0;expected_counter=&other;vehicle_live=1;
    if(physics(&other)!=1||other!=1||vehicle_observed!=.75f)return 0;
    void (*late_tick)(U64 *)=(void(*)(U64 *))late;
    counter=0;expected_counter=&counter;late_tick(&counter);
    if(counter!=1||late_observed!=1||MoonLab_CameraOverrideActive_v1())return 0;
    late_active=1;late_tick(&counter);
    if(counter!=1||late_observed!=2||!MoonLab_CameraOverrideActive_v1())return 0;
    late_active=0;late_tick(&counter);
    if(counter!=2||late_observed!=3||MoonLab_CameraOverrideActive_v1())return 0;
    return callback_order_ok&&callback_calls==6&&vehicle_order_ok&&vehicle_flight_calls==2&&late_order_ok;
}
void mainCRTStartup(void){
    const WCHAR *root=L"C:\\MoonLabDiagnostic";int n=0;while(root[n]){profile_root[n]=root[n];n++;}profile_root[n]=0;
    if(!protect_profile(GetModuleHandleW(0),1))report("{\"success\":false,\"case\":\"iat-guard\"}\n",1);
    WCHAR *path=0;
    if(SHGetKnownFolderPath(&local_low,0,0,&path)||!wide_equal(path,L"C:\\MoonLabDiagnostic\\AppData\\LocalLow"))report("{\"success\":false,\"case\":\"known-folder\"}\n",2);
    CoTaskMemFree(path);
    WCHAR legacy[260];
    if(SHGetFolderPathW(0,0x1c,0,0,legacy)||!wide_equal(legacy,L"C:\\MoonLabDiagnostic\\AppData\\Local"))report("{\"success\":false,\"case\":\"legacy-folder\"}\n",3);
    static WCHAR dll_path[1000];DWORD count=GetEnvironmentVariableW(L"MOONLAB_CHECK_LOADER",dll_path,1000);
    if(!count||count>=1000)report("{\"success\":false,\"case\":\"loader-argument\"}\n",4);
    PTR loader=LoadLibraryW(dll_path);
    DWORD (*abi)(void)=loader?(DWORD(*)(void))GetProcAddress(loader,"MoonLab_LoaderAbi"):0;
    if(!abi||abi()!=1||!GetProcAddress(loader,"GetFileVersionInfoW")||!GetProcAddress(loader,"VerQueryValueA")||!GetProcAddress(loader,"MoonLab_RegisterUpdate_v1")||!GetProcAddress(loader,"MoonLab_RegisterVehicle_v1"))report("{\"success\":false,\"case\":\"loader-dll\"}\n",5);
    MoonGetHookApiV1 get_api=(MoonGetHookApiV1)GetProcAddress(loader,"MoonLab_GetHookApi_v1");
    if(!get_api||!moon_hook_api_valid(get_api()))report("{\"success\":false,\"case\":\"hook-sdk-abi\"}\n",10);
    count=GetEnvironmentVariableW(L"MOONLAB_CHECK_MOD",dll_path,1000);
    if(!count||count>=1000)report("{\"success\":false,\"case\":\"mod-argument\"}\n",6);
    PTR mod=LoadLibraryW(dll_path);
    if(!mod||!GetProcAddress(mod,"MoonLab_ModStart")||!GetProcAddress(mod,"MoonLab_SharedUpdateAbi"))report("{\"success\":false,\"case\":\"mod-dll\"}\n",7);
    if(!check_shared_execution())report("{\"success\":false,\"case\":\"shared-update-execution\"}\n",9);
    if(GetModuleHandleW(L"UnityPlayer.dll")||GetModuleHandleW(L"GameAssembly.dll"))report("{\"success\":false,\"case\":\"unexpected-game-runtime\"}\n",8);
    report("{\"success\":true,\"known_folder_redirect\":true,\"legacy_folder_redirect\":true,\"shared_update_execution\":true,\"hook_framework_execution\":true,\"vehicle_mode_handoff\":true,\"loader_dll_loaded\":true,\"mod_dll_loaded\":true,\"unity_loaded\":false,\"game_started\":false}\n",0);
}
