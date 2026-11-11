#ifndef MOON_SERVICE_PLAN_V1_H
#define MOON_SERVICE_PLAN_V1_H
/* Parsed contracts borrow one immutable, process-lifetime deployment buffer.
 * The actual API registry remains services.h; this does not create another. */
#define MSP_MAX_BYTES (2u*1024u*1024u)
#define MSP_MAX_LIMITS 32u
typedef struct {const unsigned char *p,*end;int ok;} MspReader;
typedef struct {
    const unsigned char *name,*limits;
    unsigned int length,abi,size,count;
} MspContract;
typedef struct {
    char id[65];unsigned int package_abi,provides_count,requires_count,game_count;
    const unsigned char *provides,*requires,*game;
} MspMod;
static struct {
    unsigned int count,parsed,next_owner,active,version;
    char profile_id[65],profile_digest[65];
    const unsigned char *end;
    MspMod mods[64];
} service_plan;
static unsigned int msp_number(MspReader *r,unsigned int bytes){
    if(!r->ok||(U64)(r->end-r->p)<bytes){r->ok=0;return 0;}
    unsigned int value=0;for(unsigned int i=0;i<bytes;i++)value|=(unsigned int)*r->p++<<(8*i);return value;
}
static const unsigned char *msp_string(MspReader *r,unsigned int max,unsigned int *length){
    unsigned int n=msp_number(r,2);*length=n;
    if(!r->ok||!n||n>max||(U64)(r->end-r->p)<n){r->ok=0;return 0;}
    const unsigned char *value=r->p;r->p+=n;return value;
}
static int msp_equal(const unsigned char *a,unsigned int n,const char *b){
    if(!b)return 0;
    for(unsigned int i=0;i<n;i++)if(!b[i]||a[i]!=(unsigned char)b[i])return 0;
    return b[n]==0;
}
static int msp_bytes(const unsigned char *a,unsigned int n,const unsigned char *b,unsigned int m){
    if(n!=m)return 0;
    for(unsigned int i=0;i<n;i++)if(a[i]!=b[i])return 0;
    return 1;
}
/* kind: mod ID, qualified API, or integer-limit key. */
static int msp_name(const unsigned char *p,unsigned int n,unsigned int kind){
    if(!p||!n)return 0;
    if(kind==0){
        unsigned int segment=0;
        for(unsigned int i=0;i<n;i++){
            unsigned char c=p[i];
            if(c=='-'){if(!segment)return 0;segment=0;}
            else if((c>='a'&&c<='z')||(c>='0'&&c<='9'))segment++;
            else return 0;
        }
        return segment!=0;
    }
    if(kind==3){
        unsigned int segment=0,parts=0;
        for(unsigned int i=0;i<n;i++){
            unsigned char c=p[i];if(c=='.'){if(!segment)return 0;segment=0;parts++;continue;}
            if(!segment&&(c<'a'||c>'z'))return 0;
            if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-'))return 0;
            segment++;
        }return segment!=0&&parts!=0;
    }
    if(kind==1){
        unsigned int owner=0;while(owner<n&&p[owner]!='.')owner++;
        if(owner>64||owner==n||!msp_name(p,owner,0))return 0;
        p+=owner+1;n-=owner+1;
    }
    if(!n||p[0]<'a'||p[0]>'z')return 0;
    unsigned int segment=0;
    for(unsigned int i=0;i<n;i++){
        unsigned char c=p[i];
        if(c=='.'&&kind==1){if(!segment)return 0;segment=0;continue;}
        if(!segment&&(c<'a'||c>'z'))return 0;
        if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||(kind==2?c=='_':c=='-')))return 0;
        segment++;
    }
    return segment!=0;
}
static unsigned int msp_owner_length(const unsigned char *name,unsigned int n){
    unsigned int i=0;while(i<n&&name[i]!='.')i++;return i;
}
static int msp_contract_kind(MspReader *r,MspContract *entry,unsigned int kind){
    entry->name=msp_string(r,160,&entry->length);
    entry->abi=msp_number(r,4);entry->size=msp_number(r,4);entry->count=msp_number(r,4);
    if(!r->ok||!msp_name(entry->name,entry->length,kind)||!entry->abi||!entry->size
       ||entry->size>65536||entry->count>MSP_MAX_LIMITS)return 0;
    entry->limits=r->p;
    const unsigned char *names[MSP_MAX_LIMITS];unsigned int lengths[MSP_MAX_LIMITS];
    for(unsigned int i=0;i<entry->count;i++){
        names[i]=msp_string(r,64,&lengths[i]);(void)msp_number(r,4);
        if(!r->ok||!msp_name(names[i],lengths[i],2))return 0;
        for(unsigned int j=0;j<i;j++)if(msp_bytes(names[i],lengths[i],names[j],lengths[j]))return 0;
    }
    return r->ok;
}
static int msp_contract(MspReader *r,MspContract *entry){return msp_contract_kind(r,entry,1);}
static int msp_game_contract(MspReader *r,MspContract *entry){return msp_contract_kind(r,entry,3);}
static int msp_find(const unsigned char *name,unsigned int length,MspContract *out,unsigned int *provider){
    unsigned int owner_length=msp_owner_length(name,length);
    for(unsigned int i=0;i<service_plan.parsed;i++)if(msp_equal(name,owner_length,service_plan.mods[i].id)){
        MspMod *mod=&service_plan.mods[i];MspReader r={mod->provides,service_plan.end,1};
        for(unsigned int j=0;j<mod->provides_count;j++){
            if(!msp_contract(&r,out))return 0;
            if(msp_bytes(name,length,out->name,out->length)){*provider=i;return 1;}
        }
        return 0;
    }
    return 0;
}
static int msp_limit(const MspContract *entry,const unsigned char *key,unsigned int length,unsigned int *value){
    MspReader r={entry->limits,service_plan.end,1};
    for(unsigned int i=0;i<entry->count;i++){
        unsigned int n;const unsigned char *name=msp_string(&r,64,&n);unsigned int actual=msp_number(&r,4);
        if(!r.ok)return 0;
        if(msp_bytes(key,length,name,n)){*value=actual;return 1;}
    }
    return 0;
}
static int msp_satisfies(const MspContract *provided,const MspContract *required){
    if(provided->abi!=required->abi||provided->size<required->size)return 0;
    MspReader r={required->limits,service_plan.end,1};
    for(unsigned int i=0;i<required->count;i++){
        unsigned int n,available;const unsigned char *name=msp_string(&r,64,&n);unsigned int minimum=msp_number(&r,4);
        if(!r.ok||!msp_limit(provided,name,n,&available)||available<minimum)return 0;
    }
    return 1;
}
static inline int msp_init(const void *data,unsigned int bytes){
    if(service_plan.active||!data||bytes<12||bytes>MSP_MAX_BYTES)return 0;
    const unsigned char *p=data;
    if(p[0]!='M'||p[1]!='S'||p[2]!='A'||p[3]!='P'||p[4]!='I'||(p[5]!=1&&p[5]!=2)||p[6]||p[7])return 0;
    MspReader r={p+8,p+bytes,1};service_plan.end=r.end;service_plan.parsed=0;service_plan.next_owner=0;
    service_plan.version=p[5];service_plan.profile_id[0]=service_plan.profile_digest[0]=0;
    if(service_plan.version==2){
        unsigned int n;const unsigned char *value=msp_string(&r,64,&n);
        if(!r.ok)return 0;
        for(unsigned int i=0;i<n;i++){
            unsigned c=value[i];if((!i&&(c<'a'||c>'z'))||!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='.'||c=='-'||c=='_'))return 0;
            service_plan.profile_id[i]=(char)c;
        }service_plan.profile_id[n]=0;
        value=msp_string(&r,64,&n);if(!r.ok||n!=64)return 0;
        for(unsigned int i=0;i<64;i++){
            unsigned c=value[i];if(!((c>='a'&&c<='f')||(c>='0'&&c<='9')))return 0;
            service_plan.profile_digest[i]=(char)c;
        }service_plan.profile_digest[64]=0;
    }
    service_plan.count=msp_number(&r,4);if(service_plan.count>64)return 0;
    unsigned int total=0;
    for(unsigned int index=0;index<service_plan.count;index++){
        MspMod *mod=&service_plan.mods[index];unsigned int n;const unsigned char *id=msp_string(&r,64,&n);
        if(!r.ok||!msp_name(id,n,0))return 0;
        for(unsigned int j=0;j<index;j++)if(msp_equal(id,n,service_plan.mods[j].id))return 0;
        for(unsigned int j=0;j<n;j++)mod->id[j]=(char)id[j];
        mod->id[n]=0;
        mod->package_abi=msp_number(&r,4);mod->provides_count=msp_number(&r,4);mod->provides=r.p;
        if(!r.ok||!mod->package_abi||mod->package_abi>8||(mod->package_abi==8&&service_plan.version!=2)||mod->provides_count>64
           ||total+mod->provides_count>256||(mod->package_abi<6&&mod->provides_count))return 0;
        total+=mod->provides_count;
        const unsigned char *names[64];unsigned int lengths[64];
        for(unsigned int j=0;j<mod->provides_count;j++){
            MspContract entry;if(!msp_contract(&r,&entry)||!msp_equal(entry.name,msp_owner_length(entry.name,entry.length),mod->id))return 0;
            names[j]=entry.name;lengths[j]=entry.length;
            for(unsigned int k=0;k<j;k++)if(msp_bytes(names[j],lengths[j],names[k],lengths[k]))return 0;
        }
        service_plan.parsed=index+1;
        mod->requires_count=msp_number(&r,4);mod->requires=r.p;
        if(!r.ok||mod->requires_count>64||(mod->package_abi<6&&mod->requires_count))return 0;
        for(unsigned int j=0;j<mod->requires_count;j++){
            MspContract required,provided;unsigned int provider;
            if(!msp_contract(&r,&required)||!msp_find(required.name,required.length,&provided,&provider)
               ||provider>=index||!msp_satisfies(&provided,&required))return 0;
            names[j]=required.name;lengths[j]=required.length;
            for(unsigned int k=0;k<j;k++)if(msp_bytes(names[j],lengths[j],names[k],lengths[k]))return 0;
        }
        mod->game_count=service_plan.version==2?msp_number(&r,4):0;mod->game=r.p;
        if(!r.ok||mod->game_count>64||(mod->package_abi<8&&mod->game_count))return 0;
        for(unsigned int j=0;j<mod->game_count;j++){
            MspContract required;if(!msp_game_contract(&r,&required))return 0;
            names[j]=required.name;lengths[j]=required.length;
            for(unsigned int k=0;k<j;k++)if(msp_bytes(names[j],lengths[j],names[k],lengths[k]))return 0;
        }
    }
    if(!r.ok||r.p!=r.end)return 0;
    service_plan.active=1;
    return 1;
}
static int msp_identity(unsigned int owner,const char *id){
    if(!service_plan.active)return 1;
    if(!owner||owner>service_plan.count||owner!=service_plan.next_owner+1)return 0;
    const char *expected=service_plan.mods[owner-1].id;
    while(*expected&&*expected==*id){expected++;id++;}return !*expected&&!*id;
}
static int msp_full_name(const char *provider,const char *service,char out[161]){
    unsigned int n=0;while(provider[n]){if(n>=64)return 0;out[n]=provider[n];n++;}
    out[n++]='.';for(unsigned int i=0;service[i];i++){if(n>=160)return 0;out[n++]=service[i];}out[n]=0;return (int)n;
}
static int msp_publication(const char *provider,const MoonServicePublicationV1 *spec){
    if(!service_plan.active)return 1;
    char name[161];int n=msp_full_name(provider,spec->service_id,name);MspContract expected;unsigned int index;
    if(!n||!msp_find((const unsigned char *)name,(unsigned int)n,&expected,&index)
       ||service_plan.mods[index].package_abi<6||expected.abi!=spec->abi||expected.size!=spec->api_size)return 0;
    unsigned int count=0;const MoonServiceLimitV1 *limits=0;
    if(spec->size==sizeof(MoonServicePublicationLimitsV1)){
        const MoonServicePublicationLimitsV1 *extended=(const MoonServicePublicationLimitsV1 *)spec;
        count=extended->limit_count;limits=extended->limits;
    }
    if(count!=expected.count)return 0;
    MspReader r={expected.limits,service_plan.end,1};
    for(unsigned int i=0;i<count;i++){
        unsigned int length;const unsigned char *key=msp_string(&r,64,&length);unsigned int value=msp_number(&r,4),matches=0;
        for(unsigned int j=0;j<count;j++)if(msp_equal(key,length,limits[j].name)&&value==limits[j].value)matches++;
        if(!r.ok||matches!=1)return 0;
    }
    return 1;
}
static int msp_requirements(unsigned int owner,const void *(*find)(const char *,const char *,unsigned int,unsigned int)){
    if(!service_plan.active)return 1;
    MspMod *mod=&service_plan.mods[owner-1];MspReader r={mod->requires,service_plan.end,1};
    for(unsigned int i=0;i<mod->requires_count;i++){
        MspContract required;if(!msp_contract(&r,&required))return 0;
        unsigned int n=msp_owner_length(required.name,required.length);char provider[65],service[161];
        for(unsigned int j=0;j<n;j++)provider[j]=(char)required.name[j];
        provider[n]=0;
        unsigned int suffix=required.length-n-1;for(unsigned int j=0;j<suffix;j++)service[j]=(char)required.name[n+1+j];service[suffix]=0;
        if(!find(provider,service,required.abi,required.size))return 0;
    }
    return 1;
}
#endif
