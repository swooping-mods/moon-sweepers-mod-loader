/* Process-local save redirection. No registry or per-user known-folder changes.
 * UnityPlayer imports both shell path APIs before its engine entry is called.
 * Pinning the whole UnityPlayer file is a host prerequisite for these IAT slots. */
typedef struct {DWORD a;unsigned short b,c;unsigned char d[8];} Guid;
static const Guid local_low={0xa520a1a4,0x1780,0x4ff6,{0xbd,0x18,0x16,0x73,0x43,0xc5,0xaf,0x16}};
static const Guid local_app={0xf1b32785,0x6fba,0x4fcf,{0x9d,0x55,0x7b,0x8e,0x7f,0x15,0x70,0x91}};
static const Guid roaming_app={0x3eb685db,0x65f9,0x4cf6,{0xa0,0x3a,0xe3,0xef,0x65,0x72,0x9f,0x3d}};
static const Guid user_profile={0x5e6c858f,0x0e22,0x4760,{0x9a,0xfe,0xea,0x33,0x17,0xb6,0x71,0x73}};
static int same_guid(const Guid *a,const Guid *b){
    const unsigned char *x=(const unsigned char *)a,*y=(const unsigned char *)b;
    for(int i=0;i<16;i++)if(x[i]!=y[i])return 0;return 1;
}
static const WCHAR *folder_suffix(const Guid *id){
    if(same_guid(id,&local_low))return L"\\AppData\\LocalLow";
    if(same_guid(id,&local_app))return L"\\AppData\\Local";
    if(same_guid(id,&roaming_app))return L"\\AppData\\Roaming";
    if(same_guid(id,&user_profile))return L"";
    return 0;
}
static WCHAR profile_root[800];
static long (__stdcall *real_known)(const Guid *,DWORD,PTR,WCHAR **);
static long (__stdcall *real_folder)(PTR,int,PTR,DWORD,WCHAR *);
static int profile_path(WCHAR *out,const WCHAR *suffix){
    int i=0;while(profile_root[i]){out[i]=profile_root[i];i++;}
    while(*suffix && i<998)out[i++]=*suffix++;out[i]=0;return i;
}
static long __stdcall private_known(const Guid *id,DWORD flags,PTR token,WCHAR **out){
    const WCHAR *suffix=folder_suffix(id);
    if(!suffix)return real_known(id,flags,token,out);
    if(token||!out)return (long)0x80070005;
    WCHAR path[1000];int count=profile_path(path,suffix);
    *out=(WCHAR *)CoTaskMemAlloc((U64)(count+1)*sizeof(WCHAR));
    if(!*out)return (long)0x8007000e;
    for(int i=0;i<=count;i++)(*out)[i]=path[i];return 0;
}
static long __stdcall private_folder(PTR hwnd,int csidl,PTR token,DWORD flags,WCHAR *out){
    int id=csidl&0xff;const WCHAR *suffix=0;
    if(id==0x1a)suffix=L"\\AppData\\Roaming";
    if(id==0x1c)suffix=L"\\AppData\\Local";
    if(id==0x28)suffix=L"";
    if(!suffix)return real_folder(hwnd,csidl,token,flags,out);
    if(token||!out)return (long)0x80070005;
    WCHAR temporary[1000];int count=profile_path(temporary,suffix);
    /* SHGetFolderPathW's documented output is MAX_PATH characters. */
    if(count>=260)return (long)0x8007007a;
    for(int i=0;i<=count;i++)out[i]=temporary[i];return 0;
}
static int replace_slot(PTR *slot,PTR replacement){
    DWORD old;if(!VirtualProtect(slot,sizeof(PTR),0x04,&old))return 0;
    *slot=replacement;DWORD ignored;return VirtualProtect(slot,sizeof(PTR),old,&ignored)!=0;
}
static int protect_profile(PTR module,int required){
    if(!module)return !required;
    unsigned char *base=(unsigned char *)module;
    DWORD pe=*(DWORD *)(base+0x3c);
    if(*(DWORD *)(base+pe)!=0x00004550||*(unsigned short *)(base+pe+24)!=0x20b)return 0;
    DWORD size=*(DWORD *)(base+pe+24+56);
    DWORD imports=*(DWORD *)(base+pe+24+112+8);
    if(!imports||imports>=size)return 0;
    int known=0,folder=0;
    for(DWORD descriptor=imports;descriptor+20<size;descriptor+=20){
        DWORD original=*(DWORD *)(base+descriptor),names=*(DWORD *)(base+descriptor+12),thunk=*(DWORD *)(base+descriptor+16);
        if(!names)break;if(!original||original>=size||thunk>=size)continue;
        for(DWORD i=0;original+i*8+8<=size && thunk+i*8+8<=size;i++){
            U64 name=*(U64 *)(base+original+i*8);if(!name)break;
            if(name>>63||name+3>=size)continue;
            const char *symbol=(const char *)(base+name+2);PTR *slot=(PTR *)(base+thunk+i*8);
            if(equal(symbol,"SHGetKnownFolderPath")){
                if(!real_known)real_known=(long (__stdcall *)(const Guid *,DWORD,PTR,WCHAR **))*slot;
                if(!replace_slot(slot,(PTR)private_known))return 0;known=1;
            }
            if(equal(symbol,"SHGetFolderPathW")){
                if(!real_folder)real_folder=(long (__stdcall *)(PTR,int,PTR,DWORD,WCHAR *))*slot;
                if(!replace_slot(slot,(PTR)private_folder))return 0;folder=1;
            }
        }
    }
    return required?(known&&folder):1;
}
