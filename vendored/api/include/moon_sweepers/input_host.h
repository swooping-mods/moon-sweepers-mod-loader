#ifndef MOONLAB_INPUT_HOST_H
#define MOONLAB_INPUT_HOST_H
#include "input_registry.h"
/* The including adapter supplies MOON_INPUT_POLL(unsigned vk). */
static MoonInputRegistry moon_input_host_registry;
static unsigned moon_input_host_register(const char *name,const char *defaults){return mi_register(&moon_input_host_registry,name,defaults);}
static MoonInputState moon_input_host_sample(unsigned handle,int allowed){return mi_sample(&moon_input_host_registry,handle,allowed);}
static int moon_input_host_describe(unsigned index,MoonInputActionInfo *info){return mi_describe(&moon_input_host_registry,index,info);}
static int moon_input_host_rebind(unsigned handle,const char *binding){return mi_rebind(&moon_input_host_registry,handle,binding);}
static void moon_input_host_configure(MoonInputResolve resolve){mi_configure(&moon_input_host_registry,resolve);}
static int moon_input_host_claim(const char *channel,unsigned long long frame,const char *owner){return mi_claim(&moon_input_host_registry,channel,frame,owner);}
static int moon_input_host_key(unsigned key){return MOON_INPUT_POLL(key);}
static inline const MoonInputApiV1 *moon_input_host_api(void){
    static const MoonInputApiV1 api={sizeof(api),MOON_INPUT_ABI,moon_input_host_register,moon_input_host_sample,moon_input_host_describe,moon_input_host_rebind,moon_input_host_configure,moon_input_host_claim,moon_input_host_key};
    moon_input_host_registry.key=moon_input_host_key;return &api;
}
#endif
