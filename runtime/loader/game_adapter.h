#ifndef MOON_GAME_ADAPTER_H
#define MOON_GAME_ADAPTER_H
#include "game_adapter_core.h"
/* No general IL2CPP handle crosses ABI8. This family's checked metadata and
 * icall names are resolved once by the adapter and only if the plan needs it. */
static int game_clock_bind(PTR domain,PTR game){
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
    if(!assemblies||!image||!klass||!method||!arity||!flags||!result||!type_name||!release||!resolve)return 0;
    U64 count=0;const PTR *list=assemblies(domain,&count);if(!list||count>4096)return 0;
    PTR time=0;for(U64 i=0;i<count;i++){PTR k=klass(image(list[i]),"UnityEngine","Time");if(k){if(time&&time!=k)return 0;time=k;}}
    if(!time)return 0;
    const char *names[3]={"get_frameCount","get_timeAsDouble","get_deltaTime"};
    const char *returns[3]={"System.Int32","System.Double","System.Single"};
    for(unsigned int i=0;i<3;i++){
        PTR m=method(time,names[i],0);unsigned int implementation=0;if(!m||arity(m)||!(flags(m,&implementation)&0x10))return 0;
        char *name=type_name(result(m));int ok=name&&equal(name,returns[i]);if(name)release(name);if(!ok)return 0;
    }
    game_clock.frame=(int(*)(void))resolve("UnityEngine.Time::get_frameCount()");
    game_clock.time=(double(*)(void))resolve("UnityEngine.Time::get_timeAsDouble()");
    game_clock.delta=(float(*)(void))resolve("UnityEngine.Time::get_deltaTime()");
    return game_clock.frame&&game_clock.time&&game_clock.delta;
}
__declspec(dllexport) unsigned int MoonLab_GameAdapterAbi_v1(void){return MOON_GAME_ADAPTER_ABI;}
__declspec(dllexport) const MoonGameAdapterApiV1 *MoonLab_GetGameAdapterApi_v1(void){
    return registration_thread_matches()&&registration_owner&&service_plan.mods[registration_owner-1].package_abi==8?moon_game_adapter_api():0;
}
#endif
