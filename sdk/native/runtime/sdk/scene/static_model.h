#ifndef MOON_STATIC_MODEL_H
#define MOON_STATIC_MODEL_H
/* Static scene mesh presentation, independent of any gameplay framework.
 * Call on the Unity thread after su_bind. Resources are shared, children are
 * instance-owned. Destroy attached children before releasing their resources. */
#include "../native_adapters/unity.h"

typedef struct {const unsigned char *bytes;unsigned size;} SMImage;
typedef struct {const char *name;unsigned vertices,indices;const unsigned char *position,*normal,*uv,*index;int image;float colour[4],emission[3],metal,rough;int two_sided,transparent;} SMPart;
typedef struct {const SMImage *images;unsigned image_count;const SMPart *parts;unsigned part_count;} SMModel;
typedef struct {SURoot textures[16],meshes[64],materials[64];unsigned count;int ready;const SMModel *definition;} SMResources;

static inline int sm_property(PTR mat,const char *name,float value){
    int ok=1;void *a[]={su.string(name),&value};call(su.material_float,mat,a,&ok);return ok;
}
static inline int sm_colour(PTR mat,const char *name,SUColor value){
    int ok=1;void *a[]={su.string(name),&value};call(su_method("UnityEngine","Material","SetColor","System.String;UnityEngine.Color"),mat,a,&ok);return ok;
}
static inline void sm_release(SMResources *r){
    if(!r)return;
    for(unsigned i=0;i<64;i++){
        su_destroy(su_get(r->meshes[i]));su_drop(r->meshes+i);
        su_destroy(su_get(r->materials[i]));su_drop(r->materials+i);
    }
    for(unsigned i=0;i<16;i++){su_destroy(su_get(r->textures[i]));su_drop(r->textures+i);}
    su_zero(r,sizeof(*r));
}
static inline PTR sm_owned(const char *type,SURoot *root){
    PTR object=su_new("UnityEngine",type);*root=su_hold(object);
    if(!*root){su_destroy(object);return 0;}return object;
}
static inline int sm_array_call(PTR method_id,PTR self,PTR klass,unsigned count,const void *data,int stride){
    PTR array=su_array(klass,count,data,stride);SURoot hold=su_hold(array);
    if(!hold)return 0;
    int ok=1;void *a[]={array};call(method_id,self,a,&ok);su_drop(&hold);return ok;
}
/* Validate before allocating so malformed embedded definitions have no partial
 * scene effect. The uploader accepts only the existing bounded triangle format. */
static inline int sm_valid(const SMModel *model){
    if(!model||model->part_count>64||model->image_count>16||
       (model->part_count&&!model->parts)||(model->image_count&&!model->images))return 0;
    for(unsigned i=0;i<model->image_count;i++)if(!model->images[i].bytes||!model->images[i].size)return 0;
    for(unsigned i=0;i<model->part_count;i++){
        const SMPart *p=model->parts+i;
        if(!p->name||!p->vertices||p->vertices>65535||!p->indices||p->indices%3||
           !p->position||!p->normal||!p->uv||!p->index||p->image< -1||p->image>=(int)model->image_count)return 0;
    }
    return 1;
}
/* Data maps need linear sampling. The original entrypoint keeps its sRGB
 * contract; PBR callers explicitly identify their bounded image slots. */
static inline int sm_prepare_linear(const SMModel *model,SMResources *r,unsigned linear_images){
    if(!r||!sm_valid(model))return 0;
    if(r->ready)return r->definition==model;
    int ok=1;PTR shader=0;SURoot shader_root=0;
    const char *names[]={"Universal Render Pipeline/Lit","Standard"};
    for(unsigned i=0;i<2&&!shader;i++){void *a[]={su.string(names[i])};shader=call(su.shader_find,0,a,&ok);}
    shader_root=su_hold(shader);if(!shader_root)return 0;
    for(unsigned i=0;i<model->image_count;i++){
        int size=2,format=4;unsigned char mip=1,linear=(linear_images>>i)&1;
        PTR texture=sm_owned("Texture2D",r->textures+i);if(!texture)goto fail;
        void *a[]={&size,&size,&format,&mip,&linear};
        call(su_method("UnityEngine","Texture2D",".ctor","System.Int32;System.Int32;UnityEngine.TextureFormat;System.Boolean;System.Boolean"),texture,a,&ok);
        if(!ok)goto fail;
        PTR data=su_array(su.byte_class,model->images[i].size,model->images[i].bytes,1);SURoot hold=su_hold(data);
        if(!hold)goto fail;
        void *load[]={texture,data};PTR loaded=call(su_method("UnityEngine","ImageConversion","LoadImage","UnityEngine.Texture2D;System.Byte[]"),0,load,&ok);
        int valid=ok&&loaded&&*(unsigned char *)unbox(loaded);su_drop(&hold);if(!valid)goto fail;
    }
    for(unsigned i=0;i<model->part_count;i++){
        const SMPart *p=model->parts+i;
        PTR mesh=sm_owned("Mesh",r->meshes+i);if(!mesh)goto fail;
        PTR mat=sm_owned("Material",r->materials+i);if(!mat)goto fail;
        call(su.mesh_ctor,mesh,0,&ok);void *ctor[]={shader};call(su.material_ctor,mat,ctor,&ok);
        if(!ok||!sm_array_call(su.mesh_vertices,mesh,su.vector_class,p->vertices,p->position,12)||
           !sm_array_call(su.mesh_normals,mesh,su.vector_class,p->vertices,p->normal,12)||
           !sm_array_call(su.mesh_uv,mesh,su.uv_class,p->vertices,p->uv,8))goto fail;
        PTR indices=su_array(su.int_class,p->indices,p->index,4);SURoot hold=su_hold(indices);if(!hold)goto fail;
        int sub=0;unsigned char bounds=1;void *ia[]={indices,&sub,&bounds};
        call(su.mesh_indices,mesh,ia,&ok);su_drop(&hold);call(su.mesh_bounds,mesh,0,&ok);
        SUColor c={p->colour[0],p->colour[1],p->colour[2],p->colour[3]};void *ca[]={&c};call(su.material_color,mat,ca,&ok);
        if(!ok||!sm_colour(mat,"_BaseColor",c))goto fail;
        if(p->image>=0){
            PTR texture=su_get(r->textures[p->image]);
            for(int channel=0;channel<2;channel++){
                void *ta[]={su.string(channel?"_MainTex":"_BaseMap"),texture};
                call(su_method("UnityEngine","Material","SetTexture","System.String;UnityEngine.Texture"),mat,ta,&ok);
            }
        }
        if(!ok||!sm_property(mat,"_Metallic",p->metal)||!sm_property(mat,"_Smoothness",1-p->rough)||
           !sm_property(mat,"_Glossiness",1-p->rough)||!sm_property(mat,"_Cull",p->two_sided?0:2))goto fail;
        if(p->emission[0]+p->emission[1]+p->emission[2]>0){
            void *kw[]={su.string("_EMISSION")};call(su.material_keyword,mat,kw,&ok);
            if(!sm_colour(mat,"_EmissionColor",(SUColor){p->emission[0],p->emission[1],p->emission[2],1}))goto fail;
        }
        if(p->transparent){
            if(!sm_property(mat,"_Surface",1)||!sm_property(mat,"_Mode",3)||!sm_property(mat,"_SrcBlend",5)||
               !sm_property(mat,"_DstBlend",10)||!sm_property(mat,"_ZWrite",0))goto fail;
            void *kw[]={su.string("_SURFACE_TYPE_TRANSPARENT")};call(su.material_keyword,mat,kw,&ok);
            int queue=3000;void *qa[]={&queue};call(su_method("UnityEngine","Material","set_renderQueue","System.Int32"),mat,qa,&ok);
        }
        if(!ok)goto fail;
    }
    su_drop(&shader_root);r->count=model->part_count;r->definition=model;r->ready=1;return 1;
fail:
    su_drop(&shader_root);sm_release(r);return 0;
}
static inline int sm_prepare(const SMModel *model,SMResources *r){return sm_prepare_linear(model,r,0);}
/* The broader su_gameobject convenience helper does not expose parenting errors.
 * Scene attachments need checked parenting so a failed child cannot be orphaned. */
static inline PTR sm_scene_object(const char *name,PTR parent){
    SURoot hold=0;PTR go=sm_owned("GameObject",&hold);if(!go)return 0;
    int ok=1;void *a[]={su.string(name)};call(su.go_ctor,go,a,&ok);
    if(ok&&parent){
        PTR transform=call(su.go_transform,go,0,&ok);if(!transform)ok=0;
        if(ok){unsigned char keep_world=0;void *p[]={parent,&keep_world};call(su.tr_parent,transform,p,&ok);}
    }
    if(!ok){su_destroy(go);go=0;}su_drop(&hold);return go;
}
static inline int sm_layer(PTR go,int layer){
    int ok=1;void *a[]={&layer};call(su_method("UnityEngine","GameObject","set_layer","System.Int32"),go,a,&ok);return ok;
}
static inline PTR sm_attach(const SMModel *model,SMResources *r,PTR parent,int layer,const char *name){
    if(layer<0||layer>31||!name||!sm_prepare(model,r))return 0;
    PTR root=sm_scene_object(name,parent);if(!root)return 0;SURoot hold=su_hold(root);
    if(!hold){su_destroy(root);return 0;}if(!sm_layer(root,layer))goto fail;
    int ok=1;
    for(unsigned i=0;i<r->count;i++){
        PTR transform=call(su.go_transform,root,0,&ok);if(!ok||!transform)goto fail;
        PTR go=sm_scene_object(model->parts[i].name,transform);if(!go)goto fail;
        if(!sm_layer(go,layer))goto fail;
        PTR filter=su_add_component(go,"MeshFilter"),renderer=su_add_component(go,"MeshRenderer");if(!filter||!renderer)goto fail;
        void *mesh[]={su_get(r->meshes[i])};call(su.meshfilter_set,filter,mesh,&ok);
        PTR material=su_get(r->materials[i]),array=su_array(su.material_class,1,&material,8);SURoot material_array=su_hold(array);if(!material_array)goto fail;
        void *m[]={array};call(su.renderer_materials,renderer,m,&ok);su_drop(&material_array);
        if(model->parts[i].transparent){
            int shadows=0;unsigned char receive=0;void *s[]={&shadows},*v[]={&receive};
            call(su_method("UnityEngine","Renderer","set_shadowCastingMode","UnityEngine.Rendering.ShadowCastingMode"),renderer,s,&ok);
            call(su_method("UnityEngine","Renderer","set_receiveShadows","System.Boolean"),renderer,v,&ok);
        }
        if(!ok)goto fail;
    }
    su_drop(&hold);return root;
fail:
    su_destroy(root);su_drop(&hold);return 0;
}
#endif
