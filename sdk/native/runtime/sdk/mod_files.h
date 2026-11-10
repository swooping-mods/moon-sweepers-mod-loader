#ifndef MOONLAB_SDK_MOD_FILES_H
#define MOONLAB_SDK_MOD_FILES_H
/* Private installation-local files. Relative public paths remain unchanged;
 * resolve them once per operation and use the same pinned sidecar boundary. */
#define SS_MAX_BYTES 8192u
#define SS_ROOT_MAX 1000u
#define SS_MAX_DIRS 512u
#define SS_PATH_MAX 1200u
#include "storage.h"
static struct {
  BOOL (__stdcall *mkdir)(const char *,PTR);
  BOOL (__stdcall *ini_write)(const char *,const char *,const char *,const char *);
  DWORD (__stdcall *fullpath)(const char *,DWORD,char *,char **);
  char base[160];
} io;
static inline int ioabsolute(const char *path,char *root,char **name){
  DWORD n=io.fullpath(path,SS_PATH_MAX,root,0);
  if(!n||n>=SS_PATH_MAX)return 0;
  unsigned i=n;while(i&&root[i-1]!='\\')i--;
  if(i<=3)return 0;root[i-1]=0;*name=root+i;return ss_filename(*name);
}
static inline int iochild(const char *relative){
  char root[SS_PATH_MAX],*name;static SSPaths paths;
  if(!ioabsolute(relative,root,&name)||!ss_begin())return 0;
  int ok=ss_paths_named(&paths,root,name);
  if(ok){
    /* Parent handles remain pinned while the child is created/inspected. An
     * existing junction is rejected before any nested directory is touched. */
    if(!io.mkdir(paths.file,0)&&ss.error()!=183)ok=0;
    if(ok)ok=ss_directory(&paths,paths.file);
  }
  if(!ss_close_directories(&paths))ok=0;
  ss.busy=0;return ok;
}
static inline int iobind(const char *id){
  PTR kernel=GetModuleHandleA("kernel32.dll");
  io.mkdir=(BOOL(__stdcall *)(const char *,PTR))GetProcAddress(kernel,"CreateDirectoryA");
  io.ini_write=(BOOL(__stdcall *)(const char *,const char *,const char *,const char *))GetProcAddress(kernel,"WritePrivateProfileStringA");
  io.fullpath=(DWORD(__stdcall *)(const char *,DWORD,char *,char **))GetProcAddress(kernel,"GetFullPathNameA");
  if(!io.mkdir||!io.ini_write||!io.fullpath||!ss_bind()||!ss_filename(id))return 0;
  if(!iochild(".\\MoonLab")||!iochild(".\\MoonLab\\mods"))return 0;
  io.base[0]=0;if(!ss_append(io.base,sizeof(io.base),".\\MoonLab\\mods\\")||!ss_append(io.base,sizeof(io.base),id))return 0;
  return iochild(io.base);
}
static inline int iowrite(const char *path,const void *data,DWORD size){
  char root[SS_PATH_MAX],*name;
  return ioabsolute(path,root,&name)&&ss_replace_named(root,name,data,size);
}
static inline int ioread(const char *path,void *data,DWORD size){
  char root[SS_PATH_MAX],*name;unsigned actual=0;
  return ioabsolute(path,root,&name)&&ss_load_named(root,name,data,size,&actual)&&actual==size;
}
#endif
