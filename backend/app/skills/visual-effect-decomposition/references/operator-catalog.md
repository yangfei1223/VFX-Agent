# Operator Catalog

Complete catalog of GLSL operators for visual effect composition.

## SDF Primitives

### Circle SDF

```glsl
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `p` | vec2 | UV space | Point position |
| `r` | float | 0.0-1.0 | Circle radius |

### Box SDF

```glsl
float sdBox(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `p` | vec2 | UV space | Point position |
| `b` | vec2 | UV dimensions | Half-size (width/2, height/2) |

### Rounded Box SDF

```glsl
float sdRoundedBox(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `p` | vec2 | UV space | Point position |
| `b` | vec2 | UV dimensions | Half-size |
| `r` | float | 0.0-b | Corner radius |

### Segment SDF

```glsl
float sdSegment(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `p` | vec2 | Point position |
| `a` | vec2 | Start point |
| `b` | vec2 | End point |

### Triangle SDF

```glsl
float sdTriangle(vec2 p, vec2 p0, vec2 p1, vec2 p2) {
    // Edge distances calculation
}
```

### Polygon SDF

```glsl
float sdPolygon(vec2 p, vec2[] vertices) {
    // Edge loop calculation
}
```

---

## SDF Operations

### Union

```glsl
float opUnion(float d1, float d2) {
    return min(d1, d2);
}
```

**Use**: Combine two shapes (logical OR)

### Intersection

```glsl
float opIntersection(float d1, float d2) {
    return max(d1, d2);
}
```

**Use**: Common area of two shapes (logical AND)

### Subtraction

```glsl
float opSubtraction(float d1, float d2) {
    return max(d1, -d2);
}
```

**Use**: Remove shape2 from shape1

### Smooth Union

```glsl
float opSmoothUnion(float d1, float d2, float k) {
    float h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) - k * h * (1.0 - h);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `d1, d2` | float | SDF distances | Input distances |
| `k` | float | 0.01-0.5 | Blend width |

### Smooth Intersection

```glsl
float opSmoothIntersection(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) + k * h * (1.0 - h);
}
```

### Smooth Subtraction

```glsl
float opSmoothSubtraction(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d1 + d2) / k, 0.0, 1.0);
    return mix(d1, -d2, h) + k * h * (1.0 - h);
}
```

### Round Blend

```glsl
float opRound(float d, float r) {
    return d - r;
}
```

**Use**: Add rounded corners to any SDF

### Onion (Shell)

```glsl
float opOnion(float d, float r) {
    return abs(d) - r;
}
```

**Use**: Create hollow shape with thickness `r`

---

## Noise Functions

### Hash Function

```glsl
float hash(float n) {
    return fract(sin(n) * 43758.5453);
}

vec2 hash22(vec2 p) {
    p = fract(p * vec2(5.3983, 5.4447));
    p += dot(p.yx, p.yx + vec2(21.5351));
    return fract(vec2(p.x * p.y, p.x + p.y));
}
```

**Use**: Basic randomness, hash table

### Value Noise

```glsl
float valueNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `p` | vec2 | Noise coordinate |

### Perlin Noise

```glsl
float perlinNoise(vec2 p) {
    vec2 pi = floor(p);
    vec2 pf = fract(p);
    vec2 u = pf * pf * (3.0 - 2.0 * pf);
    
    vec2 gradient0 = hash22(pi);
    vec2 gradient1 = hash22(pi + vec2(1.0, 0.0));
    vec2 gradient2 = hash22(pi + vec2(0.0, 1.0));
    vec2 gradient3 = hash22(pi + vec2(1.0, 1.0));
    
    float n0 = dot(gradient0, pf);
    float n1 = dot(gradient1, pf - vec2(1.0, 0.0));
    float n2 = dot(gradient2, pf - vec2(0.0, 1.0));
    float n3 = dot(gradient3, pf - vec2(1.0, 1.0));
    
    return mix(mix(n0, n1, u.x), mix(n2, n3, u.x), u.y) * 0.5 + 0.5;
}
```

**Use**: Smooth gradient noise, organic movement

### Simplex Noise

```glsl
float simplexNoise(vec2 p) {
    // Simplified grid structure
    // More efficient than Perlin
}
```

**Use**: Efficient Perlin variant

### Voronoi Noise

```glsl
vec2 voronoi(vec2 p) {
    vec2 n = floor(p);
    vec2 f = fract(p);
    
    float md = 8.0;
    vec2 mr;
    
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 o = hash22(n + g);
            vec2 r = g + o - f;
            float d = dot(r, r);
            
            if (d < md) {
                md = d;
                mr = r;
            }
        }
    }
    
    return vec2(md, dot(mr, mr));
}
```

**Use**: Cellular patterns, crystal structures

### FBM (Fractal Brownian Motion)

```glsl
float fbm(vec2 p, int octaves, float frequency, float amplitude) {
    float value = 0.0;
    float amp = amplitude;
    float freq = frequency;
    
    for (int i = 0; i < octaves; i++) {
        value += amp * perlinNoise(p * freq);
        freq *= 2.0;
        amp *= 0.5;
    }
    
    return value;
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `octaves` | int | 1-8 | Detail layers |
| `frequency` | float | 1.0-10.0 | Base frequency |
| `amplitude` | float | 0.1-1.0 | Initial amplitude |

**Use**: Rich detail, natural textures

### Turbulence

```glsl
float turbulence(vec2 p, int octaves) {
    return abs(fbm(p, octaves));
}
```

**Use**: Sharp-edged noise patterns

---

## Lighting Models

### Fresnel Effect

```glsl
float fresnel(vec3 I, vec3 N, float power) {
    return pow(1.0 - dot(I, N), power);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `I` | vec3 | View direction | Camera to point |
| `N` | vec3 | Normal | Surface normal |
| `power` | float | 1.0-5.0 | Fresnel intensity |

### Specular Highlight

```glsl
vec3 specular(vec3 normal, vec3 lightDir, vec3 viewDir, float shininess) {
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(viewDir, reflectDir), 0.0), shininess);
    return vec3(spec);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `shininess` | float | 1-128 | Highlight sharpness |

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
    float a = 2.51;
    float b = 0.03;
    float c = 2.43;
    float d = 0.59;
    float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}
```

---

## Animation Drivers

### Time Loop

```glsl
float timeLoop(float duration) {
    return fract(iTime / duration);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `duration` | float | 1.0-10.0 | Cycle length (seconds) |

### Ease In-Out

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
    return sin(t * frequency * TWO_PI) * amplitude;
}
```

### Pulse

```glsl
float pulse(float t, float frequency) {
    return pow(sin(t * frequency * TWO_PI), 2.0);
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

### Glow

```glsl
vec3 glow(vec2 uv, float radius, float intensity) {
    vec3 col = vec3(0.0);
    for (float i = -radius; i <= radius; i++) {
        for (float j = -radius; j <= radius; j++) {
            col += texture(iChannel0, uv + vec2(i, j) * 0.01).rgb;
        }
    }
    return col / ((2.0 * radius + 1.0) * (2.0 * radius + 1.0)) * intensity;
}
```

### Blur

```glsl
// Gaussian blur kernel
vec3 gaussianBlur(vec2 uv, float radius) {
    // Multi-sample blur implementation
}
```

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

## Operator Usage Guide

| Effect Type | Recommended Operators | Complexity |
|-------------|---------------------|------------|
| **Simple Shape** | `SDF_Primitive` + `Color` | Low |
| **Outline Effect** | `SDF` + `Outline` + `Glow` | Medium |
| **Ripple Animation** | `SDF` + `SinWave` + `Gradient` + `TimeLoop` | Medium |
| **Frosted Glass** | `Noise` + `Blur` + `AlphaBlend` | High |
| **Glow Effect** | `SDF` + `Specular` + `Glow` | Medium |
| **Flow Light** | `Noise` + `Flow` + `ColorMix` | High |
| **Particle Effect** | `Voronoi` + `Animation` + `Alpha` | High |