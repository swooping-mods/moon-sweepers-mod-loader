/* Production core, separate from the consumer TU so calls cannot be inlined
 * across the ABI boundary. OS hooks and engine objects are deliberately absent. */
#include "runtime_profile.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>
typedef void *PTR;typedef unsigned DWORD;typedef unsigned long long U64;typedef int BOOL;
#define __stdcall
#define __declspec(x)
BOOL VirtualProtect(PTR p,U64 n,DWORD flags,DWORD *old){(void)p;(void)n;(void)flags;*old=4;return 1;}
PTR GetCurrentProcess(void){return (PTR)1;}
DWORD GetCurrentThreadId(void){return 1;}
BOOL FlushInstructionCache(PTR p,const void *a,U64 n){(void)p;(void)a;(void)n;return 1;}
#include "../../runtime/loader/dispatch.h"
PTR AddVectoredExceptionHandler(DWORD first,int (*handler)(ExceptionPointers *)){(void)first;(void)handler;return (PTR)1;}
DWORD RemoveVectoredExceptionHandler(PTR p){(void)p;return 1;}
#include "moon_sweepers/interaction_registry.h"
static ProfileTable tables[256];
static MoonInputRegistry input;
static MoonInteractionRegistry interactions;
static unsigned char physical[256];
static unsigned interaction_count;
static uint32_t frame_digest;
static unsigned long long calls,queries,polls;
static uint32_t apply(const ProfileTable *table,uint32_t value){
#ifdef PROFILE_VERIFY
    calls++;
#endif
    return value*table->factor+table->bias;
}
static void frame(void *walker,void *user){
    const ProfileTable *table=user;
    frame_digest=(frame_digest<<5|frame_digest>>27)^table->apply(table,*(const uint32_t *)walker);
}
static int poll(unsigned key){
#ifdef PROFILE_VERIFY
    polls++;
#endif
    return physical[key];
}
static int query(void *context,void *walker,MoonInteractionTarget *target){
#ifdef PROFILE_VERIFY
    queries++;
#endif
    if(walker!=(void *)1)return 0;
    unsigned i=(unsigned)(uintptr_t)context;
    *target=(MoonInteractionTarget){i,(float)(interaction_count-i+1)*.25f,0,i*3};return 1;
}
const MoonRuntimeApiV1 *profile_prepare(unsigned services,unsigned count){
    if(!services||services>256||services%4||!count||count>128)return 0;
    static unsigned char code[5]={0x48,0x8b,0xc4,0,0};update_address=code;
    const MoonRuntimeApiV1 *api=MoonLab_GetRuntimeApi_v1();
    for(unsigned owner=0;owner<services/4;owner++){
        char name[65];snprintf(name,sizeof(name),"provider-%02u",owner);
        if(!begin_runtime_registration(owner+1,name))return 0;
        for(unsigned j=0;j<4;j++){
            unsigned i=owner*4+j;tables[i]=(ProfileTable){sizeof(ProfileTable),1,i*2+3,0x9e3779b9u^i,apply};
            char service[16];snprintf(service,sizeof(service),"service-%u",j);
            MoonServicePublicationV1 spec={sizeof(spec),service,1,sizeof(ProfileTable),tables+i};
            if(!api->publish(&spec))return 0;
        }
        MoonFrameSubscriptionV1 spec={sizeof(spec),MOON_PHASE_NORMAL,0,frame,tables+owner*4};
        if(!api->subscribe_frame(&spec)||!finish_runtime_registration(1))return 0;
    }
    if(!runtime_finish_startup(seal_updates())||MoonLab_RuntimeState_v1()!=MOON_RUNTIME_READY)return 0;
    input.key=poll;interaction_count=count;
    for(unsigned i=1;i<=count;i++){
        char name[96];snprintf(name,sizeof(name),"independent.action-%03u",i);
        MoonInteractionActionV1 spec={sizeof(spec),MOON_INTERACTION_EXCLUSIVE,name,"E",query,(void *)(uintptr_t)i};
        if(!mir_register(&interactions,&input,&spec,1))return 0;
    }
    return api;
}
void profile_reset_counts(void){calls=queries=polls=0;}
unsigned long long profile_calls(void){return calls;}
unsigned long long profile_queries(void){return queries;}
unsigned long long profile_polls(void){return polls;}
void profile_frame_reset(void){frame_digest=0x12345678;}
void profile_frame(uint32_t value){Context c={0};c.rcx=(U64)(uintptr_t)&value;(void)dispatch_update(MOON_HOOK_UPDATE,&c);}
uint32_t profile_frame_digest(void){return frame_digest;}
void profile_interaction(unsigned long long epoch,unsigned *target,unsigned *take){
    physical['E']=(epoch%4==1||epoch%4==2);
    mir_begin(&interactions,&input,epoch,(void *)1);
    MoonInteractionState state=mir_sample(&interactions,interaction_count);
    *target=state.selected?(unsigned)state.target:0;
    *take=(unsigned)mir_take(&interactions,interaction_count);
    /* A repeated prompt read/take must not repeat queries or consume twice. */
    if(mir_sample(&interactions,interaction_count).target!=state.target||mir_take(&interactions,interaction_count))*target=0;
}
