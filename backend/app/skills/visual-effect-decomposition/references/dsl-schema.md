# DSL Schema

Complete specification for Visual Effect DSL JSON output.

## Required Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `effect_name` | string | ✅ | Unique identifier (snake_case) |
| `operators` | array | ✅ | List of operator definitions |
| `topology` | string | ✅ | Composition expression |
| `constraints` | object | ✅ | Performance limits |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `uniforms` | object | Custom uniform definitions |
| `description` | string | Human-readable description |
| `tags` | array | Effect category tags |

## Operators Schema

### Operator Object Structure

```json
{
  "type": "Operator_Type",
  "id": "optional_unique_id",
  "params": {
    "param1": value,
    "param2": value
  },
  "blend_mode": "none|union|intersection|subtraction|smooth_union",
  "blend_factor": 0.1
}
```

### Operator Type Registry

| Type | Required Params | Optional Params |
|------|-----------------|------------------|
| `SDF_Circle` | `radius` | `center` |
| `SDF_Box` | `size` | `center`, `cornerRadius` |
| `SDF_RoundedBox` | `size`, `cornerRadius` | `center` |
| `SDF_Segment` | `start`, `end` | `thickness` |
| `SDF_Triangle` | `vertices` | - |
| `SDF_Polygon` | `vertices` | - |
| `Hash` | - | `seed` |
| `ValueNoise` | `frequency` | `seed` |
| `PerlinNoise` | `frequency` | `octaves`, `amplitude` |
| `SimplexNoise` | `frequency` | - |
| `Voronoi` | `frequency` | `seed` |
| `FBM` | `octaves`, `frequency`, `amplitude` | `lacunarity`, `gain` |
| `Turbulence` | `octaves` | `frequency` |
| `Fresnel` | `power` | - |
| `SpecularHighlight` | `position`, `intensity` | `radius`, `color` |
| `DiffuseLight` | `direction` | `intensity` |
| `AmbientOcclusion` | `radius` | `samples` |
| `Gradient` | `type`, `stops` | `direction`, `center` |
| `ColorMix` | `colors`, `blend` | - |
| `ToneMapping` | `type` | `exposure` |
| `ColorGrade` | `params` | - |
| `TimeLoop` | `duration` | `offset` |
| `EaseInOut` | `type` | `params` |
| `SinWave` | `frequency`, `amplitude` | `phase` |
| `Pulse` | `frequency` | `intensity` |
| `Flow` | `speed`, `direction` | - |
| `UV_Transform` | `offset`, `scale` | - |
| `UV_Rotate` | `angle` | `center` |
| `UV_Scale` | `factor` | `center` |
| `Glow` | `radius`, `intensity` | `falloff`, `color` |
| `Blur` | `type`, `radius` | - |
| `Outline` | `width`, `color` | `softness`, `position` |
| `AlphaBlend` | `opacity` | `mode` |

### Example Operators Array

```json
{
  "operators": [
    {
      "type": "SDF_Circle",
      "id": "ripple_shape",
      "params": {"radius": 0.3},
      "blend_mode": "none"
    },
    {
      "type": "SinWave",
      "id": "ripple_animation",
      "params": {"frequency": 3.0, "amplitude": 0.1}
    },
    {
      "type": "Gradient",
      "id": "ripple_color",
      "params": {
        "type": "radial",
        "stops": [
          {"position": 0.0, "color": [0.2, 0.5, 1.0]},
          {"position": 1.0, "color": [1.0, 1.0, 1.0]}
        ]
      }
    },
    {
      "type": "Glow",
      "id": "ripple_glow",
      "params": {"radius": 20, "intensity": 0.5, "falloff": "exp"}
    }
  ]
}
```

## Topology Expression Grammar

### Basic Syntax

```
compose(op1, op2, op3)
add(op1, op2)
multiply(op1, op2)
blend(op1, op2, k)
layer(base, overlay)
animate(op, driver)
```

### Composition Functions

| Function | Description | Example |
|----------|-------------|---------|
| `compose(a, b, c)` | Sequential pipeline | `compose(SDF, Gradient, Glow)` |
| `add(a, b)` | Additive blend | `add(Shape, Glow)` |
| `multiply(a, b)` | Multiplicative blend | `multiply(Noise, Color)` |
| `blend(a, b, k)` | Smooth blend | `blend(SDF1, SDF2, 0.1)` |
| `layer(base, overlay)` | Layer stacking | `layer(Background, Foreground)` |
| `animate(op, driver)` | Apply animation | `animate(SDF, TimeLoop)` |

### Complex Topology Examples

```json
// Ripple effect
"topology": "animate(SDF_Circle, SinWave) → Gradient → Glow"

// Frosted glass
"topology": "compose(PerlinNoise, Blur, AlphaBlend)"

// Multi-shape
"topology": "blend(SDF_Box, SDF_Circle, 0.1) → Specular → Glow"

// Full stack
"topology": "compose(SDF, Fresnel, FBM, Gradient, animate(TimeLoop), Glow)"
```

## Uniforms Schema

### Standard Uniforms (Auto-injected)

| Uniform | Type | Source |
|---------|------|--------|
| `iTime` | float | Shadertoy runtime |
| `iResolution` | vec3 | Shadertoy runtime |
| `iMouse` | vec4 | Shadertoy runtime |
| `fragCoord` | vec4 | Shadertoy runtime |

### Custom Uniforms Definition

```json
{
  "uniforms": {
    "custom_speed": {
      "type": "float",
      "default": 1.0,
      "range": [0.5, 2.0],
      "description": "Animation speed multiplier"
    },
    "custom_color": {
      "type": "vec3",
      "default": [0.2, 0.5, 1.0],
      "description": "Main color RGB"
    },
    "custom_intensity": {
      "type": "float",
      "default": 0.8,
      "range": [0.0, 1.0],
      "description": "Effect intensity"
    }
  }
}
```

## Constraints Schema

### Performance Constraints

```json
{
  "constraints": {
    "max_alu": 256,              // ALU instruction budget
    "max_texture_fetch": 8,      // Texture read budget
    "max_fbm_octaves": 4,        // FBM complexity limit
    "max_loop_iterations": 100,  // Loop iteration limit
    "target_fps": 30,            // Minimum FPS
    "target_frame_time_ms": 33,  // Maximum frame time
    "max_shader_size_kb": 32    // Shader size budget
  }
}
```

### Platform Constraints

| Platform | max_alu | max_texture | target_fps |
|----------|---------|-------------|------------|
| Mobile Low | 128 | 4 | 30 |
| Mobile Mid | 256 | 8 | 60 |
| Desktop | 1024 | 16 | 60 |

### Quality Constraints

```json
{
  "constraints": {
    "antialiasing": true,
    "color_depth": 8,
    "use_mipmaps": true,
    "avoid_branching": true
  }
}
```

## Complete DSL Example

```json
{
  "effect_name": "ripple_diffusion",
  "description": "Ripple diffusion effect with glow",
  "tags": ["ripple", "animation", "glow"],
  
  "operators": [
    {
      "type": "SDF_Circle",
      "id": "ripple_shape",
      "params": {"radius": 0.3},
      "blend_mode": "none"
    },
    {
      "type": "SinWave",
      "id": "ripple_wave",
      "params": {"frequency": 3.0, "amplitude": 0.1}
    },
    {
      "type": "Gradient",
      "id": "ripple_color",
      "params": {
        "type": "radial",
        "stops": [
          {"position": 0.0, "color": [0.2, 0.5, 1.0]},
          {"position": 0.5, "color": [0.5, 0.7, 1.0]},
          {"position": 1.0, "color": [1.0, 1.0, 1.0]}
        ]
      }
    },
    {
      "type": "Glow",
      "id": "ripple_glow",
      "params": {"radius": 20, "intensity": 0.5, "falloff": "exp"}
    },
    {
      "type": "TimeLoop",
      "id": "ripple_animation",
      "params": {"duration": 3.5}
    },
    {
      "type": "EaseInOut",
      "id": "ripple_easing",
      "params": {"type": "cubic"}
    }
  ],
  
  "topology": "animate(compose(SDF_Circle, SinWave), compose(TimeLoop, EaseInOut)) → Gradient → Glow",
  
  "uniforms": {
    "ripple_speed": {
      "type": "float",
      "default": 1.0,
      "range": [0.5, 2.0],
      "description": "Ripple propagation speed"
    }
  },
  
  "constraints": {
    "max_alu": 150,
    "max_texture_fetch": 4,
    "target_fps": 60
  }
}
```

## Validation Rules

### Operator Validation

1. `type` must be from registry
2. Required params must present
3. Param values must in valid range
4. `blend_mode` must be valid enum

### Topology Validation

1. All operator IDs must exist
2. Composition order must be logical
3. No circular dependencies

### Constraint Validation

1. Budgets must reasonable for target platform
2. FPS targets must achievable