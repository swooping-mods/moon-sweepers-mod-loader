/* Packaged-mod bootstrap: exact host pins, explicit load order, no inventory dump.
 * The UI never calls this code; it runs only inside an explicitly started game. */
typedef void *PTR;
typedef unsigned int DWORD;
typedef unsigned long long U64;
typedef unsigned long long SIZE;
typedef int BOOL;
typedef __WCHAR_TYPE__ WCHAR;
__declspec(dllimport) PTR __stdcall LoadLibraryA(const char *);
__declspec(dllimport) PTR __stdcall LoadLibraryW(const WCHAR *);
__declspec(dllimport) PTR __stdcall GetModuleHandleW(const WCHAR *);
__declspec(dllimport) DWORD __stdcall GetModuleFileNameW(PTR,WCHAR *,DWORD);
__declspec(dllimport) PTR __stdcall GetProcAddress(PTR,const char *);
__declspec(dllimport) DWORD __stdcall GetSystemDirectoryA(char *,DWORD);
__declspec(dllimport) DWORD __stdcall GetEnvironmentVariableW(const WCHAR *,WCHAR *,DWORD);
__declspec(dllimport) PTR __stdcall CreateThread(PTR,SIZE,DWORD (__stdcall *)(PTR),PTR,DWORD,DWORD *);
__declspec(dllimport) BOOL __stdcall CloseHandle(PTR);
__declspec(dllimport) void __stdcall Sleep(DWORD);
__declspec(dllimport) void __stdcall ExitProcess(DWORD);
__declspec(dllimport) BOOL __stdcall VirtualProtect(PTR,U64,DWORD,DWORD *);
__declspec(dllimport) PTR __stdcall CreateFileW(const WCHAR *,DWORD,DWORD,PTR,DWORD,DWORD,PTR);
__declspec(dllimport) BOOL __stdcall WriteFile(PTR,const void *,DWORD,DWORD *,PTR);
__declspec(dllimport) BOOL __stdcall ReadFile(PTR,void *,DWORD,DWORD *,PTR);
__declspec(dllimport) BOOL __stdcall GetFileSizeEx(PTR,U64 *);
__declspec(dllimport) BOOL __stdcall FlushFileBuffers(PTR);
__declspec(dllimport) PTR __stdcall CoTaskMemAlloc(U64);
static char *append(char *out,const char *s){while(*s)*out++=*s++;*out=0;return out;}
static int equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
#include "forward.h"
#include "profile.h"
#include "input.h"
static int moon_game_frame_enter(unsigned int);
static void moon_game_frame_leave(unsigned int,int);
#define MOON_LOADER_GAME_FRAME_ENTER(hook) moon_game_frame_enter(hook)
#define MOON_LOADER_GAME_FRAME_LEAVE(hook,entered) moon_game_frame_leave(hook,entered)
#include "dispatch.h"
#include "interaction.h"
int _fltused=0;
__declspec(dllexport) DWORD MoonLab_LoaderAbi(void){return 1;}
__declspec(dllexport) const MoonInputApiV1 *MoonLab_GetInputApi_v1(void){return moon_input_api_v1();}
__declspec(dllexport) const MoonCameraApiV1 *MoonLab_GetCameraApi_v1(unsigned int abi,unsigned int size){
    return abi==MOON_CAMERA_ABI&&size==sizeof(MoonCameraApiV1)?moon_camera_api_v1():0;
}
static PTR log_file;
static char active_mod[65];
static void event(const char *name,int success){
    char text[256],*p=append(text,"{\"case\":\"");p=append(p,name);
    p=append(p,success?"\",\"success\":true":"\",\"success\":false");
    if(active_mod[0]){p=append(p,",\"mod\":\"");p=append(p,active_mod);p=append(p,"\"");}
    append(p,"}\n");
    DWORD written;U64 n=0;while(text[n])n++;
    if(!WriteFile(log_file,text,(DWORD)n,&written,0)||written!=n)ExitProcess(112);
    FlushFileBuffers(log_file);
}
static void fail(const char *name){runtime_startup_failed();event(name,0);ExitProcess(111);}
static void read_service_plan(void){
    static WCHAR path[1200];DWORD n=GetModuleFileNameW(self_module,path,950);
    if(!n||n>=950)fail("runtime-plan-path");
    while(n&&path[n-1]!='\\'&&path[n-1]!='/')n--;
    const WCHAR *tail=L"MoonLab\\runtime-plan.bin";while(*tail)path[n++]=*tail++;path[n]=0;
    PTR file=CreateFileW(path,0x80000000,1,0,3,0x80,0);
    if(file==(PTR)(U64)-1)fail("runtime-plan-missing");
    U64 size=0;DWORD read=0;
    if(!GetFileSizeEx(file,&size)||size<12||size>MSP_MAX_BYTES){CloseHandle(file);fail("runtime-plan-size");}
    /* One bounded allocation on startup, retained as the immutable source of
     * declared IDs/capacities. There is no allocation on API lookup or frames. */
    void *data=CoTaskMemAlloc(size);
    int success=data&&ReadFile(file,data,(DWORD)size,&read,0)&&read==size;
    CloseHandle(file);
    if(!success||!msp_init(data,(unsigned int)size))fail("runtime-plan-invalid");
    event("runtime-plan-ready",1);
}
#include "public.h"
#include "game_adapter.h"
#include "mod_entry.h"
/* The managed patcher calls this before admitting any installed plug-in. */
__declspec(dllexport) unsigned int MoonLab_InstalledManagedState_v1(void){
    unsigned int state=MoonLab_RuntimeState_v1();
    if(!public_mode)return MOON_RUNTIME_FAILED;
    if(state==MOON_RUNTIME_PENDING)return state;
    return public_managed?state:MOON_RUNTIME_FAILED;
}
static DWORD __stdcall worker(PTR unused){
    (void)unused;
    if(public_mode&&!public_startup()){
        runtime_startup_failed();
        OutputDebugStringA("MoonLab: mods disabled (configuration, build or payload validation failed).\n");
        public_release_inputs();return 0;
    }
    static WCHAR evidence[1200];DWORD n=GetEnvironmentVariableW(L"MOONLAB_EVIDENCE",evidence,1000);
    if(!n||n>=1000){runtime_startup_failed();if(public_mode)return 0;ExitProcess(110);}
    const WCHAR *tail=L"\\loader.jsonl";while(*tail)evidence[n++]=*tail++;evidence[n]=0;
    log_file=CreateFileW(evidence,0x40000000,1,0,1,0x80,0);
    if(log_file==(PTR)(U64)-1){runtime_startup_failed();if(public_mode)return 0;ExitProcess(110);}
    if(!public_mode&&!private_startup_identity())fail("game-profile-identity");
    read_service_plan();
    if(!moon_game_plan_valid())fail("game-profile-plan");
    {
        char text[300],*out=append(text,"{\"case\":\"game-profile\",\"id\":\"");out=append(out,native_profile->id);
        out=append(out,"\",\"digest\":\"");out=append(out,native_profile->digest);append(out,"\",\"success\":true}\n");
        DWORD written=0,size=0;while(text[size])size++;
        if(!WriteFile(log_file,text,size,&written,0)||written!=size)fail("game-profile-log");FlushFileBuffers(log_file);
    }
    event("loader-ready",1);event(public_mode?"installed-game":"private-profile",1);
    if(public_mode){
        char text[200],*out=append(text,"{\"case\":\"deployment\",\"installation\":\"");
        out=append(out,public_installation);out=append(out,"\",\"generation\":\"");
        for(int i=0;i<32;i++)*out++=(char)public_generation[i];
        append(out,"\",\"success\":true}\n");DWORD size=0,written=0;while(text[size])size++;
        if(!WriteFile(log_file,text,size,&written,0)||written!=size)fail("deployment-log-failed");
        FlushFileBuffers(log_file);
    }
    PTR game=0;for(int i=0;i<1200&&!game;i++){game=GetModuleHandleW(L"GameAssembly.dll");if(!game)Sleep(25);}
    if(!game)fail("gameassembly-timeout");
    if(!public_game_module(game)){runtime_startup_failed();event("gameassembly-path-mismatch",0);CloseHandle(log_file);public_release_inputs();return 0;}
    PTR player=GetModuleHandleW(L"UnityPlayer.dll");if(!player||!native_game_module(player,"UnityPlayer.dll"))fail("unityplayer-path-mismatch");
    if(!native_profile_module_bounds(game))fail("game-profile-module-bounds");
    if(!public_mode&&!protect_profile(game,0))fail("gameassembly-profile-guard");
    PTR domain=0;
    for(int i=0;i<1200;i++){
        domain=*(PTR volatile *)((char *)game+native_profile->domain_rva);
        if(domain&&*(PTR volatile *)((char *)domain+native_profile->domain_ready_offset))break;
        domain=0;Sleep(25);
    }
    if(!domain)fail("domain-timeout");
    PTR (*attach)(PTR)=(PTR(*)(PTR))GetProcAddress(game,"il2cpp_thread_attach");
    void (*detach)(PTR)=(void(*)(PTR))GetProcAddress(game,"il2cpp_thread_detach");
    if(!attach||!detach)fail("missing-runtime-api");
    PTR thread=attach(domain);if(!thread)fail("attach-failed");
    const PTR *(*assemblies)(PTR,U64 *)=(const PTR *(*)(PTR,U64 *))GetProcAddress(game,"il2cpp_domain_get_assemblies");
    PTR (*assembly_image)(PTR)=(PTR(*)(PTR))GetProcAddress(game,"il2cpp_assembly_get_image");
    const char *(*image_name)(PTR)=(const char *(*)(PTR))GetProcAddress(game,"il2cpp_image_get_name");
    if(!assemblies||!assembly_image||!image_name)fail("missing-assembly-api");
    int registered=0;
    /* Publication of the domain precedes registration of gameplay assemblies.
     * Do not mistake a cold, attached runtime for available gameplay classes. */
    for(int i=0;i<1200&&!registered;i++){
        U64 count=0;const PTR *list=assemblies(domain,&count);
        if(list&&count<=4096)for(U64 a=0;a<count;a++){
            PTR image=assembly_image(list[a]);const char *name=image?image_name(image):0;
            if(name&&equal(name,"Assembly-CSharp.dll")){registered=1;break;}
        }
        if(!registered)Sleep(25);
    }
    if(!registered)fail("gameplay-assembly-timeout");
    PTR (*get_class)(PTR,const char *,const char *)=(PTR(*)(PTR,const char *,const char *))GetProcAddress(game,"il2cpp_class_from_name");
    PTR (*get_method)(PTR,const char *,int)=(PTR(*)(PTR,const char *,int))GetProcAddress(game,"il2cpp_class_get_method_from_name");
    DWORD (*get_token)(PTR)=(DWORD(*)(PTR))GetProcAddress(game,"il2cpp_method_get_token");
    if(!get_class||!get_method||!get_token)fail("missing-dispatch-api");
    U64 assembly_count=0;const PTR *assembly_list=assemblies(domain,&assembly_count);
    if(!assembly_list||assembly_count>4096)fail("dispatch-assemblies");
    for(U64 a=0;a<assembly_count;a++){
        PTR image=assembly_image(assembly_list[a]);const char *name=image?image_name(image):0;
        if(!name||!equal(name,"Assembly-CSharp.dll"))continue;
        PTR klass=get_class(image,"MoonCleaners","MoonWalker");
        PTR update=klass?get_method(klass,"Update",0):0;
        if(!update||get_token(update)!=native_profile->update_token)fail("dispatch-update-token");
        update_address=*(PTR *)update;
        PTR late=get_method(klass,"LateUpdate",0);
        if(!late||get_token(late)!=native_profile->late_update_token)fail("dispatch-late-update-token");
        late_update_address=*(PTR *)late;
        if(late_update_address!=(char *)game+native_profile->late_update_rva)fail("dispatch-late-update-address");
        klass=get_class(image,"MoonCleaners","MoonPrototypeVehicle");
        PTR fixed=klass?get_method(klass,"FixedUpdate",0):0;
        if(!fixed||get_token(fixed)!=native_profile->vehicle_fixed_token)fail("dispatch-vehicle-token");
        vehicle_address=*(PTR *)fixed;
        if(vehicle_address!=(char *)game+native_profile->vehicle_fixed_rva)fail("dispatch-vehicle-address");
    }
    if((U64)update_address<(U64)game+native_profile->image_min_rva||(U64)update_address>=(U64)game+native_profile->image_max_rva)fail("dispatch-update-address");
    if(!moon_interaction_bind(domain,game))fail("interaction-bind-failed");
    if(!game_clock_bind(domain,game))fail("game-clock-binding");
    /* Include every maximum-length ID plus separators and termination. */
    static WCHAR ids[MOONLAB_MAX_NATIVE_MODS*65+1];
    n=GetEnvironmentVariableW(L"MOONLAB_MODS",ids,MOONLAB_MAX_NATIVE_MODS*65+1);
    if(!n){
        WCHAR managed[4];
        if((public_mode&&!public_managed)||GetEnvironmentVariableW(L"MOONLAB_BEPINEX",managed,4)!=1||managed[0]!='1')fail("missing-mod-list");
        if(service_plan.count)fail("runtime-plan-mod-list");
        if(!runtime_finish_startup(seal_updates()))fail("shared-update-install-failed");
        event("managed-host-only",1);detach(thread);event("load-complete",1);CloseHandle(log_file);return 0;
    }
    if(n>=MOONLAB_MAX_NATIVE_MODS*65+1)fail("missing-mod-list");
    static WCHAR base[1000];DWORD count=GetModuleFileNameW(self_module,base,950);
    if(!count||count>=950)fail("loader-path");
    while(count&&base[count-1]!='\\'&&base[count-1]!='/')count--;
    WCHAR *id=ids;int loaded=0;
    for(WCHAR *p=ids;;p++)if(*p==';'||!*p){
        int last=!*p;*p=0;if(!valid_id(id)||++loaded>MOONLAB_MAX_NATIVE_MODS)fail("invalid-mod-id");
        DWORD mod_length=0;for(WCHAR *q=id;*q;q++)active_mod[mod_length++]=(char)*q;active_mod[mod_length]=0;
        if(!msp_identity((unsigned int)loaded,active_mod))fail("runtime-plan-mod-list");
        event("mod-starting",1);
        static WCHAR path[1200];DWORD length=0;while(length<count){path[length]=base[length];length++;}
        const WCHAR *part=L"MoonLab\\";while(*part)path[length++]=*part++;
        part=L"mods\\";while(*part)path[length++]=*part++;
        for(WCHAR *q=id;*q;q++)path[length++]=*q;
        part=L"\\mod.dll";while(*part)path[length++]=*part++;path[length]=0;
        int adapter_mod=service_plan.mods[loaded-1].package_abi==8;
        PTR mod=LoadLibraryW(path);MoonNativeModEntry entry={0};
        if(!mod)fail("mod-library-load-failed");
        unsigned int admitted=moon_mod_entry(mod,service_plan.mods[loaded-1].package_abi,&entry);
        if(admitted==MOON_MOD_ENTRY_RUNTIME)fail("runtime-api-marker");
        if(admitted!=MOON_MOD_ENTRY_OK)fail("mod-entry-missing");
        if(!begin_runtime_registration((unsigned int)loaded,active_mod))fail("runtime-registration-scope");
        MoonModContextV8 context={sizeof(context),MOON_MOD_CONTEXT_V8_ABI,moon_game_adapter_api(),runtime_context_api_v8()};
        int started=adapter_mod?entry.adapter(&context):entry.legacy(domain,game);
        int committed=finish_runtime_registration(started);
        if(!started)fail("mod-start-failed");
        if(!committed)fail("mod-interface-contract-failed");
        event("mod-started",1);if(last)break;id=p+1;
    }
    active_mod[0]=0;
    if(service_plan.next_owner!=service_plan.count)fail("runtime-plan-mod-list");
    if(!runtime_finish_startup(seal_updates()))fail("shared-update-install-failed");
    event("shared-update-ready",1);
    event("hook-framework-ready",1);
    event("runtime-services-ready",1);
    detach(thread);event("load-complete",1);CloseHandle(log_file);return 0;
}
BOOL __stdcall DllMain(PTR module,DWORD reason,PTR reserved){
    (void)reserved;if(reason!=1)return 1;self_module=module;
    WCHAR exe[1000];DWORD n=GetModuleFileNameW(0,exe,1000);if(!n||n>=1000)return 0;
    const WCHAR *last=exe;for(WCHAR *p=exe;*p;p++)if(*p=='\\'||*p=='/')last=p+1;
    const WCHAR *expected=L"MoonSweepers.exe";while(*last&&*last==*expected){last++;expected++;}
    if(*last||*expected)return 1;
    n=public_installed_marker()?0:GetEnvironmentVariableW(L"MOONLAB_PROFILE_ROOT",profile_root,800);
    if(!n){
        public_mode=1;PTR thread=CreateThread(0,0,worker,0,0,0);
        if(thread)CloseHandle(thread);else runtime_startup_failed();return 1;
    }
    if(n>=800)return 0;
    /* Synchronous: never let Unity compute its personal persistentDataPath
     * before these required import slots are redirected. A failed guard aborts. */
    if(!protect_profile(GetModuleHandleW(L"UnityPlayer.dll"),1))return 0;
    PTR thread=CreateThread(0,0,worker,0,0,0);if(!thread)return 0;CloseHandle(thread);return 1;
}
