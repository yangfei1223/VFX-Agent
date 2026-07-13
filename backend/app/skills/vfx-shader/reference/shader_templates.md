# Shader Templates & Operator Reference (v2.0)

> Codex reads this on-demand when generating shaders. Source: v1.0 `shader_skill_reference.md`, preserved as-is.


## SDF Primitives

### sdCircle
```glsl
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}
```
- `r`: radius (0.0-1.0), default 0.3
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

### sdSegment
```glsl
float sdSegment(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}
```
- `a`: start point, `b`: end point
- Use for: lines, connectors, progress bars

### sdRing
```glsl
float sdRing(vec2 p, float r, float w) {
    return abs(length(p) - r) - w;
}
```
- `r`: ring radius, `w`: ring width (thin = 0.01-0.05)
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

---

## Extended SDF Primitives (from iq 2D SDF)

> Reference: https://iquilezles.org/articles/distfunctions2d/

### sdEllipse - exact
```glsl
float sdEllipse(vec2 p, vec2 ab) {
    p = abs(p); if (p.x > p.y) { p = p.yx; ab = ab.yx; }
    float l = ab.y*ab.y - ab.x*ab.x;
    float m = ab.x*p.x/l - ab.y*p.y/l;
    float n = ab.y*p.y/l - ab.x*p.x/l;
    float d = (m < 0.0) ? ab.x - p.x : (n > 0.0) ? length(p-ab) : dot(m*p+n*ab, vec2(m,n))/length(vec2(m,n));
    return sign(ab.x*p.x + ab.y*p.y - ab.x*ab.y) * d;
}
```
- `ab`: semi-axes (a=horizontal, b=vertical)

### sdVesica - exact
```glsl
float sdVesica(vec2 p, float r, float d) {
    p = abs(p);
    float b = sqrt(r*r - d*d*0.25);
    if (p.y > b) return length(p - vec2(0.0, b));
    return abs(length(p - vec2(-d*0.5, 0.0)) - r) * sign(p.x - d*0.5);
}
```
- `r`: radius of the two circles, `d`: distance between circle centers (0, 2r)

### sdCapsule - exact
```glsl
float sdCapsule(vec2 p, vec2 a, vec2 b, float r) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa,ba)/dot(ba,ba), 0.0, 1.0);
    return length(pa - ba*h) - r;
}
```
- `a`, `b`: axis endpoints, `r`: radius (thickness)

### sdHeart - exact
```glsl
float sdHeart(vec2 p) {
    p.x = abs(p.x);
    if (p.y + p.x > 1.0)
        return sqrt(dot(p-vec2(0.25,0.75), p-vec2(0.25,0.75))) - sqrt(2.0)/4.0;
    return sqrt(min(dot(p-vec2(0.0,1.0), p-vec2(0.0,1.0)),
                    dot(p-0.5*max(p.x+p.y,0.0), p-0.5*max(p.x+p.y,0.0)))) * sign(p.x-p.y);
}
```
- Unit-sized, centered at origin

### sdEquilateralTriangle - exact
```glsl
float sdEquilateralTriangle(vec2 p, float r) {
    const float k = sqrt(3.0);
    p.x = abs(p.x) - r;
    p.y = p.y + r/k;
    if (p.x + k*p.y > 0.0) p = vec2(p.x - k*p.y, -k*p.x - p.y)/2.0;
    p.x -= clamp(p.x, -2.0*r, 0.0);
    return -length(p)*sign(p.y);
}
```
- `r`: circumradius

### sdPentagon - exact
```glsl
float sdPentagon(vec2 p, float r) {
    const vec3 k = vec3(0.809016994, 0.587785252, 0.726542528);
    p.x = abs(p.x);
    p -= 2.0*min(dot(vec2(-k.x,k.y),p),0.0)*vec2(-k.x,k.y);
    p -= 2.0*min(dot(vec2( k.x,k.y),p),0.0)*vec2( k.x,k.y);
    p -= vec2(clamp(p.x,-r*k.z,r*k.z),r);
    return length(p)*sign(p.y);
}
```
- `r`: circumradius

### sdHexagon - exact
```glsl
float sdHexagon(vec2 p, float r) {
    const vec3 k = vec3(-0.866025404, 0.5, 0.577350269);
    p = abs(p);
    p -= 2.0*min(dot(k.xy,p),0.0)*k.xy;
    p -= vec2(clamp(p.x,-r*k.z,r*k.z),r);
    return length(p)*sign(p.y);
}
```
- `r`: circumradius

### sdOctagon - exact
```glsl
float sdOctagon(vec2 p, float r) {
    const vec3 k = vec3(-0.9238795325, 0.3826834323, 0.4142135623);
    p = abs(p);
    p -= 2.0*min(dot(vec2(k.x,k.y),p),0.0)*vec2(k.x,k.y);
    p -= 2.0*min(dot(vec2(-k.x,k.y),p),0.0)*vec2(-k.x,k.y);
    p -= vec2(clamp(p.x,-r*k.z,r*k.z),r);
    return length(p)*sign(p.y);
}
```
- `r`: circumradius

### sdStar5 - exact
```glsl
float sdStar5(vec2 p, float r, float rf) {
    const vec2 k1 = vec2(0.809016994375, -0.587785252292);
    const vec2 k2 = vec2(-k1.x, k1.y);
    p.x = abs(p.x);
    p -= 2.0*max(dot(k1,p),0.0)*k1;
    p -= 2.0*max(dot(k2,p),0.0)*k2;
    p.x = abs(p.x);
    p.y -= r;
    vec2 ba = rf*vec2(-k1.y,k1.x) - vec2(0,1);
    float h = clamp(dot(p,ba)/dot(ba,ba), 0.0, r);
    return length(p - ba*h) * sign(p.y*ba.x - p.x*ba.y);
}
```
- `r`: outer radius, `rf`: inner radius factor (0-1, controls point sharpness)

---

## SDF Boolean Operations

### Union
```glsl
float opUnion(float d1, float d2) {
    return min(d1, d2);
}
```
- Use: Combine two shapes (logical OR)

### Intersection
```glsl
float opIntersection(float d1, float d2) {
    return max(d1, d2);
}
```
- Use: Common area of two shapes (logical AND)

### Subtraction
```glsl
float opSubtraction(float d1, float d2) {
    return max(d1, -d2);
}
```
- Use: Remove shape2 from shape1

### Smooth Union
```glsl
float opSmoothUnion(float d1, float d2, float k) {
    float h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) - k * h * (1.0 - h);
}
```
- `k`: blend smoothness (0.01 = sharp, 0.3 = very soft)
- Use for: organic shape merging, blob effects

### Smooth Intersection
```glsl
float opSmoothIntersection(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) + k * h * (1.0 - h);
}
```
- Use for: constrained regions, overlap masks

### Smooth Subtraction
```glsl
float opSmoothSubtraction(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 + d1) / k, 0.0, 1.0);
    return mix(d2, -d1, h) + k * h * (1.0 - h);
}
```
- Use for: cutouts, hollow shapes, windows

### Round Blend
```glsl
float opRound(float d, float r) {
    return d - r;
}
```
- Use: Add rounded corners to any SDF

### Onion (Shell)
```glsl
float opOnion(float d, float r) {
    return abs(d) - r;
}
```
- Use: Create hollow shape with thickness `r`

### XOR (Exclusive Union) - exact everywhere
```glsl
float opXor(float d1, float d2) {
    return max(min(d1, d2), -max(d1, d2));
}
```
- Use: Show only non-overlapping regions (both interior AND exterior are exact SDF)

### Smooth Union - iq Quadratic (canonical)
```glsl
float smin(float d1, float d2, float k) {
    k *= 4.0;
    float h = max(k - abs(d1 - d2), 0.0) / k;
    return min(d1, d2) - h*h*k*(1.0/4.0);
}
```
- `k`: blend thickness in distance units (0.01 = sharp, 0.3 = very soft)
- This is iq's canonical formulation: https://iquilezles.org/articles/smoothmin/
- Normalized so `k` maps directly to blend width in SDF space

### Smooth Union with Material Blend
```glsl
// Returns vec2(distance, blendFactor)
vec2 sminBlend(float d1, float d2, float k) {
    float h = 1.0 - min(abs(d1 - d2) / (4.0*k), 1.0);
    float w = h*h;
    float m = w*0.5;
    float s = w*k;
    return (d1 < d2) ? vec2(d1 - s, m) : vec2(d2 - s, 1.0 - m);
}
```
- Second component is material blend factor (0-1), use for color/texture transitions

---

## Domain Operations

### Symmetry - Mirror X
```glsl
// Apply before SDF evaluation: p.x = abs(p.x)
// Creates mirror symmetry across Y axis
```

### Symmetry - Mirror X and Y
```glsl
// Apply before SDF evaluation: p = abs(p)
// Creates 4-fold symmetry (quadrant mirror)
```

### Infinite Repetition (2D)
```glsl
float opRepetition(vec2 p, float s) {
    vec2 q = p - s * round(p / s);
    return primitive(q);
}
```
- `s`: spacing between copies
- Use for: tiled patterns, grids, repeating elements
- Note: only works correctly for symmetric shapes; for asymmetric use `opRepetitionCorrect`

### Limited Repetition (2D)
```glsl
vec2 opLimitedRepetition(vec2 p, float s, vec2 lim) {
    vec2 id = clamp(round(p / s), -lim, lim);
    vec2 q = p - s * id;
    return vec2(primitive(q), hash21(id));  // distance + cell id for variation
}
```
- `lim`: max copies in each direction (e.g., vec2(3.0, 2.0) = 7x5 grid)
- Use for: finite grids, button arrays, icon layouts

### Rotational Repetition (2D)
```glsl
float opRotationalRepetition(vec2 p, int n) {
    float sp = 6.283185 / float(n);
    float an = atan(p.y, p.x);
    float id = floor(an / sp);
    float a1 = sp * id;
    float a2 = sp * (id + 1.0);
    float c1 = cos(a1), s1 = sin(a1);
    float c2 = cos(a2), s2 = sin(a2);
    vec2 r1 = vec2(c1*p.x + s1*p.y, -s1*p.x + c1*p.y);
    vec2 r2 = vec2(c2*p.x + s2*p.y, -s2*p.x + c2*p.y);
    return min(primitive(r1), primitive(r2));
}
```
- `n`: number of copies around center
- Use for: radial menus, clock faces, flower petals, gear patterns

---

## Noise Functions

### Hash Functions (building blocks)
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
- `hash21`: vec2 → float, output [0,1]
- `hash22`: vec2 → vec2, output [-1,1] (gradient vectors)

### Value Noise
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

### Perlin Gradient Noise
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

### Simplex Noise
```glsl
float simplexNoise(vec2 p) {
    const vec2 F = vec2(0.5 * (sqrt(3.0) - 1.0));
    const vec2 G = vec2((3.0 - sqrt(3.0)) / 6.0);

    vec2 s = floor(p + dot(p, F));
    vec2 i = s - floor(s * G);
    vec2 f = p - i - dot(i, G);

    vec2 o1 = (f.x > f.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 o2 = i + vec2(0.0, 1.0) - floor((i + vec2(0.0, 1.0)) * G);

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

### Voronoi / Worley
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
            point = 0.5 + 0.5 * sin(iTime + 6.2831 * point);
            vec2 diff = neighbor + point - f;
            float dist = length(diff);
            if (dist < d1) { d2 = d1; d1 = dist; closestCell = i + neighbor; }
            else if (dist < d2) { d2 = dist; }
        }
    }
    return vec3(d1, d2, hash21(closestCell));
}
```
- `voronoi(p).x` = F1 (nearest cell distance)
- `voronoi(p).y` = F2 (second nearest)
- `voronoi(p).z` = cell random ID
- Use for: cells, cracks, crystals, organic partitions

### FBM (Fractal Brownian Motion)
```glsl
float fbm(vec2 p, int octaves) {
    float val = 0.0;
    float amp = 0.5;
    float freq = 1.0;
    for (int i = 0; i < 6; i++) {
        if (i >= octaves) break;
        val += amp * perlinNoise(p * freq);
        freq *= 2.0;
        amp *= 0.5;
    }
    return val;
}
```
- `octaves`: 2 = very soft, 4 = standard, 6 = detailed (performance cost)
- Use for: complex natural textures, layered effects

### Turbulence
```glsl
float turbulence(vec2 p, int octaves) {
    return abs(fbm(p, octaves));
}
```
- Use: Sharp-edged noise patterns

### Smooth Voronoi
```glsl
float smoothVoronoi(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float res = 0.0;
    for (int j = -1; j <= 1; j++)
    for (int i2 = -1; i2 <= 1; i2++) {
        vec2 b = vec2(float(i2), float(j));
        vec2 r = b - f + hash22(i + b);
        float d = dot(r, r);
        res += exp2(-32.0 * sqrt(d));
    }
    return -(1.0/32.0) * log2(res);
}
```
- Output: smooth cell distances (no hard edges)
- Use for: organic cells, soft cellular textures

### Voronoise (Noise-Voronoi hybrid)
```glsl
float voronoise(vec2 p, float u, float v) {
    vec2 ip = floor(p);
    vec2 f = fract(p);
    float k = 1.0 + 63.0 * pow(1.0 - v, 4.0);
    float va = 0.0;
    float wt = 0.0;
    for (int j = -2; j <= 2; j++)
    for (int i = -2; i <= 2; i++) {
        vec2 g = vec2(float(i), float(j));
        vec3 o = vec3(hash22(ip + g), hash21(ip + g)) * vec3(u, u, 1.0);
        vec2 r = g - f + o.xy;
        float d = dot(r, r);
        float w = pow(1.0 - smoothstep(0.0, 1.414, sqrt(d)), k);
        va += w * o.z;
        wt += w;
    }
    return va / wt;
}
```
- `u=0, v=1`: Regular Noise
- `u=1, v=0`: Voronoi
- `u=1, v=1`: Voronoise (jittered interpolation)
- Use for: continuous morphing between noise types, organic patterns

### Domain Warping (Organic Distortion)
```glsl
// Two-layer fBM warping - produces organic, flowing patterns
float warpPattern(vec2 p) {
    vec2 q = vec2(fbm(p + vec2(0.0, 0.0), 4),
                  fbm(p + vec2(5.2, 1.3), 4));
    vec2 r = vec2(fbm(p + 4.0*q + vec2(1.7, 9.2), 4),
                  fbm(p + 4.0*q + vec2(8.3, 2.8), 4));
    return fbm(p + 4.0*r, 4);
}
```
- Produces highly organic, marble-like patterns
- Expensive: 5 fBM calls (4 octaves each = 20 noise evaluations)
- **Mobile warning**: reduce octaves to 2-3 for acceptable performance

---

## Lighting Models

### Fresnel Effect
```glsl
float fresnel(vec3 I, vec3 N, float power) {
    return pow(1.0 - dot(I, N), power);
}
```
- `power`: 1.0-5.0, Fresnel intensity
- Use for: edge glow, rim lighting

### Specular Highlight
```glsl
vec3 specular(vec3 normal, vec3 lightDir, vec3 viewDir, float shininess) {
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(viewDir, reflectDir), 0.0), shininess);
    return vec3(spec);
}
```
- `shininess`: 1-128, highlight sharpness

### Diffuse Light
```glsl
float diffuse(vec3 normal, vec3 lightDir) {
    return max(dot(normal, lightDir), 0.0);
}
```

### Ambient Occlusion
```glsl
float ambientOcclusion(vec2 p, float radius) {
    float ao = 0.0;
    for (int i = 0; i < 4; i++) {
        vec2 offset = vec2(cos(float(i) * 0.785), sin(float(i) * 0.785)) * radius;
        ao += smoothstep(0.0, 1.0, sdCircle(p + offset, 0.0));
    }
    return ao / 4.0;
}
```

---

## Color Operations

### Gradient
```glsl
vec3 gradient(float t, vec3[] colors, float[] positions) {
    for (int i = 0; i < colors.length - 1; i++) {
        if (t >= positions[i] && t <= positions[i + 1]) {
            float localT = (t - positions[i]) / (positions[i + 1] - positions[i]);
            return mix(colors[i], colors[i + 1], localT);
        }
    }
    return colors[colors.length - 1];
}
```

### Color Mix
```glsl
vec3 colorMix(vec3 a, vec3 b, float t) {
    return mix(a, b, t);
}
```

### Tone Mapping
```glsl
// Reinhard
vec3 reinhard(vec3 color) {
    return color / (1.0 + color);
}

// ACES Filmic
vec3 aces(vec3 x) {
    float a = 2.51; float b = 0.03; float c = 2.43;
    float d = 0.59; float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}
```

### Procedural Color Palette (iq)
```glsl
vec3 palette(float t, vec3 a, vec3 b, vec3 c, vec3 d) {
    return a + b * cos(6.283185 * (c * t + d));
}
```
- `a`: baseline color, `b`: amplitude, `c`: frequency, `d`: phase offset
- Produces smooth, cycling color gradients from a single parameter
- Examples:
  - Warm sunset: `palette(t, vec3(0.5,0.5,0.5), vec3(0.5,0.5,0.5), vec3(1.0,1.0,1.0), vec3(0.0,0.10,0.20))`
  - Cool ocean: `palette(t, vec3(0.5,0.5,0.5), vec3(0.5,0.5,0.5), vec3(1.0,1.0,1.0), vec3(0.30,0.20,0.20))`
  - Rainbow: `palette(t, vec3(0.5,0.5,0.5), vec3(0.5,0.5,0.5), vec3(1.0,1.0,1.0), vec3(0.0,0.33,0.67))`

---

## Animation Drivers

### Time Loop
```glsl
float timeLoop(float duration) {
    return fract(iTime / duration);
}
```
- `duration`: 1.0-10.0, cycle length in seconds

### Easing Functions
```glsl
float easeInOut(float t) {
    return t * t * (3.0 - 2.0 * t);  // smoothstep curve
}

float easeInOutCubic(float t) {
    return t < 0.5 ? 4.0 * t * t * t : 1.0 - pow(-2.0 * t + 2.0, 3.0) / 2.0;
}

float easeInOutQuad(float t) {
    return t < 0.5 ? 2.0 * t * t : 1.0 - pow(-2.0 * t + 2.0, 2.0) / 2.0;
}
```

### Sin Wave
```glsl
float sinWave(float t, float frequency, float amplitude) {
    return sin(t * frequency * 6.2832) * amplitude;
}
```

### Pulse
```glsl
float pulse(float t, float frequency) {
    return pow(sin(t * frequency * 6.2832), 2.0);
}
```

### Flow
```glsl
vec2 flow(vec2 uv, float speed, float direction) {
    return uv + vec2(cos(direction), sin(direction)) * speed * iTime;
}
```

---

## UV Operations

### UV Transform
```glsl
vec2 uvTransform(vec2 uv, vec2 offset, vec2 scale) {
    return (uv - offset) * scale;
}
```

### UV Rotate
```glsl
vec2 uvRotate(vec2 uv, float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return vec2(uv.x * c - uv.y * s, uv.x * s + uv.y * c);
}
```

### UV Scale
```glsl
vec2 uvScale(vec2 uv, vec2 factor) {
    return uv * factor;
}
```

### UV Offset
```glsl
vec2 uvOffset(vec2 uv, vec2 offset) {
    return uv + offset;
}
```

---

## Post Effects

### Glow (带强度基准)

**关键：Glow 在截图中必须清晰可见，不能是微弱灰色！**

```glsl
// ✅ 推荐：多层 glow，中心明亮
float d = sdf_shape(pos);
float core = exp(-abs(d) * 12.0);      // 核心亮线
float mid  = exp(-abs(d) * 4.0);        // 中层光晕  
float outer = exp(-abs(d) * 1.5);       // 外层扩散
vec3 glow = color * (core * 1.5 + mid * 0.8 + outer * 0.3);

// ❌ 错误：单层衰减、强度过低
// float glow = exp(-d * 10.0) * 0.2;  // 截图中几乎不可见
```

**强度自检：shape 边缘处 (d≈0) glow 值必须 >= 0.8**

### Outline
```glsl
float outline(float d, float width) {
    return smoothstep(-width, width, abs(d));
}
```

### Alpha Blend
```glsl
vec4 alphaBlend(vec4 src, vec4 dst) {
    return vec4(
        src.rgb * src.a + dst.rgb * (1.0 - src.a),
        src.a + dst.a * (1.0 - src.a)
    );
}
```

---

## Effect → Operator Mapping

| Effect Type | Recommended Operators | Complexity |
|-------------|----------------------|------------|
| **Simple Shape** | `SDF_Primitive` + `Color` | Low |
| **Outline Effect** | `SDF` + `Outline` + `Glow` | Medium |
| **Ripple Animation** | `SDF` + `SinWave` + `Gradient` + `TimeLoop` | Medium |
| **Frosted Glass** | `Noise` + `Blur` + `AlphaBlend` | High |
| **Glow Effect** | `SDF` + `Specular` + `Glow` | Medium |
| **Flow Light** | `Noise` + `Flow` + `ColorMix` | High |

---

## Shader Templates

Each template is a complete effect skeleton. Customize parameters based on the visual description.

### Template: Basic Gradient
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 colA = vec3(0.1, 0.1, 0.18); // top color
    vec3 colB = vec3(0.06, 0.2, 0.38); // bottom color
    vec3 col = mix(colB, colA, uv.y); // linear vertical
    // For radial: float d = length(uv - 0.5); col = mix(colA, colB, d * 2.0);
    // For angular: float a = atan(uv.y-0.5, uv.x-0.5); col = mix(colA, colB, (a/6.28+0.5));
    fragColor = vec4(col, 1.0);
}
```

### Template: Ripple
```glsl
float sdCircle(vec2 p, float r) { return length(p) - r; }

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 center = iMouse / iResolution.xy;
    float t = iTime;

    float speed = 0.8;
    float wavelength = 0.05;
    float decay = 3.0;

    vec2 p = uv - center;
    float dist = length(p);
    float wave = sin((dist - t * speed) / wavelength * 6.2832);
    float attenuation = exp(-dist * decay) * exp(-fract(t * 0.3) * 2.0);
    float ripple = wave * attenuation;

    vec3 baseColor = vec3(0.1, 0.3, 0.6);
    vec3 rippleColor = vec3(0.4, 0.7, 1.0);
    vec3 col = mix(baseColor, rippleColor, ripple * 0.5 + 0.5);
    fragColor = vec4(col, 1.0);
}
```
- Customizable: speed, wavelength, decay, baseColor, rippleColor

### Template: Frosted Glass (with backdrop texture)
```glsl
vec3 backdropBlur(vec2 uv, float radius) {
    vec3 sum = vec3(0.0);
    float total = 0.0;
    for (int i = -4; i <= 4; i++) {
        for (int j = -4; j <= 4; j++) {
            vec2 offset = vec2(float(i), float(j)) * radius / iResolution.xy;
            float w = 1.0 - length(vec2(float(i), float(j))) / 6.0;
            w = max(w, 0.0);
            sum += texture(iChannel0, uv + offset).rgb * w;
            total += w;
        }
    }
    return sum / max(total, 0.001);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 blurred = backdropBlur(uv, 4.0);
    float noise = 0.5 + 0.5 * perlinNoise(uv * 20.0 + iTime * 0.1);
    vec3 col = blurred * (0.85 + 0.15 * noise);
    col += vec3(0.8, 0.85, 0.95) * 0.08; // cool tint
    fragColor = vec4(col, 0.92);
}
```
- Requires: iChannel0 (backdrop texture)
- Customizable: blur radius, noise scale, tint color, opacity

### Template: Aurora
```glsl
float perlinNoise(vec2 p) { /* see noise functions */ }
float fbm(vec2 p) { float v=0.0; float a=0.5; for(int i=0;i<5;i++){v+=a*perlinNoise(p);p*=2.0;a*=0.5;} return v; }

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float t = iTime * 0.3;

    float n1 = fbm(vec2(uv.x * 3.0 + t, uv.y * 2.0 + t * 0.5));
    float n2 = fbm(vec2(uv.x * 2.0 - t * 0.7, uv.y * 3.0));

    vec3 col1 = vec3(0.1, 0.8, 0.4); // green
    vec3 col2 = vec3(0.2, 0.4, 0.9); // blue
    vec3 col3 = vec3(0.7, 0.2, 0.8); // purple

    float band = smoothstep(0.3, 0.7, uv.y + n1 * 0.3);
    vec3 col = mix(col1, col2, band);
    col = mix(col, col3, smoothstep(0.5, 0.8, n2));

    col *= smoothstep(0.0, 0.3, uv.y) * smoothstep(1.0, 0.5, uv.y);
    col *= 0.7 + 0.3 * sin(t * 2.0 + uv.x * 6.28);

    fragColor = vec4(col, 1.0);
}
```
- Customizable: color bands, flow speed, vertical distribution

### Template: Glow Pulse
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 center = vec2(0.5);
    float dist = length(uv - center);

    float pulse = 0.5 + 0.5 * sin(iTime * 2.0); // breathing
    float glow = exp(-dist * (4.0 + 2.0 * pulse));

    vec3 glowColor = vec3(0.3, 0.6, 1.0);
    vec3 baseColor = vec3(0.02, 0.02, 0.05);

    vec3 col = baseColor + glowColor * glow * (0.5 + 0.5 * pulse);
    fragColor = vec4(col, 1.0);
}
```
- Customizable: pulse speed, glow radius, glow color, base color

### Template: Liquid Glass (半透明 + 折射 + 高光)

适用于：液态玻璃、水滴、半透明覆盖层

```glsl
float sdShape(vec2 p) {
    // 使用 sdVesica/sdCircle 等有机形状
    return sdVesica(p - center, params);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    float d = sdShape(uv);
    
    // 半透明填充（实心用 d，空心用 abs(d)）
    float fill = 1.0 - smoothstep(0.0, edge_width, d);
    
    // 折射偏移（FBM 驱动）
    vec2 refract_offset = vec2(
        FBM(uv * 3.0 + iTime * 0.2) - 0.5,
        FBM(uv * 3.0 + vec2(5.2, 1.3) + iTime * 0.2) - 0.5
    ) * 0.03;
    
    // 背景采样（折射）
    vec3 bg = backgroundShader(uv + refract_offset);
    
    // 高光（菲涅尔）
    float highlight = pow(1.0 - abs(d) / 0.1, 3.0) * 0.8;
    
    // 混合
    vec3 tint = vec3(0.5, 0.7, 0.9);
    float alpha = fill * 0.5; // 半透明
    vec3 color = mix(bg, tint, alpha) + highlight;
    
    // 边缘光晕
    float glow = exp(-abs(d) * 8.0) * 0.3;
    color += glow_color * glow;
    
    fragColor = vec4(color, 1.0);
}
```

**关键参数:**
- alpha: 0.3-0.6（半透明范围）
- refract_offset: FBM * 0.02-0.05（微妙偏移）
- highlight: 菲涅尔 pow(x, 2-4) * 0.5-0.8
- fill 用 d（实心），不用 abs(d)（空心）

---

### Template: Particle Field (粒子点阵 + 闪烁 + 漂移)

适用于：粒子、星光、火花、尘埃

```glsl
// 网格哈希 — 粒子位置的基础
vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    float grid_scale = 20.0; // 粒子密度
    vec2 cell = floor(uv * grid_scale);
    vec2 local = fract(uv * grid_scale);
    
    // 每个网格一个粒子
    vec2 particle_offset = hash2(cell);
    vec2 particle_pos = particle_offset;
    
    // FBM 漂移（粒子随时间移动）
    particle_pos += vec2(
        FBM(cell * 0.1 + iTime * 0.3),
        FBM(cell * 0.1 + vec2(5.2, 1.3) + iTime * 0.2)
    ) * 0.3;
    particle_pos = fract(particle_pos); // wrap around
    
    // 粒子距离
    float d = length(local - particle_pos);
    
    // 粒子大小 + 闪烁
    float size = mix(0.02, 0.06, hash2(cell + 0.5).x);
    float flicker = 0.7 + 0.3 * sin(iTime * (2.0 + hash2(cell + 1.5).x * 4.0) + hash2(cell + 2.5).x * 6.28);
    
    // 点 SDF + glow
    float brightness = exp(-d * d / (size * size)) * flicker;
    
    // 颜色变化（按 cell_id 分配不同颜色）
    float hue = hash2(cell + 3.5).x;
    vec3 particle_color = palette(hue);
    
    vec3 color = particle_color * brightness * 1.2; // intensity >= 1.0
    
    fragColor = vec4(color, 1.0);
}
```

**关键参数:**
- grid_scale: 10-30（密度）
- size: 0.02-0.08（粒子大小）
- flicker: sin(time * freq + phase) * 0.3 振幅
- brightness intensity: >= 1.0（确保粒子清晰可见）
- palette: 按 hash 分配不同色相

---

### Template: Domain Warp (域扭曲 + 线条)

适用于：视错觉、背景扭曲、等高线

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // 两级 domain warping
    vec2 q = vec2(FBM(uv + vec2(0.0, 0.0)), FBM(uv + vec2(5.2, 1.3)));
    vec2 r = vec2(FBM(uv + 4.0*q + vec2(1.7, 9.2) + iTime*0.15),
                  FBM(uv + 4.0*q + vec2(8.3, 2.8) + iTime*0.12));
    
    float f = FBM(uv + 4.0*r);
    
    // 线条叠加（等高线效果）
    float lines = abs(sin(f * 20.0)) * 0.3;
    
    // 颜色映射
    vec3 color = mix(color1, color2, clamp(f * f * 4.0, 0.0, 1.0));
    color = mix(color, color3, clamp(length(q), 0.0, 1.0));
    color = mix(color, color4, clamp(length(r.x), 0.0, 1.0));
    
    // 线条高亮
    color += lines * accent_color;
    
    fragColor = vec4(color, 1.0);
}
```

**关键参数:**
- warp strength: 4.0（两级叠加）
- FBM octaves: 4-5（丰富纹理）
- lines: sin(f * frequency) * amplitude
- 多层颜色 mix 增加深度感

---

### Template: Solid Shape (实心形状 + 渐变 + 边缘光)

适用于：心形、星形、几何图形、图标

```glsl
float sdShape(vec2 p) {
    // 选择对应 SDF：sdHeart / sdStar5 / sdBox / sdCircle
    return sdHeart(p - center, size);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    float d = sdShape(uv);
    
    // ⚠️ 实心填充用 d，不用 abs(d)
    //    abs(d) 会产生空心轮廓！
    float fill = 1.0 - smoothstep(0.0, edge_width, d);
    
    // 内部渐变
    vec2 grad_dir = normalize(vec2(1.0, -1.0));
    float gradient = dot(uv - center, grad_dir) * 0.5 + 0.5;
    vec3 fill_color = mix(color_dark, color_bright, gradient);
    
    // 边缘光（柔和 glow）
    float glow = exp(-abs(d) * 6.0) * 0.5;
    
    // 最终合成
    vec3 color = fill * fill_color + (1.0 - fill) * bg_color + glow * glow_color;
    
    fragColor = vec4(color, 1.0);
}
```

**关键参数:**
- fill: 用 `d`（实心），禁用 `abs(d)`（会产生空心）
- edge_width: 0.01-0.05 UV（柔和边缘）
- glow: exp(-abs(d) * 4-8) * intensity >= 0.5
- gradient: dot(uv, dir) 实现方向性渐变

---

## Aesthetics Rules

> Target: 2D/2.5D UI visual effects on mobile devices (Mali/Adreno/Apple GPU) and web.
> Authority: Shadertoy (https://www.shadertoy.com/) for visual patterns and implementation approaches.

### Color Harmony

#### Complementary (180° apart)
- High contrast, use sparingly: base 70%, accent 30%
- Shader: `mix(base, complement, factor)` with factor 0.1-0.3
- Example: blue #1a1a2e + orange #e94560

#### Analogous (30°-60° apart)
- Natural, harmonious - safe default
- Shader: `cos(uv.x * 6.28 + offset)` for color bands
- Example: deep blue #0f3460 + indigo #16213e + purple #533483

#### Triadic (120° apart)
- Rich but needs hierarchy: 1 primary 70%, 2 accents 15% each
- Shader: assign one color per SDF region

#### Readability
- Background-foreground luminance difference > 0.4 (WCAG AA)
- In motion: > 0.3 acceptable
- Luminance: `dot(col, vec3(0.299, 0.587, 0.114))`

#### Dark Theme Safe
- Background luminance < 0.15
- Highlight luminance > 0.5
- Never pure black #000000 - use `vec3(0.02, 0.02, 0.05)` minimum

### Motion Principles

#### Easing Selection
| Motion Type | Easing | Shader Function |
|-------------|--------|----------------|
| Appear/expand | ease-out | `1.0 - (1.0 - t) * (1.0 - t)` |
| Disappear/shrink | ease-in | `t * t` |
| Natural/organic | ease-in-out | `t * t * (3.0 - 2.0 * t)` |
| Bounce/spring | spring | `1.0 - pow(cos(t * 3.14159 * 0.5), 2.0) * exp(-t * 4.0)` |
| Smooth loop | cosine | `0.5 - 0.5 * cos(t * 6.2832)` |

#### Timing
- Micro-interactions: 150-400ms
- Transitions: 300-800ms
- Ambient effects: 2-6s loop
- Never instant (0ms) - even subtle motion feels better than none

#### Rhythm
- Use `fract(iTime / duration)` for perfect loops
- Vary frequencies to avoid mechanical feel: `sin(t * 1.0) + sin(t * 1.7) * 0.5`
- Layer 2-3 speeds: slow drift + medium pulse + fast shimmer

---

## GLSL Constraints

> Target platform: **Mobile GPU (Mali/Adreno/Apple GPU) + WebGL** - not desktop.
> Target frame budget: **< 2ms per frame at 1080p** on mid-range mobile.
> Scope: **2D/2.5D flat effects only** - no 3D raymarching, no volumetric, no scene graphs.

### Mandatory Rules

1. **Do NOT declare** `iTime`, `iResolution`, `iMouse` - these are injected by runtime
2. **Must implement** `void mainImage(out vec4 fragColor, in vec2 fragCoord)` - entry point
3. **Output must be** complete, compilable GLSL ES 3.0 - no `#include`, no undefined functions
4. **2D only** - all coordinates are `vec2 uv`, all SDF operations are 2D, no `vec3` position/ray/direction for 3D scene rendering

### Banned Patterns

| Pattern | Reason | Alternative |
|---------|--------|-------------|
| **3D raymarching** (`rayDirection`, `marchRay`, `castRay`, `sceneSDF(vec3)`) | Mobile GPU too slow, not our scope | Use 2D SDF + layered composition |
| **3D SDF primitives** (`sdSphere(vec3)`, `sdBox(vec3)`) | Outside 2D/2.5D scope | Use 2D equivalents |
| **Path tracing / BRDF / PBR** | Desktop-only, not mobile real-time | Use Fresnel rim, fake AO, procedural lighting |
| **Volumetric / fog / clouds** (ray-step loops > 8) | Too expensive on mobile | Layer 2D noise with depth fade |
| `for` loops with > 8 iterations or dynamic bounds | GPU divergence, timeout | Unroll or use fixed-count loops |
| Recursion | Not supported in GLSL | Refactor to iterative |
| `discard` | Kills early-Z, hurts performance | Use alpha blending or `step()` mask |
| Dynamic array indexing | GPU register pressure | Constant-index or texture lookup |
| `while` loops | Infinite loop risk | Fixed `for` loop |
| `textureLod` in fragment | Not universally supported | `texture()` with bias parameter |

### Performance Budget (Mobile)

| Metric | Mobile Limit | Desktop/Dev Limit | Notes |
|--------|-------------|-------------------|-------|
| ALU instructions | <= 256 | <= 512 | Fragment shader instruction count |
| Texture fetches per fragment | <= 8 | <= 16 | Mobile memory bandwidth is the bottleneck |
| For-loop iterations (total) | <= 32 | <= 64 | Hard limit, no dynamic bounds |
| Target frame time | < 2ms @ 1080p | < 4ms @ 1440p | 60fps budget with headroom for OS UI |
| FBM octaves | <= 4 | <= 6 | Each octave doubles cost |
| Blur kernel | <= 7x7 (49 samples) | <= 9x9 (81 samples) | Multi-sample blur is very expensive on mobile |

### Mobile Optimization Tips

- Prefer `smoothstep` and `step` over branching - GPUs hate divergent branches
- Use `mix()` instead of `if/else` - both branches execute anyway on GPU
- Reduce texture samples: prefer mipmap LOD over multi-sample blur
- Downsample expensive effects: render at half resolution when possible
- Avoid dependent texture reads: compute UV before sampling, not after
- Keep FBM octaves <= 4 on mobile; 5+ is desktop-only
- Use `pow(x, 2.0)` instead of `x * x` only when the compiler won't optimize - usually `x * x` is fine

### Math Safety

```glsl
// Division - always guard
float safe = a / max(b, 0.0001);

// Square root - ensure non-negative
float safe = sqrt(max(val, 0.0));

// Log - ensure positive
float safe = log(max(val, 0.0001));

// Pow with negative base - use abs
float safe = pow(abs(base), exp);

// Normalize - guard zero-length
vec2 safe = length(v) > 0.0001 ? normalize(v) : vec2(0.0);

// Clamp all outputs
fragColor = vec4(clamp(col, 0.0, 1.0), clamp(alpha, 0.0, 1.0));
```

### Cross-Platform Quirks

| Issue | GLSL (WebGL/Vulkan) | MSL (Metal) | Notes |
|-------|---------------------|-------------|-------|
| Fragment output | `out vec4 fragColor` | `return vec4` | Our runtime wraps to handle this |
| Texture function | `texture(sampler, uv)` | `sampler.sample(uv)` | Use `texture()` - transpiler handles |
| Uniform declarations | Must declare in code | Declared in shader signature | Our runtime auto-injects common uniforms |
| Precision | Need `precision highp float` | Implicit | Always include precision qualifier |
| Half-float framebuffers | May not support | Supported | Assume `highp` only; don't rely on `mediump` FBO |

### Texture Support

- Textures are supported via `iChannel0`-`iChannel3` (Shadertoy convention)
- Use `texture(iChannelN, uv)` for sampling
- Our runtime will bind system textures to channels automatically
- For backdrop blur effects, iChannel0 is the system framebuffer
- For user-uploaded textures, iChannel1 is available
- Always handle the case where a channel may not be bound - use fallback procedural
- **Mobile**: keep texture samples <= 8 per fragment; prefer mipmap LOD blur over multi-sample
