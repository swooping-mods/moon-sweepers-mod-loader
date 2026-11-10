#ifndef MOON_NATIVE_CAMERA_H
#define MOON_NATIVE_CAMERA_H
#include "../sdk/camera.h"
#include "services.h"
#include "camera_target.h"
__declspec(dllexport) int MoonLab_CameraApiAbi(void){return MOON_CAMERA_ABI;}
/* The loader owns cross-mod arbitration. A standalone single-feature probe
 * uses the identical registry locally; recognized old loaders fail closed. */
#include "../sdk/camera_host.h"
static unsigned moon_native_camera_claim(const char *owner,void *world,void *walker,void *camera,unsigned resources){
  moon_camera_observe_thread();return camera_claim(owner,world,walker,camera,resources);
}
static inline const MoonCameraApiV1 *moon_camera_connect(void) {
  PTR loader=GetModuleHandleA("version.dll");
  if(loader&&GetProcAddress(loader,"MoonLab_LoaderAbi")){
    MoonGetCameraApiV1 get=(MoonGetCameraApiV1)GetProcAddress(loader,"MoonLab_GetCameraApi_v1");
    const MoonCameraApiV1 *api=get?get(MOON_CAMERA_ABI,sizeof(MoonCameraApiV1)):0;
    return moon_camera_api_valid(api)?api:0;
  }
  static const MoonCameraApiV1 local={sizeof(local),MOON_CAMERA_ABI,moon_native_camera_claim,camera_held,camera_release};
  (void)moon_camera_api_v1;return &local;
}
#endif
