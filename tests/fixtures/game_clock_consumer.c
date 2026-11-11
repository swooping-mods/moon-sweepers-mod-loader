/* Framework-only feature, compiled once and reused for both profile adapters. */
#include "moon_sweepers/game_adapter.h"
#include "game_clock_framework.h"
#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
static const ProbeClockFrameworkV1 *framework;
static double value;static unsigned int frames;
static void frame(void *opaque_actor,void *user){
    (void)opaque_actor;(void)user;double seconds=0;
    if(framework&&framework->read_seconds(&seconds)){value=seconds*2;frames++;}
}
#ifndef PROBE_RUNTIME_MARKER
#define PROBE_RUNTIME_MARKER 1
#endif
#ifndef PROBE_OMIT_RUNTIME_MARKER
EXPORT int MoonLab_RuntimeServicesAbi(void){return PROBE_RUNTIME_MARKER;}
#endif
EXPORT int MoonLab_ModStart_v8(const MoonModContextV8 *context){
    if(!moon_mod_context_v8_valid(context)||context->game->find("unity.clock",1,16)
       ||context->runtime->find("clock-framework","hidden",1,16)
       ||context->runtime->find("clock-framework","elapsed",1,32))return 0;
    framework=context->runtime->find("clock-framework","elapsed",1,sizeof(*framework));
    if(!framework||framework->abi!=1||framework->size<sizeof(*framework))return 0;
    MoonFrameSubscriptionV1 spec={sizeof(spec),MOON_PHASE_NORMAL,0,frame,0};
    return context->runtime->subscribe_frame(&spec)!=0;
}
EXPORT unsigned int probe_frames(void){return frames;}
EXPORT double probe_value(void){return value;}
EXPORT int probe_outside(void){double ignored;return framework&&framework->read_seconds(&ignored);}
