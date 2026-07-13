# Few-Shot Shader Examples (v2.0)

> 9 effect types with reference GLSL implementations. Codex reads this when generating shaders.
> Source: extracted + compressed from v1.0 `generate_system.md` L310-1040.
> Compressed: removed visual_description JSON (codex already has it) and verbose "关键学习点" blocks.

## Table of Contents

1. [Glow — 发光圆环](#1-glow--effectglow)
2. [Gradient — 多色渐变](#2-gradient--effectgradient)
3. [Shape — 实心心形](#3-shape--effectsolid)
4. [Ripple — 同心圆涟漪](#4-ripple--effectripple)
5. [Flow — 有机流动纹理](#5-flow--effectflow)
6. [Particle — 发光粒子](#6-particle--effectparticle)
7. [Warp — 域扭曲视错觉](#7-warp--effectwarp)
8. [Liquid — 液态玻璃](#8-liquid--effectliquid)
9. [Frosted — 磨砂玻璃](#9-frosted--effectfrosted)

---

## 1. Glow — `{effect.glow}`

> Shiny circle / glow ring effect. Soft bloom on a hollow ring with dark background.

**Key parameters:**
- Hollow ring: `abs(d) - edge_width` then `1.0 - smoothstep(0.0, 0.015, ...)`
- Multi-layer glow: `core=exp(-abs(d)*30)`, `mid=exp(-abs(d)*8)`, `outer=exp(-abs(d)*2.5)`
- Glow intensity sum >= 2.0 ensures brightness at edge (d≈0)
- Pure black background `vec3(0.0)`
- Secondary color tint applied to outermost layer

```glsl
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 p = uv - vec2(0.5);

    float d = sdCircle(p, 0.2);

    // hollow ring — use abs(d)
    float ring = 1.0 - smoothstep(0.0, 0.015, abs(d) - 0.01);

    // multi-layer glow
    vec3 glowColor = vec3(0.6, 0.3, 1.0);
    float core = exp(-abs(d) * 30.0);
    float mid  = exp(-abs(d) * 8.0);
    float outer = exp(-abs(d) * 2.5);
    vec3 glow = glowColor * (core * 1.2 + mid * 0.6 + outer * 0.2);

    // secondary color tint on outer glow
    vec3 outerColor = vec3(0.3, 0.5, 1.0);
    glow += outerColor * outer * 0.3;

    vec3 col = vec3(0.0) + ring * glowColor * 0.8 + glow;

    fragColor = vec4(col, 1.0);
}
```

---

## 2. Gradient — `{effect.gradient}`

> Multi-color radial gradient background. Full-screen, no SDF, no animation.

**Key parameters:**
- Fullscreen: no SDF, direct UV manipulation
- 4 color stops chained via `smoothstep(t0, t1, t)` as mix weights
- Single `mix(col1, col2, smoothstep(...))` per transition
- Radial distance `d = length(p)` as gradient driver
- `smoothstep(0.0, 0.7, d)` maps [0,0.7] → [0,1]

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 p = uv - 0.5;

    // radial distance from center
    float d = length(p);

    // smooth radial gradient
    float t = smoothstep(0.0, 0.7, d);

    // multi-color stops
    vec3 col1 = vec3(0.1, 0.8, 0.5);
    vec3 col2 = vec3(0.9, 0.9, 0.2);
    vec3 col3 = vec3(0.9, 0.3, 0.2);
    vec3 col4 = vec3(0.3, 0.2, 0.8);

    vec3 col = mix(col1, col2, smoothstep(0.0, 0.3, t));
    col = mix(col, col3, smoothstep(0.3, 0.6, t));
    col = mix(col, col4, smoothstep(0.6, 1.0, t));

    fragColor = vec4(col, 1.0);
}
```

---

## 3. Solid Shape — `{effect.solid}`

> Solid-filled heart shape with internal gradient and soft edge glow on warm beige background.

**Key parameters:**
- Solid fill: `1.0 - smoothstep(0.0, 0.02, d)` — uses `d` NOT `abs(d)`
- Internal gradient: `uv.y` as driver, darker at bottom, brighter at top
- Edge glow: `exp(-max(d, 0.0) * 6.0) * 0.3` — outward only (no inward bleed)
- Background strictly matches warm beige `vec3(0.95, 0.9, 0.85)`
- Heart SDF from iq: `sdHeart(p)` with `p.x = abs(p.x)` symmetry

```glsl
float sdHeart(vec2 p) {
    p.x = abs(p.x);
    if (p.y + p.x > 1.0)
        return sqrt(dot(p - vec2(0.25, 0.75), p - vec2(0.25, 0.75))) - 0.3536;
    return sqrt(min(dot(p - vec2(0.0, 1.0), p - vec2(0.0, 1.0)),
                    dot(p - 0.5 * max(p.x + p.y, 0.0), p - 0.5 * max(p.x + p.y, 0.0)))) * sign(p.x - p.y);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 p = uv - vec2(0.5, 0.45);

    float d = sdHeart(p) * 1.8;

    // solid fill — use d directly, NOT abs(d)
    float fill = 1.0 - smoothstep(0.0, 0.02, d);

    // internal gradient
    float grad = uv.y;
    vec3 colDark = vec3(0.7, 0.1, 0.15);
    vec3 colBright = vec3(1.0, 0.4, 0.35);
    vec3 fillColor = mix(colDark, colBright, grad);

    // soft edge glow
    float glow = exp(-max(d, 0.0) * 6.0) * 0.3;
    vec3 glowColor = vec3(1.0, 0.6, 0.5);

    // background (strict warm beige)
    vec3 bg = vec3(0.95, 0.9, 0.85);

    vec3 col = bg;
    col = mix(bg, fillColor, fill);
    col += glowColor * glow;

    fragColor = vec4(col, 1.0);
}
```

---

## 4. Ripple — `{effect.ripple}`

> Concentric ripples expanding outward with color gradient (cyan→magenta).

**Key parameters:**
- Rings: `sin((d - t * 0.15) * 40.0) * 0.5 + 0.5` maps to [0,1]
- Distance fade: `exp(-d * 2.5)` for atmospheric falloff
- Color gradient: `mix(col1, col2, d * 2.0)` — cyan at center, magenta at edge
- Animation: `iTime * 0.8` as global speed, `t * 0.15` as ring phase shift
- Dark background `vec3(0.02, 0.02, 0.05)`

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 p = uv - vec2(0.5);
    float d = length(p);

    float t = iTime * 0.8;

    // concentric rings
    float rings = sin((d - t * 0.15) * 40.0) * 0.5 + 0.5;

    // fade with distance
    float fade = exp(-d * 2.5);

    // color gradient (cyan → magenta)
    vec3 col1 = vec3(0.0, 0.8, 0.8);
    vec3 col2 = vec3(0.8, 0.2, 0.6);
    vec3 ringColor = mix(col1, col2, d * 2.0);

    vec3 col = vec3(0.02, 0.02, 0.05);
    col += ringColor * rings * fade * 0.9;

    fragColor = vec4(col, 1.0);
}
```

---

## 5. Flow — `{effect.flow}`

> Organic flowing texture via FBM domain warping (2 iterations). Deep blue palette.

**Key parameters:**
- Complete pipeline: `hash() → noise() → fbm(4 octaves)` all self-contained
- Two-level domain warping: `q = fbm(uv + t)` → `r = fbm(uv + 4*q + t)` → `f = fbm(uv + 4*r)`
- Color mix chain: 4 stops driven by `f²*4`, `length(q)`, `length(r.x)`
- Contrast boost via `pow(col, vec3(0.9))`
- FBM octaves=4 fits mobile ≤256 ALU constraint
- Animation: `iTime * 0.15` slow drift

```glsl
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * noise(p);
        p *= 2.0;
        a *= 0.5;
    }
    return v;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float t = iTime * 0.15;

    // domain warping — 2 iterations
    vec2 q = vec2(fbm(uv * 3.0 + t), fbm(uv * 3.0 + vec2(5.2, 1.3) + t));
    vec2 r = vec2(
        fbm(uv * 3.0 + 4.0 * q + vec2(1.7, 9.2) + t * 0.5),
        fbm(uv * 3.0 + 4.0 * q + vec2(8.3, 2.8) + t * 0.3)
    );
    float f = fbm(uv * 3.0 + 4.0 * r);

    // color mapping
    vec3 col1 = vec3(0.05, 0.05, 0.15);
    vec3 col2 = vec3(0.15, 0.2, 0.6);
    vec3 col3 = vec3(0.4, 0.5, 0.9);
    vec3 col4 = vec3(0.7, 0.75, 1.0);

    vec3 col = mix(col1, col2, clamp(f * f * 4.0, 0.0, 1.0));
    col = mix(col, col3, clamp(length(q), 0.0, 1.0));
    col = mix(col, col4, clamp(length(r.x), 0.0, 1.0));

    // contrast boost
    col = pow(col, vec3(0.9));

    fragColor = vec4(col, 1.0);
}
```

---

## 6. Particle — `{effect.particle}`

> Floating glowing particles on a dark background with per-particle color and flicker.

**Key parameters:**
- Grid-based: `floor(uv * scale)` → cell, `fract(uv * scale)` → local position
- Per-cell hash for position, color selection, and flicker phase
- Particle shape: `exp(-d²/size²)` — soft round glow
- Size variation: `0.015 + 0.04 * hash(cell+0.5).x`
- Slow drift: `pos += 0.15 * sin/cos(iTime + phase)` then `fract(pos)`
- Flicker: `0.7 + 0.3 * sin(iTime * (1.5 + hash.x*3.0) + hash.y*6.28)`
- 3 color buckets selected by `hash(cell+3.5).x < 0.33/0.66`

```glsl
vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 col = vec3(0.02, 0.02, 0.06);

    float scale = 15.0;
    vec2 cell = floor(uv * scale);
    vec2 local = fract(uv * scale);

    vec2 rnd = hash2(cell);
    vec2 pos = rnd;

    // slow drift
    pos += 0.15 * vec2(
        sin(iTime * 0.3 + rnd.x * 6.28),
        cos(iTime * 0.25 + rnd.y * 6.28)
    );
    pos = fract(pos);

    float d = length(local - pos);

    // size variation
    float size = 0.015 + 0.04 * hash2(cell + 0.5).x;

    // flicker
    float flicker = 0.7 + 0.3 * sin(iTime * (1.5 + rnd.x * 3.0) + rnd.y * 6.28);

    // brightness
    float brightness = exp(-d * d / (size * size)) * flicker;

    // per-particle color
    vec3 c1 = vec3(0.2, 0.7, 1.0);
    vec3 c2 = vec3(0.9, 0.3, 0.7);
    vec3 c3 = vec3(0.9, 0.8, 0.2);
    float hue = hash2(cell + 3.5).x;
    vec3 pcol = hue < 0.33 ? c1 : (hue < 0.66 ? c2 : c3);

    col += pcol * brightness * 1.2;

    fragColor = vec4(col, 1.0);
}
```

---

## 7. Warp — `{effect.warp}`

> Domain warped concentric lines with a circle shape. Lines distort near the SDF shape.

**Key parameters:**
- Lines from `sin(d * 60.0) * 0.5 + 0.5`
- SDF circle as warp field source: `warpStrength = 0.08 * exp(-abs(shape) * 5.0)`
- UV warped by FBM noise, then lines recalculated
- Shape fill + edge glow overlaid on warped lines
- Aspect correction: `(fragCoord - 0.5*iResolution.xy) / iResolution.y`

```glsl
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.0; a *= 0.5; }
    return v;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    vec2 center = vec2(0.0);

    // concentric lines
    float d = length(uv - center);
    float lines = sin(d * 60.0) * 0.5 + 0.5;

    // SDF shape — warp field source
    float shape = sdCircle(uv - center, 0.15);

    // domain warp near the shape
    vec2 warped = uv;
    float warpStrength = 0.08 * exp(-abs(shape) * 5.0);
    warped += vec2(fbm(uv * 5.0), fbm(uv * 5.0 + vec2(5.2, 1.3))) * warpStrength;

    // recalculate lines with warped UV
    float d2 = length(warped - center);
    float warpedLines = sin(d2 * 60.0) * 0.5 + 0.5;

    // color
    vec3 lineColor1 = vec3(0.9, 0.6, 0.2);
    vec3 lineColor2 = vec3(0.3, 0.5, 0.8);
    vec3 shapeColor = vec3(0.3, 0.5, 0.8);

    // fill shape
    float fill = 1.0 - smoothstep(0.0, 0.01, shape);
    vec3 col = mix(lineColor1, lineColor2, warpedLines) * 0.6;
    col = mix(col, shapeColor, fill);

    // shape edge glow
    col += vec3(0.5, 0.7, 1.0) * exp(-abs(shape) * 15.0) * 0.4;

    // dark background
    vec3 bg = vec3(0.1, 0.1, 0.15);
    col = mix(bg, col, smoothstep(0.0, 0.003, abs(length(uv) - 0.0)));

    fragColor = vec4(col, 1.0);
}
```

---

## 8. Liquid — `{effect.liquid}`

> Liquid glass bubble with refraction, Fresnel highlight, and semi-transparent tinted fill.

**Key parameters:**
- Semi-transparent fill: `mix(bg, tint, fill * 0.45)` — alpha 0.3-0.6
- Refraction offset: `fbm(uv*5 + iTime*0.2) * 0.02` creates subtle texture shift
- Fresnel highlight: `pow(1.0 - smoothstep(0.0, 0.08, abs(d)), 3.0) * 0.7`
- FBM at 3 octaves (lighter than flow's 4) for subtlety
- Background sampled after refraction offset: `fbm((uv + refract) * 3.0)`
- Edge glow adds definition: `exp(-abs(d) * 6.0) * 0.25`

```glsl
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 3; i++) { v += a * noise(p); p *= 2.0; a *= 0.5; }
    return v;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 p = uv - vec2(0.4, 0.5);

    float d = sdCircle(p, 0.2);

    // glass fill (semi-transparent)
    float fill = 1.0 - smoothstep(0.0, 0.01, d);

    // refraction offset
    vec2 refract = vec2(
        fbm(uv * 5.0 + iTime * 0.2) - 0.5,
        fbm(uv * 5.0 + vec2(5.2, 1.3) + iTime * 0.15) - 0.5
    ) * 0.02;

    // background (refracted)
    vec3 bg = vec3(0.03, 0.03, 0.08);
    bg += vec3(0.1, 0.15, 0.25) * fbm((uv + refract) * 3.0);

    // glass tint
    vec3 tint = vec3(0.5, 0.7, 0.9);
    float alpha = fill * 0.45;

    // fresnel highlight
    float fresnel = pow(1.0 - smoothstep(0.0, 0.08, abs(d)), 3.0) * 0.7;

    vec3 col = mix(bg, tint, alpha);
    col += vec3(0.9, 0.95, 1.0) * fresnel;

    // edge glow
    float glow = exp(-abs(d) * 6.0) * 0.25;
    col += tint * glow;

    fragColor = vec4(col, 1.0);
}
```

---

## 9. Frosted — `{effect.frosted}`

> Two overlapping circles — one solid gradient, one frosted (noise-overlaid). Light background.

**Key parameters:**
- Frosted texture: `noise(uv * 15.0) * 0.3` added to gradient
- Semi-transparent overlay: `mix(bg, grad2, mask2 * 0.5)` — alpha ~0.5
- Solid lower layer: `mix(bg, grad1, mask1 * 0.9)` — nearly opaque
- Light background `vec3(0.92, 0.92, 0.92)` must match exactly
- 2 overlapping circles with slightly different centers and radii
- No animation, no FBM — just value noise for the frosted texture

```glsl
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;

    // two overlapping circles
    vec2 p1 = uv - vec2(0.42, 0.5);
    vec2 p2 = uv - vec2(0.58, 0.5);
    float d1 = length(p1);
    float d2 = length(p2);

    // gradient colors
    vec3 colA = vec3(0.7, 0.4, 0.9);
    vec3 colB = vec3(0.2, 0.7, 0.7);

    // circle 1 — solid
    float mask1 = 1.0 - smoothstep(0.18, 0.22, d1);
    vec3 grad1 = mix(colA, colB, d1 * 3.0);

    // circle 2 — frosted overlay
    float mask2 = 1.0 - smoothstep(0.16, 0.22, d2);
    float n = noise(uv * 15.0) * 0.3;
    vec3 grad2 = mix(colB, colA, d2 * 3.0) + n;

    // background
    vec3 bg = vec3(0.92, 0.92, 0.92);

    vec3 col = bg;
    col = mix(col, grad1, mask1 * 0.9);
    col = mix(col, grad2, mask2 * 0.5);

    fragColor = vec4(col, 1.0);
}
```
