#ifndef MOON_LOADER_INTERACTION_H
#define MOON_LOADER_INTERACTION_H
/* Game-specific interception stays outside the portable InputApiV1. The three
 * pinned ButtonControl readers cover native Binding.Keys (including inlined
 * calls), alternate keys and mouse input without suppressing a whole binding. */
static struct {
    PTR game,domain,frame,step_field,walker,keyboard,keyboard_item,mouse,mouse_button[5],readers[3];
    PTR (*invoke)(PTR,PTR,void **,PTR *);
    const PTR *(*assemblies)(PTR,U64 *);PTR (*image)(PTR),(*klass)(PTR,const char *,const char *);
    PTR (*method)(PTR,const char *,int),(*fields)(PTR,PTR *);
    const char *(*field_name)(PTR);void (*static_get)(PTR,void *);
    DWORD (*token)(PTR);
    void *(*unbox)(PTR);
    int (*frame_count)(void);
    int key_codes[256][2];PTR controls[512],source_controls[256][2],actor;unsigned control_count;
    unsigned char held[256],pressed[256],known[256],needed[256];
    DWORD thread;int pumping,frame_valid,source_ready,source_failed;
} li;
static PTR li_class(const char *ns,const char *name){
    U64 n=0;const PTR *a=li.assemblies(li.domain,&n);if(!a||n>4096)return 0;
    for(U64 i=0;i<n;i++){PTR c=li.klass(li.image(a[i]),ns,name);if(c)return c;}return 0;
}
static PTR li_call(PTR m,PTR object,void **args){PTR exception=0;PTR result=m?li.invoke(m,object,args,&exception):0;return exception?0:result;}
static PTR li_method(const char *ns,const char *klass,const char *name,int count){PTR c=li_class(ns,klass);return c?li.method(c,name,count):0;}
static unsigned li_vk(const char *name){
    if(name[0]=='D'&&name[1]=='i'&&name[2]=='g'&&name[3]=='i'&&name[4]=='t'&&name[5]>='0'&&name[5]<='9'&&!name[6])return (unsigned)name[5];
    static const struct{const char *name;unsigned key;} aliases[]={
        {"LeftArrow",37},{"RightArrow",39},{"UpArrow",38},{"DownArrow",40},{"LeftMeta",91},{"RightMeta",92},
        {"ContextMenu",93},{"NumLock",144},{"PrintScreen",44},{"ScrollLock",145},{"NumpadDivide",111},{"NumpadMultiply",106},
        {"NumpadPlus",107},{"NumpadMinus",109},{"NumpadPeriod",110},{"NumpadEnter",13}
    };
    for(unsigned i=0;i<sizeof(aliases)/sizeof(*aliases);i++)if(mi_equal(name,aliases[i].name))return aliases[i].key;
    if(name[0]=='N'&&name[1]=='u'&&name[2]=='m'&&name[3]=='p'&&name[4]=='a'&&name[5]=='d'&&name[6]>='0'&&name[6]<='9'&&!name[7])return 96u+(unsigned)(name[6]-'0');
    return mi_key(name);
}
static void li_add_code(unsigned vk,int code){if(!vk||vk>=256||code<=0)return;int *codes=li.key_codes[vk];if(!codes[0])codes[0]=code;else if(codes[0]!=code&&!codes[1])codes[1]=code;}
static void li_mark(unsigned key){
    if(!key||key>=256)return;li.needed[key]=1;unsigned family=mir_family(key);if(family){unsigned left=mir_left(family);li.needed[family]=li.needed[left]=li.needed[left+1]=1;}
}
static int li_button(PTR method,PTR control){PTR value=li_call(method,control,0);unsigned char *bit=value?li.unbox(value):0;if(!bit)li.source_failed=1;return bit&&*bit;}
static void li_snapshot(void){
    li.source_ready=li.source_failed=0;for(unsigned k=0;k<256;k++){li.held[k]=li.pressed[k]=li.known[k]=li.needed[k]=0;li.source_controls[k][0]=li.source_controls[k][1]=0;}
    for(unsigned i=0;i<loader_interactions.count;i++){
        const MoonInputChord *c=&moon_input_host_registry.actions[loader_interactions.entries[i].action-1].chord;li_mark(c->key);
        unsigned modifiers=c->required|c->forbidden;if(modifiers&1)li_mark(17);if(modifiers&2)li_mark(16);if(modifiers&4)li_mark(18);
    }
    /* A rebind changes the action chord before the old capture retires. Keep
     * the original control/Unity state through its release epoch as well. */
    for(unsigned k=1;k<256;k++)if(loader_interactions.captured[k])li_mark(k);
    PTR keyboard=0,mouse=0,seen[256];unsigned char held[256],pressed[256];unsigned count=0;
    for(unsigned k=1;k<256;k++)if(li.needed[k]){
        li.known[k]=1;unsigned button=k==1?1:k==2?2:k==4?3:k==5?4:k==6?5:0;
        if(button){if(!mouse)mouse=li_call(li.mouse,0,0);if(mouse)li.source_controls[k][0]=li_call(li.mouse_button[button-1],mouse,0);}
        else for(unsigned j=0;j<2;j++)if(li.key_codes[k][j]){if(!keyboard)keyboard=li_call(li.keyboard,0,0);if(keyboard){void *args[]={li.key_codes[k]+j};li.source_controls[k][j]=li_call(li.keyboard_item,keyboard,args);}}
        for(unsigned j=0;j<2;j++){
            PTR control=li.source_controls[k][j];if(!control)continue;unsigned n=0;while(n<count&&seen[n]!=control)n++;
            if(n==count){if(count==256)continue;seen[count]=control;held[count]=(unsigned char)li_button(li.readers[0],control);pressed[count]=(unsigned char)li_button(li.readers[1],control);count++;}
            li.held[k]|=held[n];li.pressed[k]|=pressed[n];
        }
    }
    li.source_ready=!li.source_failed;
}
static void li_controls(void){
    li.control_count=0;
    for(unsigned k=1;k<256;k++)if(loader_interactions.captured[k]){
        for(unsigned j=0;j<2;j++)if(li.source_controls[k][j])li.controls[li.control_count++]=li.source_controls[k][j];
    }
}
static void moon_interaction_pump(void){
    if(!li.thread||li.thread!=GetCurrentThreadId()||li.pumping||MoonLab_RuntimeState_v1()!=MOON_RUNTIME_READY||!loader_interactions.count)return;
    li.pumping=1;li.frame_valid=0;int frame=li.frame_count?li.frame_count():-1;
    /* The checked Time icall reads an integer without runtime_invoke boxing
     * for every intercepted button read. Queries/snapshots run once per frame. */
    if(frame>=0){
        unsigned step=0;li.static_get(li.step_field,&step);U64 epoch=((U64)(unsigned)frame<<32)|step;
        /* Fixed/dynamic InputSystem updates can share one rendered frame.
         * ButtonControl's own edge getters use this exact update-step counter. */
        if(!loader_interactions.initialized||loader_interactions.frame!=epoch){li.actor=li_call(li.walker,0,0);li_snapshot();mir_begin_events(&loader_interactions,&moon_input_host_registry,epoch,li.source_ready?li.actor:0,li.pressed);li_controls();}
        li.frame_valid=li.source_ready;
    }else{
        li.actor=0;li.source_ready=0;for(unsigned i=0;i<loader_interactions.count;i++){
            MoonInteractionEntry *e=loader_interactions.entries+i;e->state=(MoonInteractionState){0};e->consumed=1;(void)mi_sample(&moon_input_host_registry,e->action,0);
        }
    }
    li.pumping=0;
}
static void moon_interaction_observe(PTR walker){
    (void)walker;if(!li.thread)li.thread=GetCurrentThreadId();moon_interaction_pump();
}
static int loader_interaction_poll(unsigned key){return key<256&&li.source_ready&&li.thread==GetCurrentThreadId()&&li.known[key]?(int)li.held[key]:-1;}
static int loader_interaction_admit(unsigned action,unsigned key){return li.pumping||!li.frame_valid||!li.thread||li.thread!=GetCurrentThreadId()||!mir_blocked(&loader_interactions,action,key);}
static int moon_interaction_native(int id,Context *context){
    (void)id;if(!li.thread||li.thread!=GetCurrentThreadId()||li.pumping)return 0;
    moon_interaction_pump();PTR control=(PTR)context->rcx;if(!li.frame_valid||!control)return 0;
    for(unsigned k=0;k<li.control_count;k++)if(li.controls[k]==control){context->rax=0;return 1;}
    return 0;
}
static unsigned loader_interaction_register(const MoonInteractionActionV1 *spec){
    if(!registration_thread_matches()||update_sealed||!registration_owner||!runtime_registration_id[0]||!spec||spec->size!=sizeof(*spec)||!spec->action)return 0;
    unsigned n=0;while(runtime_registration_id[n]){if(spec->action[n]!=runtime_registration_id[n])return 0;n++;}
    if(spec->action[n]!='.')return 0;
    return mir_register(&loader_interactions,&moon_input_host_registry,spec,registration_owner);
}
static MoonInteractionState loader_interaction_sample(unsigned handle){
    if(!li.thread||li.thread!=GetCurrentThreadId())return (MoonInteractionState){0};moon_interaction_pump();return li.frame_valid?mir_sample(&loader_interactions,handle):(MoonInteractionState){0};
}
static int loader_interaction_take(unsigned handle,void *actor){
    if(!li.thread||li.thread!=GetCurrentThreadId())return 0;moon_interaction_pump();return li.frame_valid&&actor&&actor==li.actor&&mir_take(&loader_interactions,handle);
}
__declspec(dllexport) const MoonInteractionApiV1 *MoonLab_GetInteractionApi_v1(void){
    static const MoonInteractionApiV1 api={sizeof(api),MOON_INTERACTION_ABI,loader_interaction_register,loader_interaction_sample,loader_interaction_take};return &api;
}
static void moon_interaction_finish(int success){if(!success)mir_rollback(&loader_interactions,registration_owner);}
static int moon_interaction_seal(void){
    if(!loader_interactions.count)return 1;
    if(hook_count+3>8)return 0;
    for(unsigned i=0;i<3;i++){
        unsigned char *address=*(unsigned char **)li.readers[i];int length=instruction_length(address);if(length!=2||address[0]!=0x40||address[1]!=0x53)return 0;
        for(int j=0;j<hook_count;j++)if(hooks[j].address==address)return 0;
        Hook *h=hooks+hook_count++;h->address=address;h->length=length;h->id=100+(int)i;for(unsigned j=0;j<5;j++)h->original[j]=address[j];
    }return 1;
}
static int moon_interaction_bind(PTR domain,PTR game){
    li.domain=domain;li.game=game;
#define LI_API(field,name,type) li.field=(type)GetProcAddress(game,"il2cpp_" name);if(!li.field)return 0
    LI_API(invoke,"runtime_invoke",PTR(*)(PTR,PTR,void **,PTR *));LI_API(assemblies,"domain_get_assemblies",const PTR *(*)(PTR,U64 *));
    LI_API(image,"assembly_get_image",PTR(*)(PTR));LI_API(klass,"class_from_name",PTR(*)(PTR,const char *,const char *));
    LI_API(method,"class_get_method_from_name",PTR(*)(PTR,const char *,int));LI_API(fields,"class_get_fields",PTR(*)(PTR,PTR *));
    LI_API(field_name,"field_get_name",const char *(*)(PTR));LI_API(static_get,"field_static_get_value",void(*)(PTR,void *));LI_API(token,"method_get_token",DWORD(*)(PTR));
    LI_API(unbox,"object_unbox",void *(*)(PTR));
#undef LI_API
    li.frame=li_method("UnityEngine","Time","get_frameCount",0);li.walker=li_method("MoonCleaners","MoonRunOver","get_LocalWalker",0);
    PTR (*resolve_icall)(const char *)=(PTR(*)(const char *))GetProcAddress(game,"il2cpp_resolve_icall");li.frame_count=resolve_icall?(int(*)(void))resolve_icall("UnityEngine.Time::get_frameCount()"):0;
    li.keyboard=li_method("UnityEngine.InputSystem","Keyboard","get_current",0);li.keyboard_item=li_method("UnityEngine.InputSystem","Keyboard","get_Item",1);li.mouse=li_method("UnityEngine.InputSystem","Mouse","get_current",0);
    const char *buttons[]={"get_leftButton","get_rightButton","get_middleButton","get_backButton","get_forwardButton"};
    for(unsigned i=0;i<5;i++)if(!(li.mouse_button[i]=li_method("UnityEngine.InputSystem","Mouse",buttons[i],0)))return 0;
    const char *readers[]={"get_isPressed","get_wasPressedThisFrame","get_wasReleasedThisFrame"};const unsigned rvas[]={0x15fea00,0x15feab0,0x15feba0},tokens[]={100668486,100668488,100668489};
    for(unsigned i=0;i<3;i++){PTR m=li_method("UnityEngine.InputSystem.Controls","ButtonControl",readers[i],0);if(!m||li.token(m)!=tokens[i]||*(PTR *)m!=(char *)game+rvas[i])return 0;li.readers[i]=m;}
    PTR keys=li_class("UnityEngine.InputSystem","Key"),it=0,f;
    PTR updates=li_class("UnityEngine.InputSystem.LowLevel","InputUpdate");
    if(updates)while((f=li.fields(updates,&it))){const char *name=li.field_name(f);if(name&&mi_equal(name,"s_UpdateStepCount")){li.step_field=f;break;}}it=0;
    if(!keys||!li.step_field||!li.frame||li.token(li.frame)!=100667208||*(PTR *)li.frame!=(char *)game+0x1ac1250||!li.frame_count||!li.walker||li.token(li.walker)!=100670068||*(PTR *)li.walker!=(char *)game+0x5484f0||!li.keyboard||!li.keyboard_item||!li.mouse)return 0;
    while((f=li.fields(keys,&it))){const char *name=li.field_name(f);unsigned vk=name?li_vk(name):0;if(!vk)continue;int code=0;li.static_get(f,&code);li_add_code(vk,code);if(vk==160||vk==161)li_add_code(16,code);if(vk==162||vk==163)li_add_code(17,code);if(vk==164||vk==165)li_add_code(18,code);}
    (void)moon_input_host_api();return li.key_codes['E'][0]==19;
}
#endif
