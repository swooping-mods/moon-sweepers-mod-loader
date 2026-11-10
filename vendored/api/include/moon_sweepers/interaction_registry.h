#ifndef MOON_INTERACTION_REGISTRY_H
#define MOON_INTERACTION_REGISTRY_H
#include "interaction.h"
#include "input_registry.h"
#define MOON_INTERACTION_CAPACITY 128u
typedef struct {
    unsigned action,flags,owner;
    MoonInteractionQuery query;void *context;
    MoonInteractionTarget target;MoonInteractionState state;
    int eligible,consumed;
} MoonInteractionEntry;
typedef struct {
    MoonInteractionEntry entries[MOON_INTERACTION_CAPACITY];unsigned count;
    unsigned captured[256];unsigned char was_down[256],down[256];
    unsigned long long frame;int initialized,busy;
} MoonInteractionRegistry;
static inline int mir_finite(float v){union{float f;unsigned u;}n={v};return (n.u&0x7f800000u)!=0x7f800000u;}
static inline unsigned mir_register(MoonInteractionRegistry *r,MoonInputRegistry *input,const MoonInteractionActionV1 *spec,unsigned owner){
    if(!owner||r->busy||!spec||spec->size!=sizeof(*spec)||!spec->query||(spec->flags&~MOON_INTERACTION_EXCLUSIVE)||r->count==MOON_INTERACTION_CAPACITY)return 0;
    for(unsigned i=0;i<r->count;i++)if(mi_equal(input->actions[r->entries[i].action-1].name,spec->action?spec->action:""))return 0;
    unsigned action=mi_register(input,spec->action,spec->binding);if(!action)return 0;
    MoonInteractionEntry *e=r->entries+r->count;*e=(MoonInteractionEntry){.action=action,.flags=spec->flags,.owner=owner,.query=spec->query,.context=spec->context};return ++r->count;
}
static inline void mir_rollback(MoonInteractionRegistry *r,unsigned owner){
    for(unsigned i=0;i<r->count;){if(r->entries[i].owner!=owner){i++;continue;}for(unsigned j=i+1;j<r->count;j++)r->entries[j-1]=r->entries[j];r->count--;}
}
static inline int mir_precedes(MoonInteractionRegistry *r,MoonInputRegistry *input,unsigned a,unsigned b){
    MoonInteractionEntry *x=r->entries+a,*y=r->entries+b;
    if(x->target.priority!=y->target.priority)return x->target.priority>y->target.priority;
    if(x->target.distance!=y->target.distance)return x->target.distance<y->target.distance;
    /* Stable action IDs settle identical soft-volume hits, not load order. */
    const char *s=input->actions[x->action-1].name,*t=input->actions[y->action-1].name;
    while(*s&&*s==*t){s++;t++;}return (unsigned char)*s<(unsigned char)*t;
}
static inline unsigned mir_family(unsigned key){return key==16||key==160||key==161?16:key==17||key==162||key==163?17:key==18||key==164||key==165?18:0;}
static inline unsigned mir_left(unsigned family){return family==16?160:family==17?162:164;}
static inline int mir_overlap(unsigned a,unsigned b){unsigned family=mir_family(a);return a==b||(family&&family==mir_family(b)&&(a==family||b==family));}
static inline int mir_blocked(const MoonInteractionRegistry *r,unsigned action,unsigned key){
    if(key>=256)return 0;
    if(r->captured[key]&&r->captured[key]!=action)return 1;
    unsigned family=mir_family(key);if(!family)return 0;
    if(r->captured[family]&&r->captured[family]!=action)return 1;
    if(key==family){unsigned left=mir_left(family);if((r->captured[left]&&r->captured[left]!=action)||(r->captured[left+1]&&r->captured[left+1]!=action))return 1;}
    return 0;
}
static inline void mir_capture(MoonInteractionRegistry *r,unsigned action,unsigned key,const unsigned char *pressed){
    unsigned family=mir_family(key);if(key!=family||!family){r->captured[key]=action;return;}
    unsigned left=mir_left(family);int sides=0;
    for(unsigned k=left;k<=left+1;k++)if(r->down[k]||(pressed&&pressed[k])){r->captured[k]=action;sides=1;}
    if(!sides)r->captured[key]=action;
}
static inline void mir_begin_events(MoonInteractionRegistry *r,MoonInputRegistry *input,unsigned long long frame,void *walker,const unsigned char *pressed){
    if(r->busy||(r->initialized&&r->frame==frame))return;
    r->busy=1;r->frame=frame;r->initialized=1;
    /* Poll once before callbacks. Query cost or physical changes during a query
     * cannot split claim retirement and edge delivery into different snapshots. */
    for(unsigned k=0;k<256;k++)r->down[k]=(unsigned char)mi_down(input,k);
    const unsigned char *previous_snapshot=input->snapshot;input->snapshot=r->down;
    unsigned order[MOON_INTERACTION_CAPACITY],count=0,modifiers=mi_modifiers(input);
    unsigned char active[MOON_INTERACTION_CAPACITY];
    for(unsigned key=1;key<256;key++){
        /* Preserve the latch through release. A fresh press on a later frame
         * is a new interaction; losing target/focus never leaks a held edge. */
        if(!r->was_down[key])r->captured[key]=0;
        r->was_down[key]=r->down[key];
    }
    for(unsigned i=0;i<r->count;i++){
        MoonInteractionEntry *e=r->entries+i;MoonInputAction *a=input->actions+e->action-1;
        e->state=(MoonInteractionState){0};e->target=(MoonInteractionTarget){0};e->consumed=0;
        e->eligible=walker&&e->query(e->context,walker,&e->target)&&e->target.identity&&mir_finite(e->target.distance)&&e->target.distance>=0&&e->target.distance<=100&&e->target.priority>=-1000&&e->target.priority<=1000;
        if(!e->eligible||!a->chord.key||(modifiers&a->chord.required)!=a->chord.required||(modifiers&a->chord.forbidden)||mir_blocked(r,e->action,a->chord.key))continue;
        active[i]=(unsigned char)(r->down[a->chord.key]||(pressed&&pressed[a->chord.key]));
        unsigned at=count++;while(at&&(active[i]>active[order[at-1]]||(active[i]==active[order[at-1]]&&mir_precedes(r,input,i,order[at-1])))){order[at]=order[at-1];at--;}order[at]=i;
    }
    /* Greedy admission in stable rank order handles generic modifiers sharing
     * either side, while distinct left/right controls can still act separately. */
    for(unsigned n=0;n<count;n++){
        MoonInteractionEntry *e=r->entries+order[n];unsigned key=input->actions[e->action-1].chord.key;int selected=1;
        for(unsigned j=0;j<n;j++){MoonInteractionEntry *other=r->entries+order[j];if(other->state.selected&&mir_overlap(key,input->actions[other->action-1].chord.key)){selected=0;break;}}
        e->state.selected=(unsigned)selected;
    }
    for(unsigned i=0;i<r->count;i++){
        MoonInteractionEntry *e=r->entries+i;unsigned key=input->actions[e->action-1].chord.key;
        int selected=(int)e->state.selected,inhibited=input->actions[e->action-1].inhibit;
        MoonInputState state=mi_sample(input,e->action,selected);
        if(selected){
            if(pressed&&pressed[key]&&!inhibited)state.pressed=1;
            e->state=(MoonInteractionState){state,1,e->target.token,e->target.identity};if(state.pressed&&(e->flags&MOON_INTERACTION_EXCLUSIVE))mir_capture(r,e->action,key,pressed);
        }
    }
    input->snapshot=previous_snapshot;
    r->busy=0;
}
static inline void mir_begin(MoonInteractionRegistry *r,MoonInputRegistry *input,unsigned long long frame,void *walker){mir_begin_events(r,input,frame,walker,0);}
static inline MoonInteractionState mir_sample(const MoonInteractionRegistry *r,unsigned handle){return handle&&handle<=r->count&&!r->busy?r->entries[handle-1].state:(MoonInteractionState){0};}
static inline int mir_take(MoonInteractionRegistry *r,unsigned handle){
    if(!handle||handle>r->count||r->busy)return 0;
    MoonInteractionEntry *e=r->entries+handle-1;
    if(!e->state.input.pressed||!e->state.selected||e->consumed)return 0;
    e->consumed=1;return 1;
}
#endif
