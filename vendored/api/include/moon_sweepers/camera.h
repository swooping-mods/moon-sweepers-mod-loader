#ifndef MOON_CAMERA_V1_H
#define MOON_CAMERA_V1_H
#define MOON_CAMERA_ABI 1u
#define MOON_CAMERA_POSE 1u
#define MOON_CAMERA_FOV 2u
#define MOON_CAMERA_MODE 4u
#define MOON_CAMERA_ALL 7u
typedef struct {
  unsigned size,abi;
  unsigned (*claim)(const char *owner,void *world,void *walker,void *camera,unsigned resources);
  int (*held)(const char *owner,unsigned token);
  int (*release)(const char *owner,unsigned token);
} MoonCameraApiV1;
typedef const MoonCameraApiV1 *(*MoonGetCameraApiV1)(unsigned abi,unsigned size);
static inline int moon_camera_api_valid(const MoonCameraApiV1 *api) {
  return api&&api->size==sizeof(*api)&&api->abi==MOON_CAMERA_ABI&&api->claim&&api->held&&api->release;
}
/* Targets must remain rooted by the provider until finish succeeds. Snapshot
 * capture is read-only. Restoration runs while the lease is still exclusive;
 * failure retains both snapshot and lease so the next tick can retry safely. */
typedef struct {
  const MoonCameraApiV1 *api; const char *owner; unsigned token;
} MoonCameraSession;
static inline int moon_camera_begin(MoonCameraSession *s,const MoonCameraApiV1 *api,
 const char *owner,void *world,void *walker,void *camera,unsigned resources,
 int (*capture)(void *),void *context) {
  if(!s||s->token||!moon_camera_api_valid(api)||!capture)return 0;
  unsigned token=api->claim(owner,world,walker,camera,resources);
  if(!token)return 0;
  if(!capture(context)){api->release(owner,token);return 0;}
  s->api=api;s->owner=owner;s->token=token;return 1;
}
static inline int moon_camera_finish(MoonCameraSession *s,int (*restore)(void *),void *context) {
  if(!s||!s->token)return 1;
  if(!s->api->held(s->owner,s->token)||!restore||!restore(context))return 0;
  if(!s->api->release(s->owner,s->token))return 0;
  s->api=0;s->owner=0;s->token=0;return 1;
}
#endif
