#ifndef MOONLAB_LOADER_INPUT_H
#define MOONLAB_LOADER_INPUT_H
#include "../native/hook_context.h"
/* Interaction is an explicit adapter over the unchanged InputApiV1 table. */
static void moon_interaction_pump(void);
static int loader_interaction_admit(unsigned,unsigned);
static int loader_interaction_poll(unsigned);
#define MOON_INPUT_BEFORE_SAMPLE() moon_interaction_pump()
#define MOON_INPUT_ADMIT(action,key) loader_interaction_admit(action,key)
static int loader_input_poll(unsigned vk){
    int coherent=loader_interaction_poll(vk);if(coherent>=0)return coherent;
    static short (*key)(int);if(!key){PTR user=LoadLibraryW(L"user32.dll");if(user)key=(short(*)(int))GetProcAddress(user,"GetAsyncKeyState");}
    return key&&vk<256&&(key((int)vk)&0x8000)!=0;
}
#define MOON_INPUT_POLL loader_input_poll
#include "../../vendored/api/include/moon_sweepers/input_host.h"
#undef MOON_INPUT_POLL
#undef MOON_INPUT_BEFORE_SAMPLE
#undef MOON_INPUT_ADMIT
#include "../../vendored/api/include/moon_sweepers/interaction_registry.h"
static MoonInteractionRegistry loader_interactions;
#define MOON_LOADER_INPUT_PREFLIGHT(walker) moon_interaction_observe(walker)
#define MOON_LOADER_INTERACTION_SEAL() moon_interaction_seal()
#define MOON_LOADER_INTERACTION_FINISH(success) moon_interaction_finish(success)
#define MOON_LOADER_INTERACTION_COUNT loader_interactions.count
static void moon_interaction_observe(PTR);
static int moon_interaction_seal(void);
static void moon_interaction_finish(int);
#define MOON_LOADER_INPUT_HOOK(id,context) moon_interaction_native(id,context)
static int moon_interaction_native(int,Context *);
static inline const MoonInputApiV1 *moon_input_api_v1(void){return moon_input_host_api();}
#endif
