#ifndef MOON_UPDATE_DRIVER_SDK_H
#define MOON_UPDATE_DRIVER_SDK_H
/* Optional startup bridge for the standalone unit/audio services. The first
 * service keeps its Update hook; the other contributes one borrowed-walker
 * callback. Modules remain resident and do not hot-unload. */
#define MOON_UPDATE_DRIVER_ABI 1u
#define MOON_ATTACH_UNIT_FRAME "MoonLab_AttachUnitFrame_v1"
#define MOON_ATTACH_SOUND_FRAME "MoonLab_AttachSoundFrame_v1"
typedef void (*MoonUpdateFrame)(void *walker);
typedef int (*MoonUpdateAttach)(unsigned abi,MoonUpdateFrame callback);
#endif
