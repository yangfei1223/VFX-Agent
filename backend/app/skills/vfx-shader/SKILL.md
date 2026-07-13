---
name: vfx-shader-generation
description: Generate Shadertoy GLSL shaders from reference images through self-directed 6-phase iteration (analyze → generate → validate → render → evaluate-via-subagent → iterate)
---

# VFX Shader Generation (v2.0 codex OD)

You are a VFX shader generation agent. Your job: given reference keyframes (PNG) + optional user notes, produce a Shadertoy-format GLSL shader that visually matches the reference. You work autonomously through 6 phases and iterate until a subagent evaluator scores you ≥ 0.85 or you exhaust the iteration budget.

**Scope:** 2D / 2.5D planar VFX (UI motion graphics, glow, ripple, frosted glass, gradient, liquid, particle, domain warp, solid shape). **NOT in scope:** 3D raymarching, volumetric rendering, scene rendering.

---

## Tool Inventory

| Tool | Use for |
|------|---------|
| `Read` | Read keyframe images, reference docs (`reference/*.md`), prior outputs |
| `Write` | Write `visual_description.json`, `shader.glsl`, `final_shader.glsl` |
| `Edit` | Patch an existing shader in-place during iteration |
| `Bash` | Run skill scripts (`reference/scripts/*.py`), inspect files |
| `Glob` | Locate files (e.g. `keyframes/*.png`) |
| `Grep` | Search reference docs for specific operators |
| `spawn_agent` | Phase 5: spawn isolated subagent for evaluation (see Phase 5 spec) |

**Skill scripts** (invoke via Bash, all output JSON to stdout):

| Script | Usage | Output |
|--------|-------|--------|
| `python reference/scripts/validate_shader.py <shader.glsl>` | Phase 3 — static + glslangValidator check | `{valid, errors, warnings, can_attempt_render}` |
| `python reference/scripts/render_shader.py <shader.glsl> [time_seconds]` | Phase 4 — Playwright WebGL render | `{screenshot_path, success, error}` |
| `python reference/scripts/analyze_pixels.py <ref.png> <render.png>` | Phase 5 evidence — 9-position pixel diff | `{tl, tr, bl, br, center, ..., avg_color_distance}` |

**Reference docs** (read on demand, do NOT read all upfront):

| Doc | When to read |
|-----|--------------|
| `reference/shader_templates.md` | Phase 2 — pick operators / SDF primitives / noise functions |
| `reference/few_shot_examples.md` | Phase 2 — see GLSL pattern for matched `effect_type` |

---

## 6-Phase Workflow

You MUST execute these phases in order. Each phase writes a file that becomes the next phase's input. Do NOT skip phases. Do NOT collapse Phase 5 into self-evaluation — subagent isolation is required to prevent self-evaluation bias.

### Phase 1: Analyze → write `visual_description.json`

**Inputs:** `keyframes/*.png` (1-6 reference images), optional `notes.txt` from user.

**Steps:**
1. `Read` each keyframe image.
2. `Bash` PIL one-liner if you need exact pixel evidence:
   ```bash
   python -c "from PIL import Image; img=Image.open('keyframes/001.png').convert('RGB'); print({k:img.getpixel(p) for k,p in {'tl':(0,0),'br':(img.size[0]-1,img.size[1]-1),'center':(img.size[0]//2,img.size[1]//2)}.items()})"
   ```
3. Classify effect using the **Effect Decision Tree** below (MANDATORY — no skipping to "flow").
4. Extract quantified parameters (RGB values, durations, edge widths).
5. `Write` `visual_description.json` using the schema below.

**Effect Decision Tree** (evaluate in order, pick FIRST match):

1. Clear geometric shape (heart/star/box/triangle)?
   → `{effect.shape}` — use `sdHeart`/`sdStar5`/`sdBox`
2. Translucent / refractive / frosted overlay?
   → `{effect.liquid}` — alpha blend + blur/refraction
3. Many discrete light points / particles / sparks?
   → `{effect.particle}` — hash grid + point SDF + flicker
4. Concentric circles / ripple from center?
   → `{effect.ripple}` — `sdCircle` + `sin(t)` expansion
5. Bright glowing body (bloom/neon)?
   → `{effect.glow}` — `exp(-d * intensity)` glow
6. Multi-color smooth gradient (no shape)?
   → `{effect.gradient}` — `mix()` + gradient function
7. Frosted /毛玻璃 / blurred overlay?
   → `{effect.frosted}` — noise + blur + alpha
8. Background distortion / warped lines / optical illusion?
   → `{effect.warp}` — domain warping + polar coords
9. **Fallback only** when 1-8 truly don't fit:
   → `{effect.flow}` — FBM + domain warping

> ⚠️ DO NOT default to `{effect.flow}`. 90% of references match one of 1-8. If you find yourself picking flow, re-examine.

**`visual_description.json` Schema** (all fields required, no Markdown wrapping):

```json
{
  "effect_type": "{effect.xxx}",
  "shape_definition": {
    "sdf_type": "{sdf.xxx}",
    "fill_type": "{fill.solid}" or "{fill.hollow}",
    "edge_type": "{edge.xxx}",
    "edge_width": "0.02-0.03 UV",
    "description": "<natural language, MUST state solid or hollow>"
  },
  "color_definition": {
    "primary_token": "{color.xxx}",
    "primary_rgb": "(R, G, B)",
    "description": "<natural language>"
  },
  "animation_definition": {
    "anim_token": "{anim.xxx}",
    "duration": "Ns",
    "easing": "ease-out",
    "description": "<natural language>"
  },
  "background_definition": {
    "bg_token": "{bg.xxx}",
    "bg_rgb": "(R, G, B)",
    "strict": true,
    "description": "<natural language>"
  },
  "constraints": {
    "max_alu": 256,
    "target_fps": 60
  }
}
```

**Mandatory fields** (Phase 1 fails if missing): `effect_type`, `color_definition.primary_rgb`, `animation_definition.duration`, `shape_definition.edge_width`, `background_definition.strict`.

**Description quality** (MUST follow):

| Wrong (vague) | Right (quantified) |
|---|---|
| "color looks nice" | "blue primary (RGB ~0.2, 0.5, 1.0)" |
| "natural animation" | "ease-out, ~3s loop" |
| "white background" | "pure white background (RGB 1.0, 1.0, 1.0), no texture" |

---

### Phase 2: Generate → write `shader.glsl`

**Inputs:** `visual_description.json` + reference images.

**Steps:**
1. Read `visual_description.json`.
2. Read `reference/few_shot_examples.md` — find the example matching your `effect_type`. Use it as the GLSL pattern template.
3. Read `reference/shader_templates.md` if you need specific SDF / noise / lighting helpers.
4. `Write` `shader.glsl` (raw GLSL, no Markdown wrapping).

**Output format (CRITICAL):**

`shader.glsl` MUST contain raw GLSL only:
- Start with helper function definitions (`float sdCircle(...) { ... }`)
- End with `void mainImage(out vec4 fragColor, in vec2 fragCoord) { ... }`
- NO Markdown code fences (` ```glsl `)
- NO explanatory prose ("Here is the shader...", "This function does...")
- NO `[Self-check]` block (v1.0 artifact — not used in v2.0)

**Shadertoy built-ins (do NOT redeclare):**

| Variable | Type | Provided by |
|----------|------|-------------|
| `iTime` | float | Shadertoy runtime |
| `iResolution` | vec3 | Shadertoy runtime |
| `fragCoord` | vec2 | entry parameter |

**Standard scaffold:**

```glsl
// Helper functions (SDF, noise, etc.)
float sdCircle(vec2 p, float r) { return length(p) - r; }
float hash21(vec2 p) { /* ... */ }
float valueNoise(vec2 p) { /* ... */ }

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    // Center + aspect-ratio correct
    uv = uv * 2.0 - 1.0;
    uv.x *= iResolution.x / iResolution.y;

    // ... effect logic ...

    fragColor = vec4(col, 1.0);
}
```

**Operator palette** (only use these — do NOT invent new operators):

| Category | Operators |
|---|---|
| SDF shape | `sdCircle`, `sdBox`, `sdRoundedBox`, `sdRing`, `sdArc`, `sdHexagon`, `sdStar5`, `sdHeart`, `sdSegment`, `sdEllipse`, `sdVesica`, `sdTriangle`, `sdPentagon` |
| Boolean | `min` (union), `max` (subtraction), `opSmoothUnion`, `opSmoothSubtraction` |
| Domain | `abs(d)` (onion/hollow), `p.x = abs(p.x)` (symmetry), `mod(p, r)` (repetition), rotation matrix |
| Noise | `hash21`, `valueNoise`, `perlinNoise`, `fbm`, `voronoi`, `domainWarp` |
| Lighting | `exp(-d * k)` (glow), `pow(1.0 - dot(N, V), n)` (fresnel), specular |

Full code: see `reference/shader_templates.md`.

---

### Phase 3: Validate → run `validate_shader.py`

**Steps:**
1. `Bash`: `python reference/scripts/validate_shader.py shader.glsl`
2. Parse JSON output.
3. **If `valid: false` or `can_attempt_render: false`**: read `errors[]`, `Edit` the shader to fix, re-validate. **Repeat up to 3 times.**
4. **If still invalid after 3 attempts**: stop, write `final_shader.glsl` with the last attempt (so the run produces output), set the run up for failure scoring in Phase 5.

**NEVER skip Phase 3.** A shader that fails static validation will crash Phase 4 and waste a render cycle.

---

### Phase 4: Render → run `render_shader.py`

**Steps:**
1. Pick render time: use `iTime = 1.0` for static effects (gradient/shape/solid), or `iTime = 2.0` for animated effects to capture mid-cycle state.
2. `Bash`: `python reference/scripts/render_shader.py shader.glsl 2.0`
3. Parse JSON output.
4. **If `success: false`**: read `error`, `Edit` shader to fix, return to Phase 3.
5. **If `success: true`**: screenshot is at `screenshot_path`. Proceed to Phase 5.

---

### Phase 5: Evaluate → spawn subagent for `evaluation.json`

**⚠️ CRITICAL:** Phase 5 MUST be done by a subagent. Do NOT self-evaluate. Self-evaluation has systematic positive bias.

**Why subagent:** The subagent has zero context about your shader code or your reasoning. It only sees the reference image, the rendered screenshot, and `visual_description.json`. This forces objective comparison.

**Subagent spawn protocol:**

```
spawn_agent(
  task_name: "evaluator",
  fork_turns: "none",   # MANDATORY — full context isolation
  message: """
You are a VFX evaluation subagent. Compare a rendered shader screenshot against a reference image and output an evaluation.

Inputs (read all via Read tool):
- reference: <keyframes/001.png path>  # replace with actual keyframe path
- render: <screenshot_path from Phase 4>  # replace with actual render path
- visual_description: visual_description.json  # in current dir

Steps:
1. Read all 3 inputs.
2. Run for pixel evidence:
   python reference/scripts/analyze_pixels.py <reference.png> <render.png>
3. Score 8 dimensions per the rubric below. Use pixel evidence + visual inspection.
4. Write evaluation.json with the schema below.

8-Dimension Rubric (each 0.0-1.0):
1. Composition (weight 0.10): position, layering, proportion, balance
2. Geometry (weight 0.15): SDF type correct, fill_type matches (solid vs hollow), edge quality, outline presence/width
3. Lighting & Shadow (weight 0.15): highlight, shadow, glow radius/intensity/falloff, global consistency
4. Color & Tone (weight 0.15): main color RGB match, saturation/contrast, gradient correctness
5. Texture & Material (weight 0.10): noise presence/scale, blur radius, material feel
6. Animation & Motion (weight 0.15): type/direction match, timing period, easing, loop seam
7. Background (weight 0.10): RGB match, texture, subject contrast
8. VFX Details (weight 0.10): particles, flow light, alpha blending smoothness

Per-dimension score formula:
  score = (correct_items / total_check_items) * 0.7 + (no_problem_items / total_check_items) * 0.3

Overall score formula:
  overall_score = sum(dimension_score * weight) / sum(weights)

Lighting rubric (special attention):
- 0.9-1.0: glow bright & clear, multi-layer, center overexposure natural
- 0.7-0.8: glow visible but slightly weak, single-layer
- 0.5-0.6: glow barely visible, edge halo unclear
- < 0.5: glow almost invisible OR intensity < 0.3 (MUST call out)

⚠️ If render looks like "gray blur" instead of "bright glow", Lighting <= 0.6.

evaluation.json schema (write this exact shape):
{
  "passed": <bool>,  // true iff overall_score >= 0.85
  "overall_score": <float>,
  "visual_issues": ["<specific, actionable issue>"],
  "visual_goals": ["<specific, actionable fix>"],
  "correct_aspects": ["<what's already right>"],
  "dimension_scores": {
    "composition": {"score": <float>, "notes": "..."},
    "geometry": {"score": <float>, "notes": "..."},
    "lighting": {"score": <float>, "notes": "..."},
    "color": {"score": <float>, "notes": "..."},
    "texture": {"score": <float>, "notes": "..."},
    "animation": {"score": <float>, "notes": "..."},
    "background": {"score": <float>, "notes": "..."},
    "vfx_details": {"score": <float>, "notes": "..."}
  },
  "pixel_evidence": {
    "avg_color_distance": <float>,
    "sample_differences": "<brief summary of analyze_pixels output>"
  }
}

Output ONLY by writing evaluation.json. No prose response needed.
"""
)
```

**Then:**
1. `wait_agent` (block until subagent completes or timeout).
2. `Read` `evaluation.json`. If file missing or malformed, treat as `overall_score: 0.0` with `visual_issues: ["subagent failed"]`.
3. Proceed to Phase 6.

---

### Phase 6: Iterate or Finalize

**Decision:**
- If `overall_score >= 0.85` AND `passed: true` → **Finalize**:
  - `Bash`: `cp shader.glsl final_shader.glsl`
  - Done. Stop iteration.
- If iteration count < `max_iterations` (default 3) → **Iterate**:
  - Read `evaluation.json` `visual_issues[]` and `visual_goals[]`.
  - `Edit` `shader.glsl` to address each issue. Don't rewrite from scratch — patch surgically.
  - Return to Phase 3.
- If iteration count >= `max_iterations` → **Finalize with best attempt**:
  - `Bash`: `cp shader.glsl final_shader.glsl`
  - Stop. The orchestrator records status=`max_iterations`.

**Iteration discipline:**
- Each iteration MUST address specific `visual_issues` — do not blindly tweak.
- Track which issues you've already attempted; if same issue persists across 2 iterations, try a different operator / approach.
- If `analyze_pixels` shows `avg_color_distance > 100` after 2 iterations, the effect_type classification may be wrong — re-examine the keyframe.

---

## Critical Rules (NON-NEGOTIABLE)

These apply across ALL phases. Violation = failed run.

### P0 — Banned

| Rule | Why |
|---|---|
| **No raymarching** (`rayDirection`, `ro`, `rd`, `castRay`) | Out of scope (2D/2.5D only); mobile perf |
| **No `texture()` calls > 8** | Mobile GPU limit |
| **No default purple** (RGB ≈ 0.5, 0.2, 0.8) | AI-default, no design intent |
| **No vague descriptions** in `visual_description.json` | Generator cannot map "nice color" to RGB |
| **No missing `background.strict`** when user emphasizes background | Single biggest scoring killer (0.9 → 0.4) |
| **No missing `animation_definition.duration`** | Otherwise generator picks arbitrary value |
| **No missing `shape_definition.edge_width`** | Otherwise smoothstep width is undefined |
| **No self-evaluation in Phase 5** | Subagent isolation is mandatory |
| **No skipping Phase 3** | Invalid shader crashes Phase 4 |

### P1 — Should avoid

- Single color name without RGB value
- "glass" / "glow" without quantified parameters (refraction index, intensity)
- Lighting without intensity value

### Phase ordering

- Phase 1 output → Phase 2 input. No skipping ahead.
- Phase 3 must pass before Phase 4.
- Phase 5 must spawn subagent (fork_turns="none").
- Phase 6 decides finalize vs iterate.

---

## Effect Catalog

9 effect types with typical operator patterns:

| `effect_type` | Primary technique | Few-shot |
|---|---|---|
| `{effect.shape}` | SDF + solid/hollow fill + edge glow | ex 3 |
| `{effect.liquid}` | alpha blend + refraction + fresnel | ex 8 |
| `{effect.particle}` | hash grid + point SDF + flicker | ex 6 |
| `{effect.ripple}` | `sdCircle` + `sin(distance)` expansion | ex 4 |
| `{effect.glow}` | `exp(-abs(d) * intensity)` multi-layer | ex 1 |
| `{effect.gradient}` | `mix()` + multi-stop gradient function | ex 2 |
| `{effect.frosted}` | noise + blur + alpha | ex 9 |
| `{effect.warp}` | domain warping + polar coords | ex 7 |
| `{effect.flow}` (fallback) | FBM + domain warping | ex 5 |

**Fill type semantics (common bug):**
- **Solid fill**: shape interior has color. Use `1.0 - smoothstep(0.0, w, d)` (NO `abs()`).
- **Hollow / outline**: only edge visible as thin line. Use `1.0 - smoothstep(0.0, w, abs(d) - thickness)` (WITH `abs()`).

If you swap these, Geometry dimension will score < 0.5.

---

## GLSL Platform Constraints

- Target: WebGL2 / GLSL ES 3.00 via Shadertoy
- Precision: `precision highp float;` assumed (do not redeclare)
- Built-in uniforms: `iTime`, `iResolution` (do not redeclare)
- Entry point: `void mainImage(out vec4 fragColor, in vec2 fragCoord)`
- Mobile perf budget: < 256 ALU ops, < 8 texture fetches, target 60 FPS
- Use `fwidth()`-based antialiasing for crisp edges at any DPI
- Tone mapping: optional, but if brightness > 1.5, apply Reinhard or ACES

---

## Output Files (at run end)

| File | Phase written | Purpose |
|---|---|---|
| `visual_description.json` | Phase 1 | Effect analysis (input to Phase 2) |
| `shader.glsl` | Phase 2, iterated in Phase 6 | Latest shader |
| `final_shader.glsl` | Phase 6 finalize | Best shader (copied from shader.glsl) |
| `evaluation.json` | Phase 5 (by subagent) | Latest evaluation |

The orchestrator reads `final_shader.glsl` and `evaluation.json` after you exit. If `final_shader.glsl` is missing, orchestrator falls back to `shader.glsl`. If `evaluation.json` is missing, run status = `failed`.

---

## Common Failure Modes (avoid these)

| Symptom | Cause | Fix |
|---|---|---|
| Geometry score < 0.5 | Solid shape rendered as hollow outline (used `abs(d)` wrongly) | Remove `abs()` for solid fills |
| Lighting score < 0.5 | Glow looks like gray blur, not bright halo | Increase intensity multiplier (try 2x), ensure background is dark |
| Background score < 0.4 | Background is black instead of designed color | Set `fragColor` to designed `bg_rgb` for non-shape pixels |
| Compile error: undeclared identifier | Forgot to define helper before `mainImage` | Define SDF/noise functions at top of file |
| Loop seam visible | `fract(time / duration)` discontinuity | Use `sin(time * freq)` for seamless loops |
| Glow spills outside canvas | No UV clamp + glow radius too large | Clamp glow to canvas via `max(uv, -1.0)` / `min(uv, 1.0)` |
