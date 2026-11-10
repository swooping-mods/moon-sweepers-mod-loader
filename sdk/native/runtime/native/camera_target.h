#ifndef MOON_NATIVE_CAMERA_TARGET_H
#define MOON_NATIVE_CAMERA_TARGET_H
/* A failed liveness query is not evidence that a captured target was destroyed.
 * Propagate invocation and missing-box failures so restoration retains its
 * lease and roots for retry. A successfully observed false needs no writes. */
static inline int moon_camera_target_alive(PTR alive_method,PTR target,int *ok) {
  if(!*ok||!target)return 0;
  void *args[]={target};PTR boxed=call(alive_method,0,args,ok);
  if(!*ok||!boxed){*ok=0;return 0;}
  unsigned char *value=unbox(boxed);
  if(!value){*ok=0;return 0;}
  return *value!=0;
}
#endif
