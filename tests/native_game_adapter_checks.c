/* Actual production plan, registry, frame dispatch, broker and clock binder.
 * Only Windows/Unity exports are replaced by bounded original host fixtures. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <pthread.h>
typedef void *PTR;typedef unsigned int DWORD;typedef unsigned long long U64;typedef int BOOL;
#define __stdcall
#define __declspec(x)
static _Thread_local DWORD fake_thread=7;
DWORD GetCurrentThreadId(void){return fake_thread;}
BOOL VirtualProtect(PTR p,U64 n,DWORD flags,DWORD *old){(void)p;(void)n;(void)flags;*old=4;return 1;}
PTR GetCurrentProcess(void){return (PTR)1;}
BOOL FlushInstructionCache(PTR p,const void *a,U64 n){(void)p;(void)a;(void)n;return 1;}
static int moon_game_frame_enter(unsigned int);
static void moon_game_frame_leave(unsigned int,int);
#define MOON_LOADER_GAME_FRAME_ENTER(hook) moon_game_frame_enter(hook)
#define MOON_LOADER_GAME_FRAME_LEAVE(hook,entered) moon_game_frame_leave(hook,entered)
#include "../runtime/loader/dispatch.h"
#include "../runtime/loader/game_profile.h"
PTR AddVectoredExceptionHandler(DWORD first,int (*handler)(ExceptionPointers *)){(void)first;(void)handler;return (PTR)1;}
DWORD RemoveVectoredExceptionHandler(PTR p){(void)p;return 1;}
static int equal(const char *a,const char *b){return strcmp(a,b)==0;}
static PTR GetProcAddress(PTR,const char *);
#include "../runtime/loader/game_adapter.h"
#include "../runtime/loader/mod_entry.h"
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}}while(0)
static unsigned int engine_calls,metadata_calls,bad_arity,bad_flags,bad_return,absent_icall;
static unsigned int selected_adapter;
static struct {double time;float delta;int frame;} state_a={21,.25f,12};
static struct {unsigned char relocation[64];int frame;double time;float delta;} state_b={{0},12,21,.25f};
static int frame_a(void){engine_calls++;return state_a.frame;}
static double time_a(void){engine_calls++;return state_a.time;}
static float delta_a(void){engine_calls++;return state_a.delta;}
static int frame_b(void){engine_calls++;return state_b.frame;}
static double time_b(void){engine_calls++;return state_b.time;}
static float delta_b(void){engine_calls++;return state_b.delta;}
static const PTR *assemblies(PTR domain,U64 *count){static const PTR images[1]={(PTR)1};(void)domain;metadata_calls++;*count=1;return images;}
static PTR image(PTR assembly){return assembly;}
static PTR klass(PTR assembly,const char *ns,const char *name){(void)assembly;return !strcmp(ns,"UnityEngine")&&!strcmp(name,"Time")?(PTR)1:0;}
static PTR method(PTR type,const char *name,int argc){(void)type;(void)argc;return !strcmp(name,"get_frameCount")?(PTR)1:!strcmp(name,"get_timeAsDouble")?(PTR)2:!strcmp(name,"get_deltaTime")?(PTR)3:0;}
static unsigned int arity(PTR m){(void)m;return bad_arity;}
static unsigned int flags(PTR m,unsigned int *implementation){(void)m;*implementation=0;return bad_flags?0:0x10;}
static PTR result(PTR m){return m;}
static char *type_name(PTR m){return (char *)(bad_return?"System.Int64":m==(PTR)1?"System.Int32":m==(PTR)2?"System.Double":"System.Single");}
static void release(PTR p){(void)p;}
static PTR resolve(const char *name){
    if(absent_icall)return 0;
    if(!strcmp(name,"UnityEngine.Time::get_frameCount()"))return selected_adapter?(PTR)frame_b:(PTR)frame_a;
    if(!strcmp(name,"UnityEngine.Time::get_timeAsDouble()"))return selected_adapter?(PTR)time_b:(PTR)time_a;
    if(!strcmp(name,"UnityEngine.Time::get_deltaTime()"))return selected_adapter?(PTR)delta_b:(PTR)delta_a;
    return 0;
}
static PTR GetProcAddress(PTR module,const char *name){
    if(module!=(PTR)2)return dlsym(module,name);
#define EXPORT(s,f) if(!strcmp(name,"il2cpp_" s))return (PTR)f
    EXPORT("domain_get_assemblies",assemblies);EXPORT("assembly_get_image",image);
    EXPORT("class_from_name",klass);EXPORT("class_get_method_from_name",method);
    EXPORT("method_get_param_count",arity);EXPORT("method_get_flags",flags);
    EXPORT("method_get_return_type",result);EXPORT("type_get_name",type_name);
    EXPORT("free",release);EXPORT("resolve_icall",resolve);
#undef EXPORT
    return 0;
}
static unsigned char code[3][5]={{0x48,0x8b,0xc4,0,0},{0x48,0x8b,0xc4,0,0},{0x48,0x8b,0xc4,0,0}};
static int raw_observer(int id,MoonHookContext *context){(void)id;(void)context;return 0;}
typedef struct {int (*sample)(void);unsigned int admitted;} ForeignClock;
static void *foreign_clock(void *data){ForeignClock *test=data;fake_thread=8;for(unsigned int i=0;i<1000;i++)if(test->sample())test->admitted++;return 0;}
int main(int argc,char **argv){
    CHECK(argc==6);selected_adapter=!strcmp(argv[2],"b");
    MoonNativeGameProfile adapters[2]={
        {.id="synthetic.profile-a",.digest=PROBE_PROFILE_A_DIGEST,.hashes={PROBE_PROFILE_A_GAME,PROBE_PROFILE_A_EXE,PROBE_PROFILE_A_PLAYER},.domain_rva=16},
        {.id="synthetic.profile-b",.digest=PROBE_PROFILE_B_DIGEST,.hashes={PROBE_PROFILE_B_GAME,PROBE_PROFILE_B_EXE,PROBE_PROFILE_B_PLAYER},.domain_rva=128}
    };
    const char *const *observed=adapters[selected_adapter].hashes;
    CHECK(moon_profile_select(adapters,2,observed)==adapters+selected_adapter);
    const char *mixed[3]={observed[0],observed[1],"changed-player"};CHECK(!moon_profile_select(adapters,2,mixed));
    CHECK(moon_profile_match(moon_native_game_profiles[0].hashes)==moon_native_game_profiles);
    native_profile=adapters+selected_adapter;
    FILE *file=fopen(argv[1],"rb");CHECK(file);CHECK(!fseek(file,0,SEEK_END));long bytes=ftell(file);CHECK(bytes>0);rewind(file);
    unsigned char *data=malloc((size_t)bytes);CHECK(data);CHECK(fread(data,1,(size_t)bytes,file)==(size_t)bytes);fclose(file);
    if(!strcmp(argv[5],"parser-reject")){CHECK(!msp_init(data,(unsigned int)bytes));free(data);return 0;}
    if(!strcmp(argv[5],"truncations")){
        for(unsigned int n=0;n<(unsigned int)bytes;n++){memset(&service_plan,0,sizeof(service_plan));CHECK(!msp_init(data,n));}
        memset(&service_plan,0,sizeof(service_plan));CHECK(msp_init(data,(unsigned int)bytes));free(data);return 0;
    }
    CHECK(msp_init(data,(unsigned int)bytes));
    if(!strcmp(argv[5],"profile-reject")){CHECK(!moon_game_plan_valid());free(data);return 0;}
    CHECK(moon_game_plan_valid());CHECK(moon_game_clock_required());
    if(!strncmp(argv[5],"entry-",6)){
        void *module=dlopen(argv[4],RTLD_NOW|RTLD_LOCAL);CHECK(module);MoonNativeModEntry entry={0};
        unsigned int expected=!strcmp(argv[5],"entry-missing")?MOON_MOD_ENTRY_MISSING:MOON_MOD_ENTRY_RUNTIME;
        CHECK(moon_mod_entry(module,8,&entry)==expected);CHECK(!engine_calls);free(data);return 0;
    }
    CHECK(!game_find("unity.clock",1,16));CHECK(!engine_calls);
    bad_arity=1;CHECK(!game_clock_bind((PTR)1,(PTR)2));bad_arity=0;
    bad_flags=1;CHECK(!game_clock_bind((PTR)1,(PTR)2));bad_flags=0;
    bad_return=1;CHECK(!game_clock_bind((PTR)1,(PTR)2));bad_return=0;
    absent_icall=1;CHECK(!game_clock_bind((PTR)1,(PTR)2));absent_icall=0;
    CHECK(!engine_calls);CHECK(game_clock_bind((PTR)1,(PTR)2));CHECK(metadata_calls);
    update_address=code[0];late_update_address=code[1];vehicle_address=code[2];
    void *framework=dlopen(argv[3],RTLD_NOW|RTLD_LOCAL);CHECK(framework);
    void *feature=dlopen(argv[4],RTLD_NOW|RTLD_LOCAL);CHECK(feature);
    MoonModStartV8 start_framework=(MoonModStartV8)dlsym(framework,"MoonLab_ModStart_v8");
    MoonModStartV8 start_feature=(MoonModStartV8)dlsym(feature,"MoonLab_ModStart_v8");CHECK(start_framework&&start_feature);
    MoonNativeModEntry admitted={0};CHECK(moon_mod_entry(feature,8,&admitted)==MOON_MOD_ENTRY_OK&&admitted.adapter==start_feature&&!admitted.legacy);
    CHECK(!dlsym(feature,"MoonLab_ModStart"));
    int (*marker)(void)=(int(*)(void))dlsym(feature,"MoonLab_RuntimeServicesAbi");CHECK(marker&&marker()==1);
    MoonModContextV8 context={sizeof(context),MOON_MOD_CONTEXT_V8_ABI,moon_game_adapter_api(),runtime_context_api_v8()};
    CHECK(moon_mod_context_v8_valid(&context));CHECK(!strcmp(context.game->profile_id,native_profile->id));
    CHECK(begin_runtime_registration(1,"clock-framework"));
    MoonHookSubscriptionV1 raw={sizeof(raw),MOON_HOOK_UPDATE,MOON_ROLE_OBSERVER,MOON_PHASE_NORMAL,0,1,raw_observer,0};CHECK(!hook_subscribe(&raw));
    CHECK(start_framework(&context));CHECK(!engine_calls);CHECK(finish_runtime_registration(1));
    CHECK(begin_runtime_registration(2,"clock-feature"));CHECK(start_feature(&context));CHECK(finish_runtime_registration(1));
    CHECK(runtime_finish_startup(seal_updates()));
    CHECK(!context.runtime->find("clock-framework","elapsed",1,16));CHECK(!context.game->find("unity.clock",1,16));
    CHECK(MoonLab_GetRuntimeApi_v1()->find("clock-framework","hidden",1,16));
    unsigned int (*frames)(void)=(unsigned int(*)(void))dlsym(feature,"probe_frames");
    double (*value)(void)=(double(*)(void))dlsym(feature,"probe_value");
    int (*outside)(void)=(int(*)(void))dlsym(feature,"probe_outside");CHECK(frames&&value&&outside);
    CHECK(!outside()&&!engine_calls);
    Context machine={0};machine.rcx=0;CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));
    CHECK(frames()==1&&value()==42&&engine_calls==3);
    CHECK(!outside()&&engine_calls==3);
    fake_thread=8;CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));CHECK(frames()==1&&engine_calls==3);fake_thread=7;
    CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));CHECK(frames()==2&&value()==42&&engine_calls==6);
    ForeignClock foreign={outside,0};pthread_t other;CHECK(!pthread_create(&other,0,foreign_clock,&foreign));
    for(unsigned int i=0;i<1000;i++)CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));
    CHECK(!pthread_join(other,0));CHECK(!foreign.admitted&&frames()==1002&&engine_calls==3006);
    runtime_startup_failed();CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));CHECK(frames()==1002&&engine_calls==3006);
    free(data);dlclose(feature);dlclose(framework);puts("immutable feature/framework + relocated adapter + scoped broker passed");return 0;
}
