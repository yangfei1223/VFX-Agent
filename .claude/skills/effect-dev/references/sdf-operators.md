# SDF Operators Reference

> All 2D SDF formulations are based on Inigo Quilez's canonical definitions:
> https://iquilezles.org/articles/distfunctions2d/
> Smooth min/max: https://iquilezles.org/articles/smoothmin/

## Primitives

### sdCircle
```glsl
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}
```
- `r`: radius (0.0–1.0), default 0.3
- Use for: circles, rings, ripples, radial masks
- Compose with: smooth_union, fresnel, rotation

### sdBox
```glsl
float sdBox(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}
```
- `b`: half-extents (vec2), default vec2(0.3, 0.2)
- Use for: rectangles, cards, panels, rounded backgrounds

### sdRoundedBox
```glsl
float sdRoundedBox(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}
```
- `b`: half-extents, `r`: corner radius
- Use for: OS UI elements, cards with rounded corners

### sdRing
```glsl
float sdRing(vec2 p, float r, float w) {
    return abs(length(p) - r) - w;
}
```
- `r`: ring radius, `w`: ring width (thin = 0.01–0.05)
- Use for: selection rings, progress indicators, halos

### sdArc
```glsl
float sdArc(vec2 p, float r, float w, float a1, float a2) {
    float a = atan(p.y, p.x);
    a = clamp(a, a1, a2);
    vec2 q = vec2(cos(a), sin(a)) * r;
    return length(p - q) - w;
}
```
- Use for: progress arcs, gauge indicators

## Boolean Operations

### opSmoothUnion
```glsl
float opSmoothUnion(float d1, float d2, float k) {
    float h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) - k * h * (1.0 - h);
}
```
- `k`: blend smoothness (0.01 = sharp, 0.3 = very soft)
- Use for: organic shape merging, blob effects

### opSmoothSubtraction
```glsl
float opSmoothSubtraction(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 + d1) / k, 0.0, 1.0);
    return mix(d2, -d1, h) + k * h * (1.0 - h);
}
```
- Use for: cutouts, hollow shapes, windows

### opSmoothIntersection
```glsl
float opSmoothIntersection(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) + k * h * (1.0 - h);
}
```
- Use for: constrained regions, overlap masks