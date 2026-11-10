/* Synthetic machine contexts and writable byte arrays, no game code. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef void *PTR;typedef uint32_t DWORD;typedef uint64_t U64;typedef int BOOL;
#define __stdcall
#define __declspec(x)
static int protect_calls,fail_protect,removed;
BOOL VirtualProtect(PTR p,U64 n,DWORD flags,DWORD *old){(void)p;(void)n;(void)flags;*old=4;return ++protect_calls!=fail_protect;}
PTR GetCurrentProcess(void){return (PTR)1;}
DWORD GetCurrentThreadId(void){return 1;}
BOOL FlushInstructionCache(PTR p,const void *a,U64 n){(void)p;(void)a;(void)n;return 1;}
#include "../runtime/loader/dispatch.h"
PTR AddVectoredExceptionHandler(DWORD first,int (*handler)(ExceptionPointers *)){(void)first;(void)handler;return (PTR)1;}
DWORD RemoveVectoredExceptionHandler(PTR p){(void)p;removed++;return 1;}
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}}while(0)
static int seen[4],calls;
static int first(int id,Context *c){seen[calls++]=id;c->rcx=99;c->rip=99;return 1;}
static int second(int id,Context *c){seen[calls++]=c->rcx==17?id:-1;return 0;}
static void reset(void){
    hook_count=update_sealed=calls=protect_calls=fail_protect=removed=late_override_active=0;
    subscription_count=next_subscription=registration_owner=0;vehicle_address=late_update_address=0;
    begin_hook_registration(1);
}
static int seal_test(void){finish_hook_registration(1);return seal_updates();}
static int camera_active,late_seen;
static int camera_owner(int id,Context *c){if(id!=31||c->rcx!=17)return 0;c->rcx=99;return camera_active;}
static int line_observer(int id,Context *c){if(id==32&&c->rcx==17)late_seen++;c->rip=99;return 1;}
static int input_live=1,flight_active=0,vehicle_calls=0;
static float observed_throttle;
static int wheel_callback(int id,Context *c,MoonVehicleInput *input){
    if(id!=12||c->rcx!=17)return 0;
    vehicle_calls++;c->rcx=99;
    if(input_live){input->valid=1;input->throttle=.75f;input->steer=.5f;input->boost=1;}
    return 1; /* An input producer must never suppress vanilla physics. */
}
static int flight_callback(int id,Context *c,MoonVehicleInput *input){
    if(id!=13||c->rcx!=17)return 0;
    vehicle_calls++;observed_throttle=input->valid?input->throttle:0;
    return flight_active;
}
int main(void){
 unsigned char code[5]={0x48,0x89,0x5c,0x24,0x08};update_address=code;reset();
 CHECK(!MoonLab_RegisterUpdate_v1(code,0,1,first));
 CHECK(!MoonLab_RegisterUpdate_v1(code+1,100671733,1,first));
 CHECK(!MoonLab_RegisterUpdate_v1(code,100671733,1,0));
 CHECK(MoonLab_RegisterUpdate_v1(code,100671733,7,first));
 CHECK(!MoonLab_RegisterUpdate_v1(code,100671733,9,first));
 CHECK(MoonLab_RegisterUpdate_v1(code,100671733,8,second));
 CHECK(code[0]==0x48);CHECK(seal_test());CHECK(code[0]==0xcc);
 CHECK(!MoonLab_RegisterUpdate_v1(code,100671733,9,second));
 U64 stack[4]={123,0,0,0};Context c={0};c.rsp=(U64)stack;c.rcx=17;c.rbx=42;
 ExceptionRecord record={.code=0x80000003,.address=code};ExceptionPointers e={&record,&c};
 CHECK(exception_handler(&e)==-1);CHECK(calls==2&&seen[0]==7&&seen[1]==8);
 CHECK(c.rcx==17&&c.rip==(U64)code+5&&c.rsp==(U64)stack&&stack[1]==42);
 record.address=code+1;CHECK(exception_handler(&e)==0);CHECK(calls==2);
 record.address=code;record.code=0;CHECK(exception_handler(&e)==0);record.code=0x80000003;
 /* Emulation preserves the original instruction for each supported shape. */
 reset();code[0]=0x40;code[1]=0x53;
 CHECK(MoonLab_RegisterUpdate_v1(code,100671733,7,first));CHECK(seal_test());
 c.rsp=(U64)(stack+1);c.rbx=55;CHECK(exception_handler(&e)==-1);CHECK(c.rsp==(U64)stack&&stack[0]==55&&c.rip==(U64)code+2);
 reset();code[0]=0x48;code[1]=0x8b;code[2]=0xc4;
 CHECK(MoonLab_RegisterUpdate_v1(code,100671733,7,first));CHECK(seal_test());
 c.rsp=(U64)stack;CHECK(exception_handler(&e)==-1);CHECK(c.rax==(U64)stack&&c.rip==(U64)code+3);
 reset();code[0]=0x90;CHECK(!MoonLab_RegisterUpdate_v1(code,100671733,7,first));
 code[0]=0x48;CHECK(MoonLab_RegisterUpdate_v1(code,100671733,7,first));
 fail_protect=2;CHECK(!seal_test());CHECK(code[0]==0x48&&removed==1);
 reset();CHECK(seal_test());CHECK(protect_calls==0);
 reset();subscription_count=MOONLAB_MAX_SUBSCRIPTIONS;CHECK(!MoonLab_RegisterUpdate_v1(code,100671733,7,first));
 reset();unsigned char fixed[5]={0x48,0x8b,0xc4,0,0};vehicle_address=fixed;
 CHECK(!MoonLab_RegisterVehicle_v1(fixed,0,1,12,wheel_callback));
 CHECK(!MoonLab_RegisterVehicle_v1(fixed,100669323,3,12,wheel_callback));
 CHECK(MoonLab_RegisterVehicle_v1(fixed,100669323,2,13,flight_callback));
 CHECK(!MoonLab_RegisterVehicle_v1(fixed,100669323,2,13,flight_callback));
 code[0]=0x48;CHECK(MoonLab_RegisterUpdate_v1(code,100671733,7,first));
 CHECK(MoonLab_RegisterVehicle_v1(fixed,100669323,1,12,wheel_callback));CHECK(hook_count==0);CHECK(seal_test());CHECK(hook_count==2);
 CHECK(!MoonLab_RegisterVehicle_v1(fixed,100669323,1,12,wheel_callback));
 record.address=fixed;c.rcx=17;c.rsp=(U64)stack;stack[0]=123;
 CHECK(exception_handler(&e)==-1);CHECK(vehicle_calls==2&&observed_throttle==.75f&&c.rip==(U64)fixed+3&&c.rcx==17);
 flight_active=1;c.rsp=(U64)stack;CHECK(exception_handler(&e)==-1);CHECK(c.rip==123&&c.rsp==(U64)(stack+1));
 input_live=0;c.rsp=(U64)stack;CHECK(exception_handler(&e)==-1);CHECK(observed_throttle==0);
 flight_active=0;c.rsp=(U64)stack;CHECK(exception_handler(&e)==-1);CHECK(c.rip==(U64)fixed+3);
 CHECK(vehicle_calls==8);
 reset();unsigned char late[5]={0x40,0x55,0x53,0x57,0x48};late_update_address=late;
 CHECK(!MoonLab_RegisterLateUpdate_v1(late,0,1,32,line_observer));
 CHECK(!MoonLab_RegisterLateUpdate_v1(late+1,100671741,1,32,line_observer));
 CHECK(!MoonLab_RegisterLateUpdate_v1(late,100671741,3,32,line_observer));
 CHECK(MoonLab_RegisterLateUpdate_v1(late,100671741,1,32,line_observer));
 CHECK(!MoonLab_RegisterLateUpdate_v1(late,100671741,1,32,line_observer));
 CHECK(MoonLab_RegisterLateUpdate_v1(late,100671741,2,31,camera_owner));
 CHECK(!MoonLab_RegisterLateUpdate_v1(late,100671741,2,33,first));
 CHECK(hook_count==0&&seal_test());CHECK(hook_count==1);
 CHECK(!MoonLab_RegisterLateUpdate_v1(late,100671741,1,7,first));
 record.address=late;c.rcx=17;c.rbp=55;c.rsp=(U64)(stack+1);camera_active=0;
 CHECK(exception_handler(&e)==-1);CHECK(late_seen==1&&c.rcx==17&&c.rip==(U64)late+2&&stack[0]==55&&!MoonLab_CameraOverrideActive_v1());
 camera_active=1;stack[0]=123;c.rsp=(U64)stack;
 CHECK(exception_handler(&e)==-1);CHECK(late_seen==2&&c.rip==123&&c.rsp==(U64)(stack+1)&&c.rcx==17&&MoonLab_CameraOverrideActive_v1());
 camera_active=0;c.rsp=(U64)(stack+1);CHECK(exception_handler(&e)==-1);CHECK(!MoonLab_CameraOverrideActive_v1());
 reset();late[0]=0x40;late_update_address=late;subscription_count=MOONLAB_MAX_SUBSCRIPTIONS;
 CHECK(!MoonLab_RegisterLateUpdate_v1(late,100671741,1,32,line_observer));
 puts("shared Update order, context isolation, original continuation, validation, seal and rollback passed");return 0;
}
