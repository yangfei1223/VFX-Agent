# Texture Sampling Reference

## iChannel System

Shadertoy provides up to 4 texture channels via `iChannel0`–`iChannel3`. In our runtime, these map to:

| Channel | Content | Type |
|---------|---------|------|
| iChannel0 | Backdrop/framebuffer capture | sampler2D (system-provided) |
| iChannel1 | User-uploaded texture | sampler2D (optional) |
| iChannel2 | Reserved | — |
| iChannel3 | Reserved | — |

## Sampling Patterns

### Standard texture sample
```glsl
vec4 texColor = texture(iChannel0, uv);
```

### Backdrop blur (frosted glass)
```glsl
vec3 backdropBlur(vec2 uv, float radius, sampler2D channel) {
    vec3 sum = vec3(0.0);
    float total = 0.0;
    for (int i = -4; i <= 4; i++) {
        for (int j = -4; j <= 4; j++) {
            vec2 offset = vec2(float(i), float(j)) * radius / u_resolution.xy;
            float w = 1.0 - length(vec2(float(i), float(j))) / 6.0;
            w = max(w, 0.0);
            sum += texture(channel, uv + offset).rgb * w;
            total += w;
        }
    }
    return sum / max(total, 0.001);
}
```
- `radius`: blur spread in pixels (2.0–16.0)
- Note: 9×9 kernel = 81 samples, keep radius moderate for performance

### Parallax / offset sampling
```glsl
vec2 distortedUV = uv + vec2(noise * 0.02, 0.0);
vec4 texColor = texture(iChannel0, distortedUV);
```
- Use for: glass refraction, heat distortion, water surface

### Mipmap LOD for blur
```glsl
// Hardware-accelerated blur via LOD bias
vec4 blurred = texture(iChannel0, uv, lod_bias);
```
- `lod_bias`: 0.0 = sharp, higher = blurrier
- Performance: single sample, hardware-accelerated
- Use when quality isn't critical (subtle blur)

## Texture + Procedural Mix

### Blended approach (recommended)
```glsl
vec3 texSample = texture(iChannel0, uv).rgb;
float procedural = perlinNoise(uv * 8.0);
vec3 color = mix(texSample, vec3(procedural), blend_factor);
```
- `blend_factor`: 0.0 = pure texture, 1.0 = pure procedural
- Use for: adding noise/grain to sampled textures

### Tinted backdrop
```glsl
vec3 backdrop = texture(iChannel0, uv).rgb;
vec3 tint = vec3(0.8, 0.9, 1.0); // cool tint
vec3 color = backdrop * tint;
```

## Constraints

- Always check if channel is available: wrap texture calls in `#ifdef` or runtime checks
- Maximum texture samples per fragment: 16 (budget for performance)
- Prefer procedural noise over texture when possible — zero memory, infinite resolution
- For backdrop blur: prefer mipmap LOD over multi-sample when quality allows