#ifndef MOON_CAMERA_REGISTRY_H
#define MOON_CAMERA_REGISTRY_H
#include "camera.h"
#define MOON_CAMERA_CLAIMS 16u
typedef struct {char owner[96];void *world,*walker,*camera;unsigned resources,token;} MoonCameraClaim;
typedef struct {MoonCameraClaim claims[MOON_CAMERA_CLAIMS];unsigned next;} MoonCameraRegistry;
static inline int moon_camera_owner_equal(const char *a,const char *b) {
  if(!a||!b)return 0;
  while(*a&&*a==*b){a++;b++;}return *a==*b;
}
static inline unsigned moon_camera_registry_claim(MoonCameraRegistry *r,const char *owner,
 void *world,void *walker,void *camera,unsigned resources) {
  if(!r||!owner||!owner[0]||!world||!walker||!camera||!resources||
     (resources&~MOON_CAMERA_ALL)||r->next==(unsigned)-1)return 0;
  unsigned n=0;while(n<96&&owner[n])n++;if(n==96)return 0;
  MoonCameraClaim *free_slot=0;
  for(unsigned i=0;i<MOON_CAMERA_CLAIMS;i++){
    MoonCameraClaim *c=&r->claims[i];if(!c->token){if(!free_slot)free_slot=c;continue;}
    /* One outstanding snapshot per provider, and never silently expire a
     * scene's claim: only its provider can restore and release the snapshot. */
    if(moon_camera_owner_equal(c->owner,owner))return 0;
    if((c->walker==walker||c->camera==camera)&&(c->resources&resources))return 0;
  }
  if(!free_slot)return 0;
  *free_slot=(MoonCameraClaim){0};for(unsigned i=0;i<=n;i++)free_slot->owner[i]=owner[i];
  free_slot->world=world;free_slot->walker=walker;free_slot->camera=camera;
  free_slot->resources=resources;return free_slot->token=++r->next;
}
static inline MoonCameraClaim *moon_camera_registry_find(MoonCameraRegistry *r,const char *owner,unsigned token) {
  if(!r||!token)return 0;
  for(unsigned i=0;i<MOON_CAMERA_CLAIMS;i++)if(r->claims[i].token==token&&moon_camera_owner_equal(r->claims[i].owner,owner))return &r->claims[i];
  return 0;
}
#endif
