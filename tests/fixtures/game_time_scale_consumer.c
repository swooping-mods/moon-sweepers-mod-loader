/* Independent consumer caches only typed semantic tables during startup. */
#include "moon_sweepers/game_adapter.h"
#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
static const MoonGameTimeScaleV1 *scale_api;
static int clock_available;
static unsigned int frames;
static float last_scale;
static void frame(void *actor,void *user){
    (void)actor;(void)user;
    MoonGameTimeScaleSampleV1 value={sizeof(value),MOON_GAME_TIME_SCALE_ABI,0,0};
    if(scale_api&&scale_api->sample(&value)){last_scale=value.time_scale;frames++;}
}
EXPORT int MoonLab_RuntimeServicesAbi(void){return 1;}
EXPORT int MoonLab_ModStart_v8(const MoonModContextV8 *context){
    if(!moon_mod_context_v8_valid(context)
       ||context->game->find("unity.time-scale",2,16)
       ||context->game->find("unity.time-scale",1,32)
       ||context->game->find("unity.undeclared",1,16))return 0;
    scale_api=context->game->find("unity.time-scale",1,sizeof(*scale_api));
    if(!moon_game_time_scale_valid(scale_api))return 0;
    clock_available=context->game->find("unity.clock",1,16)!=0;
    MoonGameTimeScaleSampleV1 value={sizeof(value),MOON_GAME_TIME_SCALE_ABI,123,0};
    if(scale_api->sample(&value)||value.time_scale!=123||value.reserved)return 0;
    MoonFrameSubscriptionV1 spec={sizeof(spec),MOON_PHASE_NORMAL,0,frame,0};
    return context->runtime->subscribe_frame(&spec)!=0;
}
EXPORT int probe_time_scale_sample(MoonGameTimeScaleSampleV1 *out){return scale_api&&scale_api->sample(out);}
EXPORT int probe_time_scale_clock_available(void){return clock_available;}
EXPORT unsigned int probe_time_scale_frames(void){return frames;}
EXPORT float probe_time_scale_value(void){return last_scale;}
