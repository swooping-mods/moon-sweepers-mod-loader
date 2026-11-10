#ifndef MOONLAB_INTERACTION_UNITY_H
#define MOONLAB_INTERACTION_UNITY_H
#include "interaction.h"
/* Shared adapter for the pinned rooted su/sw consumers. Reflection offsets are
 * provided by their checked Unity binding; no raw hit layout is guessed here. */
static inline MoonInteractionPoint moon_interaction_from_sp(SPVec3 p){return (MoonInteractionPoint){p.x,p.y,p.z};}
static inline int moon_interaction_unity_ray(void *context,MoonInteractionPoint origin,MoonInteractionPoint direction,float reach,MoonInteractionHit *out){
    (void)context;union{U64 align;unsigned char bytes[96];}hit;su_zero(&hit,sizeof(hit));
    if(su.hit_size<=0||su.hit_size>96||su.hit_distance<0||su.hit_distance+4>su.hit_size)return -1;
    int ok=1,mask=~(1<<2),triggers=1;void *args[]={&origin,&direction,hit.bytes,&reach,&mask,&triggers};sw.raycasts++;
    PTR value=call(su.physics_ray,0,args,&ok);if(!ok||!value)return -1;if(!*(unsigned char *)unbox(value))return 0;
    PTR collider=call(su.hit_collider,hit.bytes,0,&ok);if(!ok||!collider)return -1;
    PTR go=call(su_method("UnityEngine","Component","get_gameObject",""),collider,0,&ok);if(!ok||!go)return -1;
    out->object=sw_object_id(go);su_copy(&out->distance,hit.bytes+su.hit_distance,4);return out->object?1:-1;
}
static inline int moon_interaction_unity_view(PTR walker,MoonInteractionPoint *origin,MoonInteractionPoint *direction){
    PTR camera=0;field_value(walker,sw.camera_field,&camera);if(!su_alive(camera))return 0;
    PTR transform=sw_transform(camera);if(!su_alive(transform))return 0;
    *origin=moon_interaction_from_sp(su_vector(su.tr_get_position,transform));*direction=moon_interaction_from_sp(su_vector(su.tr_forward,transform));return moon_interaction_ray_valid(*origin,*direction,1);
}
static inline int moon_interaction_unity_target(PTR walker,float reach,const unsigned long long *objects,unsigned count){
    MoonInteractionPoint origin,direction;if(!moon_interaction_unity_view(walker,&origin,&direction))return -1;
    return moon_interaction_target(moon_interaction_unity_ray,0,origin,direction,reach,objects,count);
}
static inline int moon_interaction_unity_gate(PTR walker,PTR expected,PTR world_field,PTR restoring,PTR blocked,PTR typing,PTR firstperson,PTR focus){
    if(!su_alive(walker)||!su_alive(expected))return 0;PTR current=0;field_value(walker,world_field,&current);if(current!=expected)return 0;
    int ok=1;return !boolean(restoring,current,&ok)&&boolean(focus,0,&ok)&&!boolean(blocked,walker,&ok)&&!boolean(typing,0,&ok)&&boolean(firstperson,walker,&ok)&&ok;
}
#endif
