/* Included by dispatch.h: registry mutations use its bootstrap scope/thread.
 * The loader retains all modules; publication stores opaque resident pointers. */
#define MOONLAB_MAX_SERVICES (MOONLAB_MAX_NATIVE_MODS*4)
#include "service_plan.h"
typedef struct {
    char provider_id[65],service_id[161];
    unsigned int owner,abi,api_size;const void *api;int committed;
} RuntimeService;
static RuntimeService runtime_services[MOONLAB_MAX_SERVICES];
static unsigned int runtime_service_count;
static unsigned int runtime_startup_state;
__declspec(dllexport) unsigned int MoonLab_RuntimeState_v1(void){
    return __atomic_load_n(&runtime_startup_state,__ATOMIC_ACQUIRE);
}
static inline void runtime_startup_failed(void){
    __atomic_store_n(&runtime_startup_state,MOON_RUNTIME_FAILED,__ATOMIC_RELEASE);
}
static inline int runtime_finish_startup(int hooks_installed){
    if(MoonLab_RuntimeState_v1()!=MOON_RUNTIME_PENDING)return 0;
    if(!hooks_installed||!update_sealed||registration_owner
       ||(service_plan.active&&service_plan.next_owner!=service_plan.count)){
        runtime_startup_failed();return 0;
    }
    __atomic_store_n(&runtime_startup_state,MOON_RUNTIME_READY,__ATOMIC_RELEASE);return 1;
}
static char runtime_registration_id[65];
static int runtime_id_valid(const char *id,unsigned int maximum){
    if(!id||!*id)return 0;
    unsigned int n=0;
    while(id[n]){char c=id[n];if(n>=maximum||!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-'||c=='.'||c=='_'))return 0;n++;}
    return 1;
}
static int runtime_id_equal(const char *a,const char *b){
    while(*a&&*a==*b){a++;b++;}return *a==*b;
}
static void runtime_id_copy(char *out,const char *in){while((*out++=*in++)){} }
static int runtime_publish(const MoonServicePublicationV1 *spec){
    if(!registration_thread_matches())return 0;
    if(update_sealed||!registration_owner||!runtime_registration_id[0]||!spec
       ||(spec->size!=sizeof(*spec)&&spec->size!=sizeof(MoonServicePublicationLimitsV1))
       ||!runtime_id_valid(spec->service_id,160)||!spec->abi||!spec->api_size||spec->api_size>65536||!spec->api
       ||runtime_service_count>=MOONLAB_MAX_SERVICES)return 0;
    if(spec->size==sizeof(MoonServicePublicationLimitsV1)){
        const MoonServicePublicationLimitsV1 *extended=(const MoonServicePublicationLimitsV1 *)spec;
        if(extended->reserved||extended->limit_count>MSP_MAX_LIMITS
           ||(extended->limit_count&&!extended->limits))return 0;
    }
    if(!msp_publication(runtime_registration_id,spec))return 0;
    for(unsigned int i=0;i<runtime_service_count;i++){
        RuntimeService *entry=&runtime_services[i];
        if(entry->abi==spec->abi&&runtime_id_equal(entry->provider_id,runtime_registration_id)
           &&runtime_id_equal(entry->service_id,spec->service_id))return 0;
    }
    RuntimeService *entry=&runtime_services[runtime_service_count++];
    runtime_id_copy(entry->provider_id,runtime_registration_id);runtime_id_copy(entry->service_id,spec->service_id);
    entry->owner=registration_owner;entry->abi=spec->abi;entry->api_size=spec->api_size;
    entry->api=spec->api;entry->committed=0;return 1;
}
static const void *runtime_find(const char *provider,const char *service,unsigned int abi,unsigned int size){
    /* During mutable startup only the bootstrap worker may read. After sealing
     * the registry is immutable; provider functions define their own threads. */
    if(!__atomic_load_n(&update_sealed,__ATOMIC_ACQUIRE)&&!registration_thread_matches())return 0;
    if(!runtime_id_valid(provider,64)||!runtime_id_valid(service,160)||!abi||!size||size>65536)return 0;
    for(unsigned int i=0;i<runtime_service_count;i++){
        const RuntimeService *entry=&runtime_services[i];
        if(entry->committed&&entry->abi==abi&&entry->api_size>=size
           &&runtime_id_equal(entry->provider_id,provider)&&runtime_id_equal(entry->service_id,service))return entry->api;
    }
    return 0;
}
static unsigned int runtime_subscribe_frame(const MoonFrameSubscriptionV1 *spec){
    if(!registration_thread_matches())return 0;
    if(!spec||spec->size!=sizeof(*spec)||!spec->callback)return 0;
    MoonHookSubscriptionV1 hook={sizeof(hook),MOON_HOOK_UPDATE,MOON_ROLE_OBSERVER,spec->phase,spec->priority,0,0,0};
    return subscribe_observer(&hook,spec->callback,spec->user);
}
static const MoonRuntimeApiV1 runtime_api={sizeof(MoonRuntimeApiV1),MOON_RUNTIME_SERVICES_ABI,
    runtime_publish,runtime_find,runtime_subscribe_frame,hook_unsubscribe};
__declspec(dllexport) const MoonRuntimeApiV1 *MoonLab_GetRuntimeApi_v1(void){return &runtime_api;}
static inline int begin_runtime_registration(unsigned int owner,const char *id){
    if(!runtime_id_valid(id,64)||!msp_identity(owner,id)||!begin_hook_registration(owner))return 0;
    runtime_id_copy(runtime_registration_id,id);
    if(!msp_requirements(owner,runtime_find)){
        runtime_registration_id[0]=0;finish_hook_registration(0);return 0;
    }
    return 1;
}
static inline int finish_runtime_registration(int success){
    /* Both API pointers and scheduled callbacks belong to this exact scope. */
    if(!registration_thread_matches()||!registration_owner)return 0;
    if(success&&service_plan.active){
        unsigned int count=0;
        for(unsigned int i=0;i<runtime_service_count;i++)if(runtime_services[i].owner==registration_owner)count++;
        if(count!=service_plan.mods[registration_owner-1].provides_count)success=0;
    }
    for(unsigned int i=0;i<runtime_service_count;){
        RuntimeService *entry=&runtime_services[i];
        if(entry->owner!=registration_owner){i++;continue;}
        if(success){entry->committed=1;i++;continue;}
        for(unsigned int j=i+1;j<runtime_service_count;j++)registry_copy(&runtime_services[j-1],&runtime_services[j],sizeof(runtime_services[j]));
        runtime_service_count--;
    }
    if(success&&service_plan.active)service_plan.next_owner++;
    runtime_registration_id[0]=0;finish_hook_registration(success);return success;
}
