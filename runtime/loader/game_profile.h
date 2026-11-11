#ifndef MOON_GAME_PROFILE_H
#define MOON_GAME_PROFILE_H
/* The catalog is compiled, not loaded from player-editable deployment data.
 * Its family selects the complete reviewed core adapter, including the input,
 * camera and object-layout assumptions that are not generic capability names. */
typedef struct {
    const char *id,*digest,*hashes[3];
    unsigned int domain_rva,domain_ready_offset,image_min_rva,image_max_rva;
    unsigned int update_token,late_update_token,late_update_rva,vehicle_fixed_token,vehicle_fixed_rva;
} MoonNativeGameProfile;
#include "game_profiles.generated.h"
static const MoonNativeGameProfile *native_profile;
static int moon_profile_equal(const char *a,const char *b){
    if(!a||!b)return 0;while(*a&&*a==*b){a++;b++;}return *a==*b;
}
static const MoonNativeGameProfile *moon_profile_select(const MoonNativeGameProfile *profiles,unsigned int count,const char *const hashes[3]){
    const MoonNativeGameProfile *found=0;
    if(!profiles||!count||count>16||!hashes)return 0;
    for(unsigned int p=0;p<count;p++){
        const MoonNativeGameProfile *profile=profiles+p;int same=1;
        for(unsigned int n=0;n<3;n++)if(!moon_profile_equal(hashes[n],profile->hashes[n]))same=0;
        if(same){if(found)return 0;found=profile;}
    }return found;
}
static const MoonNativeGameProfile *moon_profile_match(const char *const hashes[3]){
    return moon_profile_select(moon_native_game_profiles,MOON_NATIVE_GAME_PROFILE_COUNT,hashes);
}
#endif
