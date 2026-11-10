#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef void *PTR;typedef uint32_t DWORD;typedef uint64_t U64;typedef int BOOL;
#include "../runtime/native/hook_context.h"
static PTR AddVectoredExceptionHandler(DWORD a,int (*b)(ExceptionPointers *)){(void)a;(void)b;return (PTR)1;}
static DWORD RemoveVectoredExceptionHandler(PTR a){(void)a;return 1;}
static BOOL VirtualProtect(PTR a,U64 b,DWORD c,DWORD *d){(void)a;(void)b;(void)c;*d=4;return 1;}
static PTR GetCurrentProcess(void){return (PTR)1;}
static BOOL FlushInstructionCache(PTR a,const void *b,U64 c){(void)a;(void)b;(void)c;return 1;}
#include "../runtime/native/hook_engine.h"
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}}while(0)
static int observer(int id,Context *c){(void)id;(void)c;return 0;}
int main(void){
    unsigned char code[5]={0x48,0x89,0x74,0x24,0x18};before_hook=observer;hook_count=1;
    hook_count=0;CHECK(install_local_hooks());hook_count=1;
    for(int reg=0;reg<2;reg++)for(int offset=8;offset<=32;offset+=8){
        code[2]=reg?0x54:0x74;
        code[4]=(unsigned char)offset;
        CHECK(instruction_length(code)==5);
        Hook *h=hooks;h->address=code;h->length=5;memcpy(h->original,code,5);
        U64 stack[6]={11,22,33,44,55,66},original[6];memcpy(original,stack,sizeof(stack));
        Context context={0};context.rsp=(U64)stack;context.rsi=0x123456789abcULL;context.rdx=0xfedcba987654ULL;context.eflags=0x246;
        ExceptionRecord record={.code=0x80000003,.address=code};ExceptionPointers exception={&record,&context};
        CHECK(exception_handler(&exception)==-1);CHECK(context.rsp==(U64)stack&&context.rip==(U64)code+5&&context.eflags==0x246);
        for(int i=0;i<6;i++)CHECK(stack[i]==(i==offset/8?(reg?context.rdx:context.rsi):original[i]));
    }
    code[4]=0x28;CHECK(!instruction_length(code));code[4]=0x18;code[2]=0x64;CHECK(!instruction_length(code));
    puts("vessel/map RSI/RDX prologues preserve exact stack offsets, flags and continuation");return 0;
}
