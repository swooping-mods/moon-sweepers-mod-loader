#ifndef MOON_STATIC_MODEL_PBR_H
#define MOON_STATIC_MODEL_PBR_H
#include "static_model.h"

/* Optional per-part maps, without changing existing SMModel/SMPart layouts.
 * Metallic maps use Unity R=metallic/A=smoothness; normals use the converted
 * tangent frame. Both are linear textures. Prepare before sm_attach. */
typedef struct {int normal,metallic;float normal_scale;} SMPbr;
static inline int sm_prepare_pbr(const SMModel *model,SMResources *r,const SMPbr *maps,unsigned count){
    if(!r||!sm_valid(model)||count!=model->part_count||(count&&!maps))return 0;
    unsigned linear=0;
    for(unsigned i=0;i<count;i++){
        int indices[]={maps[i].normal,maps[i].metallic};
        for(unsigned j=0;j<2;j++){
            int index=indices[j];if(index< -1||index>=(int)model->image_count)return 0;
            if(index>=0)linear|=1u<<index;
        }
        if(!(maps[i].normal_scale>=0&&maps[i].normal_scale<=16))return 0;
    }
    /* Reject conflicting colour/data interpretations of one texture slot. */
    for(unsigned i=0;i<count;i++)if(model->parts[i].image>=0&&(linear&(1u<<model->parts[i].image)))return 0;
    if(r->ready)return r->definition==model;
    if(!sm_prepare_linear(model,r,linear))return 0;
    int ok=1;
    for(unsigned i=0;i<count;i++){
        PTR mat=su_get(r->materials[i]);
        if(maps[i].normal>=0){
            void *texture[]={su.string("_BumpMap"),su_get(r->textures[maps[i].normal])};
            call(su_method("UnityEngine","Material","SetTexture","System.String;UnityEngine.Texture"),mat,texture,&ok);
            void *keyword[]={su.string("_NORMALMAP")};call(su.material_keyword,mat,keyword,&ok);
            if(!sm_property(mat,"_BumpScale",maps[i].normal_scale))goto fail;
            call(su_method("UnityEngine","Mesh","RecalculateTangents",""),su_get(r->meshes[i]),0,&ok);
        }
        if(maps[i].metallic>=0){
            void *texture[]={su.string("_MetallicGlossMap"),su_get(r->textures[maps[i].metallic])};
            call(su_method("UnityEngine","Material","SetTexture","System.String;UnityEngine.Texture"),mat,texture,&ok);
            const char *keywords[]={"_METALLICSPECGLOSSMAP","_METALLICGLOSSMAP"};
            for(unsigned j=0;j<2;j++){void *keyword[]={su.string(keywords[j])};call(su.material_keyword,mat,keyword,&ok);}
            if(!sm_property(mat,"_Smoothness",1)||!sm_property(mat,"_GlossMapScale",1)||
               !sm_property(mat,"_SmoothnessTextureChannel",0))goto fail;
        }
        if(!ok)goto fail;
    }
    return 1;
fail:
    sm_release(r);return 0;
}
#endif
