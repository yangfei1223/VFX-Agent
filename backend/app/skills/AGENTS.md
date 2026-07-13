# VFX-Agent v2.0 (codex OD mode)

You are operating inside a VFX shader generation pipeline. Your host process is `codex exec` invoked by the Python orchestrator (`backend/app/orchestrator.py`). You run autonomously through the 6-phase workflow defined in `skills/vfx-shader/SKILL.md`.

**What you do:** Given reference keyframes + optional user notes, produce a Shadertoy GLSL shader that visually matches the reference, evaluated by an isolated subagent. Iterate up to `max_iterations` (default 3) until subagent score ≥ 0.85.

**What you do NOT do:** 3D raymarching, volumetric rendering, scene rendering, video processing. Scope is 2D / 2.5D planar VFX.

---

## Available Tools

| Tool | Purpose |
|------|---------|
| `Read` | Read keyframe images, reference docs, prior phase outputs |
| `Write` | Write `visual_description.json`, `shader.glsl`, `final_shader.glsl` |
| `Edit` | Patch existing shader during iteration |
| `Bash` | Run skill scripts (`skills/vfx-shader/reference/scripts/*.py`) |
| `Glob` | Locate files (e.g. `keyframes/*.png`) |
| `Grep` | Search reference docs for specific operators |
| `spawn_agent` | Phase 5 evaluation subagent (fork_turns="none" required) |
| `wait_agent` | Block until subagent completes |

The Python orchestrator handles: keyframe extraction (FFmpeg), workdir setup, JSONL streaming to frontend, hard timeout (600s), output extraction. You do NOT need to manage these.

---

## Skill Inventory

### `vfx-shader-generation`

The only skill in v2.0. See `skills/vfx-shader/SKILL.md` for the full 6-phase workflow.

**Reference assets** (under `skills/vfx-shader/reference/`):
- `shader_templates.md` — SDF primitives, noise functions, lighting, 9 shader templates, GLSL constraints (~1200 lines)
- `few_shot_examples.md` — 9 effect types with reference GLSL implementations (~540 lines)
- `scripts/validate_shader.py` — Phase 3 validation
- `scripts/render_shader.py` — Phase 4 rendering
- `scripts/analyze_pixels.py` — Phase 5 pixel evidence

---

## Output Files Convention

You operate inside a workdir (passed via `-C` flag). Each pipeline run produces:

| File | Phase | Owner |
|------|-------|-------|
| `keyframes/001.png`, `002.png`, ... | pre-run | orchestrator (FFmpeg) |
| `notes.txt` | pre-run | orchestrator (from user input) |
| `visual_description.json` | Phase 1 | You (main agent) |
| `shader.glsl` | Phase 2, iterated Phase 6 | You (main agent) |
| `evaluation.json` | Phase 5 | Subagent |
| `final_shader.glsl` | Phase 6 finalize | You (main agent) |

After you exit, the orchestrator reads `final_shader.glsl` (fallback: `shader.glsl`) + `evaluation.json`. If both missing → run status `failed`. If shader present but no evaluation → run status `failed`. If `overall_score >= 0.85` → run status `passed`. Otherwise → `max_iterations`.

---

## Iteration Budget

Default `max_iterations = 3` (passed via prompt by orchestrator). You MUST stop after this many Phase 2-5 loops even if score < 0.85. The orchestrator enforces a hard 600s timeout regardless.

Iteration discipline:
- Each iteration MUST address specific `evaluation.json.visual_issues[]`. No blind tweaking.
- If same issue persists across 2 iterations, change operator / approach (don't repeat the same fix).
- If `avg_color_distance > 100` after 2 iterations, suspect effect_type misclassification. Re-examine the keyframe and consider switching type.

---

## Phase 5 Subagent Protocol (Recap)

**MANDATORY:** Phase 5 evaluation MUST use `spawn_agent` with `fork_turns: "none"`. Self-evaluation is banned.

Subagent receives:
- Reference keyframe path (via message)
- Rendered screenshot path (via message)
- `visual_description.json` (via shared filesystem)

Subagent writes `evaluation.json` and exits. You `wait_agent`, then `Read` the result.

See `skills/vfx-shader/SKILL.md` Phase 5 for the full spawn template.

---

## Quick Reference

### Effect type decision (Phase 1)

In priority order — pick FIRST match:
1. Geometric shape → `{effect.shape}`
2. Translucent/refractive overlay → `{effect.liquid}`
3. Many particles → `{effect.particle}`
4. Concentric ripples → `{effect.ripple}`
5. Bright glow/bloom → `{effect.glow}`
6. Multi-color gradient → `{effect.gradient}`
7. Frosted/blur overlay → `{effect.frosted}`
8. Warped background → `{effect.warp}`
9. Fallback (rare) → `{effect.flow}`

### Score thresholds

| Score | Status | Action |
|---|---|---|
| ≥ 0.85 | passed | Finalize |
| 0.80-0.85 | borderline | Iterate (if budget allows) |
| 0.50-0.80 | needs work | Iterate (mandatory) |
| < 0.50 | major mismatch | Iterate with operator change, or re-examine effect_type |

### Banned patterns (P0)

- Raymarching (`rayDirection`, `ro`, `rd`, `castRay`)
- `texture()` count > 8
- Default purple (RGB ≈ 0.5, 0.2, 0.8)
- Vague descriptions ("nice color")
- Missing `background.strict`, `animation.duration`, `shape.edge_width`
- Self-evaluation in Phase 5

---

# VFX Terminology

> Shared VFX vocabulary. Use these terms in `visual_description.json` descriptions, `evaluation.json` notes, and reasoning. Source: v1.0 `shared_vfx_terminology.md`.

## Lighting & Shadow Terms

### Highlight Types

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Specular highlight** | Bright reflection from light source on surface | `dot(reflect, viewDir)` calculation |
| **Point highlight** | Concentrated bright spot at specific location | Small radius, high intensity glow |
| **Diffuse highlight** | Soft, spread-out reflection | Lambert lighting model |
| **Fresnel highlight** | Brightening at edges due to viewing angle | `pow(1.0 - dot(N, V), n)` |
| **Rim light** | Light from behind object, creating edge glow | Edge detection + additive blending |
| **Global illumination** | Indirect lighting from environment | Multiple light bounces simulation |
| **Ambient light** | Base lighting level throughout scene | Constant color addition |
| **Bloom** | Glow diffusion around bright areas | Multi-pass blur + additive |
| **Glow** | Soft light emission around object | Gaussian blur on bright areas |
| **Light shaft** | Visible light beams through atmosphere | Volumetric light rendering |

### Shadow Types

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Hard shadow** | Sharp-edged shadow with distinct boundary | Step function transition |
| **Soft shadow** | Gradual transition at shadow edge | Smoothstep or blur function |
| **Ambient occlusion** | Darkening in corners and crevices | SDF-based AO calculation |
| **Directional shadow** | Shadow based on light direction | Single light source shadow |
| **Contact shadow** | Shadow where object touches surface | Very short, hard shadow |
| **Drop shadow** | Shadow offset from object position | Blur + offset positioning |
| **Inner shadow** | Shadow within object boundary | Inner glow with inverted color |

### Shadow Parameters

| Term | Definition | Range |
|------|------------|-------|
| **Shadow depth** | Darkness intensity of shadow | 0.0 (invisible) - 1.0 (black) |
| **Shadow softness** | Blur width at shadow edge | 0.0 (hard) - large (soft) |
| **Shadow direction** | Angle relative to light source | Vector direction |
| **Shadow spread** | Area coverage of shadow | Radius in pixels/UV units |

## Color & Tone Terms

### Color Properties

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Hue** | Color type (red, blue, green, etc.) | RGB to HSV conversion |
| **Saturation** | Color intensity/purity | 0.0 (gray) - 1.0 (pure color) |
| **Luminance** | Brightness value | Grayscale intensity |
| **Value** | Brightness in HSV model | 0.0 (black) - 1.0 (white) |
| **Chroma** | Colorfulness measure | Similar to saturation |
| **Tint** | Light color (white added) | High luminance, low saturation |
| **Shade** | Dark color (black added) | Low luminance |
| **Tone** | Gray added to pure color | Medium saturation |

### Color Operations

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Color grading** | Adjusting color for mood/style | `pow(color, vec3(gamma))` or LUT |
| **Tone mapping** | HDR to LDR conversion | Reinhard, ACES, AgX curves |
| **Color correction** | Fixing color imbalances | Channel adjustments |
| **Gamma correction** | Adjusting brightness curve | `pow(color, 1.0/gamma)` |
| **White balance** | Adjusting color temperature | Shift toward warm/cool |
| **Contrast** | Difference between light/dark | `mix(0.5, color, contrast)` |
| **Exposure** | Overall brightness level | Multiplication factor |

### Gradient Types

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Linear gradient** | Straight color transition | `mix(colorA, colorB, t)` |
| **Radial gradient** | Circular color transition | Distance from center |
| **Angular gradient** | Rotation-based transition | Angle calculation |
| **Multi-stop gradient** | Multiple color transition points | Multiple mix operations |
| **Smooth gradient** | Gradual transition | Smoothstep interpolation |
| **Hard gradient** | Abrupt transition | Step function |
| **Dithered gradient** | Noise-added to prevent banding | Add noise to smooth gradient |

### Color Relationships

| Term | Definition | Application |
|------|------------|-------------|
| **Complementary colors** | Opposite on color wheel | Contrast effect |
| **Analogous colors** | Adjacent on color wheel | Harmonious effect |
| **Triadic colors** | Three evenly spaced colors | Balanced diversity |
| **Monochromatic** | Single hue variations | Subtle variation |
| **Warm colors** | Red, orange, yellow range | Energetic mood |
| **Cool colors** | Blue, green, purple range | Calm mood |

## Geometry & Shape Terms

### Shape Types

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **SDF (Signed Distance Field)** | Distance function for shapes | `sdCircle(p, r)`, `sdBox(p, b)` |
| **Circle SDF** | Circular distance function | `length(p) - radius` |
| **Box SDF** | Rectangular distance function | Abs + max calculation |
| **Rounded box SDF** | Rectangle with rounded corners | Box SDF minus corner radius |
| **Line SDF** | Distance to line segment | Point-to-line calculation |
| **Triangle SDF** | Triangular distance function | Edge distance calculation |
| **Polygon SDF** | Multi-sided shape | Edge loop calculation |

### Shape Operations

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Union** | Combine two shapes (OR) | `min(d1, d2)` |
| **Intersection** | Common area (AND) | `max(d1, d2)` |
| **Subtraction** | Remove one shape from another | `max(d1, -d2)` |
| **Smooth union** | Blended shape combination | `smin(d1, d2, k)` |
| **Smooth intersection** | Blended intersection | Polynomial blend |
| **Smooth subtraction** | Blended subtraction | Modified subtraction |
| **Round blend** | Smooth shape blending | Smooth min function |

### Fill Type

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Solid fill** | Shape interior is filled with color | `1.0 - smoothstep(0, w, d)` — no abs() |
| **Hollow / Outline** | Only shape boundary visible as thin line | `1.0 - smoothstep(0, w, abs(d) - thickness)` — uses abs() |

#### Edge & Outline Terms

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Outline** | Border around shape | SDF edge detection |
| **Stroke** | Line drawn around shape | Width-based outline |
| **Edge detection** | Finding shape boundary | SDF threshold `abs(d) < width` |
| **Edge transition** | Smoothness at boundary | Smoothstep width control |
| **Antialiasing** | Smooth pixel edges | fwidth-based smoothstep |
| **Hard edge** | Sharp boundary | Step function |
| **Soft edge** | Gradual boundary | Smoothstep function |
| **Edge glow** | Bright outline effect | Outline + glow blur |

#### Outline Parameters

| Term | Definition | Range |
|------|------------|-------|
| **Outline width** | Border thickness | Pixels or UV units |
| **Outline color** | Border color value | RGB/RGBA vector |
| **Outline softness** | Edge blur amount | 0.0 (hard) - blur width |
| **Outline position** | Inside/outside/center | Inset, outset, centered |
| **Outline opacity** | Border transparency | 0.0 - 1.0 |

## Texture & Material Terms

### Noise Types

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Perlin noise** | Smooth gradient noise | Classic noise function |
| **Simplex noise** | Efficient Perlin variant | Reduced grid complexity |
| **Value noise** | Random value interpolation | Linear interpolation |
| **Worley noise** | Cellular pattern | Distance to points |
| **Voronoi noise** | Cell-based pattern | Worley variant |
| **FBM (Fractal Brownian Motion)** | Multi-octave noise | Layered noise sum |
| **Turbulence** | Absolute FBM | `abs(fbm(p))` |
| **Ridge noise** | Inverted turbulence | `1.0 - abs(fbm(p))` |

### Texture Effects

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Frosted glass** | Blurred transparent effect | Blur + transparency |
| **Grain** | Film-style noise overlay | Noise addition |
| **Pixelation** | Blocky resolution reduction | Floor UV coordinates |
| **Dithering** | Pattern-based color reduction | Bayer matrix or noise |
| **Scanlines** | Horizontal line pattern | Sin wave overlay |
| **Vignette** | Edge darkening | Distance-based fade |
| **Chromatic aberration** | Color channel separation | Offset per channel |

### Material Properties

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Metallic** | Metal-like reflection | High specular, colored reflection |
| **Roughness** | Surface smoothness | Affects specular blur |
| **Subsurface scattering** | Light penetration | Inner glow effect |
| **Clearcoat** | Top layer reflection | Additional specular layer |
| **Anisotropy** | Direction-dependent reflection | Stretched highlights |
| **Emission** | Self-lighting | Additive color output |
| **Opacity** | Transparency level | Alpha channel value |

## Animation & Motion Terms

### Animation Types

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Ripple** | Circular wave expansion | Distance-based sine wave |
| **Wave** | Linear/curved motion | Sine/cosine pattern |
| **Pulse** | Periodic intensity change | Breathing effect |
| **Flow** | Continuous directional movement | Time-based offset |
| **Rotate** | Circular motion | Angle + time function |
| **Scale** | Size change animation | Size multiplier + time |
| **Fade** | Transparency change | Opacity + time |

### Timing Functions

| Term | Definition | Formula |
|------|------------|---------|
| **Linear** | Constant speed | `t` |
| **Ease-in** | Slow start, fast end | `pow(t, 2)` |
| **Ease-out** | Fast start, slow end | `1.0 - pow(1.0 - t, 2)` |
| **Ease-in-out** | Slow start and end | Smoothstep-like curve |
| **Bounce** | Elastic overshoot | Polynomial overshoot |
| **Elastic** | Spring-like oscillation | Sin wave + exponential |
| **Step** | Instant transition | `step(threshold, t)` |

### Animation Parameters

| Term | Definition | Range |
|------|------------|-------|
| **Duration** | Total animation time | Seconds |
| **Cycle period** | Repeat interval | Seconds |
| **Amplitude** | Movement range | Distance units |
| **Frequency** | Repetition rate | Cycles per second |
| **Phase** | Starting offset | 0.0 - duration |
| **Speed** | Movement rate | Units per second |
| **Delay** | Wait before start | Seconds |

### Motion Patterns

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Loop** | Repeating animation | `fract(time / duration)` |
| **Ping-pong** | Back-and-forth motion | `abs(sin(time))` |
| **One-shot** | Single animation run | Clamp to duration |
| **Random motion** | Noise-driven movement | Noise function |
| **Spiral** | Circular + linear | Angle + radius |
| **Orbit** | Path around center | Angle-based position |

## VFX Detail Terms

### Particle Terms

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Particle density** | Number of particles | Count per area |
| **Particle size** | Individual particle scale | Radius/UV units |
| **Particle shape** | Individual particle form | SDF type |
| **Particle distribution** | Placement pattern | Random/grid/cluster |
| **Particle lifetime** | Duration of existence | Seconds |
| **Particle spawn** | Creation rate | Per second |
| **Particle decay** | Fade out rate | Opacity reduction |

### Glow Effects

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Inner glow** | Brightness inside edge | Inverted outline |
| **Outer glow** | Brightness around edge | Outline + blur |
| **Glow radius** | Effect spread distance | Blur width |
| **Glow intensity** | Brightness level | Multiplier |
| **Glow falloff** | Edge softness | Exponential decrease |
| **Bloom intensity** | Global bright glow | Additive blend amount |

### Blur Types

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Gaussian blur** | Smooth even blur | Multi-sample average |
| **Box blur** | Simple average blur | Single-pass average |
| **Motion blur** | Directional blur | Offset-based sampling |
| **Radial blur** | Center-outward blur | Distance-based offset |
| **Depth blur** | Focus-based blur | Distance from focal plane |
| **Bokeh blur** | Lens-style blur | Circle of confusion |

### Transparency Terms

| Term | Definition | GLSL Context |
|------|------------|--------------|
| **Alpha blending** | Standard transparency | `mix(src, dst, alpha)` |
| **Additive blending** | Brightness addition | Color sum |
| **Subtractive blending** | Darkness addition | Color subtract |
| **Alpha cutout** | Hard transparency | Threshold-based alpha |
| **Alpha fade** | Gradual transparency | Distance-based alpha |
| **Transparency gradient** | Varying opacity | Position-based alpha |

## Composition & Layout Terms

| Term | Definition | Application |
|------|------------|-------------|
| **Focal point** | Primary attention area | Center position |
| **Subject** | Main visual element | Primary shape |
| **Background** | Supporting area | Behind subject |
| **Foreground** | Front elements | Overlay shapes |
| **Layer** | Depth separation | Z-order positioning |
| **Hierarchy** | Importance ordering | Size/position/contrast |
| **Balance** | Visual equilibrium | Symmetrical distribution |
| **Spacing** | Element distance | Gap between shapes |
| **Proportion** | Size relationship | Ratio between elements |
| **Alignment** | Position coordination | Grid/axis alignment |
| **Contrast** | Difference emphasis | Light/dark, color/neutral |
| **Repetition** | Pattern consistency | Repeated elements |

## Performance Terms

| Term | Definition | Target |
|------|------------|--------|
| **FPS** | Frames per second | > 30 for smooth |
| **Frame time** | Duration per frame | < 33ms for 30 FPS |
| **ALU instructions** | Math operations | < 256 for mobile |
| **Texture fetch** | Memory reads | < 8 per shader |
| **Branching** | Conditional logic | Minimize for GPU |
| **LOD** | Level of detail | Distance-based complexity |
| **Optimization** | Performance improvement | Faster execution |

## Common Shader Effects

| Effect | Key Components | Typical Parameters |
|--------|---------------|-------------------|
| **Ripple** | SDF + sin wave + time | Speed, wavelength, decay |
| **Glow/Bloom** | Bright extraction + blur | Threshold, blur radius, intensity |
| **Frosted glass** | Noise + blur + transparency | Blur width, noise scale, alpha |
| **Flow light** | Noise + movement + color | Speed, noise octaves, color |
| **Outline** | SDF edge + stroke | Width, color, softness |
| **Gradient** | Color mix + position | Start/end color, direction |
| **Noise texture** | FBM + scale | Octaves, frequency, amplitude |
| **Pulse** | Sine + opacity | Frequency, amplitude, phase |
| **Wave** | Sine + offset | Amplitude, frequency, direction |

## Specialized Effect Definitions

### Liquid Glass Effect (液态玻璃效果)
- **Definition**: 半透明、折射、高光特征的流体/玻璃质感效果
- **Identification**: alpha < 1.0、背景可见但扭曲、边缘高光反射
- **GLSL keywords**: alpha blend, refraction offset, fresnel highlight, sdVesica
- **Token**: `{effect.liquid}`

### Particle Field Effect (粒子场效果)
- **Definition**: 大量离散光点/粒子在空间中分布、移动、闪烁
- **Identification**: 离散点状元素、数量 > 20、有闪烁/漂移动画
- **GLSL keywords**: hash grid, point SDF, flicker, FBM drift, palette per particle
- **Token**: `{effect.particle}`

### Domain Warp Effect (域扭曲效果)
- **Definition**: 通过噪声函数扭曲 UV 坐标，产生线条弯曲/等高线/视错觉
- **Identification**: 背景线条弯曲、等高线图案、有机纹理变形
- **GLSL keywords**: domain warping, polar coordinates, line integral, FBM warp
- **Token**: `{effect.warp}`

### Shape Effect (几何形状效果)
- **Definition**: 以明确的几何图形（心形/星形/方块等）为主体，带渐变填充和边缘光
- **Identification**: 清晰可辨识的几何形状、实心或空心填充、可能有内部渐变
- **GLSL keywords**: sdHeart/sdStar5/sdBox, solid fill (d) or hollow (abs(d)), edge glow
- **Token**: `{effect.shape}`
