/* Installed-game startup: bounded configuration, pinned inputs, no save redirect.
 * Called on the worker thread, never under the Windows loader lock. */
__declspec(dllimport) BOOL __stdcall ReadFile(PTR,void *,DWORD,DWORD *,PTR);
__declspec(dllimport) BOOL __stdcall SetEnvironmentVariableW(const WCHAR *,const WCHAR *);
__declspec(dllimport) void __stdcall OutputDebugStringA(const char *);
__declspec(dllimport) DWORD __stdcall GetFileAttributesW(const WCHAR *);
__declspec(dllimport) BOOL __stdcall CreateDirectoryW(const WCHAR *,PTR);
__declspec(dllimport) U64 __stdcall GetTickCount64(void);
__declspec(dllimport) DWORD __stdcall GetCurrentProcessId(void);
__declspec(dllimport) int __stdcall BCryptOpenAlgorithmProvider(PTR *,const WCHAR *,const WCHAR *,DWORD);
__declspec(dllimport) int __stdcall BCryptCreateHash(PTR,PTR *,void *,DWORD,void *,DWORD,DWORD);
__declspec(dllimport) int __stdcall BCryptHashData(PTR,void *,DWORD,DWORD);
__declspec(dllimport) int __stdcall BCryptFinishHash(PTR,void *,DWORD,DWORD);
__declspec(dllimport) int __stdcall BCryptDestroyHash(PTR);
__declspec(dllimport) int __stdcall BCryptCloseAlgorithmProvider(PTR,DWORD);
static int public_mode;
static WCHAR public_base[1000], public_generation[33], public_ids[MOONLAB_MAX_NATIVE_MODS*65+1];
static char public_installation[17];
static DWORD public_base_length;
static char public_inventory[1048577];
static PTR public_inputs[3];

static int public_same_path(const WCHAR *a,const WCHAR *b){
    for(;;){
        WCHAR x=*a++,y=*b++;
        if(x=='/')x='\\';if(y=='/')y='\\';
        if(x>='A'&&x<='Z')x+='a'-'A';if(y>='A'&&y<='Z')y+='a'-'A';
        if(x!=y)return 0;if(!x)return 1;
    }
}

static int public_installed_marker(void){
    static WCHAR path[1100];DWORD n=GetModuleFileNameW(self_module,path,950);
    if(!n||n>=950)return 0;
    while(n&&path[n-1]!='\\'&&path[n-1]!='/')n--;
    const WCHAR *tail=L"MoonLab\\owner.json";while(*tail)path[n++]=*tail++;path[n]=0;
    DWORD attributes=GetFileAttributesW(path);
    return attributes!=0xffffffffu&&!(attributes&16);
}

static int public_path(WCHAR *out,DWORD capacity,const char *relative){
    DWORD n=public_base_length;
    if(n>=capacity)return 0;
    for(DWORD i=0;i<n;i++)out[i]=public_base[i];
    for(;*relative;relative++){
        unsigned char c=(unsigned char)*relative;
        if(c<32||c>126||n+1>=capacity)return 0;
        out[n++]=c=='/'?'\\':c;
    }
    out[n]=0;return 1;
}
static int public_read(const char *name,char *out,DWORD capacity,DWORD *size){
    WCHAR path[1500];if(!public_path(path,1500,name))return 0;
    PTR file=CreateFileW(path,0x80000000,1,0,3,0x80,0);
    if(file==(PTR)(U64)-1)return 0;
    DWORD n=0;int ok=ReadFile(file,out,capacity,&n,0)&&n<capacity;
    CloseHandle(file);if(!ok)return 0;out[n]=0;*size=n;return 1;
}
static int public_hex(const char *s,DWORD length){
    for(DWORD i=0;i<length;i++)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return 0;
    return 1;
}
static char *public_field(char **cursor,const char *prefix){
    char *start=*cursor;
    while(*prefix)if(*start++!=*prefix++)return 0;
    char *value=start;
    while(*start&&*start!='\n')start++;
    if(*start!='\n')return 0;
    *start=0;*cursor=start+1;return value;
}
static int public_parse(char *text){
    char *cursor=text;
    char *magic=public_field(&cursor,""),*installation=public_field(&cursor,"installation="),
         *generation=public_field(&cursor,"generation="),*enabled=public_field(&cursor,"enabled="),
         *mods=public_field(&cursor,"mods=");
    if(!magic||!installation||!generation||!enabled||!mods||*cursor||
       !equal(magic,"MOONLAB-PUBLIC-1")||!equal(enabled,"1"))return 0;
    DWORD n=0;while(installation[n])n++;
    if(n!=16||!public_hex(installation,16))return 0;
    for(DWORD i=0;i<17;i++)public_installation[i]=installation[i];
    n=0;while(generation[n])n++;
    if(n!=32||!public_hex(generation,32))return 0;
    for(DWORD i=0;i<33;i++)public_generation[i]=(WCHAR)generation[i];
    n=0;while(mods[n]){if(n>=MOONLAB_MAX_NATIVE_MODS*65)return 0;public_ids[n]=(unsigned char)mods[n];n++;}
    public_ids[n]=0;if(!n)return 0;
    DWORD count=0;WCHAR *id=public_ids;
    for(WCHAR *p=id;;p++)if(*p==';'||!*p){
        int last=!*p;WCHAR saved=*p;*p=0;
        if(!valid_id(id)||++count>MOONLAB_MAX_NATIVE_MODS){*p=saved;return 0;}
        for(WCHAR *previous=public_ids;previous<id;){
            WCHAR *a=previous,*b=id;while(a<id&&*a!=';'&&*a==*b){a++;b++;}
            if((!*a||*a==';')&&!*b){*p=saved;return 0;}
            while(previous<id&&*previous!=';')previous++;previous++;
        }
        *p=saved;if(last)break;id=p+1;
    }
    return 1;
}
static int public_hash(const char *relative,const char *expected,PTR *retained){
    WCHAR path[1500];if(!public_path(path,1500,relative))return 0;
    PTR file=CreateFileW(path,0x80000000,1,0,3,0x80,0);
    if(file==(PTR)(U64)-1)return 0;
    PTR algorithm=0,hash=0;int ok=0;
    if(BCryptOpenAlgorithmProvider(&algorithm,L"SHA256",0,0)<0)goto done;
    if(BCryptCreateHash(algorithm,&hash,0,0,0,0,0)<0)goto done;
    static unsigned char block[65536];DWORD n;
    for(;;){
        if(!ReadFile(file,block,sizeof(block),&n,0))goto done;
        if(!n)break;
        if(BCryptHashData(hash,block,n,0)<0)goto done;
    }
    unsigned char bytes[32];
    if(BCryptFinishHash(hash,bytes,32,0)<0)goto done;
    const char *digits="0123456789abcdef";
    for(int i=0;i<32;i++)if(expected[i*2]!=digits[bytes[i]>>4]||expected[i*2+1]!=digits[bytes[i]&15])goto done;
    ok=1;
done:
    if(hash)BCryptDestroyHash(hash);
    if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);
    if(ok&&retained)*retained=file;else CloseHandle(file);
    return ok;
}
static void public_prefix(char *out){
    char *p=append(out,"MoonLab/deployments/");
    for(int i=0;i<32;i++)*p++=(char)public_generation[i];
    append(p,"/");
}
static int public_relative(const char *s){
    int part=0,total=0;char previous=0;
    for(;*s;s++){
        char c=*s;if(++total>220||c<32||c>126||c=='\\'||c==':'||c=='*'||c=='?'||c=='"'||c=='<'||c=='>'||c=='|')return 0;
        if(c=='/'){if(!part||previous=='.'||previous==' ')return 0;part=0;}
        else part++;
        previous=c;
    }
    return part&&previous!='.'&&previous!=' ';
}
static int public_payload(void){
    char prefix[80];public_prefix(prefix);
    char inventory[100];append(append(inventory,prefix),"files.txt");DWORD size;
    if(!public_read(inventory,public_inventory,sizeof(public_inventory),&size)||!size)return 0;
    for(DWORD i=0;i<size;i++)if(!public_inventory[i])return 0;
    char *line=public_inventory;unsigned int entries=0;
    while(*line){
        char *end=line;while(*end&&*end!='\n')end++;
        if(*end!='\n'||end-line<67)return 0;
        *end=0;if(line[64]!=' '||!public_hex(line,64))return 0;
        char *name=line+65,*p=name;const char *q="MoonLab/mods/";
        if(!equal(name,"MoonLab/runtime-plan.bin"))while(*q)if(*p++!=*q++)return 0;
        if(!public_relative(name)||!public_hash(name,line,0))return 0;
        entries++;line=end+1;
    }
    /* Every selected DLL must occur in the checked inventory. */
    for(WCHAR *id=public_ids;;){
        char required[180],*out=append(required,"MoonLab/mods/");
        while(*id&&*id!=';')*out++=(char)*id++;
        append(out,"/mod.dll");int found=0;
        for(char *entry=public_inventory;entry<public_inventory+size;){
            if(equal(entry+65,required))found=1;
            while(*entry)entry++;entry++;
        }
        if(!found)return 0;
        if(!*id)break;id++;
    }
    return entries>0;
}
static int public_startup(void){
    DWORD n=GetModuleFileNameW(self_module,public_base,950);
    if(!n||n>=950)return 0;
    while(n&&public_base[n-1]!='\\'&&public_base[n-1]!='/')n--;
    if(n>171)return 0;
    for(DWORD i=0;i<n;i++)if(public_base[i]<32||public_base[i]>126)return 0;
    public_base[n]=0;public_base_length=n;
    static WCHAR actual[1200],expected[1200];
    if(!public_path(expected,1200,"MoonSweepers.exe")||!GetModuleFileNameW(0,actual,1200))return 0;
    if(!public_same_path(actual,expected))return 0;
    static char text[MOONLAB_MAX_NATIVE_MODS*65+256];DWORD size;
    if(!public_read("MoonLab/active.txt",text,sizeof(text),&size))return 0;
    for(DWORD i=0;i<size;i++)if(!text[i]||(unsigned char)text[i]>127)return 0;
    if(!public_parse(text))return 0;
    const char *names[3]={"GameAssembly.dll","MoonSweepers.exe","UnityPlayer.dll"};
    const char *hashes[3]={
        "14f711a6a3b1b7cd803a03f85cc6c6201c5b546ab9b90329533f5cb8ae2e7f13",
        "0e780f8e8d4bf26ed6bdd8a4068ac42a18846a66a80da7ba5c78f1917a093901",
        "bfafc49b185eb8427ad75e3648bcba3bf5b07455567ca05ae2b2e23bc1646c0c"};
    for(int i=0;i<3;i++)if(!public_hash(names[i],hashes[i],&public_inputs[i]))return 0;
    if(!public_payload())return 0;
    static WCHAR path[1500],run_id[40];char run[100];char *end=append(run,"MoonLab/logs/run-");
    U64 stamp=GetTickCount64();DWORD pid=GetCurrentProcessId();const char *hex="0123456789abcdef";
    for(int i=15;i>=0;i--)*end++=hex[(stamp>>(i*4))&15];*end++='-';
    for(int i=7;i>=0;i--)*end++=hex[(pid>>(i*4))&15];*end=0;
    for(int i=0;i<29;i++)run_id[i]=(unsigned char)run[13+i];run_id[29]=0;
    if(!public_path(path,1500,run)||!CreateDirectoryW(path,0))return 0;
    if(!SetEnvironmentVariableW(L"MOONLAB_EVIDENCE",path)||!SetEnvironmentVariableW(L"MOONLAB_MODS",public_ids)||
       !SetEnvironmentVariableW(L"MOONLAB_RUN_ID",run_id))return 0;
    const WCHAR *clear[]={L"MOONLAB_TEST_TOOLS",L"MOONLAB_SLIME_TEST_TOOLS",L"MOONLAB_STATS_TEST",L"MOONLAB_UNIT_INSPECT"};
    for(unsigned int i=0;i<sizeof(clear)/sizeof(clear[0]);i++)if(!SetEnvironmentVariableW(clear[i],0))return 0;
    const char *settings[][2]={
        {"custom-keybinds","MOONLAB_KEYBINDS_CONFIG"},{"gambling","MOONLAB_GAMBLING_CONFIG"},
        {"item-stacking","MOONLAB_STACKING_CONFIG"},{"idle-vehicle-storage","MOONLAB_IDLE_VEHICLE_STORAGE_CONFIG"},
        {"rover-horns","MOONLAB_HORN_SETTINGS"},{"mars-planet","MOONLAB_MARS_PLANET_SETTINGS"},
        {"multi-belt-balancer","MOONLAB_BALANCER_CONFIG"},{"precise-build-snapping","MOONLAB_SNAPPING_CONFIG"},
        {"conveyor-upgrade-wrench","MOONLAB_CONVEYOR_TIERS_CONFIG"},{"area-blueprints","MOONLAB_BLUEPRINTS_CONFIG"},
        {"building-drone","MOONLAB_BUILDING_DRONE_CONFIG"},{"joonas-backpack","MOONLAB_JOONAS_BACKPACK_CONFIG"},
        {"player-catapult","MOONLAB_PLAYER_CATAPULT_CONFIG"}};
    for(unsigned int i=0;i<sizeof(settings)/sizeof(settings[0]);i++){
        char relative[160];append(append(append(relative,"MoonLab/settings/"),settings[i][0]),".ini");
        WCHAR variable[80];unsigned int j=0;while(settings[i][1][j]){variable[j]=settings[i][1][j];j++;}variable[j]=0;
        if(!public_path(path,1500,relative)||!SetEnvironmentVariableW(variable,path))return 0;
    }
    return 1;
}
static int public_game_module(PTR game){
    static WCHAR expected[1200],actual[1200];
    if(!public_path(expected,1200,"GameAssembly.dll")||!GetModuleFileNameW(game,actual,1200))return 0;
    return public_same_path(actual,expected);
}
static void public_release_inputs(void){
    for(int i=0;i<3;i++)if(public_inputs[i]){CloseHandle(public_inputs[i]);public_inputs[i]=0;}
}
