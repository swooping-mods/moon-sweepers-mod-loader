#ifndef MOON_NATIVE_RAYCAST_LAYOUT_H
#define MOON_NATIVE_RAYCAST_LAYOUT_H
/* Current Steam Unity 6000.6 value layout, excluding the boxed object header.
 * Collider is an eight-byte EntityId; a guessed older 44-byte stride corrupts
 * array traversal. Call with runtime-observed value size and field offsets. */
static inline int moon_raycast_layout_valid(int size,unsigned alignment,int point,int normal,int distance,int collider){
    return size==48&&alignment&&alignment<=8&&!(alignment&(alignment-1))&&point==0&&normal==12&&distance==28&&collider==40;
}
#endif
