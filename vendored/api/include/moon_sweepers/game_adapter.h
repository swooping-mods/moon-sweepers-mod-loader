#ifndef MOONLAB_GAME_ADAPTER_V1_H
#define MOONLAB_GAME_ADAPTER_V1_H
#include "services.h"
#define MOON_GAME_ADAPTER_ABI 1u
#define MOON_MOD_CONTEXT_V8_ABI 8u
#define MOON_GAME_CLOCK_ABI 1u
#define MOON_GAME_TIME_SCALE_ABI 1u
/* The loader supplies tables only from the exact reviewed game profile. Find
 * is admitted during this owner's ModStart_v8 and only for declared needs.
 * Requested ABI must match the declaration and the requested prefix must not
 * exceed its declared minimum. Cache typed tables, not per-frame name lookup. */
typedef struct {
    unsigned int size,abi;
    const char *profile_id,*profile_digest;
    const void *(*find)(const char *capability,unsigned int abi,unsigned int min_size);
} MoonGameAdapterApiV1;
typedef struct {
    unsigned int size,abi;
    const MoonGameAdapterApiV1 *game;
    /* Same runtime ABI1, with find scoped to this owner's declared requires_apis
     * during startup. Bind/cache once. Legacy global runtime lookup is separate.
     * Publication and frame registration retain their ordinary owner rules. */
    const MoonRuntimeApiV1 *runtime;
} MoonModContextV8;
typedef int (*MoonModStartV8)(const MoonModContextV8 *);
/* Export int MoonLab_ModStart_v8(const MoonModContextV8 *). No IL2CPP domain,
 * GameAssembly module base or machine hook context is supplied by this ABI. */
typedef struct {
    unsigned int size,abi;
    double time_seconds,delta_seconds;
    unsigned long long frame;
} MoonGameClockSampleV1;
typedef struct {
    unsigned int size,abi;
    /* Caller initializes sample size/ABI. Returns zero without a Unity call
     * outside an admitted game-thread frame. Values are Unity scaled time and
     * deltaTime; frame zero-extends the unsigned 32-bit frameCount (may wrap). */
    int (*sample)(MoonGameClockSampleV1 *);
} MoonGameClockV1;
/* Separate unity.time-scale capability; clock ABI1 is unchanged. The value is
 * Unity's configured timeScale, not an inferred ratio of delta times. */
typedef struct {
    unsigned int size,abi;
    float time_scale;
    unsigned int reserved;
} MoonGameTimeScaleSampleV1;
typedef struct {
    unsigned int size,abi;
    /* Initialize sample size/ABI and reserved=0. Returns zero without an engine
     * call outside an admitted game-thread frame or for an invalid descriptor.
     * Success writes a finite nonnegative scale (zero means paused), reserved=0.
     * Failure leaves caller storage unchanged. No setter is exposed. */
    int (*sample)(MoonGameTimeScaleSampleV1 *);
} MoonGameTimeScaleV1;
static inline int moon_game_adapter_valid(const MoonGameAdapterApiV1 *api){
    return api&&api->size>=sizeof(*api)&&api->abi==MOON_GAME_ADAPTER_ABI
        &&api->profile_id&&api->profile_digest&&api->find;
}
static inline int moon_mod_context_v8_valid(const MoonModContextV8 *context){
    return context&&context->size>=sizeof(*context)&&context->abi==MOON_MOD_CONTEXT_V8_ABI
        &&moon_game_adapter_valid(context->game)&&moon_runtime_api_valid(context->runtime);
}
static inline int moon_game_clock_valid(const MoonGameClockV1 *clock){
    return clock&&clock->size>=sizeof(*clock)&&clock->abi==MOON_GAME_CLOCK_ABI&&clock->sample;
}
static inline int moon_game_time_scale_valid(const MoonGameTimeScaleV1 *scale){
    return scale&&scale->size>=sizeof(*scale)&&scale->abi==MOON_GAME_TIME_SCALE_ABI&&scale->sample;
}
_Static_assert(sizeof(MoonGameAdapterApiV1)==32,"game adapter ABI v1");
_Static_assert(sizeof(MoonModContextV8)==24,"broker-only mod context v8");
_Static_assert(sizeof(MoonGameClockV1)==16,"game clock ABI v1");
_Static_assert(sizeof(MoonGameClockSampleV1)==32,"game clock sample ABI v1");
_Static_assert(sizeof(MoonGameTimeScaleV1)==16,"game time-scale ABI v1");
_Static_assert(sizeof(MoonGameTimeScaleSampleV1)==16,"game time-scale sample ABI v1");
#endif
