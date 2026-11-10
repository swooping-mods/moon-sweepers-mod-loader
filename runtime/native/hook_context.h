#ifndef MOONLAB_HOOK_CONTEXT_H
#define MOONLAB_HOOK_CONTEXT_H
typedef struct {unsigned int code,flags;void *nested,*address;} ExceptionRecord;
#include "../../vendored/api/include/moon_sweepers/context.h"
typedef MoonHookContext Context;
typedef struct {ExceptionRecord *record;Context *context;} ExceptionPointers;
_Static_assert(__builtin_offsetof(Context,rip)==248,"AMD64 CONTEXT layout");
#endif
