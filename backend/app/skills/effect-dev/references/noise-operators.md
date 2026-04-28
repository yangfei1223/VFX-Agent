# Noise Operators Reference

## Hash Functions (building blocks)

```glsl
float hash21(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return fract(p.x * p.y);
}

vec2 hash22(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}
```

## Value Noise
```glsl
float valueNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), u.x),
               mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), u.x),
               u.y);
}
```
- Output: [0, 1], cheap, blocky appearance
- Best for: subtle grain, low-detail textures

## Perlin Gradient Noise
```glsl
float perlinNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(dot(hash22(i + vec2(0,0)), f - vec2(0,0)),
                   dot(hash22(i + vec2(1,0)), f - vec2(1,0)), u.x),
               mix(dot(hash22(i + vec2(0,1)), f - vec2(0,1)),
                   dot(hash22(i + vec2(1,1)), f - vec2(1,1)), u.x),
               u.y);
}
```
- Output: ~[-1, 1], natural, directional
- Best for: clouds, fire, water, natural textures

## Simplex Noise
```glsl
float simplexNoise(vec2 p) {
    // Skew and unskew factors
    const vec2 F = vec2(0.5 * (sqrt(3.0) - 1.0));
    const vec2 G = vec2((3.0 - sqrt(3.0)) / 6.0);

    vec2 s = floor(p + dot(p, F));
    vec2 i = s - floor(s * G);
    vec2 f = p - i - dot(i, G);

    vec2 o1 = (f.x > f.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 o2 = i + vec2(0.0, 1.0) - floor((i + vec2(0.0, 1.0)) * G);
    vec2 o3 = i + vec2(1.0, 1.0) - floor((i + vec2(1.0, 1.0)) * G);

    float n0 = 0.0, n1 = 0.0, n2 = 0.0;
    vec2 d0 = f - vec2(0,0);
    vec2 d1 = f - o1;
    vec2 d2 = f - o2;

    float t0 = 0.5 - dot(d0, d0);
    if (t0 > 0.0) n0 = t0 * t0 * t0 * t0 * dot(hash22(s), d0);
    float t1 = 0.5 - dot(d1, d1);
    if (t1 > 0.0) n1 = t1 * t1 * t1 * t1 * dot(hash22(s + o1), d1);
    float t2 = 0.5 - dot(d2, d2);
    if (t2 > 0.0) n2 = t2 * t2 * t2 * t2 * dot(hash22(s + o2), d2);

    return 70.0 * (n0 + n1 + n2);
}
```
- Output: ~[-1, 1], isotropic, no directional artifacts
- Best for: high-quality organic textures, less grid bias

## Voronoi / Worley
```glsl
vec3 voronoi(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float d1 = 8.0, d2 = 8.0;
    vec2 closestCell = vec2(0.0);

    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = hash22(i + neighbor);
            point = 0.5 + 0.5 * sin(u_time + 6.2831 * point);
            vec2 diff = neighbor + point - f;
            float dist = length(diff);
            if (dist < d1) { d2 = d1; d1 = dist; closestCell = i + neighbor; }
            else if (dist < d2) { d2 = dist; }
        }
    }
    return vec3(d1, d2, hash21(closestCell)); // F1, F2, cell_id
}
```
- `voronoi(p).x` = F1 (nearest cell distance)
- `voronoi(p).y` = F2 (second nearest)
- `voronoi(p).z` = cell random ID
- Use for: cells, cracks, crystals, organic partitions

## FBM (Fractal Brownian Motion)
```glsl
float fbm(vec2 p, int octaves) {
    float val = 0.0;
    float amp = 0.5;
    float freq = 1.0;
    for (int i = 0; i < 6; i++) {
        if (i >= octaves) break;
        val += amp * perlinNoise(p * freq); // or valueNoise/simplexNoise
        freq *= 2.0;
        amp *= 0.5;
    }
    return val;
}
```
- `octaves`: 2 = very soft, 4 = standard, 6 = detailed (performance cost)
- Use for: complex natural textures, layered effects