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
static unsigned int engine_calls,metadata_calls,bad_arity,bad_flags,bad_return,bad_time_return,absent_icall,absent_scale_method;
static unsigned int selected_adapter;
static struct {float time;float delta;int frame;} state_a={21,.25f,12};
static struct {unsigned char relocation[64];int frame;float time;float delta;} state_b={{0},12,21,.25f};
static float scale_state_a=1,scale_state_b=1;
static int frame_a(void){engine_calls++;return state_a.frame;}
static float time_a(void){engine_calls++;return state_a.time;}
static float delta_a(void){engine_calls++;return state_a.delta;}
static int frame_b(void){engine_calls++;return state_b.frame;}
static float time_b(void){engine_calls++;return state_b.time;}
static float delta_b(void){engine_calls++;return state_b.delta;}
static float scale_a(void){engine_calls++;return scale_state_a;}
static float scale_b(void){engine_calls++;return scale_state_b;}
static const PTR *assemblies(PTR domain,U64 *count){static const PTR images[1]={(PTR)1};(void)domain;metadata_calls++;*count=1;return images;}
static PTR image(PTR assembly){return assembly;}
static PTR klass(PTR assembly,const char *ns,const char *name){(void)assembly;return !strcmp(ns,"UnityEngine")&&!strcmp(name,"Time")?(PTR)1:0;}
static PTR method(PTR type,const char *name,int argc){(void)type;(void)argc;return !strcmp(name,"get_frameCount")?(PTR)1:!strcmp(name,"get_time")?(PTR)2:!strcmp(name,"get_deltaTime")?(PTR)3:!strcmp(name,"get_timeScale")&&!absent_scale_method?(PTR)4:0;}
static unsigned int arity(PTR m){(void)m;return bad_arity;}
static unsigned int flags(PTR m,unsigned int *implementation){(void)m;*implementation=0;return bad_flags?0:0x10;}
static PTR result(PTR m){return m;}
static char *type_name(PTR m){return (char *)(bad_return?"System.Int64":m==(PTR)1?"System.Int32":m==(PTR)2&&bad_time_return?"System.Double":"System.Single");}
static void release(PTR p){(void)p;}
static PTR resolve(const char *name){
    if(absent_icall)return 0;
    if(!strcmp(name,"UnityEngine.Time::get_frameCount()"))return selected_adapter?(PTR)frame_b:(PTR)frame_a;
    if(!strcmp(name,"UnityEngine.Time::get_time()"))return selected_adapter?(PTR)time_b:(PTR)time_a;
    if(!strcmp(name,"UnityEngine.Time::get_deltaTime()"))return selected_adapter?(PTR)delta_b:(PTR)delta_a;
    if(!strcmp(name,"UnityEngine.Time::get_timeScale()"))return selected_adapter?(PTR)scale_b:(PTR)scale_a;
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
typedef struct {int (*sample)(MoonGameTimeScaleSampleV1 *);unsigned int admitted,changed;} ForeignScale;
static void *foreign_scale(void *data){
    ForeignScale *test=data;fake_thread=8;
    for(unsigned int i=0;i<1000;i++){
        MoonGameTimeScaleSampleV1 value={sizeof(value),MOON_GAME_TIME_SCALE_ABI,123,0},before=value;
        if(test->sample(&value))test->admitted++;
        if(memcmp(&before,&value,sizeof(value)))test->changed++;
    }return 0;
}
static int check_time_scale(const char *module_path,int clock_required){
    CHECK(moon_game_time_scale_required());CHECK(moon_game_clock_required()==clock_required);
    CHECK(!game_find("unity.time-scale",1,16));
    absent_scale_method=1;CHECK(!game_time_scale_bind((PTR)1,(PTR)2));CHECK(equal(game_time_scale_bind_failure,"time-scale-method"));absent_scale_method=0;
    bad_arity=1;CHECK(!game_time_scale_bind((PTR)1,(PTR)2));CHECK(equal(game_time_scale_bind_failure,"time-scale-signature"));bad_arity=0;
    bad_flags=1;CHECK(!game_time_scale_bind((PTR)1,(PTR)2));CHECK(equal(game_time_scale_bind_failure,"time-scale-signature"));bad_flags=0;
    bad_return=1;CHECK(!game_time_scale_bind((PTR)1,(PTR)2));CHECK(equal(game_time_scale_bind_failure,"time-scale-return"));bad_return=0;
    absent_icall=1;CHECK(!game_time_scale_bind((PTR)1,(PTR)2));CHECK(equal(game_time_scale_bind_failure,"time-scale-icall"));absent_icall=0;
    CHECK(!engine_calls);CHECK(game_time_scale_bind((PTR)1,(PTR)2));CHECK(!game_time_scale_bind_failure);
    unsigned int bound_metadata=metadata_calls;
    CHECK(game_clock_bind((PTR)1,(PTR)2));CHECK(clock_required||metadata_calls==bound_metadata);
    update_address=code[0];late_update_address=code[1];vehicle_address=code[2];
    void *module=dlopen(module_path,RTLD_NOW|RTLD_LOCAL);CHECK(module);
    MoonModStartV8 start=(MoonModStartV8)dlsym(module,"MoonLab_ModStart_v8");CHECK(start);
    MoonModContextV8 context={sizeof(context),MOON_MOD_CONTEXT_V8_ABI,moon_game_adapter_api(),runtime_context_api_v8()};
    CHECK(begin_runtime_registration(1,"clock-framework"));CHECK(start(&context));CHECK(!engine_calls);CHECK(finish_runtime_registration(1));
    CHECK(begin_runtime_registration(2,"clock-feature"));CHECK(!context.game->find("unity.time-scale",1,16));CHECK(finish_runtime_registration(1));
    CHECK(runtime_finish_startup(seal_updates()));CHECK(!context.game->find("unity.time-scale",1,16));
    int (*sample)(MoonGameTimeScaleSampleV1 *)=(int(*)(MoonGameTimeScaleSampleV1 *))dlsym(module,"probe_time_scale_sample");
    int (*clock_available)(void)=(int(*)(void))dlsym(module,"probe_time_scale_clock_available");
    unsigned int (*frames)(void)=(unsigned int(*)(void))dlsym(module,"probe_time_scale_frames");
    float (*value)(void)=(float(*)(void))dlsym(module,"probe_time_scale_value");CHECK(sample&&clock_available&&frames&&value);
    CHECK(clock_available()==clock_required);
    MoonGameTimeScaleSampleV1 out={sizeof(out),MOON_GAME_TIME_SCALE_ABI,123,0},before=out;
    CHECK(!sample(&out)&&!memcmp(&before,&out,sizeof(out))&&!engine_calls);
    Context machine={0};CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));CHECK(frames()==1&&value()==1&&engine_calls==1);
    float *state=selected_adapter?&scale_state_b:&scale_state_a;
    *state=0;CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));CHECK(frames()==2&&value()==0&&engine_calls==2);
    *state=.25f;CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));CHECK(frames()==3&&value()==.25f&&engine_calls==3);
    *state=2;CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));CHECK(frames()==4&&value()==2&&engine_calls==4);
    unsigned int calls=engine_calls;bound_metadata=metadata_calls;
    CHECK(!moon_game_frame_enter(MOON_HOOK_LATE_UPDATE));CHECK(!sample(&out)&&!memcmp(&before,&out,sizeof(out)));
    fake_thread=8;CHECK(!moon_game_frame_enter(MOON_HOOK_UPDATE));CHECK(!sample(&out));fake_thread=7;
    CHECK(moon_game_frame_enter(MOON_HOOK_UPDATE));
    CHECK(!sample(0));
    for(unsigned int size=0;size<sizeof(out);size++){
        out=(MoonGameTimeScaleSampleV1){size,MOON_GAME_TIME_SCALE_ABI,123,0};before=out;
        CHECK(!sample(&out)&&!memcmp(&before,&out,sizeof(out)));
    }
    out=(MoonGameTimeScaleSampleV1){sizeof(out),2,123,0};before=out;CHECK(!sample(&out)&&!memcmp(&before,&out,sizeof(out)));
    out=(MoonGameTimeScaleSampleV1){sizeof(out),MOON_GAME_TIME_SCALE_ABI,123,1};before=out;CHECK(!sample(&out)&&!memcmp(&before,&out,sizeof(out)));
    out=(MoonGameTimeScaleSampleV1){sizeof(out),MOON_GAME_TIME_SCALE_ABI,123,0};before=out;
    float (*bound_scale)(void)=game_time_scale;game_time_scale=0;
    CHECK(!sample(&out)&&!memcmp(&before,&out,sizeof(out)));game_time_scale=bound_scale;
    CHECK(engine_calls==calls);
    const unsigned int invalid[]={0xbf800000u,0x7fc00000u,0x7f800000u,0xff800000u};
    for(unsigned int i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++){
        union{unsigned int u;float f;} bits={invalid[i]};*state=bits.f;
        out=(MoonGameTimeScaleSampleV1){sizeof(out),MOON_GAME_TIME_SCALE_ABI,123,0};before=out;
        CHECK(!sample(&out)&&!memcmp(&before,&out,sizeof(out)));
    }
    *state=1;
    for(unsigned int i=0;i<15;i++)CHECK(moon_game_frame_enter(MOON_HOOK_UPDATE));
    CHECK(!moon_game_frame_enter(MOON_HOOK_UPDATE));
    struct {MoonGameTimeScaleSampleV1 sample;unsigned int tail;} extended={{sizeof(extended),MOON_GAME_TIME_SCALE_ABI,123,0},0x12345678};
    CHECK(sample(&extended.sample)&&extended.sample.size==16&&extended.sample.time_scale==1&&!extended.sample.reserved&&extended.tail==0x12345678);
    for(unsigned int i=0;i<15;i++)moon_game_frame_leave(MOON_HOOK_UPDATE,1);
    moon_game_frame_leave(MOON_HOOK_UPDATE,1);
    ForeignScale foreign={sample,0,0};pthread_t other;CHECK(!pthread_create(&other,0,foreign_scale,&foreign));
    for(unsigned int i=0;i<1000;i++)CHECK(!dispatch_update(MOON_HOOK_UPDATE,&machine));
    CHECK(!pthread_join(other,0));CHECK(!foreign.admitted&&!foreign.changed&&frames()==1004&&engine_calls==calls+1005);
    CHECK(metadata_calls==bound_metadata);
    out=(MoonGameTimeScaleSampleV1){sizeof(out),MOON_GAME_TIME_SCALE_ABI,123,0};before=out;calls=engine_calls;
    CHECK(!sample(&out)&&!memcmp(&before,&out,sizeof(out))&&engine_calls==calls);
    runtime_startup_failed();CHECK(!moon_game_frame_enter(MOON_HOOK_UPDATE));
    CHECK(!sample(&out)&&!memcmp(&before,&out,sizeof(out))&&engine_calls==calls);
    dlclose(module);return 0;
}
int main(int argc,char **argv){
    CHECK(argc==6);selected_adapter=!strcmp(argv[2],"b");
    MoonNativeGameProfile adapters[2]={
        {.id="synthetic.profile-a",.digest=PROBE_PROFILE_A_DIGEST,.hashes={PROBE_PROFILE_A_GAME,PROBE_PROFILE_A_EXE,PROBE_PROFILE_A_PLAYER},.domain_rva=16,.capabilities=MOON_PROFILE_CLOCK|MOON_PROFILE_TIME_SCALE},
        {.id="synthetic.profile-b",.digest=PROBE_PROFILE_B_DIGEST,.hashes={PROBE_PROFILE_B_GAME,PROBE_PROFILE_B_EXE,PROBE_PROFILE_B_PLAYER},.domain_rva=128,.capabilities=MOON_PROFILE_CLOCK|MOON_PROFILE_TIME_SCALE}
    };
    const char *const *observed=adapters[selected_adapter].hashes;
    CHECK(moon_profile_select(adapters,2,observed)==adapters+selected_adapter);
    const char *mixed[3]={observed[0],observed[1],"changed-player"};CHECK(!moon_profile_select(adapters,2,mixed));
    CHECK(moon_profile_match(moon_native_game_profiles[0].hashes)==moon_native_game_profiles);
    CHECK(moon_native_game_profiles[0].capabilities==MOON_PROFILE_CLOCK);
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
    if(!strcmp(argv[5],"time-scale-profile-reject")){
        adapters[selected_adapter].capabilities=MOON_PROFILE_CLOCK;CHECK(!moon_game_plan_valid());free(data);return 0;
    }
    CHECK(moon_game_plan_valid());
    if(!strncmp(argv[5],"time-scale",10)){
        int result=check_time_scale(argv[3],!strcmp(argv[5],"time-scale-both"));free(data);return result;
    }
    CHECK(moon_game_clock_required());CHECK(!moon_game_time_scale_required());
    CHECK(game_time_scale_bind((PTR)1,(PTR)2));CHECK(!game_time_scale&&!metadata_calls);
    if(!strncmp(argv[5],"entry-",6)){
        void *module=dlopen(argv[4],RTLD_NOW|RTLD_LOCAL);CHECK(module);MoonNativeModEntry entry={0};
        unsigned int expected=!strcmp(argv[5],"entry-missing")?MOON_MOD_ENTRY_MISSING:MOON_MOD_ENTRY_RUNTIME;
        CHECK(moon_mod_entry(module,8,&entry)==expected);CHECK(!engine_calls);free(data);return 0;
    }
    CHECK(!game_find("unity.clock",1,16));CHECK(!engine_calls);
    bad_arity=1;CHECK(!game_clock_bind((PTR)1,(PTR)2));CHECK(equal(game_clock_bind_failure,"clock-frame-signature"));bad_arity=0;
    bad_flags=1;CHECK(!game_clock_bind((PTR)1,(PTR)2));CHECK(equal(game_clock_bind_failure,"clock-frame-signature"));bad_flags=0;
    bad_return=1;CHECK(!game_clock_bind((PTR)1,(PTR)2));CHECK(equal(game_clock_bind_failure,"clock-frame-return"));bad_return=0;
    bad_time_return=1;CHECK(!game_clock_bind((PTR)1,(PTR)2));CHECK(equal(game_clock_bind_failure,"clock-time-return"));bad_time_return=0;
    absent_icall=1;CHECK(!game_clock_bind((PTR)1,(PTR)2));CHECK(equal(game_clock_bind_failure,"clock-frame-icall"));absent_icall=0;
    CHECK(!engine_calls);CHECK(game_clock_bind((PTR)1,(PTR)2));CHECK(!game_clock_bind_failure);CHECK(metadata_calls);
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
