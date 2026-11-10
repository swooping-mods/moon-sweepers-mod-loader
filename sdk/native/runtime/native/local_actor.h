#ifndef MOON_NATIVE_LOCAL_ACTOR_H
#define MOON_NATIVE_LOCAL_ACTOR_H
/* Domain frame owners choose local control explicitly. Generic Hook/Frame API1
 * continues to observe each walker; this guard must precede a domain's frame
 * latch so a remote walker cannot use up the local player's update. */
static PTR moon_local_actor_method;
static inline int moon_local_actor_bind(void){
    moon_local_actor_method=method("MoonCleaners","MoonRunOver","get_LocalWalker",0);
    if(!moon_local_actor_method||method_token(moon_local_actor_method)!=100670068){moon_local_actor_method=0;return 0;}return 1;
}
static inline int moon_local_actor_read(PTR *local){
    *local=0;if(!moon_local_actor_method)return 0;int ok=1;
    PTR value=call(moon_local_actor_method,0,0,&ok);if(ok)*local=value;return ok;
}
static inline int moon_local_actor_admit(PTR walker){
    PTR local=0;return moon_local_actor_read(&local)&&local&&local==walker;
}
#endif
