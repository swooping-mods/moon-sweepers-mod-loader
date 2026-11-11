#ifndef MOON_GAME_ADAPTER_H
#define MOON_GAME_ADAPTER_H
#include "game_adapter_core.h"
/* No general IL2CPP handle crosses ABI8. This family's checked metadata and
 * icall names are resolved once by the adapter and only if the plan needs it. */
static const char *game_clock_bind_failure;
static int game_clock_bind_reject(const char *stage){game_clock_bind_failure=stage;return 0;}
static int game_clock_bind(PTR domain,PTR game){
    game_clock_bind_failure=0;
    game_clock.frame=0;game_clock.time=0;game_clock.delta=0;
    if(!moon_game_clock_required())return 1;
    const PTR *(*assemblies)(PTR,U64 *)=(const PTR *(*)(PTR,U64 *))GetProcAddress(game,"il2cpp_domain_get_assemblies");
    PTR (*image)(PTR)=(PTR(*)(PTR))GetProcAddress(game,"il2cpp_assembly_get_image");
    PTR (*klass)(PTR,const char *,const char *)=(PTR(*)(PTR,const char *,const char *))GetProcAddress(game,"il2cpp_class_from_name");
    PTR (*method)(PTR,const char *,int)=(PTR(*)(PTR,const char *,int))GetProcAddress(game,"il2cpp_class_get_method_from_name");
    unsigned int (*arity)(PTR)=(unsigned int(*)(PTR))GetProcAddress(game,"il2cpp_method_get_param_count");
    unsigned int (*flags)(PTR,unsigned int *)=(unsigned int(*)(PTR,unsigned int *))GetProcAddress(game,"il2cpp_method_get_flags");
    PTR (*result)(PTR)=(PTR(*)(PTR))GetProcAddress(game,"il2cpp_method_get_return_type");
    char *(*type_name)(PTR)=(char *(*)(PTR))GetProcAddress(game,"il2cpp_type_get_name");
    void (*release)(PTR)=(void(*)(PTR))GetProcAddress(game,"il2cpp_free");
    PTR (*resolve)(const char *)=(PTR(*)(const char *))GetProcAddress(game,"il2cpp_resolve_icall");
    if(!assemblies)return game_clock_bind_reject("clock-export-assemblies");
    if(!image)return game_clock_bind_reject("clock-export-image");
    if(!klass)return game_clock_bind_reject("clock-export-class");
    if(!method)return game_clock_bind_reject("clock-export-method");
    if(!arity)return game_clock_bind_reject("clock-export-arity");
    if(!flags)return game_clock_bind_reject("clock-export-flags");
    if(!result)return game_clock_bind_reject("clock-export-return");
    if(!type_name)return game_clock_bind_reject("clock-export-type-name");
    if(!release)return game_clock_bind_reject("clock-export-free");
    if(!resolve)return game_clock_bind_reject("clock-export-icall");
    U64 count=0;const PTR *list=assemblies(domain,&count);if(!list||count>4096)return game_clock_bind_reject("clock-assemblies-bounds");
    PTR time=0;for(U64 i=0;i<count;i++){PTR k=klass(image(list[i]),"UnityEngine","Time");if(k){if(time&&time!=k)return game_clock_bind_reject("clock-class-ambiguous");time=k;}}
    if(!time)return game_clock_bind_reject("clock-class-missing");
    /* This reviewed build strips timeAsDouble. Widen scaled Time.time instead
     * of substituting realtimeSinceStartup, which changes pause/timeScale semantics. */
    const char *names[3]={"get_frameCount","get_time","get_deltaTime"};
    const char *returns[3]={"System.Int32","System.Single","System.Single"};
    const char *missing[3]={"clock-frame-method","clock-time-method","clock-delta-method"};
    const char *signature[3]={"clock-frame-signature","clock-time-signature","clock-delta-signature"};
    const char *return_type[3]={"clock-frame-return","clock-time-return","clock-delta-return"};
    for(unsigned int i=0;i<3;i++){
        PTR m=method(time,names[i],0);unsigned int implementation=0;if(!m)return game_clock_bind_reject(missing[i]);
        if(arity(m)||!(flags(m,&implementation)&0x10))return game_clock_bind_reject(signature[i]);
        char *name=type_name(result(m));int ok=name&&equal(name,returns[i]);if(name)release(name);if(!ok)return game_clock_bind_reject(return_type[i]);
    }
    game_clock.frame=(int(*)(void))resolve("UnityEngine.Time::get_frameCount()");
    game_clock.time=(float(*)(void))resolve("UnityEngine.Time::get_time()");
    game_clock.delta=(float(*)(void))resolve("UnityEngine.Time::get_deltaTime()");
    if(!game_clock.frame)return game_clock_bind_reject("clock-frame-icall");
    if(!game_clock.time)return game_clock_bind_reject("clock-time-icall");
    if(!game_clock.delta)return game_clock_bind_reject("clock-delta-icall");
    return 1;
}
__declspec(dllexport) unsigned int MoonLab_GameAdapterAbi_v1(void){return MOON_GAME_ADAPTER_ABI;}
__declspec(dllexport) const MoonGameAdapterApiV1 *MoonLab_GetGameAdapterApi_v1(void){
    return registration_thread_matches()&&registration_owner&&service_plan.mods[registration_owner-1].package_abi==8?moon_game_adapter_api():0;
}
#endif
