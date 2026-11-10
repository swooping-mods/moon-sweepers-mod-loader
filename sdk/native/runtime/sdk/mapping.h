#ifndef MOONLAB_MAPPING_H
#define MOONLAB_MAPPING_H

/* Header-only map services. Callers own storage, clocks, range and gameplay
 * policy; a query never retains a world or a borrowed landmark. */
#define MOON_MAP_LANDMARK_LIMIT 1024
typedef struct {
    float x, y, z;
} MoonMapPoint;
typedef struct {
    MoonMapPoint direction;
    int flag, raised;
} MoonMapLandmark;
typedef struct {
    void *context;
    int (*count)(void *context, int *ok);
    int (*sample)(void *context, int index, MoonMapLandmark *landmark);
} MoonMapQuery;
enum { MOON_MAP_FLAGS = 0, MOON_MAP_SITES = 1, MOON_MAP_ALL = 2 };
static inline int moon_map_known(const unsigned char *bits, unsigned bytes, int index) {
    return bits && index >= 0 && (unsigned)index / 8 < bytes && (bits[index / 8] & (1u << (index % 8))) != 0;
}
static inline int moon_map_discover(unsigned char *bits, unsigned bytes, int index) {
    if (!bits || index < 0 || (unsigned)index / 8 >= bytes || moon_map_known(bits, bytes, index))
        return 0;
    bits[index / 8] |= (unsigned char)(1u << (index % 8));
    return 1;
}
static inline int moon_map_count(int count) {
    return count < 0 ? 0 : (count > MOON_MAP_LANDMARK_LIMIT ? MOON_MAP_LANDMARK_LIMIT : count);
}
static inline MoonMapPoint moon_map_globe_point(MoonMapPoint direction, float radius, float scale) {
    return (MoonMapPoint){direction.x * radius * scale, direction.y * radius * scale,
                          direction.z * radius * scale};
}
static inline float moon_map_distance2(MoonMapPoint a, MoonMapPoint b) {
    float x = a.x - b.x, y = a.y - b.y, z = a.z - b.z;
    return x * x + y * y + z * z;
}
/* The signed seam convention matches the native compass (-180..180). */
static inline float moon_map_bearing_delta(float bearing, float heading) {
    float delta = bearing - heading;
    if (!(delta == delta) || delta > 1e7f || delta < -1e7f)
        return 0;
    while (delta > 180)
        delta -= 360;
    while (delta < -180)
        delta += 360;
    return delta;
}
static inline int moon_map_category(int kind, const int *kinds, unsigned count) {
    if (kinds)
        for (unsigned i = 0; i < count; i++)
            if (kind == kinds[i])
                return (int)i;
    return -1;
}
static inline int moon_map_marker_visible(unsigned hidden, int category, float distance, float limit) {
    return category >= 0 && category < 32 && !(hidden & (1u << category)) && distance <= limit;
}
/* Radar uses a strict limit and first-index tie break. Raising, rewards and
 * discovery rules remain with the feature; this only queries native data. */
static inline int moon_map_nearest(const MoonMapQuery *query, MoonMapPoint position, float radius, int filter,
                                   float limit2, float *distance2) {
    int ok = 1, nearest = -1;
    float best = limit2;
    if (distance2)
        *distance2 = best;
    if (!query || !query->count || !query->sample || !(radius > 0) || !(limit2 > 0))
        return -1;
    int count = moon_map_count(query->count(query->context, &ok));
    if (!ok)
        return -1;
    for (int i = 0; i < count; i++) {
        MoonMapLandmark item;
        if (!query->sample(query->context, i, &item))
            return -1;
        if (item.raised || (filter == MOON_MAP_FLAGS && !item.flag) ||
            (filter == MOON_MAP_SITES && item.flag))
            continue;
        float d = moon_map_distance2(moon_map_globe_point(item.direction, radius, 1), position);
        if (d < best) {
            best = d;
            nearest = i;
        }
    }
    if (distance2)
        *distance2 = best;
    return nearest;
}
static inline int moon_map_discover_near(const MoonMapQuery *query, MoonMapPoint position, float radius,
                                         float limit2, unsigned char *bits, unsigned bytes) {
    int ok = 1, found = 0;
    if (!query || !query->count || !query->sample || !(radius > 0) || !(limit2 >= 0))
        return 0;
    int count = moon_map_count(query->count(query->context, &ok));
    if (!ok)
        return 0;
    for (int i = 0; i < count; i++) {
        if (moon_map_known(bits, bytes, i))
            continue;
        MoonMapLandmark item;
        if (!query->sample(query->context, i, &item))
            break;
        if (item.flag &&
            moon_map_distance2(moon_map_globe_point(item.direction, radius, 1), position) <= limit2)
            found += moon_map_discover(bits, bytes, i);
    }
    return found;
}
#endif
