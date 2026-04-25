// 效果名称：pixel_dissolve_wave

// ---- 用户自定义函数区 ----

// Standard 2D SDF for a rectangle
// p: point to evaluate
// b: half-extents (half-width, half-height) of the rectangle
float sdRect(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

// Smooth union operator (not used in final version but good to have)
/*
float opSmoothUnion(float d1, float d2, float k) {
    float h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) - k * h * (1.0 - h);
}
*/

// Define colors from the palette
#define COLOR_DARK_CYAN     vec3(0.129, 0.486, 0.486) // #217C7C
#define COLOR_RED           vec3(0.898, 0.357, 0.357) // #E55B5B
#define COLOR_LIGHT_GREEN   vec3(0.565, 0.784