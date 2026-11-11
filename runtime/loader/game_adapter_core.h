#ifndef MOON_GAME_ADAPTER_CORE_H
#define MOON_GAME_ADAPTER_CORE_H
/* Portable broker rules are exercised with independently compiled consumers.
 * The Windows/IL2CPP binder is separate; neither profiles nor lookups contain
 * a user-controlled pointer or an unchecked native offset. */
static unsigned int game_plan_admitted,game_frame_depth;
static DWORD game_frame_thread;
static const void *game_find(const char *,unsigned int,unsigned int);
static MoonGameAdapterApiV1 game_adapter_api={sizeof(MoonGameAdapterApiV1),MOON_GAME_ADAPTER_ABI,0,0,game_find};
static struct {int (*frame)(void);float (*time)(void);float (*delta)(void);} game_clock;
static int game_double_valid(double value){union{double f;U64 u;}x={value};return (x.u&0x7ff0000000000000ull)!=0x7ff0000000000000ull;}
static int game_clock_sample(MoonGameClockSampleV1 *out){
    if(!out||out->size<sizeof(*out)||out->abi!=MOON_GAME_CLOCK_ABI||!game_plan_admitted
       ||MoonLab_RuntimeState_v1()!=MOON_RUNTIME_READY)return 0;
    DWORD thread=__atomic_load_n(&game_frame_thread,__ATOMIC_ACQUIRE);
    /* Reject foreign threads before reading mutable main-thread frame state. */
    if(!thread||thread!=GetCurrentThreadId()||!game_frame_depth
       ||!game_clock.frame||!game_clock.time||!game_clock.delta)return 0;
    /* Affinity is checked before any engine call, including the cheap getters. */
    MoonGameClockSampleV1 value={sizeof(value),MOON_GAME_CLOCK_ABI,(double)game_clock.time(),(double)game_clock.delta(),(unsigned int)game_clock.frame()};
    if(!game_double_valid(value.time_seconds)||!game_double_valid(value.delta_seconds)||value.time_seconds<0||value.delta_seconds<0)return 0;
    *out=value;return 1;
}
static const MoonGameClockV1 game_clock_api={sizeof(MoonGameClockV1),MOON_GAME_CLOCK_ABI,game_clock_sample};
static int game_contract_supported(const MspContract *contract){
    return msp_equal(contract->name,contract->length,"unity.clock")&&contract->abi==MOON_GAME_CLOCK_ABI
        &&contract->size<=sizeof(game_clock_api)&&!contract->count;
}
static int moon_game_plan_valid(void){
    if(game_plan_admitted)return 0;
    if(!native_profile||!service_plan.active)return 0;
    if(service_plan.version==2&&(!moon_profile_equal(service_plan.profile_id,native_profile->id)
       ||!moon_profile_equal(service_plan.profile_digest,native_profile->digest)))return 0;
    int legacy=service_plan.version==1;
    for(unsigned int i=0;i<service_plan.count;i++){
        MspMod *mod=service_plan.mods+i;if(mod->package_abi<8)legacy=1;
        MspReader reader={mod->game,service_plan.end,1};
        for(unsigned int j=0;j<mod->game_count;j++){
            MspContract required;if(!msp_game_contract(&reader,&required)||!game_contract_supported(&required))return 0;
        }
    }
    if(legacy&&!moon_profile_equal(native_profile->id,MOON_GAME_LEGACY_PROFILE_ID))return 0;
    /* Publish identity once before any module can retain the broker. */
    game_adapter_api.profile_id=native_profile->id;game_adapter_api.profile_digest=native_profile->digest;
    game_plan_admitted=1;return 1;
}
static int moon_game_clock_required(void){
    for(unsigned int i=0;i<service_plan.count;i++)if(service_plan.mods[i].game_count)return 1;
    return 0;
}
static const void *game_find(const char *name,unsigned int abi,unsigned int size){
    if(!game_plan_admitted||!registration_thread_matches()||update_sealed||!registration_owner
       ||registration_owner>service_plan.count||!name||!size)return 0;
    MspMod *mod=service_plan.mods+registration_owner-1;if(mod->package_abi!=8)return 0;
    MspReader reader={mod->game,service_plan.end,1};
    for(unsigned int i=0;i<mod->game_count;i++){
        MspContract need;if(!msp_game_contract(&reader,&need))return 0;
        if(msp_equal(need.name,need.length,name))return abi==need.abi&&size<=need.size&&game_contract_supported(&need)
            &&game_clock.frame&&game_clock.time&&game_clock.delta?&game_clock_api:0;
    }return 0;
}
static const MoonGameAdapterApiV1 *moon_game_adapter_api(void){
    if(!game_plan_admitted||!native_profile)return 0;
    return &game_adapter_api;
}
static int moon_game_frame_enter(unsigned int hook){
    if(hook!=MOON_HOOK_UPDATE||!game_plan_admitted||MoonLab_RuntimeState_v1()!=MOON_RUNTIME_READY)return 0;
    DWORD thread=GetCurrentThreadId();
    DWORD known=__atomic_load_n(&game_frame_thread,__ATOMIC_ACQUIRE);
    if(!known){DWORD empty=0;(void)__atomic_compare_exchange_n(&game_frame_thread,&empty,thread,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);known=__atomic_load_n(&game_frame_thread,__ATOMIC_ACQUIRE);}
    if(known!=thread||game_frame_depth>=16)return 0;
    game_frame_depth++;return 1;
}
static void moon_game_frame_leave(unsigned int hook,int entered){
    if(entered&&hook==MOON_HOOK_UPDATE&&__atomic_load_n(&game_frame_thread,__ATOMIC_ACQUIRE)==GetCurrentThreadId()&&game_frame_depth)game_frame_depth--;
}
#endif
