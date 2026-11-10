/* Reflection boundary for the pinned IL2CPP runtime. Unity calls belong to the
 * main-thread callback; persistent managed objects are held by GC handles. */
#ifndef MOON_NATIVE_UNITY_H
#define MOON_NATIVE_UNITY_H
#include "raycast_layout.h"
#ifndef SP_VEC3_DEFINED
#define SP_VEC3_DEFINED
typedef struct {float x,y,z;} SPVec3;
#endif
typedef struct {float x,y,z,w;} SUQuat;
typedef struct {float r,g,b,a;} SUColor;
/* Unity's current GC handles are pointer-sized slot addresses, not the u32
 * indices used by older IL2CPP releases. Truncating one corrupts its page. */
typedef U64 SURoot;
_Static_assert(sizeof(SURoot)==sizeof(PTR),"current IL2CPP pointer-sized GC handle");
static struct {
    PTR (*methods)(PTR,PTR *),(*param)(PTR,DWORD),(*class_type)(PTR),(*type_object)(PTR);
    const char *(*name)(PTR);DWORD (*arity)(PTR);
    char *(*type_name)(PTR);void (*free)(PTR);
    PTR (*new_object)(PTR),(*new_array)(PTR,U64),(*string)(const char *);
    PTR (*array_address)(PTR,int,U64),(*target)(SURoot);
    U64 (*array_length)(PTR);SURoot (*root)(PTR,BOOL);void (*unroot)(SURoot);
    const unsigned short *(*chars)(PTR);int (*string_length)(PTR);
    void (*static_field)(PTR,void *);int (*field_offset)(PTR);
    int (*value_size)(PTR,DWORD *);
    PTR go_ctor,go_add,go_component,go_transform,obj_alive,obj_destroy,obj_name;
    PTR tr_position,tr_local_position,tr_rotation,tr_local_rotation,tr_scale,tr_parent;
    PTR tr_get_position,tr_get_rotation,tr_up,tr_forward,tr_right;
    PTR look_rotation,mesh_ctor,mesh_vertices,mesh_normals,mesh_uv,mesh_subcount,mesh_indices,mesh_bounds;
    PTR meshfilter_set,renderer_materials,material_ctor,material_color,material_float,material_int,material_keyword;
    PTR shader_find,primitive,collider_enabled,renderer_enabled;
    PTR vector_class,int_class,uv_class,material_class,byte_class,intptr_class;
    PTR physics_ray,physics_capsule,physics_cast,hit_collider;
    PTR time_delta,time_unscaled,input_key,input_mouse,camera_main,camera_ray;
    PTR text_ctor,text_text,text_size,text_anchor,text_align,text_color,text_fontsize;
    int hit_size,hit_point,hit_normal,hit_distance,ready;const char *failed;
} su;
static inline int su_eq(const char *a,const char *b){if(!a||!b)return a==b;while(*a&&*a==*b){a++;b++;}return *a==*b;}
static inline void su_copy(void *to,const void *from,U64 n){unsigned char *d=to;const unsigned char *s=from;for(U64 i=0;i<n;i++)d[i]=s[i];}
static inline void su_zero(void *to,U64 n){unsigned char *d=to;for(U64 i=0;i<n;i++)d[i]=0;}
/* Pinned array-length producer reads length at +0x18; the adjacent native
 * element-address producer uses +0x20. These are checked current-build facts. */
static inline PTR su_array_address(PTR array,int stride,U64 index){
    if(!array||stride<1||index>=su.array_length(array))return 0;
    return (unsigned char *)array+32+(U64)stride*index;
}
static inline float su_sqrt(float x){if(x<=0)return 0;float n=x>1?x:1;for(int i=0;i<14;i++)n=.5f*(n+x/n);return n;}
static inline SPVec3 su_v(float x,float y,float z){return (SPVec3){x,y,z};}
static inline SPVec3 su_add(SPVec3 a,SPVec3 b){return su_v(a.x+b.x,a.y+b.y,a.z+b.z);}
static inline SPVec3 su_sub(SPVec3 a,SPVec3 b){return su_v(a.x-b.x,a.y-b.y,a.z-b.z);}
static inline SPVec3 su_mul(SPVec3 a,float s){return su_v(a.x*s,a.y*s,a.z*s);}
static inline float su_dot(SPVec3 a,SPVec3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
static inline SPVec3 su_cross(SPVec3 a,SPVec3 b){return su_v(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x);}
static inline SPVec3 su_normal(SPVec3 v){float n=su_sqrt(su_dot(v,v));return n>.00001f?su_mul(v,1/n):su_v(0,1,0);}
/* A full parameter list prevents accidental selection of a same-arity overload.
 * Parameter names come from this exact runtime, including & on by-reference args. */
static inline PTR su_method(const char *ns,const char *type,const char *name,const char *signature){
    PTR k=find_class(ns,type),it=0,m,found=0;if(!k)return 0;
    while((m=su.methods(k,&it))){
        if(!su_eq(su.name(m),name))continue;
        const char *s=signature;DWORD count=su.arity(m);int match=1;
        for(DWORD i=0;i<count;i++){
            char *type_name=su.type_name(su.param(m,i));const char *t=type_name;
            while(*t&&*s&&*s!=';'&&*t==*s){t++;s++;}
            if(*t||(*s&&*s!=';'))match=0;
            if(type_name)su.free(type_name);
            if(*s==';')s++;else if(i+1<count)match=0;
            if(!match)break;
        }
        if(*s)match=0;if(match){if(found)return 0;found=m;}
    }return found;
}
static inline PTR su_type(const char *ns,const char *name){PTR k=find_class(ns,name);return k?su.type_object(su.class_type(k)):0;}
static inline PTR su_new(const char *ns,const char *name){PTR k=find_class(ns,name);return k?su.new_object(k):0;}
static inline SURoot su_hold(PTR obj){return obj?su.root(obj,0):0;}
static inline PTR su_get(SURoot root){return root?su.target(root):0;}
static inline void su_drop(SURoot *root){if(*root)su.unroot(*root);*root=0;}
static inline int su_alive(PTR obj){if(!obj)return 0;int ok=1;void *a[]={obj};PTR value=call(su.obj_alive,0,a,&ok);return ok&&value&&*(unsigned char *)unbox(value);}
static inline PTR su_transform(PTR go){int ok=1;return call(su.go_transform,go,0,&ok);}
static inline PTR su_add_component(PTR go,const char *name){int ok=1;PTR t=su_type("UnityEngine",name);void *a[]={t};return t?call(su.go_add,go,a,&ok):0;}
static inline PTR su_component(PTR go,const char *name){int ok=1;PTR t=su_type("UnityEngine",name);void *a[]={t};return t?call(su.go_component,go,a,&ok):0;}
static inline void su_set_vector(PTR method_id,PTR transform,SPVec3 v){int ok=1;void *a[]={&v};call(method_id,transform,a,&ok);}
static inline SPVec3 su_vector(PTR method_id,PTR transform){int ok=1;SPVec3 v={0};PTR boxed=call(method_id,transform,0,&ok);if(ok&&boxed)su_copy(&v,unbox(boxed),sizeof(v));return v;}
static inline SUQuat su_rotation(SPVec3 forward,SPVec3 up){int ok=1;SUQuat q={0,0,0,1};void *a[]={&forward,&up};PTR b=call(su.look_rotation,0,a,&ok);if(ok&&b)su_copy(&q,unbox(b),sizeof(q));return q;}
static inline void su_set_quat(PTR method_id,PTR transform,SUQuat q){int ok=1;void *a[]={&q};call(method_id,transform,a,&ok);}
static inline void su_parent(PTR child,PTR parent){int ok=1;unsigned char keep_world=0;void *a[]={parent,&keep_world};call(su.tr_parent,child,a,&ok);}
static inline PTR su_gameobject(const char *name,PTR parent){
    int ok=1;PTR go=su_new("UnityEngine","GameObject");void *a[]={su.string(name)};
    call(su.go_ctor,go,a,&ok);if(!ok)return 0;if(parent)su_parent(su_transform(go),parent);return go;
}
static inline void su_destroy(PTR obj){if(!obj)return;int ok=1;void *a[]={obj};call(su.obj_destroy,0,a,&ok);}
static inline void su_bool(PTR method_id,PTR self,int enabled){int ok=1;unsigned char value=(unsigned char)!!enabled;void *a[]={&value};call(method_id,self,a,&ok);}
static inline void su_float(PTR method_id,PTR self,float value){int ok=1;void *a[]={&value};call(method_id,self,a,&ok);}
static inline void su_int(PTR method_id,PTR self,int value){int ok=1;void *a[]={&value};call(method_id,self,a,&ok);}
static inline float su_number(PTR method_id,PTR self){int ok=1;PTR v=call(method_id,self,0,&ok);return ok&&v?*(float *)unbox(v):0;}
static inline PTR su_array(PTR klass,U64 count,const void *values,int stride){PTR a=su.new_array(klass,count);if(a&&count&&values)su_copy(su.array_address(a,stride,0),values,count*(U64)stride);return a;}
static inline void su_text(PTR text,const char *value){int ok=1;void *a[]={su.string(value)};call(su.text_text,text,a,&ok);}
static inline int su_string(PTR str,char *out,int cap){
    if(!str||cap<1)return 0;int n=su.string_length(str);const unsigned short *s=su.chars(str);if(n>=cap)n=cap-1;
    for(int i=0;i<n;i++)out[i]=s[i]<128?(char)s[i]:'?';out[n]=0;return n;
}
static inline int su_bind_hit(PTR game){
    su.hit_size=0;su.hit_collider=0;su.failed="RaycastHit::layout";
    su.value_size=(int(*)(PTR,DWORD *))GetProcAddress(game,"il2cpp_class_value_size");if(!su.value_size)return 0;
    PTR hit=find_class("UnityEngine","RaycastHit");if(!hit)return 0;
    PTR pf=get_field(hit,"m_Point"),nf=get_field(hit,"m_Normal"),df=get_field(hit,"m_Distance"),cf=get_field(hit,"m_Collider");if(!pf||!nf||!df||!cf)return 0;
    su.hit_point=su.field_offset(pf)-16;su.hit_normal=su.field_offset(nf)-16;su.hit_distance=su.field_offset(df)-16;
    DWORD alignment=0;su.hit_size=su.value_size(hit,&alignment);
    if(!moon_raycast_layout_valid(su.hit_size,alignment,su.hit_point,su.hit_normal,su.hit_distance,su.field_offset(cf)-16))return 0;
    su.hit_collider=su_method("UnityEngine","RaycastHit","get_collider","");return su.hit_collider!=0;
}
static inline int su_bind(PTR game){
#define SU_EXPORT(F,N,T) su.failed=N;su.F=(T)GetProcAddress(game,"il2cpp_" N);if(!su.F)return 0
    SU_EXPORT(methods,"class_get_methods",PTR(*)(PTR,PTR *));SU_EXPORT(param,"method_get_param",PTR(*)(PTR,DWORD));
    SU_EXPORT(name,"method_get_name",const char *(*)(PTR));SU_EXPORT(arity,"method_get_param_count",DWORD(*)(PTR));
    SU_EXPORT(type_name,"type_get_name",char *(*)(PTR));SU_EXPORT(free,"free",void(*)(PTR));
    SU_EXPORT(class_type,"class_get_type",PTR(*)(PTR));SU_EXPORT(type_object,"type_get_object",PTR(*)(PTR));
    SU_EXPORT(new_object,"object_new",PTR(*)(PTR));SU_EXPORT(new_array,"array_new",PTR(*)(PTR,U64));
    SU_EXPORT(array_length,"array_length",U64(*)(PTR));
    SU_EXPORT(string,"string_new",PTR(*)(const char *));SU_EXPORT(chars,"string_chars",const unsigned short *(*)(PTR));
    SU_EXPORT(string_length,"string_length",int(*)(PTR));SU_EXPORT(root,"gchandle_new",SURoot(*)(PTR,BOOL));
    SU_EXPORT(target,"gchandle_get_target",PTR(*)(SURoot));SU_EXPORT(unroot,"gchandle_free",void(*)(SURoot));
    SU_EXPORT(static_field,"field_static_get_value",void(*)(PTR,void *));SU_EXPORT(field_offset,"field_get_offset",int(*)(PTR));
#undef SU_EXPORT
    const unsigned char *length_code=(const unsigned char *)(PTR)su.array_length;
    if(length_code[0]!=0xe9)return 0;int displacement=0;su_copy(&displacement,length_code+1,4);length_code+=5+displacement;
    if(length_code[0]!=0x8b||length_code[1]!=0x41||length_code[2]!=0x18||length_code[3]!=0xc3)return 0;
    su.array_address=su_array_address;
#define SU_BIND(F,T,N,S) su.failed=T "::" N;su.F=su_method("UnityEngine",T,N,S);if(!su.F)return 0
    SU_BIND(go_ctor,"GameObject",".ctor","System.String");SU_BIND(go_add,"GameObject","AddComponent","System.Type");
    SU_BIND(go_component,"GameObject","GetComponent","System.Type");SU_BIND(go_transform,"GameObject","get_transform","");
    SU_BIND(obj_alive,"Object","op_Implicit","UnityEngine.Object");SU_BIND(obj_destroy,"Object","Destroy","UnityEngine.Object");
    SU_BIND(obj_name,"Object","set_name","System.String");
    SU_BIND(tr_position,"Transform","set_position","UnityEngine.Vector3");SU_BIND(tr_local_position,"Transform","set_localPosition","UnityEngine.Vector3");
    SU_BIND(tr_rotation,"Transform","set_rotation","UnityEngine.Quaternion");SU_BIND(tr_local_rotation,"Transform","set_localRotation","UnityEngine.Quaternion");
    SU_BIND(tr_scale,"Transform","set_localScale","UnityEngine.Vector3");SU_BIND(tr_parent,"Transform","SetParent","UnityEngine.Transform;System.Boolean");
    SU_BIND(tr_get_position,"Transform","get_position","");SU_BIND(tr_get_rotation,"Transform","get_rotation","");
    SU_BIND(tr_up,"Transform","get_up","");SU_BIND(tr_forward,"Transform","get_forward","");SU_BIND(tr_right,"Transform","get_right","");
    SU_BIND(look_rotation,"Quaternion","LookRotation","UnityEngine.Vector3;UnityEngine.Vector3");
    SU_BIND(mesh_ctor,"Mesh",".ctor","");SU_BIND(mesh_vertices,"Mesh","set_vertices","UnityEngine.Vector3[]");
    SU_BIND(mesh_normals,"Mesh","set_normals","UnityEngine.Vector3[]");SU_BIND(mesh_uv,"Mesh","set_uv","UnityEngine.Vector2[]");
    SU_BIND(mesh_subcount,"Mesh","set_subMeshCount","System.Int32");
    SU_BIND(mesh_indices,"Mesh","SetTriangles","System.Int32[];System.Int32;System.Boolean");
    SU_BIND(mesh_bounds,"Mesh","RecalculateBounds","");SU_BIND(meshfilter_set,"MeshFilter","set_sharedMesh","UnityEngine.Mesh");
    SU_BIND(renderer_materials,"Renderer","set_sharedMaterials","UnityEngine.Material[]");
    SU_BIND(renderer_enabled,"Renderer","set_enabled","System.Boolean");
    SU_BIND(material_ctor,"Material",".ctor","UnityEngine.Shader");SU_BIND(material_color,"Material","set_color","UnityEngine.Color");
    SU_BIND(material_float,"Material","SetFloat","System.String;System.Single");
    SU_BIND(material_keyword,"Material","EnableKeyword","System.String");SU_BIND(shader_find,"Shader","Find","System.String");
    SU_BIND(primitive,"GameObject","CreatePrimitive","UnityEngine.PrimitiveType");SU_BIND(collider_enabled,"Collider","set_enabled","System.Boolean");
    SU_BIND(time_delta,"Time","get_deltaTime","");SU_BIND(time_unscaled,"Time","get_unscaledTime","");
    SU_BIND(physics_ray,"Physics","Raycast","UnityEngine.Vector3;UnityEngine.Vector3;UnityEngine.RaycastHit&;System.Single;System.Int32;UnityEngine.QueryTriggerInteraction");
    SU_BIND(physics_capsule,"Physics","CheckCapsule","UnityEngine.Vector3;UnityEngine.Vector3;System.Single;System.Int32;UnityEngine.QueryTriggerInteraction");
    SU_BIND(physics_cast,"Physics","CapsuleCastNonAlloc","UnityEngine.Vector3;UnityEngine.Vector3;System.Single;UnityEngine.Vector3;UnityEngine.RaycastHit[];System.Single;System.Int32;UnityEngine.QueryTriggerInteraction");
#undef SU_BIND
    su.vector_class=find_class("UnityEngine","Vector3");su.uv_class=find_class("UnityEngine","Vector2");
    su.int_class=find_class("System","Int32");su.byte_class=find_class("System","Byte");su.intptr_class=find_class("System","IntPtr");su.material_class=find_class("UnityEngine","Material");
    if(!su.vector_class||!su.int_class||!su.uv_class||!su.material_class||!su.byte_class||!su.intptr_class)return 0;
    /* Current Unity's native RaycastHit fields are checked rather than copied
     * from a different game/version. IL2CPP offsets include the object header. */
    if(!su_bind_hit(game))return 0;
    su.input_key=su_method("UnityEngine","Input","GetKeyDown","UnityEngine.KeyCode");
    su.input_mouse=su_method("UnityEngine","Input","GetMouseButtonDown","System.Int32");
    su.camera_main=su_method("UnityEngine","Camera","get_main","");
    su.ready=1;return 1;
}
#endif
