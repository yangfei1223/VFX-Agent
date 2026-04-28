# Aesthetics Rules Reference

> Target: 2D/2.5D UI visual effects on mobile devices (Mali/Adreno/Apple GPU) and web.
> Authority: Shadertoy (https://www.shadertoy.com/) for visual patterns and implementation approaches.

## Color Harmony

### Complementary (180° apart)
- High contrast, use sparingly: base 70%, accent 30%
- Shader: `mix(base, complement, factor)` with factor 0.1–0.3
- Example: blue #1a1a2e + orange #e94560

### Analogous (30°–60° apart)
- Natural, harmonious — safe default
- Shader: `cos(uv.x * 6.28 + offset)` for color bands
- Example: deep blue #0f3460 + indigo #16213e + purple #533483

### Triadic (120° apart)
- Rich but needs hierarchy: 1 primary 70%, 2 accents 15% each
- Shader: assign one color per SDF region

### Readability
- Background-foreground luminance difference > 0.4 (WCAG AA)
- In motion: > 0.3 acceptable
- Luminance: `dot(col, vec3(0.299, 0.587, 0.114))`

### Dark Theme Safe
- Background luminance < 0.15
- Highlight luminance > 0.5
- Never pure black #000000 — use `vec3(0.02, 0.02, 0.05)` minimum

## Motion Principles

### Easing Selection
| Motion Type | Easing | Shader Function |
|-------------|--------|----------------|
| Appear/expand | ease-out | `1.0 - (1.0 - t) * (1.0 - t)` |
| Disappear/shrink | ease-in | `t * t` |
| Natural/organic | ease-in-out | `t * t * (3.0 - 2.0 * t)` |
| Bounce/spring | spring | `1.0 - pow(cos(t * 3.14159 * 0.5), 2.0) * exp(-t * 4.0)` |
| Smooth loop | cosine | `0.5 - 0.5 * cos(t * 6.2832)` |

### Timing
- Micro-interactions: 150–400ms
- Transitions: 300–800ms
- Ambient effects: 2–6s loop
- Never instant (0ms) — even subtle motion feels better than none

### Rhythm
- Use `fract(u_time / duration)` for perfect loops
- Vary frequencies to avoid mechanical feel: `sin(t * 1.0) + sin(t * 1.7) * 0.5`
- Layer 2–3 speeds: slow drift + medium pulse + fast shimmer

## Performance Budget (Mobile/Web)

> These are **mobile** budgets — significantly tighter than desktop.
> A 2022 mid-range phone (e.g. Snapdragon 778G, Mali-G78) is the reference device.

| Metric | Mobile Limit | Desktop/Dev Limit | Notes |
|--------|-------------|-------------------|-------|
| ALU instructions | ≤ 256 | ≤ 512 | Fragment shader instruction count |
| Texture fetches per fragment | ≤ 8 | ≤ 16 | Mobile memory bandwidth is the bottleneck |
| For-loop iterations (total) | ≤ 32 | ≤ 64 | Hard limit, no dynamic bounds |
| Target frame time | < 2ms @ 1080p | < 4ms @ 1440p | 60fps budget with headroom for OS UI |
| FBM octaves | ≤ 4 | ≤ 6 | Each octave doubles cost |
| Blur kernel | ≤ 7×7 (49 samples) | ≤ 9×9 (81 samples) | Multi-sample blur is very expensive on mobile |

### Optimization Tips (Mobile-First)
- Prefer `smoothstep` over conditional branches
- Use `step()` for binary masks instead of `if`
- Precompute constants outside `mainImage`
- Use `mix` instead of branching where possible
- **Prefer mipmap LOD blur over multi-sample blur** — single texture fetch vs. 49+
- Downsample expensive effects: render at half resolution when precision allows
- Avoid dependent texture reads on mobile (compute UV, then sample, don't sample-then-recompute)
- Keep FBM at 4 octaves max on mobile; 5+ causes visible jank
- Use `lowp`/`mediump` for colors where precision loss is acceptable (but not for UVs or SDF distances)