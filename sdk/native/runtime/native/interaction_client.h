#ifndef MOON_NATIVE_INTERACTION_CLIENT_H
#define MOON_NATIVE_INTERACTION_CLIENT_H
#include "input.h"
#include "../sdk/interaction.h"
__declspec(dllexport) int MoonLab_InteractionApiAbi(void){return MOON_INTERACTION_ABI;}
/* Exclusive native interception requires the matching process-wide loader.
 * Refuse a split local registry; standalone probes cannot qualify arbitration. */
static inline const MoonInteractionApiV1 *moon_interactions(void){
    static const MoonInteractionApiV1 *api;
    if(!api){void *loader=GetModuleHandleA("version.dll");MoonGetInteractionApiV1 get=loader?(MoonGetInteractionApiV1)GetProcAddress(loader,"MoonLab_GetInteractionApi_v1"):0;const MoonInteractionApiV1 *a=get?get():0;if(moon_interaction_api_valid(a))api=a;}
    return api;
}
static inline unsigned moon_interaction_register(const char *action,const char *binding,unsigned flags,MoonInteractionQuery query,void *context){
    const MoonInteractionApiV1 *api=moon_interactions();MoonInteractionActionV1 spec={sizeof(spec),flags,action,binding,query,context};return api?api->register_action(&spec):0;
}
static inline MoonInteractionState moon_interaction_sample(unsigned handle){const MoonInteractionApiV1 *api=moon_interactions();return api?api->sample(handle):(MoonInteractionState){0};}
static inline int moon_interaction_take(unsigned handle,void *actor){const MoonInteractionApiV1 *api=moon_interactions();return api&&api->take(handle,actor);}
#endif
