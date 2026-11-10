#ifndef MOONLAB_INTERACTION_H
#define MOONLAB_INTERACTION_H
/* Pure geometry and delivery helpers. Scene adapters own nearest solid-ray
 * queries; callers retain prices, authority, persistence and action semantics. */
typedef struct {float x,y,z;} MoonInteractionPoint;
typedef struct {unsigned long long object;float distance;} MoonInteractionHit;
/* -1 query failure, 0 clear, 1 nearest solid hit. Never omit occluders just
 * because they are not registered interaction targets. */
typedef int (*MoonInteractionRay)(void *,MoonInteractionPoint,MoonInteractionPoint,float,MoonInteractionHit *);
typedef struct {void *context;void (*show)(void *,const char *);} MoonInteractionFeedback;
static inline int moon_interaction_finite(float v){union{float f;unsigned u;}n={v};return (n.u&0x7f800000u)!=0x7f800000u;}
static inline int moon_interaction_point(MoonInteractionPoint p){return moon_interaction_finite(p.x)&&moon_interaction_finite(p.y)&&moon_interaction_finite(p.z)&&p.x>=-10000000&&p.x<=10000000&&p.y>=-10000000&&p.y<=10000000&&p.z>=-10000000&&p.z<=10000000;}
static inline float moon_interaction_distance2(MoonInteractionPoint a,MoonInteractionPoint b){float x=a.x-b.x,y=a.y-b.y,z=a.z-b.z;return x*x+y*y+z*z;}
static inline int moon_interaction_reach(MoonInteractionPoint a,MoonInteractionPoint b,float reach){return moon_interaction_point(a)&&moon_interaction_point(b)&&moon_interaction_finite(reach)&&reach>0&&reach<=100&&moon_interaction_distance2(a,b)<=reach*reach;}
static inline int moon_interaction_ray_valid(MoonInteractionPoint origin,MoonInteractionPoint direction,float reach){
    float square=direction.x*direction.x+direction.y*direction.y+direction.z*direction.z;
    return moon_interaction_point(origin)&&moon_interaction_point(direction)&&square>=.99f&&square<=1.01f&&moon_interaction_finite(reach)&&reach>0&&reach<=100;
}
static inline int moon_interaction_target(MoonInteractionRay ray,void *context,MoonInteractionPoint origin,MoonInteractionPoint direction,float reach,const unsigned long long *objects,unsigned count){
    if(!ray||!objects||!count||count>128||!moon_interaction_ray_valid(origin,direction,reach))return -1;
    MoonInteractionHit hit={0};if(ray(context,origin,direction,reach,&hit)!=1||!hit.object||!moon_interaction_finite(hit.distance)||hit.distance<0||hit.distance>reach)return -1;
    for(unsigned i=0;i<count;i++)if(objects[i]&&objects[i]==hit.object)return (int)i;return -1;
}
static inline int moon_interaction_aim(MoonInteractionRay ray,void *context,MoonInteractionPoint origin,MoonInteractionPoint direction,float reach,MoonInteractionPoint point,float radius,float front_margin){
    if(!ray||!moon_interaction_ray_valid(origin,direction,reach)||!moon_interaction_point(point)||!moon_interaction_finite(radius)||radius<0||radius>10||!moon_interaction_finite(front_margin)||front_margin<0||front_margin>radius)return 0;
    float x=point.x-origin.x,y=point.y-origin.y,z=point.z-origin.z,along=x*direction.x+y*direction.y+z*direction.z;
    if(along<=0||along>reach)return 0;x-=direction.x*along;y-=direction.y*along;z-=direction.z*along;
    if(x*x+y*y+z*z>radius*radius)return 0;
    MoonInteractionHit hit={0};float probe=along>front_margin?along-front_margin:along;
    return ray(context,origin,direction,probe,&hit)==0;
}
static inline int moon_interaction_feedback(MoonInteractionFeedback sink,const char *message){
    if(!sink.show||!message||!*message)return 0;unsigned n=0;while(message[n]&&n<256)n++;if(n==256)return 0;sink.show(sink.context,message);return 1;
}
/* Input arbitration is process-wide in the desktop loader. Standalone probes
 * use the input SDK's per-module fallback and do not qualify combined mods. */
#ifndef MOON_INTERACTION_NO_INPUT
#include "input.h"
static inline int moon_interaction_binding_hint(char *out,unsigned cap,const char *prefix,const char *action,const char *defaults,const char *suffix){
    char label[64];if(!out||!cap||!prefix||!suffix||!moon_input_label(action,defaults,label,sizeof(label)))return 0;
    const char *parts[]={prefix,label,suffix};unsigned n=0;
    for(unsigned i=0;i<3;i++)for(unsigned j=0;parts[i][j];j++){if(n+1>=cap){out[0]=0;return 0;}out[n++]=parts[i][j];}
    out[n]=0;return 1;
}
static inline int moon_interaction_claim(unsigned long long frame,const char *owner,int eligible,int pressed){return eligible&&pressed&&moon_input_claim("world-interact",frame,owner);}
#endif
#endif
