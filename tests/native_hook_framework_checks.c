/* Owned synthetic native functions. Exercises the public ABI and legacy mix. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include "../vendored/api/include/moon_sweepers/hooks.h"
/* The SDK must compile before any loader/Windows typedefs. */
typedef void *PTR;typedef unsigned int DWORD;typedef unsigned long long U64;typedef int BOOL;
#define __stdcall
#define __declspec(x)
BOOL VirtualProtect(PTR p,U64 n,DWORD flags,DWORD *old){(void)p;(void)n;(void)flags;*old=4;return 1;}
PTR GetCurrentProcess(void){return (PTR)1;}
static DWORD fake_thread=1;
DWORD GetCurrentThreadId(void){return fake_thread;}
BOOL FlushInstructionCache(PTR p,const void *a,U64 n){(void)p;(void)a;(void)n;return 1;}
#include "../runtime/loader/dispatch.h"
PTR AddVectoredExceptionHandler(DWORD first,int (*handler)(ExceptionPointers *)){(void)first;(void)handler;return (PTR)1;}
DWORD RemoveVectoredExceptionHandler(PTR p){(void)p;return 1;}
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}}while(0)
static unsigned char code[3][5];
static int seen[128],calls,isolated=1;
static int observe(int id,MoonHookContext *context){
    if(context->rcx!=17)isolated=0;
    seen[calls++]=id;context->rcx=999;context->rip=999;return 1;
}
/* Different real functions allow a genuine full-table/callback uniqueness test. */
#define OBSERVER(N) static int observer_##N(int id,MoonHookContext *c){return observe(id,c);}
OBSERVER(0)
OBSERVER(1)
OBSERVER(2)
OBSERVER(3)
OBSERVER(4)
OBSERVER(5)
OBSERVER(6)
OBSERVER(7)
OBSERVER(8)
OBSERVER(9)
OBSERVER(10)
OBSERVER(11)
OBSERVER(12)
OBSERVER(13)
OBSERVER(14)
OBSERVER(15)
OBSERVER(16)
OBSERVER(17)
OBSERVER(18)
OBSERVER(19)
OBSERVER(20)
OBSERVER(21)
OBSERVER(22)
OBSERVER(23)
OBSERVER(24)
OBSERVER(25)
OBSERVER(26)
OBSERVER(27)
OBSERVER(28)
OBSERVER(29)
OBSERVER(30)
OBSERVER(31)
OBSERVER(32)
OBSERVER(33)
OBSERVER(34)
OBSERVER(35)
OBSERVER(36)
OBSERVER(37)
OBSERVER(38)
OBSERVER(39)
OBSERVER(40)
OBSERVER(41)
OBSERVER(42)
OBSERVER(43)
OBSERVER(44)
OBSERVER(45)
OBSERVER(46)
OBSERVER(47)
OBSERVER(48)
OBSERVER(49)
OBSERVER(50)
OBSERVER(51)
OBSERVER(52)
OBSERVER(53)
OBSERVER(54)
OBSERVER(55)
OBSERVER(56)
OBSERVER(57)
OBSERVER(58)
OBSERVER(59)
OBSERVER(60)
OBSERVER(61)
OBSERVER(62)
OBSERVER(63)
OBSERVER(64)
static MoonHookCallback observers[]={observer_0,observer_1,observer_2,observer_3,observer_4,observer_5,observer_6,observer_7,observer_8,observer_9,observer_10,observer_11,observer_12,observer_13,observer_14,observer_15,observer_16,observer_17,observer_18,observer_19,observer_20,observer_21,observer_22,observer_23,observer_24,observer_25,observer_26,observer_27,observer_28,observer_29,observer_30,observer_31,observer_32,observer_33,observer_34,observer_35,observer_36,observer_37,observer_38,observer_39,observer_40,observer_41,observer_42,observer_43,observer_44,observer_45,observer_46,observer_47,observer_48,observer_49,observer_50,observer_51,observer_52,observer_53,observer_54,observer_55,observer_56,observer_57,observer_58,observer_59,observer_60,observer_61,observer_62,observer_63,observer_64};
static void reset(void){
    hook_count=update_sealed=late_override_active=0;
    subscription_count=next_subscription=registration_owner=0;calls=0;isolated=1;
    for(int i=0;i<3;i++){code[i][0]=0x48;code[i][1]=0x8b;code[i][2]=0xc4;code[i][3]=code[i][4]=0;}
    update_address=code[0];late_update_address=code[1];vehicle_address=code[2];
}
static MoonHookSubscriptionV1 observer(unsigned int hook,int index,unsigned int phase,int priority){
    MoonHookSubscriptionV1 spec={sizeof(spec),hook,MOON_ROLE_OBSERVER,phase,priority,index,observers[index],0};return spec;
}
static int camera(int id,MoonHookContext *c){(void)id;seen[calls++]=77;c->rcx=99;return 1;}
static int input(int id,MoonHookContext *c,MoonVehicleInput *value){(void)id;c->rcx=99;value->valid=1;value->throttle=2;return 1;}
static int physics(int id,MoonHookContext *c,MoonVehicleInput *value){(void)id;return c->rcx==17&&!value->valid&&value->throttle==0;}
int main(void){
    const MoonHookApiV1 *api=MoonLab_GetHookApi_v1();CHECK(moon_hook_api_valid(api));
    MoonHookApiV1 bad=*api;bad.abi=2;CHECK(!moon_hook_api_valid(&bad));bad=*api;bad.size--;CHECK(!moon_hook_api_valid(&bad));
    reset();MoonHookSubscriptionV1 spec=observer(MOON_HOOK_UPDATE,0,MOON_PHASE_NORMAL,0);
    CHECK(!api->subscribe(&spec));CHECK(!begin_hook_registration(0));CHECK(begin_hook_registration(1));CHECK(!begin_hook_registration(2));
    CHECK(!seal_updates());CHECK(!api->subscribe(0));
    spec.size--;CHECK(!api->subscribe(&spec));spec.size++;
    spec.hook=999;CHECK(!api->subscribe(&spec));spec.hook=MOON_HOOK_UPDATE;
    spec.phase=999;CHECK(!api->subscribe(&spec));spec.phase=MOON_PHASE_NORMAL;
    spec.role=MOON_ROLE_OVERRIDE;CHECK(!api->subscribe(&spec));spec.role=MOON_ROLE_OBSERVER;
    spec.vehicle_callback=input;CHECK(!api->subscribe(&spec));spec.vehicle_callback=0;
    unsigned int handle=api->subscribe(&spec);CHECK(handle&&subscription_count==1&&hook_count==0);
    fake_thread=2;CHECK(!api->subscribe(&spec)&&!api->unsubscribe(handle));fake_thread=1;
    CHECK(!api->subscribe(&spec));CHECK(!api->unsubscribe(0));CHECK(api->unsubscribe(handle));CHECK(!api->unsubscribe(handle));
    unsigned int replacement=api->subscribe(&spec);CHECK(replacement&&replacement!=handle);
    finish_hook_registration(1);CHECK(!api->unsubscribe(replacement));CHECK(!api->subscribe(&spec));
    CHECK(begin_hook_registration(2));CHECK(!api->unsubscribe(replacement));
    MoonHookSubscriptionV1 temporary=observer(MOON_HOOK_UPDATE,1,MOON_PHASE_NORMAL,0);
    unsigned int removed=api->subscribe(&temporary);CHECK(removed);finish_hook_registration(0);
    CHECK(subscription_count==1&&subscriptions[0].handle==replacement&&hook_count==0&&code[0][0]==0x48);
    CHECK(begin_hook_registration(3));CHECK(!api->unsubscribe(removed));finish_hook_registration(0);CHECK(subscription_count==1);

    reset();CHECK(begin_hook_registration(1));
    const unsigned int phases[]={MOON_PHASE_LATE,MOON_PHASE_EARLY,MOON_PHASE_EARLY,MOON_PHASE_NORMAL,MOON_PHASE_NORMAL,MOON_PHASE_LATE};
    const int priorities[]={INT_MIN,10,-4,0,0,INT_MAX};
    for(int i=0;i<6;i++){spec=observer(MOON_HOOK_UPDATE,i,phases[i],priorities[i]);CHECK(api->subscribe(&spec));}
    finish_hook_registration(1);CHECK(seal_updates());CHECK(hook_count==1&&code[0][0]==0xcc);
    U64 stack[4]={123,0,0,0};Context c={0};c.rsp=(U64)stack;c.rcx=17;
    ExceptionRecord record={.code=0x80000003,.address=code[0]};ExceptionPointers e={&record,&c};
    CHECK(exception_handler(&e)==-1);const int expected[]={2,1,3,4,0,5};
    CHECK(calls==6&&!memcmp(seen,expected,sizeof(expected))&&isolated&&c.rcx==17&&c.rip==(U64)code[0]+3&&c.rsp==(U64)stack);
    CHECK(!begin_hook_registration(2)&&!api->subscribe(&spec)&&!api->unsubscribe(1)&&!seal_updates());

    reset();CHECK(begin_hook_registration(1));
    spec=observer(MOON_HOOK_LATE_UPDATE,0,MOON_PHASE_EARLY,INT_MIN);CHECK(api->subscribe(&spec));
    CHECK(MoonLab_RegisterLateUpdate_v1(code[1],100671741,2,0,camera));
    MoonHookSubscriptionV1 wheel={sizeof(wheel),MOON_HOOK_VEHICLE_FIXED,MOON_ROLE_INPUT,MOON_PHASE_NORMAL,0,0,0,input};
    wheel.priority=1;CHECK(!api->subscribe(&wheel));wheel.priority=0;
    CHECK(api->subscribe(&wheel));CHECK(MoonLab_RegisterVehicle_v1(code[2],100669323,2,0,physics));
    finish_hook_registration(1);CHECK(seal_updates());record.address=code[1];c.rsp=(U64)stack;c.rcx=17;
    CHECK(exception_handler(&e)==-1);CHECK(calls==2&&seen[0]==77&&seen[1]==0&&c.rcx==17&&api->camera_override_active()&&c.rip==123);
    record.address=code[2];c.rsp=(U64)stack;
    CHECK(exception_handler(&e)==-1&&c.rcx==17&&c.rip==123); /* Invalid producer snapshot was zeroed; physics alone may cancel. */

    reset();CHECK(begin_hook_registration(1));
    for(int i=0;i<64;i++){spec=observer(MOON_HOOK_UPDATE,i,MOON_PHASE_NORMAL,0);CHECK(api->subscribe(&spec));}
    spec=observer(MOON_HOOK_UPDATE,64,MOON_PHASE_NORMAL,0);CHECK(!api->subscribe(&spec));
    for(int i=0;i<64;i++){spec=observer(MOON_HOOK_LATE_UPDATE,i,MOON_PHASE_NORMAL,0);CHECK(api->subscribe(&spec));}
    spec=observer(MOON_HOOK_LATE_UPDATE,64,MOON_PHASE_NORMAL,0);CHECK(!api->subscribe(&spec));
    CHECK(MoonLab_RegisterLateUpdate_v1(code[1],100671741,2,0,camera));
    CHECK(api->subscribe(&wheel));CHECK(MoonLab_RegisterVehicle_v1(code[2],100669323,2,0,physics));
    CHECK(subscription_count==MOONLAB_MAX_SUBSCRIPTIONS);CHECK(!api->subscribe(&wheel));
    finish_hook_registration(0);CHECK(subscription_count==0&&hook_count==0&&seal_updates()&&hook_count==0);
    puts("hook SDK validation, ordering, role boundaries, mixed ABI, ownership, removal, rollback and real capacity passed");return 0;
}
