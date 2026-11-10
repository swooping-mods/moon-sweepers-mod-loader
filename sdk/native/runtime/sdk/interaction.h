#ifndef MOON_INTERACTION_API_V1_H
#define MOON_INTERACTION_API_V1_H
#include "input.h"
#define MOON_INTERACTION_ABI 1u
/* Opt in per action/item. A successful press owns its physical base key until
 * release, including the release frame, across native and registered mod input. */
#define MOON_INTERACTION_EXCLUSIVE 1u
#define MOON_INTERACTION_CARRY_PRIORITY 100
typedef struct {
    unsigned long long identity;
    float distance;
    int priority;
    unsigned token;
} MoonInteractionTarget;
/* Query is read-only, on the Unity thread, before ordinary mod/native input.
 * Validate world, focus, menus, typing, authority, reach and occlusion here.
 * walker is borrowed for this call; never retain it without an engine root. */
typedef int (*MoonInteractionQuery)(void *,void *walker,MoonInteractionTarget *);
typedef struct {
    unsigned size,flags;
    const char *action,*binding;
    MoonInteractionQuery query;
    void *context;
} MoonInteractionActionV1;
typedef struct {
    MoonInputState input;
    unsigned selected,token;
    unsigned long long target;
} MoonInteractionState;
typedef struct {
    unsigned size,abi;
    /* Register resident queries during ModStart. Names/bindings are copied.
     * A handle identifies one action and its frame-cached selected target. */
    unsigned (*register_action)(const MoonInteractionActionV1 *);
    MoonInteractionState (*sample)(unsigned);
    /* Atomically consume the selected pressed edge once per input epoch. sample is
     * a repeatable read for prompts; only take authorizes an action handler.
     * actor must match the adapter's current borrowed local actor. */
    int (*take)(unsigned,void *actor);
} MoonInteractionApiV1;
typedef const MoonInteractionApiV1 *(*MoonGetInteractionApiV1)(void);
static inline int moon_interaction_api_valid(const MoonInteractionApiV1 *a){return a&&a->size==sizeof(*a)&&a->abi==MOON_INTERACTION_ABI&&a->register_action&&a->sample&&a->take;}
_Static_assert(sizeof(MoonInteractionActionV1)==40,"interaction action ABI v1");
_Static_assert(sizeof(MoonInteractionState)==32,"interaction result ABI v1");
_Static_assert(sizeof(MoonInteractionApiV1)==32,"interaction API ABI v1");
#endif
