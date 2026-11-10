/* No private registry declarations or game bindings are visible here. */
#include "runtime_fixture.h"
static int frames;
static unsigned actors;
static void frame(void *walker,void *user){
    int *value=user;(*value)++;actors|=walker==(void *)17?1u:walker==(void *)18?2u:4u;
}
unsigned int independent_frame(const MoonRuntimeApiV1 *api){
    MoonFrameSubscriptionV1 spec={sizeof(spec),MOON_PHASE_NORMAL,0,frame,&frames};
    return api->subscribe_frame(&spec);
}
int independent_consume(const MoonRuntimeApiV1 *api){
    const IndependentMath *math=api->find("other-authors-library","building",7,16);
    return math&&math->size==sizeof(*math)&&math->abi==7&&math->add(10,32)==42
        &&independent_frame(api)!=0;
}
int independent_frame_count(void){return frames;}
unsigned independent_frame_actors(void){return actors;}
