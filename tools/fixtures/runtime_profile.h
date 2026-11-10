#include "moon_sweepers/services.h"
#include <stdint.h>
typedef struct ProfileTable ProfileTable;
struct ProfileTable {
    unsigned size,abi,factor,bias;
    uint32_t (*apply)(const ProfileTable *,uint32_t);
};
_Static_assert(sizeof(ProfileTable)==24,"profile domain prefix");
const MoonRuntimeApiV1 *profile_prepare(unsigned services,unsigned interactions);
void profile_reset_counts(void);
unsigned long long profile_calls(void);
unsigned long long profile_queries(void);
unsigned long long profile_polls(void);
void profile_frame_reset(void);
void profile_frame(uint32_t value);
uint32_t profile_frame_digest(void);
void profile_interaction(unsigned long long epoch,unsigned *target,unsigned *take);
