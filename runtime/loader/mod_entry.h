#ifndef MOON_MOD_ENTRY_H
#define MOON_MOD_ENTRY_H
typedef int (*MoonLegacyModStart)(PTR,PTR);
typedef struct {MoonLegacyModStart legacy;MoonModStartV8 adapter;} MoonNativeModEntry;
#define MOON_MOD_ENTRY_OK 1u
#define MOON_MOD_ENTRY_MISSING 2u
#define MOON_MOD_ENTRY_RUNTIME 3u
static unsigned int moon_mod_entry(PTR module,unsigned int abi,MoonNativeModEntry *entry){
    if(!module||!entry||!abi||abi>8)return MOON_MOD_ENTRY_MISSING;
    entry->legacy=0;entry->adapter=0;
    if(abi==8)entry->adapter=(MoonModStartV8)GetProcAddress(module,"MoonLab_ModStart_v8");
    else entry->legacy=(MoonLegacyModStart)GetProcAddress(module,"MoonLab_ModStart");
    if((abi==8&&!entry->adapter)||(abi!=8&&!entry->legacy))return MOON_MOD_ENTRY_MISSING;
    if(abi>=6){
        int (*marker)(void)=(int(*)(void))GetProcAddress(module,"MoonLab_RuntimeServicesAbi");
        if(!marker||(unsigned int)marker()!=MOON_RUNTIME_SERVICES_ABI)return MOON_MOD_ENTRY_RUNTIME;
    }
    return MOON_MOD_ENTRY_OK;
}
#endif
