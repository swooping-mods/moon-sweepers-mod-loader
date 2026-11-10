#ifndef MOONLAB_LOADER_INPUT_H
#define MOONLAB_LOADER_INPUT_H
/* Loader-owned registry; querying actions never intercepts native/game input. */
static int loader_input_poll(unsigned vk){
    static short (*key)(int);if(!key){PTR user=LoadLibraryW(L"user32.dll");if(user)key=(short(*)(int))GetProcAddress(user,"GetAsyncKeyState");}
    return key&&vk<256&&(key((int)vk)&0x8000)!=0;
}
#define MOON_INPUT_POLL loader_input_poll
#include "../../vendored/api/include/moon_sweepers/input_host.h"
#undef MOON_INPUT_POLL
static inline const MoonInputApiV1 *moon_input_api_v1(void){return moon_input_host_api();}
#endif
