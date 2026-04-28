# Shader Templates Reference

Each template is a complete effect skeleton. Customize parameters based on the visual description.

## Template: Basic Gradient
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    vec3 colA = vec3(0.1, 0.1, 0.18); // top color
    vec3 colB = vec3(0.06, 0.2, 0.38); // bottom color
    vec3 col = mix(colB, colA, uv.y); // linear vertical
    // For radial: float d = length(uv - 0.5); col = mix(colA, colB, d * 2.0);
    // For angular: float a = atan(uv.y-0.5, uv.x-0.5); col = mix(colA, colB, (a/6.28+0.5));
    fragColor = vec4(col, 1.0);
}
```

## Template: Ripple
```glsl
float sdCircle(vec2 p, float r) { return length(p) - r; }

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    vec2 center = u_mouse / u_resolution.xy;
    float t = u_time;

    float speed = 0.8;
    float wavelength = 0.05;
    float decay = 3.0;

    vec2 p = uv - center;
    float dist = length(p);
    float wave = sin((dist - t * speed) / wavelength * 6.2832);
    float attenuation = exp(-dist * decay) * exp(-fract(t * 0.3) * 2.0);
    float ripple = wave * attenuation;

    vec3 baseColor = vec3(0.1, 0.3, 0.6);
    vec3 rippleColor = vec3(0.4, 0.7, 1.0);
    vec3 col = mix(baseColor, rippleColor, ripple * 0.5 + 0.5);
    fragColor = vec4(col, 1.0);
}
```
- Customizable: speed, wavelength, decay, baseColor, rippleColor

## Template: Frosted Glass (with backdrop texture)
```glsl
vec3 backdropBlur(vec2 uv, float radius) {
    vec3 sum = vec3(0.0);
    float total = 0.0;
    for (int i = -4; i <= 4; i++) {
        for (int j = -4; j <= 4; j++) {
            vec2 offset = vec2(float(i), float(j)) * radius / u_resolution.xy;
            float w = 1.0 - length(vec2(float(i), float(j))) / 6.0;
            w = max(w, 0.0);
            sum += texture(iChannel0, uv + offset).rgb * w;
            total += w;
        }
    }
    return sum / max(total, 0.001);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    vec3 blurred = backdropBlur(uv, 4.0);
    float noise = 0.5 + 0.5 * perlinNoise(uv * 20.0 + u_time * 0.1);
    vec3 col = blurred * (0.85 + 0.15 * noise);
    col += vec3(0.8, 0.85, 0.95) * 0.08; // cool tint
    fragColor = vec4(col, 0.92);
}
```
- Requires: iChannel0 (backdrop texture)
- Customizable: blur radius, noise scale, tint color, opacity

## Template: Aurora
```glsl
float perlinNoise(vec2 p) { /* see noise-operators */ }
float fbm(vec2 p) { float v=0.0; float a=0.5; for(int i=0;i<5;i++){v+=a*perlinNoise(p);p*=2.0;a*=0.5;} return v; }

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    float t = u_time * 0.3;

    float n1 = fbm(vec2(uv.x * 3.0 + t, uv.y * 2.0 + t * 0.5));
    float n2 = fbm(vec2(uv.x * 2.0 - t * 0.7, uv.y * 3.0));

    vec3 col1 = vec3(0.1, 0.8, 0.4); // green
    vec3 col2 = vec3(0.2, 0.4, 0.9); // blue
    vec3 col3 = vec3(0.7, 0.2, 0.8); // purple

    float band = smoothstep(0.3, 0.7, uv.y + n1 * 0.3);
    vec3 col = mix(col1, col2, band);
    col = mix(col, col3, smoothstep(0.5, 0.8, n2));

    col *= smoothstep(0.0, 0.3, uv.y) * smoothstep(1.0, 0.5, uv.y);
    col *= 0.7 + 0.3 * sin(t * 2.0 + uv.x * 6.28);

    fragColor = vec4(col, 1.0);
}
```
- Customizable: color bands, flow speed, vertical distribution

## Template: Glow Pulse
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / u_resolution.xy;
    vec2 center = vec2(0.5);
    float dist = length(uv - center);

    float pulse = 0.5 + 0.5 * sin(u_time * 2.0); // breathing
    float glow = exp(-dist * (4.0 + 2.0 * pulse));

    vec3 glowColor = vec3(0.3, 0.6, 1.0);
    vec3 baseColor = vec3(0.02, 0.02, 0.05);

    vec3 col = baseColor + glowColor * glow * (0.5 + 0.5 * pulse);
    fragColor = vec4(col, 1.0);
}
```
- Customizable: pulse speed, glow radius, glow color, base color