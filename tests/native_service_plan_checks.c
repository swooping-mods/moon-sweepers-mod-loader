#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "fixtures/runtime_fixture.h"
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
#define CHECK(value) do{if(!(value)){fprintf(stderr,"line %d: %s\n",__LINE__,#value);return 1;}}while(0)
static unsigned char code[3][5]={{0x48,0x8b,0xc4,0,0},{0x48,0x8b,0xc4,0,0},{0x48,0x8b,0xc4,0,0}};
int main(int argc,char **argv){
    CHECK(argc==3);
    FILE *file=fopen(argv[1],"rb");CHECK(file);CHECK(!fseek(file,0,SEEK_END));long size=ftell(file);CHECK(size>=0);
    CHECK(!fseek(file,0,SEEK_SET));unsigned char *data=malloc((size_t)size+1);CHECK(data);
    CHECK(fread(data,1,(size_t)size,file)==(size_t)size);CHECK(!fclose(file));
    if(!strcmp(argv[2],"reject")){CHECK(!msp_init(data,(unsigned int)size));free(data);return 0;}
    if(!strcmp(argv[2],"truncations")){
        for(unsigned int n=0;n<(unsigned int)size;n++){
            memset(&service_plan,0,sizeof(service_plan));CHECK(!msp_init(data,n));
        }
        memset(&service_plan,0,sizeof(service_plan));CHECK(msp_init(data,(unsigned int)size));free(data);return 0;
    }
    CHECK(msp_init(data,(unsigned int)size));
    if(!strcmp(argv[2],"parse")){printf("parsed %u mods\n",service_plan.count);free(data);return 0;}
    update_address=code[0];late_update_address=code[1];vehicle_address=code[2];
    const MoonRuntimeApiV1 *api=MoonLab_GetRuntimeApi_v1();CHECK(moon_runtime_api_valid(api));
    CHECK(!api->find("other-authors-library","building",7,16));
    CHECK(!begin_runtime_registration(1,"foreign-owner"));
    CHECK(begin_runtime_registration(1,"other-authors-library"));
    fake_thread=2;CHECK(!independent_publish(api,0));CHECK(!finish_runtime_registration(1));fake_thread=1;
    if(!strcmp(argv[2],"missing")){
        CHECK(independent_frame(api));CHECK(!finish_runtime_registration(1));
        CHECK(!runtime_service_count&&!subscription_count&&!registration_owner);
        CHECK(!begin_runtime_registration(2,"independent-feature"));free(data);return 0;
    }
    for(unsigned int variant=1;variant<=9;variant++)CHECK(!independent_publish(api,variant));
    CHECK(independent_publish(api,0));CHECK(!independent_publish(api,0));
    CHECK(!api->find("other-authors-library","building",7,16));
    if(!strcmp(argv[2],"rollback")){
        CHECK(independent_frame(api));CHECK(!finish_runtime_registration(0));
        CHECK(!runtime_service_count&&!subscription_count&&!registration_owner);
        CHECK(!api->find("other-authors-library","building",7,16));free(data);return 0;
    }
    CHECK(finish_runtime_registration(1));
    CHECK(!api->find("other-authors-library","building",8,16));
    CHECK(!api->find("other-authors-library","building",7,65));
    CHECK(!api->find("other-authors-library","building",7,0));
    fake_thread=2;CHECK(!api->find("other-authors-library","building",7,16));fake_thread=1;
    CHECK(begin_runtime_registration(2,"independent-feature"));CHECK(independent_consume(api));CHECK(finish_runtime_registration(1));
    CHECK(service_plan.next_owner==2);CHECK(seal_updates());
    fake_thread=2;const IndependentMath *math=api->find("other-authors-library","building",7,16);
    CHECK(math&&math->add(20,22)==42);CHECK(!independent_publish(api,0));CHECK(!independent_frame(api));
    Context context={0};context.rcx=17;CHECK(!dispatch_update(MOON_HOOK_UPDATE,&context));
    CHECK(independent_frame_count()==1);free(data);puts("production registry + independent provider/consumer passed");return 0;
}
