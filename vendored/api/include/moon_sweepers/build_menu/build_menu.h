#ifndef MOON_BUILD_MENU_V1_H
#define MOON_BUILD_MENU_V1_H
#define MB_ABI 1u
#define MB_NATIVE_LAST_KIND 192
/* Saved IDs never depend on registration order. Preserve the original range
 * and admit 192 explicit provider definitions using the native record format. */
#define MB_FIRST_KIND 193
#define MB_LAST_KIND 384
#define MB_LIMIT (MB_LAST_KIND-MB_FIRST_KIND+1)
typedef struct {
    unsigned int abi, size;
    const char *key, *name, *category, *description;
    const char *image; /* Native catalog art key; NULL inherits the template. */
    int kind, template_kind, price;
    int power_node;
    float power_range, peak_kw, battery_kwh;
    int (*configure)(void *definition, void *world);
    void (*release)(void *definition, void *world);
    void (*update)(void *walker); /* Same main-thread dispatch in both loaders. */
    /* Optional appended v1 extension: old definition sizes remain accepted. */
    const unsigned char *icon_png;
    unsigned int icon_size, icon_width, icon_height;
} MoonBuildDefinition;
#define MB_LEGACY_SIZE ((unsigned int)__builtin_offsetof(MoonBuildDefinition,icon_png))
typedef struct {
    unsigned int abi, size;
    int (*register_item)(const MoonBuildDefinition *definition);
    int (*begin_placement)(void *walker, int kind);
} MoonBuildMenu;
typedef const MoonBuildMenu *(*MoonBuildMenuGet)(unsigned int abi, unsigned int size);
#endif
