#include <assert.h>
#include <stdio.h>
static unsigned thread=7;
#define MOON_CAMERA_THREAD() thread
#include "../runtime/loader/camera.h"
static int world,walker,camera,other;
static const MoonCameraApiV1 *api;
static int original=60,current=60,restores,restore_ok=1;
static int capture(void *context){*(int *)context=current;return 1;}
static int bad_capture(void *context){(void)context;return 0;}
static int restore(void *context){
  assert(!api->claim("competing",&world,&walker,&camera,MOON_CAMERA_FOV));
  restores++;if(!restore_ok)return 0;current=*(int *)context;return 1;
}
static void exclusivity(void){
  unsigned zoom=api->claim("zoom",&world,&walker,&camera,MOON_CAMERA_FOV);
  unsigned first=api->claim("first",&world,&walker,&camera,MOON_CAMERA_MODE);
  assert(zoom&&first);
  assert(!api->claim("drone",&world,&walker,&camera,MOON_CAMERA_ALL));
  assert(!api->claim("zoom",&world,&other,&other,MOON_CAMERA_POSE));
  assert(!api->claim("new-camera",&world,&walker,&other,MOON_CAMERA_FOV));
  assert(!api->claim("new-walker",&world,&other,&camera,MOON_CAMERA_MODE));
  assert(!api->release("first",zoom));
  thread=8;moon_camera_observe_thread();assert(!api->held("zoom",zoom));
  assert(!api->claim("off-thread",&world,&other,&other,MOON_CAMERA_ALL));
  assert(!api->release("zoom",zoom));thread=7;
  assert(api->held("zoom",zoom));assert(api->release("zoom",zoom));
  assert(api->release("first",first));assert(!api->release("first",first));
  unsigned drone=api->claim("drone",&world,&walker,&camera,MOON_CAMERA_ALL);assert(drone);
  assert(!api->claim("survey",&world,&walker,&camera,MOON_CAMERA_POSE|MOON_CAMERA_MODE));
  assert(api->release("drone",drone));
}
static void sessions(void){
  MoonCameraSession s={0};
  assert(!moon_camera_begin(&s,api,"bad",&world,&walker,&camera,MOON_CAMERA_ALL,bad_capture,0));
  assert(!s.token);
  assert(moon_camera_begin(&s,api,"zoom",&world,&walker,&camera,MOON_CAMERA_FOV,capture,&original));
  current=20;restore_ok=0;
  assert(!moon_camera_finish(&s,restore,&original));assert(s.token&&current==20);
  restore_ok=1;assert(moon_camera_finish(&s,restore,&original));
  assert(current==60&&restores==2&&!s.token);
  assert(moon_camera_finish(&s,restore,&original));assert(restores==2);
  unsigned new_owner=api->claim("next",&world,&walker,&camera,MOON_CAMERA_FOV);
  assert(new_owner&&api->release("next",new_owner));
}
static void bounds(void){
  assert(!api->claim("invalid",0,&walker,&camera,1));
  assert(!api->claim("invalid",&world,0,&camera,1));
  assert(!api->claim("invalid",&world,&walker,0,1));
  assert(!api->claim("invalid",&world,&walker,&camera,0));
  assert(!api->claim("invalid",&world,&walker,&camera,8));
  assert(!api->claim("",&world,&walker,&camera,1));
  char overlong[97];for(unsigned i=0;i<96;i++)overlong[i]='a';overlong[96]=0;
  assert(!api->claim(overlong,&world,&walker,&camera,1));
  int identities[17];char names[17][12];unsigned tokens[16];
  for(unsigned i=0;i<16;i++){
    snprintf(names[i],12,"owner-%u",i);
    tokens[i]=api->claim(names[i],&world,&identities[i],&identities[i],MOON_CAMERA_ALL);assert(tokens[i]);
  }
  assert(!api->claim("full",&world,&identities[16],&identities[16],1));
  for(unsigned i=0;i<16;i++)assert(api->release(names[i],tokens[i]));
  camera_registry.next=(unsigned)-1;
  assert(!api->claim("exhausted",&world,&walker,&camera,1));
}
int main(void){
  api=moon_camera_api_v1();assert(moon_camera_api_valid(api));
  assert(!api->claim("not-observed",&world,&walker,&camera,1));
  moon_camera_observe_thread();exclusivity();sessions();bounds();
  puts("camera exclusivity, thread gates, capture and restoration passed");return 0;
}
