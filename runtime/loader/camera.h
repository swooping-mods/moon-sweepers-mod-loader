#ifndef MOON_LOADER_CAMERA_H
#define MOON_LOADER_CAMERA_H
#include "../../vendored/api/include/moon_sweepers/camera_registry.h"
#ifndef MOON_CAMERA_THREAD
#define MOON_CAMERA_THREAD() GetCurrentThreadId()
#endif
static MoonCameraRegistry camera_registry;
static unsigned camera_thread;
static inline void moon_camera_observe_thread(void) {
  unsigned expected=0,current_id=MOON_CAMERA_THREAD();
  __atomic_compare_exchange_n(&camera_thread,&expected,current_id,0,__ATOMIC_RELEASE,__ATOMIC_RELAXED);
}
static unsigned camera_claim(const char *owner,void *world,void *walker,void *camera,unsigned resources) {
  unsigned observed_id=__atomic_load_n(&camera_thread,__ATOMIC_ACQUIRE);
  if(!observed_id||observed_id!=MOON_CAMERA_THREAD())return 0;
  return moon_camera_registry_claim(&camera_registry,owner,world,walker,camera,resources);
}
static int camera_held(const char *owner,unsigned token) {
  unsigned observed_id=__atomic_load_n(&camera_thread,__ATOMIC_ACQUIRE);
  return observed_id&&observed_id==MOON_CAMERA_THREAD()&&moon_camera_registry_find(&camera_registry,owner,token)!=0;
}
static int camera_release(const char *owner,unsigned token) {
  if(!camera_held(owner,token))return 0;
  *moon_camera_registry_find(&camera_registry,owner,token)=(MoonCameraClaim){0};return 1;
}
static inline const MoonCameraApiV1 *moon_camera_api_v1(void) {
  static const MoonCameraApiV1 api={sizeof(api),MOON_CAMERA_ABI,camera_claim,camera_held,camera_release};return &api;
}
#endif
