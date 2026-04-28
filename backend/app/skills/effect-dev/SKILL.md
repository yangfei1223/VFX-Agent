---
name: effect-dev
description: |
  VFX shader development skill for 2D/2.5D procedural motion effects on mobile and web.
  Use when generating, reviewing, or debugging Shadertoy-format GLSL fragment shaders.
  Covers SDF operators (based on iq's formulations), noise functions, texture sampling,
  animation timing, shader templates, aesthetics rules, and GLSL safety constraints.
  Target: OS-level UI visual effects — flat/layered motion, NOT 3D scenes or raymarching.
  Activates when writing or modifying shader code, visual effect generation, or GPU rendering logic.
---

# VFX Effect Development Skill

You are developing **2D/2.5D procedural motion-effect shaders** for an OS-level visual FX agent system. The target is **mobile devices and web platforms** — performance and real-time responsiveness are paramount. This skill provides the complete knowledge base: operator libraries, shader templates, aesthetics principles, and safety constraints.

## Scope: 2D/2.5D Only

This skill covers **flat and layered visual effects** only:
- ✅ Background gradients, noise textures, atmospheric effects
- ✅ UI element effects: ripple, glow, pulse, frosted glass, shimmer
- ✅ 2D SDF shapes with smooth blending, masks, transitions
- ✅ Procedural animation: breathing, flowing, pulsing, oscillating
- ✅ Texture sampling for backdrop blur, distortion, tinting
- ❌ **NOT**: 3D raymarching, path tracing, volumetric rendering, camera/scene graphs
- ❌ **NOT**: High-polygon mesh rendering, PBR material systems, shadow maps

If a request implies 3D scene rendering, simplify to a 2D approximation or push back.

## Authority Sources

The knowledge in this skill is grounded in two authoritative references:

1. **Shadertoy** (https://www.shadertoy.com/) — Community repository of GLSL visual effects. When unsure about an effect's implementation, reference popular Shadertoy shaders for patterns. Key channels: `shadertoy.com/results?query=<effect_name>`
2. **Inigo Quilez (iq)** (https://iquilezles.org/) — Foundational SDF and noise operator definitions. The SDF operators in this skill are derived from iq's formulations:
   - 2D SDF: `https://iquilezles.org/articles/distfunctions2d/`
   - Noise: `https://iquilezles.org/articles/noise/`
   - Smooth minimum: `https://iquilezles.org/articles/smoothmin/`
   - Voronoi: `https://iquilezles.org/articles/voronoise/`

When generating shaders, prefer operators from these sources over ad-hoc implementations.

## Core Workflow

1. **Read the visual description JSON** to understand effect intent
2. **Select operators** from the references below based on shape/color/animation requirements
3. **Pick a template** if one matches the effect category, or compose from scratch
4. **Apply aesthetics rules** for color harmony and motion design
5. **Respect GLSL constraints** — safety, performance (mobile!), portability
6. **Output complete, compilable Shadertoy-format GLSL**

## Reference Files

Load these when you need detailed content (don't load all at once):

- `references/sdf-operators.md` — 2D SDF shape primitives (iq's formulations): circle, box, rounded rect, smooth union/intersection/subtraction, ring, arc
- `references/noise-operators.md` — Noise functions: Perlin, Simplex, Value, Voronoi, Worley (F1/F2), FBM composition
- `references/lighting-transforms.md` — Fresnel, 2D AO, rotation/scale transforms, UV manipulation
- `references/texture-sampling.md` — Texture/channel sampling patterns, iChannel usage, backdrop blur, procedural vs. sampled textures
- `references/shader-templates.md` — Full 2D effect skeletons: gradient, ripple, frosted glass, aurora, glow pulse
- `references/aesthetics-rules.md` — Color harmony, motion principles, mobile performance budget, dark-theme safety
- `references/gls-constraints.md` — GLSL safety rules, banned patterns, mobile GPU performance limits, cross-platform quirks

## Quick Reference: Shader Skeleton

See `assets/shader-skeleton.glsl` for the canonical file structure every shader must follow.

## Quick Reference: Validation

Run `scripts/validate-shader.py <file.glsl>` to check for banned patterns, missing mainImage, unsafe math, 3D raymarching detection, and texture usage errors before submitting.

## When to Load References

| Task | Load these |
|------|-----------|
| Generate new shader from description | sdf-operators, noise-operators, shader-templates, aesthetics-rules |
| Fix shape/geometry issues | sdf-operators, lighting-transforms |
| Fix color/appearance issues | noise-operators, aesthetics-rules, texture-sampling |
| Fix animation/timing issues | shader-templates (for easing patterns), aesthetics-rules (motion section) |
| Fix compile errors | gls-constraints |
| Fix performance issues | gls-constraints, aesthetics-rules (performance section) |
| Add texture support | texture-sampling |