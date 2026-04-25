# GLSL Constraints Reference

> Target platform: **Mobile GPU (Mali/Adreno/Apple GPU) + WebGL** — not desktop.
> Target frame budget: **< 2ms per frame at 1080p** on mid-range mobile.
> Scope: **2D/2.5D flat effects only** — no 3D raymarching, no volumetric, no scene graphs.

## Mandatory Rules

1. **Do NOT declare** `u_time`, `u_resolution`, `u_mouse` — these are injected by runtime
2. **Must implement** `void mainImage(out vec4 fragColor, in vec2 fragCoord)` — entry point
3. **Output must be** complete, compilable GLSL ES 3.0 — no `#include`, no undefined functions
4. **2D only** — all coordinates are `vec2 uv`, all SDF operations are 2D, no `vec3` position/ray/direction for 3D scene rendering

## Banned Patterns

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

## Mobile Performance Budget

| Metric | Limit | Rationale |
|--------|-------|-----------|
| Fragment shader ALU instructions | ≤ 256 | Mid-range mobile at 1080p |
| Texture fetches per fragment | ≤ 8 | Mobile memory bandwidth limited |
| For-loop iterations (total across all loops) | ≤ 32 | Prevents GPU timeout |
| Target frame time | < 2ms at 1080p | 60fps budget with headroom for UI |
| FBM octaves | ≤ 4 | Each octave doubles cost; 4 is already heavy on mobile |
| Blur kernel | ≤ 7×7 (49 samples) | 9×9 is too slow on mobile GPU |
| Total fragment shader complexity | "simple" to "moderate" | If it wouldn't run smoothly on a 2022 mid-range phone, simplify |

### Mobile Optimization Tips

- **Prefer `smoothstep` and `step` over branching** — GPUs hate divergent branches
- **Use `mix()` instead of `if/else`** — both branches execute anyway on GPU
- **Reduce texture samples**: prefer mipmap LOD over multi-sample blur
- **Downsample expensive effects**: render at half resolution when possible
- **Avoid dependent texture reads**: compute UV before sampling, not after
- **Keep FBM octaves ≤ 4** on mobile; 5+ is desktop-only
- **Use `pow(x, 2.0)` instead of `x * x` only when the compiler won't optimize** — usually `x * x` is fine

## Math Safety

```glsl
// Division — always guard
float safe = a / max(b, 0.0001);

// Square root — ensure non-negative
float safe = sqrt(max(val, 0.0));

// Log — ensure positive
float safe = log(max(val, 0.0001));

// Pow with negative base — use abs
float safe = pow(abs(base), exp);

// Normalize — guard zero-length
vec2 safe = length(v) > 0.0001 ? normalize(v) : vec2(0.0);

// Clamp all outputs
fragColor = vec4(clamp(col, 0.0, 1.0), clamp(alpha, 0.0, 1.0));
```

## Cross-Platform Quirks

| Issue | GLSL (WebGL/Vulkan) | MSL (Metal) | Notes |
|-------|---------------------|-------------|-------|
| Fragment output | `out vec4 fragColor` | `return vec4` | Our runtime wraps to handle this |
| Texture function | `texture(sampler, uv)` | `sampler.sample(uv)` | Use `texture()` — transpiler handles |
| Uniform declarations | Must declare in code | Declared in shader signature | Our runtime auto-injects common uniforms |
| Precision | Need `precision highp float` | Implicit | Always include precision qualifier |
| Half-float framebuffers | May not support | Supported | Assume `highp` only; don't rely on `mediump` FBO |

## Texture Support

- Textures are supported via `iChannel0`–`iChannel3` (Shadertoy convention)
- Use `texture(iChannelN, uv)` for sampling
- Our runtime will bind system textures to channels automatically
- For backdrop blur effects, iChannel0 is the system framebuffer
- For user-uploaded textures, iChannel1 is available
- Always handle the case where a channel may not be bound — use fallback procedural
- **Mobile**: keep texture samples ≤ 8 per fragment; prefer mipmap LOD blur over multi-sample