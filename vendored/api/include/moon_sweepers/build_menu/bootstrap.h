#ifndef MOON_BUILD_MENU_BOOTSTRAP_H
#define MOON_BUILD_MENU_BOOTSTRAP_H
typedef void *PTR;
typedef unsigned int DWORD;
__declspec(dllimport) PTR __stdcall LoadLibraryA(const char *);
__declspec(dllimport) PTR __stdcall GetProcAddress(PTR,const char *);
static char *cat(char *p,const char *s){while(*s)*p++=*s++;*p=0;return p;}
#include "client.h"
#endif
