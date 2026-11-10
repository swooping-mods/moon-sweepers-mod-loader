/* This provider compiles against the public SDK and its own domain contract. */
#include "runtime_fixture.h"
static int add(int a,int b){return a+b;}
static const IndependentMath math={sizeof(math),7,add,{0}};
int independent_publish(const MoonRuntimeApiV1 *api,unsigned int variant){
    char service[]="building",capacity[]="build_menu_max_kind";
    MoonServiceLimitV1 limit={capacity,384};
    MoonServicePublicationLimitsV1 spec={
        {sizeof(spec),service,7,sizeof(math),&math},1,0,&limit
    };
    if(variant==1)spec.base.abi=8;
    if(variant==2)spec.base.api_size=63;
    if(variant==3)limit.value=383;
    if(variant==4)spec.reserved=1;
    if(variant==5)spec.limit_count=33;
    if(variant==6)spec.limits=0;
    if(variant==7)spec.base.service_id="unadvertised";
    if(variant==8)spec.base.api=0;
    if(variant==9)spec.base.size=sizeof(MoonServicePublicationV1);
    int accepted=api->publish(&spec.base);
    /* The caller may release/alter borrowed descriptor strings immediately. */
    service[0]='x';capacity[0]='x';return accepted;
}
