/* Independent framework binary: no game addresses, fields or IL2CPP handles. */
#include "moon_sweepers/game_adapter.h"
#include "game_clock_framework.h"
#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
static const MoonGameClockV1 *clock_api;
static int read_seconds(double *out){
    MoonGameClockSampleV1 sample={sizeof(sample),MOON_GAME_CLOCK_ABI,0,0,0};
    if(!out||!clock_api||!clock_api->sample(&sample))return 0;
    *out=sample.time_seconds;return 1;
}
static const ProbeClockFrameworkV1 api={sizeof(api),1,read_seconds};
EXPORT int MoonLab_RuntimeServicesAbi(void){return 1;}
EXPORT int MoonLab_ModStart_v8(const MoonModContextV8 *context){
    if(!moon_mod_context_v8_valid(context))return 0;
    if(context->game->find("unity.clock",2,16)||context->game->find("unity.clock",1,32)
       ||context->game->find("unity.undeclared",1,16))return 0;
    clock_api=context->game->find("unity.clock",1,sizeof(*clock_api));
    if(!moon_game_clock_valid(clock_api))return 0;
    double ignored;if(read_seconds(&ignored))return 0;
    MoonServicePublicationV1 elapsed={sizeof(elapsed),"elapsed",1,sizeof(api),&api};
    MoonServicePublicationV1 hidden={sizeof(hidden),"hidden",1,sizeof(api),&api};
    return context->runtime->publish(&elapsed)&&context->runtime->publish(&hidden);
}
