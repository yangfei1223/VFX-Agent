# Lighting & Transform Operators Reference

## Fresnel (Schlick Approximation)
```glsl
float fresnel(float cosTheta, float f0) {
    return f0 + (1.0 - f0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
}
```
- `f0`: base reflectance (0.02–0.08 for dielectrics, 0.8+ for metals)
- Use for: rim lighting, edge glow, glass-like effects
- In 2D: compute cosTheta from SDF gradient `cosTheta = dot(normalize(grad), viewDir)`

## Simplified 2D Ambient Occlusion
```glsl
float ao(vec2 p, float d, float stepSize, int steps) {
    float occ = 0.0;
    float scale = 1.0;
    for (int i = 0; i < 5; i++) {
        if (i >= steps) break;
        float dist = d + 0.01 + float(i + 1) * stepSize;
        float sd = sceneSDF(p + normalize(p) * dist); // user-defined scene
        float diff = dist - sd;
        occ += scale * clamp(diff, 0.0, 1.0);
        scale *= 0.5;
    }
    return clamp(1.0 - 2.0 * occ, 0.0, 1.0);
}
```

## 2D Rotation
```glsl
mat2 rot2D(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}
// Usage: uv = rot2D(angle) * uv;
```

## UV Manipulations
```glsl
// Mirror/repeat
vec2 mirrorUV(vec2 uv) {
    return fract(uv) * 2.0 - 1.0; // tile with mirror
}

// Polar coordinates
vec2 toPolar(vec2 uv, vec2 center) {
    vec2 p = uv - center;
    return vec2(length(p), atan(p.y, p.x));
}

// From polar back to cartesian
vec2 fromPolar(vec2 polar) {
    return vec2(polar.x * cos(polar.y), polar.x * sin(polar.y));
}
```