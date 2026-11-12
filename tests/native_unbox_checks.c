/* Actual SDK headers with injected invocation/unboxing; no game is loaded.
 * Unused Windows entry points are discarded by the host fixture's section GC. */
#include <assert.h>
#include <stdio.h>
#ifndef _WIN32
#define __declspec(value)
#define __stdcall
#endif
#include "../sdk/native/runtime/native/gameplay.h"
#include "../sdk/native/runtime/sdk/native_adapters/reflection.h"
#include "../sdk/native/runtime/sdk/native_adapters/unity.h"

enum {GOOD,NO_BOX,NO_PAYLOAD,EXCEPTION};
static int mode,invocations,unboxes,box_tag,method_tag,exception_tag,object_tag;
static PTR payload;
static PTR fake_invoke(PTR m,PTR self,void **args,PTR *exception){
    assert(m==&method_tag);(void)self;(void)args;invocations++;
    if(mode==EXCEPTION)*exception=&exception_tag;
    return mode==NO_BOX?0:&box_tag;
}
static PTR fake_unbox(PTR box){assert(box==&box_tag);unboxes++;return mode==NO_PAYLOAD?0:payload;}
static void prepare(PTR data,int failure){payload=data;mode=failure;invocations=unboxes=0;}
static void failure_counts(void){assert(invocations==1&&unboxes==(mode==NO_PAYLOAD));}
static void failed_reads(void){
    int number=73;unsigned char truth=1;float scalar=8;
    DVec vector={1,2,3};SUQuat rotation={1,2,3,4};
    for(int fault=NO_BOX;fault<=EXCEPTION;fault++){
        int ok=1;prepare(&number,fault);assert(!integer(&method_tag,0,&ok)&&!ok);failure_counts();
        ok=1;prepare(&truth,fault);assert(!boolean(&method_tag,0,&ok)&&!ok);failure_counts();
        ok=1;prepare(&scalar,fault);assert(dnumber(&method_tag,0,&ok)==0&&!ok);failure_counts();
        ok=1;prepare(&vector,fault);DVec d=dvector(&method_tag,0,&ok);
        assert(!ok&&d.x==0&&d.y==0&&d.z==0);failure_counts();
        prepare(&scalar,fault);assert(su_number(&method_tag,0)==0);failure_counts();
        prepare(&vector,fault);SPVec3 v=su_vector(&method_tag,0);
        assert(v.x==0&&v.y==0&&v.z==0);failure_counts();
        prepare(&truth,fault);assert(!su_alive(&object_tag));failure_counts();
        prepare(&rotation,fault);SUQuat q=su_rotation(su_v(0,0,1),su_v(0,1,0));
        assert(q.x==0&&q.y==0&&q.z==0&&q.w==1);failure_counts();
        float out=42;prepare(&scalar,fault);
        assert(!su_number_checked(&method_tag,0,&out)&&out==42);failure_counts();
        SPVec3 outv={42,43,44};prepare(&vector,fault);
        assert(!su_vector_checked(&method_tag,0,&outv));
        assert(outv.x==42&&outv.y==43&&outv.z==44);failure_counts();
    }
    /* A sticky failed query is not repaired by a later nonnull result. */
    int ok=0;prepare(&number,GOOD);assert(!integer(&method_tag,0,&ok)&&!ok&&!unboxes);
    ok=0;prepare(&truth,GOOD);assert(!boolean(&method_tag,0,&ok)&&!ok&&!unboxes);
    ok=0;prepare(&scalar,GOOD);assert(dnumber(&method_tag,0,&ok)==0&&!ok&&!unboxes);
    ok=0;prepare(&vector,GOOD);DVec d=dvector(&method_tag,0,&ok);
    assert(!ok&&d.x==0&&d.y==0&&d.z==0&&!unboxes);
    prepare(&scalar,GOOD);assert(!su_number_checked(&method_tag,0,0)&&!invocations&&!unboxes);
    prepare(&vector,GOOD);assert(!su_vector_checked(&method_tag,0,0)&&!invocations&&!unboxes);
    ok=1;prepare(&number,GOOD);assert(!integer(0,0,&ok)&&!ok&&!invocations&&!unboxes);
}
static void valid_values(void){
    int number=-73,ok=1;prepare(&number,GOOD);assert(integer(&method_tag,0,&ok)==-73&&ok&&unboxes==1);
    unsigned char truth=2;prepare(&truth,GOOD);assert(boolean(&method_tag,0,&ok)==1&&ok);
    truth=0;prepare(&truth,GOOD);assert(boolean(&method_tag,0,&ok)==0&&ok);
    float scalar=-4.5f;prepare(&scalar,GOOD);assert(dnumber(&method_tag,0,&ok)==scalar&&ok);
    prepare(&scalar,GOOD);assert(su_number(&method_tag,0)==scalar&&unboxes==1);
    float out=42;scalar=0;prepare(&scalar,GOOD);
    assert(su_number_checked(&method_tag,0,&out)&&out==0&&unboxes==1);
    DVec vector={1,-2,3};prepare(&vector,GOOD);DVec d=dvector(&method_tag,0,&ok);
    assert(ok&&d.x==1&&d.y==-2&&d.z==3);
    prepare(&vector,GOOD);SPVec3 v=su_vector(&method_tag,0);
    assert(v.x==1&&v.y==-2&&v.z==3&&unboxes==1);
    SPVec3 outv={0};prepare(&vector,GOOD);assert(su_vector_checked(&method_tag,0,&outv));
    assert(outv.x==1&&outv.y==-2&&outv.z==3);
    truth=1;prepare(&truth,GOOD);assert(su_alive(&object_tag));
    SUQuat rotation={1,2,3,4};prepare(&rotation,GOOD);
    SUQuat q=su_rotation(su_v(0,0,1),su_v(0,1,0));assert(q.x==1&&q.y==2&&q.z==3&&q.w==4);
    /* Nonfinite policy belongs to callers, not boxed-value transport. */
    union {unsigned u;float f;} nan={0x7fc00000u};prepare(&nan.f,GOOD);
    assert(su_number_checked(&method_tag,0,&out)&&out!=out);
    prepare(&nan.f,GOOD);float n=dnumber(&method_tag,0,&ok);assert(ok&&n!=n);
    vector.x=nan.f;prepare(&vector,GOOD);assert(su_vector_checked(&method_tag,0,&outv)&&outv.x!=outv.x);
}
int main(void){
    invoke=fake_invoke;unbox=fake_unbox;su.obj_alive=su.look_rotation=&method_tag;
    failed_reads();valid_values();
    puts("native boxed payload failure/default/status checks passed");return 0;
}
