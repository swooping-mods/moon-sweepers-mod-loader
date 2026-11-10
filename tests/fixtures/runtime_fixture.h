#include "moon_sweepers/services.h"
typedef struct {
    unsigned int size,abi;
    int (*add)(int,int);
    unsigned char reserved[48];
} IndependentMath;
_Static_assert(sizeof(IndependentMath)==64,"independent domain table");
int independent_publish(const MoonRuntimeApiV1 *,unsigned int variant);
int independent_consume(const MoonRuntimeApiV1 *);
unsigned int independent_frame(const MoonRuntimeApiV1 *);
int independent_frame_count(void);
unsigned independent_frame_actors(void);
