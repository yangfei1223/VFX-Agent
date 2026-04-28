---
name: visual-effect-decomposition
description: |
  Professional visual effect decomposition methodology for DSL generation.
  
  Use when Decompose Agent needs to:
  (1) Analyze design reference (image/video) and extract structured visual description
  (2) Output DSL JSON with operators, topology, and constraints
  (3) Use professional terminology for visual analysis
  (4) Generate complete operators list (SDF, noise, lighting, animation)
  (5) Define operator topology (composition relationships)
  
  Provides: decomposition dimensions, operator catalog, DSL schema, topology patterns, animation analysis, background handling.
---

# Visual Effect Decomposition Skill

Professional methodology for decomposing visual effects into structured DSL representation.

## Core Philosophy

**Decompose Agent outputs visual analysis, Generate Agent writes GLSL code.**

Decomposition must:
- ✅ Cover ALL visual aspects (shape, color, lighting, animation, background)
- ✅ Use PROFESSIONAL terminology (SDF types, noise types, lighting models)
- ✅ Generate COMPLETE operators list (not partial)
- ✅ Define OPERATOR topology (composition relationships)
- ✅ Specify CONSTRAINTS (performance budget, platform limits)
- ❌ NOT write GLSL code (that's Generate Agent's job)

## Workflow

### Step 1: Visual Analysis

Analyze design reference across 8 dimensions:

1. **Composition**: Position, hierarchy, spacing, proportion
2. **Geometry**: Shape types, SDF primitives, outline properties
3. **Lighting**: Highlight types, shadow types, glow effects
4. **Color**: Main hue, saturation, gradients, color layers
5. **Texture**: Noise types, blur effects, material properties
6. **Animation**: Animation types, timing curves, rhythm, cycles
7. **Background**: Color, texture, transparency, dynamic effects
8. **VFX Details**: Particles, flow lights, alpha blending

**See detailed analysis guide:** [references/visual-analysis.md](references/visual-analysis.md)

### Step 2: Operator Extraction

For each visual element, identify corresponding GLSL operators.

**Operator Categories**:

| Category | Operators | When to Use |
|----------|-----------|-------------|
| **SDF Primitives** | `SDF_Circle`, `SDF_Box`, `SDF_Rect`, `SDF_Line` | Basic shapes |
| **SDF Operations** | `SDF_Union`, `SDF_Intersection`, `SDF_Subtraction`, `Smooth_Union` | Shape combination |
| **Noise Functions** | `Hash`, `ValueNoise`, `PerlinNoise`, `SimplexNoise`, `Voronoi`, `FBM` | Texture/movement |
| **Lighting Models** | `Fresnel`, `SpecularHighlight`, `DiffuseLight`, `AmbientOcclusion` | Light effects |
| **Color Operations** | `Gradient`, `ColorMix`, `ToneMapping`, `ColorGrade` | Color effects |
| **Animation Drivers** | `TimeLoop`, `EaseInOut`, `SinWave`, `Pulse`, `Flow` | Animation timing |
| **UV Operations** | `UV_Transform`, `UV_Rotate`, `UV_Scale`, `UV_Offset` | Coordinate manipulation |
| **Post Effects** | `Glow`, `Blur`, `Outline`, `AlphaBlend` | Final composition |

**See operator catalog:** [references/operator-catalog.md](references/operator-catalog.md)

### Step 3: Topology Definition

Define how operators compose together:

**Common Topology Patterns**:

| Pattern | Structure | Example |
|---------|-----------|---------|
| **Single Layer** | `SDF → Color → Output` | Simple shape with color |
| **Multi-Shape** | `SDF1 + SDF2 → Smooth_Union → Color` | Combined shapes |
| **Layered Effect** | `Shape → Glow → Blur → Output` | Outline + glow |
| **Animated** | `SDF(TimeLoop) → Animation → Output` | Moving shape |
| **Full Stack** | `SDF → Lighting → Noise → Color → Animation → Post → Output` | Complex effect |

**See topology patterns:** [references/topology-patterns.md](references/topology-patterns.md)

### Step 4: DSL Generation

Output structured DSL JSON:

```json
{
  "effect_name": "effect_identifier",
  "operators": [
    {"type": "SDF_Primitive", "params": {...}, "blend_mode": "..."},
    {"type": "Noise_Function", "params": {...}},
    {"type": "Lighting_Model", "params": {...}},
    ...
  ],
  "topology": "compose(SDF, lighting(Specular, Fresnel), noise(FBM), animation(TimeLoop))",
  "uniforms": {
    "iTime": "fract(t / duration)",
    "custom_speed": {"type": "float", "default": 1.0}
  },
  "constraints": {
    "max_alu": 256,
    "max_texture_fetch": 8,
    "target_fps": 30
  }
}
```

**See DSL schema:** [references/dsl-schema.md](references/dsl-schema.md)

## DSL Schema

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `effect_name` | string | Unique identifier (e.g., "ripple_diffusion") |
| `operators` | array | List of operator definitions |
| `topology` | string | Composition structure |
| `constraints` | object | Performance and platform limits |

### Operators Object Structure

```json
{
  "type": "Operator_Type",
  "params": {
    "param1": value1,
    "param2": value2
  },
  "blend_mode": "none|union|intersection|subtraction|smooth_union"
}
```

### Topology Expression Grammar

```
compose(op1, op2, op3)       // Sequential composition
add(op1, op2)                // Additive blend
multiply(op1, op2)           // Multiplicative blend
blend(op1, op2, k)           // Smooth blend with factor k
layer(base, overlay)         // Layer stacking
animate(op, driver)          // Apply animation driver
```

### Constraints Object

```json
{
  "max_alu": 256,              // ALU instruction limit (mobile)
  "max_texture_fetch": 8,      // Texture read limit
  "max_fbm_octaves": 4,        // FBM complexity limit
  "target_fps": 30,            // Minimum FPS target
  "target_frame_time_ms": 33   // Maximum frame time
}
```

## Analysis Templates

### Shape Analysis Template

```json
{
  "shape": {
    "type": "SDF_Primitive_Type",
    "sdf_primitives": [
      {"type": "SDF_Box", "size": [width, height]},
      {"type": "SDF_Circle", "radius": radius}
    ],
    "blend_mode": "smooth_union",
    "blend_factor": 0.1,
    "outline": {
      "present": true,
      "width": 2,
      "color": "RGB(r, g, b)",
      "position": "outer"
    }
  }
}
```

### Color Analysis Template

```json
{
  "color": {
    "main_hue": "blue",
    "main_rgb": [0.2, 0.5, 1.0],
    "saturation": 0.8,
    "gradient": {
      "type": "linear",
      "direction": "vertical",
      "stops": [
        {"position": 0.0, "color": [0.2, 0.5, 1.0]},
        {"position": 1.0, "color": [1.0, 1.0, 1.0]}
      ]
    },
    "layers": 3,
    "transitions": "smooth"
  }
}
```

### Lighting Analysis Template

```json
{
  "lighting": {
    "highlight": {
      "type": "specular",
      "position": "top-center",
      "intensity": 0.7,
      "radius": 5
    },
    "shadow": {
      "type": "soft",
      "direction": "bottom-left",
      "depth": 0.6,
      "softness": 0.3
    },
    "glow": {
      "present": true,
      "radius": 15,
      "intensity": 0.5,
      "falloff": "exponential"
    },
    "rim_light": {
      "present": false,
      "width": 3
    }
  }
}
```

### Animation Analysis Template

```json
{
  "animation": {
    "type": "ripple",
    "direction": "outward",
    "cycle_duration_s": 3.5,
    "easing": "ease-in-out",
    "amplitude": 1.0,
    "frequency": 1.0,
    "trajectory": "radial",
    "coverage": "full_screen"
  }
}
```

### Background Analysis Template (Critical)

```json
{
  "background": {
    "color": {
      "main_rgb": [0.1, 0.8, 0.7],
      "name": "cyan"
    },
    "texture": {
      "type": "radial_gradient",
      "center": [0.5, 0.5],
      "stops": [...]
    },
    "transparency": 0.5,
    "dynamic": {
      "present": true,
      "type": "noise_drift",
      "speed": 0.5
    }
  }
}
```

## Common Effect Patterns

### Ripple Effect

```json
{
  "effect_name": "ripple_diffusion",
  "operators": [
    {"type": "SDF_Circle", "params": {"radius": 0.3}},
    {"type": "SinWave", "params": {"frequency": 3.0, "amplitude": 0.1}},
    {"type": "Gradient", "params": {"type": "radial", "stops": [...]}},
    {"type": "Glow", "params": {"radius": 20, "intensity": 0.5}}
  ],
  "topology": "animate(SDF_Circle, SinWave) → Gradient → Glow",
  "constraints": {"max_alu": 100, "target_fps": 60}
}
```

### Frosted Glass Effect

```json
{
  "effect_name": "frosted_glass",
  "operators": [
    {"type": "Blur", "params": {"type": "gaussian", "radius": 15}},
    {"type": "PerlinNoise", "params": {"octaves": 4, "frequency": 2.0}},
    {"type": "AlphaBlend", "params": {"mode": "normal", "opacity": 0.7}}
  ],
  "topology": "Noise → Blur → AlphaBlend",
  "constraints": {"max_alu": 200, "max_texture_fetch": 8}
}
```

### Glow Effect

```json
{
  "effect_name": "glow_effect",
  "operators": [
    {"type": "SDF_Circle", "params": {"radius": 0.2}},
    {"type": "SpecularHighlight", "params": {"position": "center", "intensity": 1.0}},
    {"type": "Glow", "params": {"radius": 30, "intensity": 0.8, "falloff": "exp"}}
  ],
  "topology": "SDF_Circle → SpecularHighlight → Glow",
  "constraints": {"max_alu": 150}
}
```

## References

- [Visual Analysis Guide](references/visual-analysis.md) - Complete analysis methodology
- [Operator Catalog](references/operator-catalog.md) - All available operators with parameters
- [Topology Patterns](references/topology-patterns.md) - Common composition patterns
- [DSL Schema](references/dsl-schema.md) - Complete DSL specification
- [Animation Analysis](references/animation-analysis.md) - Animation decomposition guide
- [Background Handling](references/background-handling.md) - Background analysis focus