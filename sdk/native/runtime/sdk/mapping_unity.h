#ifndef MOONLAB_MAPPING_UNITY_H
#define MOONLAB_MAPPING_UNITY_H
#include "mapping.h"

/* Uses the shared reflection subset already supplied by each native consumer.
 * Bindings contain metadata only; worlds and screens stay caller-owned. */
typedef struct {
    PTR component, map_open, map_begin, map_close, count, direction, raised, landmark;
    PTR settings_field, radius_field;
    int flag_kind;
} MoonMapBindings;
typedef struct {
    const MoonMapBindings *bindings;
    PTR world;
} MoonMapWorld;
static inline int moon_map_bind(MoonMapBindings *b) {
#define MM(F, N, T, M, S)                                                                                    \
    b->F = dmethod(N, T, M, S);                                                                              \
    if (!b->F)                                                                                               \
    return 0
    MM(component, "UnityEngine", "Component", "GetComponent", "System.Type");
    MM(map_open, "MoonCleaners", "MoonMapScreen", "get_IsOpen", "");
    MM(map_begin, "MoonCleaners", "MoonMapScreen", "Open", "");
    MM(map_close, "MoonCleaners", "MoonMapScreen", "Close", "");
    MM(count, "MoonCleaners", "MoonWorld", "get_LandmarkCount", "");
    MM(direction, "MoonCleaners", "MoonWorld", "LandmarkDirection", "System.Int32");
    MM(raised, "MoonCleaners", "MoonWorld", "IsLandmarkRaised", "System.Int32");
    MM(landmark, "MoonCleaners", "MoonWorld", "Landmark", "System.Int32");
#undef MM
    b->settings_field = get_field(find_class("MoonCleaners", "MoonWorld"), "settings");
    b->radius_field = get_field(find_class("MoonCleaners", "MoonSettings"), "radius");
    /* Landmark's concrete class is not assumed: resolve its kind per sample. */
    PTR flag = get_field(find_class("MoonCleaners", "MoonLandmarkKind"), "Flag");
    void (*stat)(PTR, void *) = (void (*)(PTR, void *))GetProcAddress(GetModuleHandleA("GameAssembly.dll"),
                                                                      "il2cpp_field_static_get_value");
    if (!b->settings_field || !b->radius_field || !flag || !stat)
        return 0;
    stat(flag, &b->flag_kind);
    return 1;
}
static inline PTR moon_map_screen(const MoonMapBindings *b, PTR walker, int *ok) {
    void *a[] = {dtype("MoonCleaners", "MoonMapScreen")};
    return a[0] ? call(b->component, walker, a, ok) : 0;
}
static inline int moon_map_open(const MoonMapBindings *b, PTR screen) {
    int ok = 1;
    return screen && boolean(b->map_open, screen, &ok) && ok;
}
static inline float moon_map_radius(const MoonMapBindings *b, PTR world) {
    PTR settings = 0;
    float radius = 0;
    if (world)
        field_value(world, b->settings_field, &settings);
    if (settings)
        field_value(settings, b->radius_field, &radius);
    return radius;
}
static inline int moon_map_world_count(void *context, int *ok) {
    MoonMapWorld *q = context;
    return integer(q->bindings->count, q->world, ok);
}
static inline MoonMapPoint moon_map_direction(const MoonMapBindings *b, PTR world, int index, int *ok) {
    void *a[] = {&index};
    PTR v = call(b->direction, world, a, ok);
    MoonMapPoint p = {0};
    if (v)
        dcopy(&p, unbox(v), sizeof(p));
    else
        *ok = 0;
    return p;
}
static inline int moon_map_world_sample(void *context, int index, MoonMapLandmark *out) {
    MoonMapWorld *q = context;
    const MoonMapBindings *b = q->bindings;
    int ok = 1;
    void *a[] = {&index};
    DRoot record = dhold(call(b->landmark, q->world, a, &ok));
    PTR item = dget(record);
    PTR kind = item ? get_field(object_class(item), "kind") : 0;
    if (!ok || !kind) {
        ddrop(&record);
        return 0;
    }
    int value = -1;
    field_value(item, kind, &value);
    out->flag = value == b->flag_kind;
    ddrop(&record);
    PTR raised = call(b->raised, q->world, a, &ok);
    if (!raised)
        return 0;
    out->raised = *(unsigned char *)unbox(raised) != 0;
    out->direction = moon_map_direction(b, q->world, index, &ok);
    return ok;
}
static inline MoonMapQuery moon_map_query(MoonMapWorld *world) {
    return (MoonMapQuery){world, moon_map_world_count, moon_map_world_sample};
}

typedef struct {
    DRoot object, material;
} MoonMapGlobeMarker;
static inline int moon_map_object_alive(PTR object) {
    int ok = 1;
    void *a[] = {object};
    PTR v =
        object ? call(dmethod("UnityEngine", "Object", "op_Implicit", "UnityEngine.Object"), 0, a, &ok) : 0;
    return ok && v && *(unsigned char *)unbox(v);
}
static inline void moon_map_globe_marker_remove(MoonMapGlobeMarker *marker) {
    DRoot *roots[] = {&marker->object, &marker->material};
    for (unsigned i = 0; i < 2; i++) {
        PTR object = dget(*roots[i]);
        if (moon_map_object_alive(object)) {
            int ok = 1;
            void *a[] = {object};
            call(dmethod("UnityEngine", "Object", "Destroy", "UnityEngine.Object"), 0, a, &ok);
        }
        ddrop(roots[i]);
    }
}
static inline int moon_map_globe_marker_place(MoonMapGlobeMarker *marker, PTR parent, MoonMapPoint direction,
                                              float radius, float surface_scale, float size,
                                              const float color[4]) {
    if (moon_map_object_alive(dget(marker->object)))
        return 1;
    moon_map_globe_marker_remove(marker);
    if (!parent || !(radius > 0))
        return 0;
    int ok = 1, sphere = 0;
    void *a[] = {&sphere};
    PTR object =
        call(dmethod("UnityEngine", "GameObject", "CreatePrimitive", "UnityEngine.PrimitiveType"), 0, a, &ok);
    if (!ok || !object)
        return 0;
    marker->object = dhold(object);
    PTR transform = call(dmethod("UnityEngine", "GameObject", "get_transform", ""), object, 0, &ok);
    unsigned char no = 0;
    void *pa[] = {parent, &no};
    call(dmethod("UnityEngine", "Transform", "SetParent", "UnityEngine.Transform;System.Boolean"), transform,
         pa, &ok);
    MoonMapPoint position = moon_map_globe_point(direction, radius, surface_scale),
                 scale = {radius * size, radius * size, radius * size};
    void *pos[] = {&position}, *sc[] = {&scale};
    call(dmethod("UnityEngine", "Transform", "set_localPosition", "UnityEngine.Vector3"), transform, pos,
         &ok);
    call(dmethod("UnityEngine", "Transform", "set_localScale", "UnityEngine.Vector3"), transform, sc, &ok);
    void *ct[] = {dtype("UnityEngine", "Collider")};
    PTR collider = call(dmethod("UnityEngine", "GameObject", "GetComponent", "System.Type"), object, ct, &ok);
    void *off[] = {&no};
    if (collider)
        call(dmethod("UnityEngine", "Collider", "set_enabled", "System.Boolean"), collider, off, &ok);
    void *rt[] = {dtype("UnityEngine", "MeshRenderer")};
    PTR renderer = call(dmethod("UnityEngine", "GameObject", "GetComponent", "System.Type"), object, rt, &ok);
    PTR material =
        renderer ? call(dmethod("UnityEngine", "Renderer", "get_material", ""), renderer, 0, &ok) : 0;
    if (material) {
        marker->material = dhold(material);
        void *c[] = {(void *)color};
        call(dmethod("UnityEngine", "Material", "set_color", "UnityEngine.Color"), material, c, &ok);
    }
    if (!ok) {
        moon_map_globe_marker_remove(marker);
        return 0;
    }
    return 1;
}
#endif
