#define _POSIX_C_SOURCE 200809L
#include "runtime_profile.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static unsigned long long now(clockid_t clock){struct timespec t;if(clock_gettime(clock,&t))exit(2);return (unsigned long long)t.tv_sec*1000000000u+(unsigned long long)t.tv_nsec;}
static uint32_t value(unsigned i){return i*2654435761u^0xa5a5a5a5u;}
static uint32_t result(unsigned table,uint32_t input){return input*(table*2+3)+(0x9e3779b9u^table);}
static uint32_t mix(uint32_t a,uint32_t b){return (a<<5|a>>27)^b;}
static int failure(const char *why){fprintf(stderr,"profile parity failed: %s\n",why);return 3;}
int main(int argc,char **argv){
    if(argc<4||argc>5)return 2;
    unsigned services=(unsigned)strtoul(argv[1],0,10),iterations=(unsigned)strtoul(argv[2],0,10),trials=(unsigned)strtoul(argv[3],0,10);
    if((services!=4&&services!=64&&services!=256)||!iterations||iterations>1000000||!trials||trials>51)return 2;
    unsigned count=services==4?3:services==64?16:128;
    unsigned long long start=now(CLOCK_THREAD_CPUTIME_ID);
    const MoonRuntimeApiV1 *api=profile_prepare(services,count);if(!api)return failure("startup");
    unsigned long long setup=now(CLOCK_THREAD_CPUTIME_ID)-start;
    char owner[65];snprintf(owner,sizeof(owner),"provider-%02u",services/4-1);
    const ProfileTable *cached=api->find(owner,"service-3",1,sizeof(*cached));
    if(!cached||cached->size!=sizeof(*cached)||cached->abi!=1)return failure("table");
    if(argc==5){cached=api->find("provider-00","service-0",1,sizeof(*cached));if(!cached)return failure("negative control lookup");}
    unsigned long long epoch=0;
    printf("{\"setup_cpu_ns\":%llu,\"services\":%u,\"callbacks\":%u,\"interactions\":%u,\"samples\":[",setup,services,services/4,count);
    int comma=0;
    /* Trial zero is verified warmup, excluded from the reported timings.
     * Alternating lookup/cached order reduces systematic first-case bias. */
    for(unsigned trial=0;trial<=trials;trial++)for(unsigned order=0;order<4;order++){
        unsigned mode=order<2?order^(trial&1):order;
        unsigned ops=mode==3?(iterations/100?iterations/100:1):iterations;
        uint32_t digest=0x12345678,expected=0x12345678;
        unsigned long long first_epoch=epoch;profile_reset_counts();profile_frame_reset();
        unsigned long long wall0=now(CLOCK_MONOTONIC),cpu0=now(CLOCK_THREAD_CPUTIME_ID);
        for(unsigned i=0;i<ops;i++){
            if(mode<2){
                const ProfileTable *table=mode==0?cached:api->find(owner,"service-3",1,sizeof(*cached));
                if(!table)return failure("lookup");
                digest=mix(digest,table->apply(table,value(i)));
            }else if(mode==2)profile_frame(value(i));
            else {unsigned target,take;profile_interaction(++epoch,&target,&take);digest=mix(digest,target^(take<<16));}
        }
        unsigned long long cpu=now(CLOCK_THREAD_CPUTIME_ID)-cpu0,wall=now(CLOCK_MONOTONIC)-wall0;
        for(unsigned i=0;i<ops;i++){
            if(mode<2)expected=mix(expected,result(services-1,value(i)));
            else if(mode==2)for(unsigned j=0;j<services/4;j++)expected=mix(expected,result(j*4,value(i)));
            else expected=mix(expected,count^((unsigned)((first_epoch+i+1)%4==1)<<16));
        }
        if(mode==2)digest=profile_frame_digest();
        if(digest!=expected)return failure(argc==5?"wrong cached owner":"output digest");
#ifdef PROFILE_VERIFY
        unsigned long long calls=mode<2?ops:mode==2?(unsigned long long)ops*(services/4):0;
        unsigned long long queries=mode==3?(unsigned long long)ops*count:0;
        if(profile_calls()!=calls||profile_queries()!=queries)return failure("work counts");
        if(mode==3&&profile_polls()>(unsigned long long)ops*255)return failure("physical poll budget");
#endif
        if(trial){
            printf("%s{\"mode\":%u,\"trial\":%u,\"ops\":%u,\"cpu_ns\":%llu,\"wall_ns\":%llu,\"digest\":%u",comma?",":"",mode,trial,ops,cpu,wall,digest);
#ifdef PROFILE_VERIFY
            printf(",\"verified_calls\":%llu,\"verified_queries\":%llu,\"verified_polls\":%llu",profile_calls(),profile_queries(),profile_polls());
#endif
            putchar('}');comma=1;
        }
    }
    puts("],\"parity\":true}");return 0;
}
