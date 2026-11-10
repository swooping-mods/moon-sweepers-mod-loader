/* One registry owns the supported native hooks. Registration is scoped to each
 * ModStart; tables become immutable before any breakpoint is published. */
#include "../native/hook_context.h"
#include "sdk.h"
__declspec(dllimport) PTR __stdcall GetCurrentProcess(void);
__declspec(dllimport) DWORD __stdcall GetCurrentThreadId(void);
__declspec(dllimport) BOOL __stdcall FlushInstructionCache(PTR,const void *,U64);
__declspec(dllimport) PTR __stdcall AddVectoredExceptionHandler(DWORD,int (*)(ExceptionPointers *));
__declspec(dllimport) DWORD __stdcall RemoveVectoredExceptionHandler(PTR);
#include "../native/hook_engine.h"
#include "camera.h"
#define MOONLAB_MAX_NATIVE_MODS 64
#define MOONLAB_MAX_SUBSCRIPTIONS (2*MOONLAB_MAX_NATIVE_MODS+3)
typedef struct {
    MoonHookSubscriptionV1 spec;unsigned int handle,owner;
    MoonFrameCallback frame_callback;void *frame_user;
} HookSubscription;
static HookSubscription subscriptions[MOONLAB_MAX_SUBSCRIPTIONS];
static unsigned int subscription_count,next_subscription,registration_owner;
static DWORD registration_thread;
static int update_sealed,late_override_active;
static PTR update_address,vehicle_address,late_update_address;
static int registration_thread_matches(void){return GetCurrentThreadId()==__atomic_load_n(&registration_thread,__ATOMIC_ACQUIRE);}
/* The freestanding proxy links without a C runtime, including implicit memcpy
 * emitted for larger registry records. Keep these copies explicit. */
static void registry_copy(void *out,const void *in,U64 size){
    for(U64 i=0;i<size;i++)((unsigned char *)out)[i]=((const unsigned char *)in)[i];
}

static PTR hook_address(unsigned int hook){
    switch(hook){case MOON_HOOK_UPDATE:return update_address;
    case MOON_HOOK_LATE_UPDATE:return late_update_address;
    case MOON_HOOK_VEHICLE_FIXED:return vehicle_address;default:return 0;}
}
static int begin_hook_registration(unsigned int owner){
    if(update_sealed||registration_owner||!owner)return 0;
    DWORD thread=GetCurrentThreadId();
    DWORD registered=__atomic_load_n(&registration_thread,__ATOMIC_ACQUIRE);
    if(registered&&registered!=thread)return 0;
    __atomic_store_n(&registration_thread,thread,__ATOMIC_RELEASE);
    registration_owner=owner;return 1;
}
static void finish_hook_registration(int success){
    if(!registration_thread_matches()||!registration_owner)return;
    if(!success)for(unsigned int i=0;i<subscription_count;){
        if(subscriptions[i].owner!=registration_owner){i++;continue;}
        for(unsigned int j=i+1;j<subscription_count;j++)registry_copy(&subscriptions[j-1],&subscriptions[j],sizeof(subscriptions[j]));
        subscription_count--;
    }
    registration_owner=0;
}
static unsigned int subscribe_observer(const MoonHookSubscriptionV1 *spec,MoonFrameCallback frame,void *user){
    if(!registration_thread_matches())return 0;
    if(update_sealed||!registration_owner||!spec||spec->size!=sizeof(*spec)
       ||subscription_count>=MOONLAB_MAX_SUBSCRIPTIONS||next_subscription==(unsigned int)-1)return 0;
    PTR address=hook_address(spec->hook);
    if(!address||!instruction_length(address)||spec->phase>MOON_PHASE_LATE)return 0;
    int observer=spec->role==MOON_ROLE_OBSERVER;
    if(!observer&&(spec->phase!=MOON_PHASE_NORMAL||spec->priority))return 0;
    if(spec->hook==MOON_HOOK_UPDATE||spec->hook==MOON_HOOK_LATE_UPDATE){
        if((!spec->callback&&!frame)||(spec->callback&&frame)||spec->vehicle_callback
           ||(!observer&&(spec->hook!=MOON_HOOK_LATE_UPDATE||spec->role!=MOON_ROLE_OVERRIDE)))return 0;
        if(frame&&(spec->hook!=MOON_HOOK_UPDATE||!observer))return 0;
    }else if(spec->hook==MOON_HOOK_VEHICLE_FIXED){
        if(spec->callback||!spec->vehicle_callback||(spec->role!=MOON_ROLE_INPUT&&spec->role!=MOON_ROLE_PHYSICS))return 0;
    }else return 0;
    unsigned int count=0;
    for(unsigned int i=0;i<subscription_count;i++){
        const MoonHookSubscriptionV1 *other=&subscriptions[i].spec;
        if(other->hook!=spec->hook)continue;
        if((spec->callback&&spec->callback==other->callback)
           ||(spec->vehicle_callback&&spec->vehicle_callback==other->vehicle_callback)
           ||(frame&&frame==subscriptions[i].frame_callback&&user==subscriptions[i].frame_user))return 0;
        if(other->role==spec->role){if(!observer)return 0;count++;}
    }
    if(observer&&count>=MOONLAB_MAX_NATIVE_MODS)return 0;
    HookSubscription *slot=&subscriptions[subscription_count++];
    slot->spec=*spec;slot->owner=registration_owner;slot->handle=++next_subscription;
    slot->frame_callback=frame;slot->frame_user=user;
    return slot->handle;
}
static unsigned int hook_subscribe(const MoonHookSubscriptionV1 *spec){return subscribe_observer(spec,0,0);}
static int hook_unsubscribe(unsigned int handle){
    if(!registration_thread_matches())return 0;
    if(update_sealed||!registration_owner||!handle)return 0;
    for(unsigned int i=0;i<subscription_count;i++)if(subscriptions[i].handle==handle){
        if(subscriptions[i].owner!=registration_owner)return 0;
        for(unsigned int j=i+1;j<subscription_count;j++)registry_copy(&subscriptions[j-1],&subscriptions[j],sizeof(subscriptions[j]));
        subscription_count--;return 1;
    }
    return 0;
}
__declspec(dllexport) int MoonLab_CameraOverrideActive_v1(void){return late_override_active;}
static const MoonHookApiV1 hook_api={sizeof(MoonHookApiV1),1,hook_subscribe,hook_unsubscribe,MoonLab_CameraOverrideActive_v1};
__declspec(dllexport) const MoonHookApiV1 *MoonLab_GetHookApi_v1(void){return &hook_api;}
#include "services.h"

static void copy_context(Context *out,const Context *in){
    for(U64 i=0;i<sizeof(*out);i++)((unsigned char *)out)[i]=((const unsigned char *)in)[i];
}
static int dispatch_update(int id,Context *context){
    moon_camera_observe_thread();
    unsigned int hook=(unsigned int)id;int skip=0;
    MoonVehicleInput input={0};
    /* The role boundary is invariant even if registration order is reversed. */
    if(hook==MOON_HOOK_LATE_UPDATE||hook==MOON_HOOK_VEHICLE_FIXED){
        for(unsigned int i=0;i<subscription_count;i++){
            const MoonHookSubscriptionV1 *spec=&subscriptions[i].spec;
            if(spec->hook!=hook)continue;
            Context copy;copy_context(&copy,context);
            if(spec->role==MOON_ROLE_OVERRIDE)skip=spec->callback(spec->local_id,&copy)!=0;
            else if(spec->role==MOON_ROLE_INPUT){
                spec->vehicle_callback(spec->local_id,&copy,&input);
                if(!moon_vehicle_input_valid(&input))input=(MoonVehicleInput){0};
            }
        }
        if(hook==MOON_HOOK_LATE_UPDATE)late_override_active=skip;
    }
    for(unsigned int i=0;i<subscription_count;i++){
        const MoonHookSubscriptionV1 *spec=&subscriptions[i].spec;
        if(spec->hook!=hook)continue;
        if(spec->role==MOON_ROLE_OBSERVER){
            if(subscriptions[i].frame_callback)
                subscriptions[i].frame_callback((void *)context->rcx,subscriptions[i].frame_user);
            else{
                Context copy;copy_context(&copy,context);
                spec->callback(spec->local_id,&copy);
            }
        }else if(spec->role==MOON_ROLE_PHYSICS){
            /* Legacy physics owns its return register as well as cancellation. */
            skip=spec->vehicle_callback(spec->local_id,context,&input)!=0;
        }
    }
    return skip;
}
static unsigned int legacy_subscribe(unsigned int hook,unsigned int role,int id,MoonHookCallback callback,MoonHookVehicleCallback vehicle_callback){
    MoonHookSubscriptionV1 spec={sizeof(spec),hook,role,MOON_PHASE_NORMAL,0,id,callback,vehicle_callback};
    return hook_subscribe(&spec);
}
/* Binary compatibility shims use exactly the same registry and ownership rules. */
__declspec(dllexport) int MoonLab_RegisterUpdate_v1(PTR address,DWORD token,int id,MoonHookCallback callback){
    return address&&address==update_address&&token==100671733
        &&legacy_subscribe(MOON_HOOK_UPDATE,MOON_ROLE_OBSERVER,id,callback,0)!=0;
}
__declspec(dllexport) int MoonLab_RegisterLateUpdate_v1(PTR address,DWORD token,int role,int id,MoonHookCallback callback){
    return address&&address==late_update_address&&token==100671741&&(role==1||role==2)
        &&legacy_subscribe(MOON_HOOK_LATE_UPDATE,role==1?MOON_ROLE_OBSERVER:MOON_ROLE_OVERRIDE,id,callback,0)!=0;
}
__declspec(dllexport) int MoonLab_RegisterVehicle_v1(PTR address,DWORD token,int role,int id,MoonHookVehicleCallback callback){
    return address&&address==vehicle_address&&token==100669323&&(role==1||role==2)
        &&legacy_subscribe(MOON_HOOK_VEHICLE_FIXED,role==1?MOON_ROLE_INPUT:MOON_ROLE_PHYSICS,id,0,callback)!=0;
}
static int seal_updates(void){
    if(update_sealed||registration_owner)return 0;
    __atomic_store_n(&update_sealed,1,__ATOMIC_RELEASE);
    /* Stable insertion ordering: phase, ascending priority, registration order.
     * Default registrations therefore preserve dependency/ID startup order. */
    for(unsigned int i=1;i<subscription_count;i++){
        HookSubscription value;registry_copy(&value,&subscriptions[i],sizeof(value));unsigned int j=i;
        while(j&&(subscriptions[j-1].spec.phase>value.spec.phase
              ||(subscriptions[j-1].spec.phase==value.spec.phase&&subscriptions[j-1].spec.priority>value.spec.priority))){
            registry_copy(&subscriptions[j],&subscriptions[j-1],sizeof(subscriptions[j]));j--;
        }
        registry_copy(&subscriptions[j],&value,sizeof(value));
    }
    for(unsigned int kind=MOON_HOOK_UPDATE;kind<=MOON_HOOK_VEHICLE_FIXED;kind++){
        int used=0;
        for(unsigned int i=0;i<subscription_count;i++)if(subscriptions[i].spec.hook==kind){used=1;break;}
        if(!used)continue;
        unsigned char *address=hook_address(kind);int length=instruction_length(address);
        if(!length||hook_count>=8)return 0;
        for(int i=0;i<hook_count;i++)if(hooks[i].address==address)return 0;
        Hook *hook=&hooks[hook_count++];hook->address=address;hook->length=length;hook->id=(int)kind;
        for(int i=0;i<5;i++)hook->original[i]=address[i];
    }
    before_hook=dispatch_update;
    return !hook_count||install_local_hooks();
}
