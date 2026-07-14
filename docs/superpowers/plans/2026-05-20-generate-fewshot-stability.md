# Generate Agent Few-Shot 稳定性优化

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 Generate Agent 的 system prompt 添加端到端 few-shot 示例（visual_description JSON → 完整 GLSL shader），降低代码生成的方差，提升单次生成质量

**Architecture:** 在 `generate_system.md` 中新增 `## 端到端示例` 章节，覆盖 9 种 effect type，每种提供 1 个完整的 "输入 → 输出" 示例。示例代码必须是**可直接编译运行的完整 GLSL**，包含所有 helper 函数定义

**Tech Stack:** Markdown prompt editing, GLSL shader code

**数据依据：**
- A/B 测试证明更多结构化数据无效（9/16 样本受损）
- V2 vs A/B 对比：同一样本分数波动 ±0.4~0.81（Generate 不稳定）
- 简单效果稳定（渐变/形状），复杂效果灾难性失败（极光/粒子/域扭曲）
- 当前 system prompt 有 1447 行指令但 **0 个端到端示例**

---

## 设计原则

1. **示例即规格说明** — 每个示例展示了该 effect type 的标准代码结构、参数使用方式、SDF 选择、颜色处理
2. **代码必须自包含** — 所有 helper 函数（sdCircle, FBM, hash 等）内联在示例中，不依赖外部引用
3. **输入用典型 visual_description** — 示例输入贴近真实 Decompose 输出格式
4. **不增加 prompt 长度** — 用示例替换部分冗长的指令性文字，净增 ≤200 行

---

## File Structure

```
修改文件：
└── backend/app/prompts/generate_system.md    # 新增 few-shot 章节
```

---

### Task 1: 添加 few-shot 章节框架

**Files:**
- Modify: `backend/app/prompts/generate_system.md`

**目标:** 在 `## Glow/Bloom 强度规范` 章节之前插入 few-shot 章节框架

- [ ] **Step 1: 在 generate_system.md 的第 202 行之前（Glow/Bloom 章节）插入 few-shot 章节标题和说明**

在第 202 行 `## Glow/Bloom 强度规范（强制）` 之前插入：

```markdown
## 端到端示例（Few-shot Reference）

> 以下示例展示了每种 effect_type 的标准实现方式。
> 当你收到 visual_description 时，**优先参考对应 effect_type 的示例代码结构**。
> 注意观察：SDF 选择、fill_type 处理、颜色映射、动画驱动、背景处理。

---

### 示例 1: effect.glow — 发光圆形（shiny-circle 类效果）

**输入 (visual_description):**
```json
{
  "effect_type": "{effect.glow}",
  "shape_definition": {
    "sdf_type": "{sdf.circle}",
    "center": "(0.5, 0.5)",
    "size": "0.2",
    "fill_type": "{fill.hollow}",
    "edge_width": "0.01"
  },
  "color_definition": {
    "primary_rgb": "(0.6, 0.3, 1.0)",
    "secondary_rgb": "(0.3, 0.5, 1.0)",
    "glow_intensity": "high"
  },
  "animation_definition": {
    "animation_type": "none"
  },
  "background_definition": {
    "color_rgb": "(0.0, 0.0, 0.0)",
    "strict": true
  }
}
```

**输出 (GLSL):**

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

**关键学习点:**
- hollow 形状用 `abs(d) - thickness`
- 多层 glow 叠加：core(30) + mid(8) + outer(2.5)，强度递减
- glow intensity 总和 >= 2.0，确保边缘处 (d≈0) 明亮可见
- 纯黑背景 `vec3(0.0)`，strict=true

---

### 示例 2: effect.gradient — 多色渐变（4-col-grad 类效果）

**输入 (visual_description):**
```json
{
  "effect_type": "{effect.gradient}",
  "shape_definition": {
    "sdf_type": "none"
  },
  "color_definition": {
    "primary_rgb": "(0.2, 0.8, 0.4)",
    "secondary_rgb": "(0.9, 0.3, 0.2)",
    "gradient_direction": "radial",
    "gradient_smoothness": "smooth"
  },
  "animation_definition": {
    "animation_type": "none"
  },
  "background_definition": {
    "color_rgb": "fullscreen"
  }
}
```

**输出 (GLSL):**

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

**关键学习点:**
- fullscreen 效果无 SDF，直接操作 UV
- 多色 stop 用多个 `smoothstep + mix` 链式叠加
- smoothstep 确保颜色过渡无断层

---

### 示例 3: effect.shape — 实心心形（heart-2d 类效果）

**输入 (visual_description):**
```json
{
  "effect_type": "{effect.shape}",
  "shape_definition": {
    "sdf_type": "{sdf.heart}",
    "center": "(0.5, 0.5)",
    "size": "0.15",
    "fill_type": "{fill.solid}",
    "edge_width": "0.02"
  },
  "color_definition": {
    "primary_rgb": "(0.9, 0.2, 0.2)",
    "gradient_direction": "linear",
    "gradient_smoothness": "smooth"
  },
  "animation_definition": {
    "animation_type": "none"
  },
  "background_definition": {
    "color_rgb": "(0.95, 0.9, 0.85)",
    "strict": true
  }
}
```

**输出 (GLSL):**

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

**关键学习点:**
- 实心形状用 `d` 不用 `abs(d)`（`abs(d)` 会变成空心轮廓）
- `exp(-max(d, 0.0) * intensity)` — 仅向外发光
- 内部渐变用 `uv.y` 或 `dot(uv - center, direction)` 实现方向性
- strict 背景颜色必须精确匹配

---

### 示例 4: effect.ripple — 同心圆涟漪（hypnotic-ripples 类效果）

**输入 (visual_description):**
```json
{
  "effect_type": "{effect.ripple}",
  "shape_definition": {
    "sdf_type": "none",
    "center": "(0.5, 0.5)"
  },
  "color_definition": {
    "primary_rgb": "(0.0, 0.8, 0.8)",
    "secondary_rgb": "(0.8, 0.2, 0.6)",
    "gradient_direction": "radial"
  },
  "animation_definition": {
    "animation_type": "expand",
    "duration": "loop",
    "speed": "medium"
  },
  "background_definition": {
    "color_rgb": "(0.02, 0.02, 0.05)"
  }
}
```

**输出 (GLSL):**

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

**关键学习点:**
- 同心圆用 `sin(distance * frequency + time)` 实现
- `exp(-d * decay)` 控制衰减
- 颜色随距离渐变用 `mix(col1, col2, distance)`
- 动画用 `iTime * speed` 驱动

---

### 示例 5: effect.flow — 有机流动纹理（vortex-street 类效果）

**输入 (visual_description):**
```json
{
  "effect_type": "{effect.flow}",
  "shape_definition": {
    "sdf_type": "none"
  },
  "color_definition": {
    "primary_rgb": "(0.15, 0.2, 0.6)",
    "secondary_rgb": "(0.7, 0.75, 1.0)",
    "gradient_direction": "organic"
  },
  "animation_definition": {
    "animation_type": "flow",
    "speed": "slow"
  },
  "background_definition": {
    "color_rgb": "(0.05, 0.05, 0.15)"
  }
}
```

**输出 (GLSL):**

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

**关键学习点:**
- FBM 自包含（hash → noise → fbm），所有函数内联
- 两级 domain warping: q → r → f
- 多层颜色 mix 增加深度感
- FBM octaves=4（符合 Mobile ≤256 ALU 约束）

---

### 示例 6: effect.particle — 发光粒子（happy-diwali 类效果）

**输入 (visual_description):**
```json
{
  "effect_type": "{effect.particle}",
  "shape_definition": {
    "sdf_type": "none"
  },
  "color_definition": {
    "primary_rgb": "(0.2, 0.7, 1.0)",
    "secondary_rgb": "(0.9, 0.3, 0.7)",
    "tertiary_rgb": "(0.9, 0.8, 0.2)"
  },
  "animation_definition": {
    "animation_type": "float",
    "speed": "slow"
  },
  "background_definition": {
    "color_rgb": "(0.02, 0.02, 0.06)"
  }
}
```

**输出 (GLSL):**

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

**关键学习点:**
- hash grid 创建粒子位置
- `exp(-d²/size²)` 做柔和圆形粒子
- flicker 用 `sin(time * freq + phase)` 实现
- 颜色按 hash 分配
- intensity >= 1.0 确保粒子明亮

---

### 示例 7: effect.warp — 域扭曲视错觉（moon-distance 类效果）

**输入 (visual_description):**
```json
{
  "effect_type": "{effect.warp}",
  "shape_definition": {
    "sdf_type": "{sdf.circle}",
    "center": "(0.5, 0.5)",
    "size": "0.15",
    "fill_type": "{fill.solid}"
  },
  "color_definition": {
    "primary_rgb": "(0.3, 0.5, 0.8)",
    "secondary_rgb": "(0.9, 0.6, 0.2)",
    "gradient_direction": "concentric"
  },
  "animation_definition": {
    "animation_type": "none"
  },
  "background_definition": {
    "color_rgb": "(0.1, 0.1, 0.15)"
  }
}
```

**输出 (GLSL):**

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

**关键学习点:**
- 线条用 `sin(distance * frequency)` 生成
- 形状附近的域扭曲强度用 `exp(-abs(shape_d) * decay)` 衰减
- 扭曲后重新计算线条距离
- 形状填充 + 线条背景的组合

---

### 示例 8: effect.liquid — 液态玻璃（liquid-glass-ui 类效果）

**输入 (visual_description):**
```json
{
  "effect_type": "{effect.liquid}",
  "shape_definition": {
    "sdf_type": "{sdf.circle}",
    "center": "(0.4, 0.5)",
    "size": "0.2",
    "fill_type": "{fill.solid}"
  },
  "color_definition": {
    "primary_rgb": "(0.5, 0.7, 0.9)",
    "glow_intensity": "medium"
  },
  "animation_definition": {
    "animation_type": "flow",
    "speed": "slow"
  },
  "background_definition": {
    "color_rgb": "(0.03, 0.03, 0.08)"
  }
}
```

**输出 (GLSL):**

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

**关键学习点:**
- 液态玻璃核心：`fill * alpha`（0.3-0.6 半透明）+ `mix(bg, tint, alpha)`
- 折射偏移：FBM * 0.02-0.05 微妙偏移
- 菲涅尔高光：`pow(1.0 - smoothstep(...), 3.0)`
- 背景在折射偏移后采样

---

### 示例 9: effect.frosted — 磨砂玻璃（supah-frosted-glass 类效果）

**输入 (visual_description):**
```json
{
  "effect_type": "{effect.frosted}",
  "shape_definition": {
    "sdf_type": "none"
  },
  "color_definition": {
    "primary_rgb": "(0.7, 0.4, 0.9)",
    "secondary_rgb": "(0.2, 0.7, 0.7)",
    "gradient_direction": "radial",
    "gradient_smoothness": "soft"
  },
  "animation_definition": {
    "animation_type": "none"
  },
  "background_definition": {
    "color_rgb": "(0.92, 0.92, 0.92)"
  }
}
```

**输出 (GLSL):**

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

**关键学习点:**
- 磨砂效果：噪声叠加 `noise(uv * scale) * amplitude` 打破均匀感
- 半透明覆盖：`mix(bg, color, mask * 0.5)` alpha < 1
- 多层叠加：底层不透明 + 上层半透明
- 浅色背景精确匹配 `vec3(0.92)`
```

- [ ] **Step 2: 验证章节结构完整**

```bash
cd backend && python -c "
from app.services.context_assembler import load_prompt
p = load_prompt('generate_system')
examples = [f'示例 {i}' for i in range(1, 10)]
for e in examples:
    found = e in p
    print(f'  {e}: {\"✅\" if found else \"❌\"}  ')
print()
print(f'generate_system.md total lines: {len(p.splitlines())}')
"
```

Expected: 全部 ✅，总行数 ≤750

- [ ] **Step 3: 提交**

```bash
git add backend/app/prompts/generate_system.md
git commit -m "feat: add 9 few-shot examples to Generate Agent system prompt"
```

---

### Task 2: 清理冗余指令，控制 prompt 总长度

**Files:**
- Modify: `backend/app/prompts/generate_system.md`

**目标:** 新增 ~200 行示例后，删减冗余/重复的指令性文字，保持 prompt 总长度 ≤750 行

**可精简的区域（按优先级）：**

1. **反例 3（背景颜色偏差）** — 与示例中的 background 处理重复，可缩短为 2 行提示
2. **反例 4（机械调整参数）** — 与 few-shot 示例中的参数使用方式重复，可缩短
3. **自然语言描述解析** — 表格信息已被 few-shot 示例覆盖，可精简为 "参考 few-shot 示例中的实现方式"
4. **自检清单** — 与 Self-check 步骤重复，可合并

**原则：不删除任何唯一信息，只删除被 few-shot 示例更好地传达的内容。**

- [ ] **Step 1: 精简反例 3 和反例 4**

将反例 3 从 ~20 行缩减到 5 行：
```markdown
### ❌ 问题案例 3：背景颜色偏差（违反 strict 约束）
背景 RGB 必须精确匹配 `background_definition.color_rgb`，误差 <0.05。strict=true 时评分权重加倍。
❌ `vec3(0.95, 0.95, 0.95)` — 偏灰  ✅ `vec3(1.0, 1.0, 1.0)` — 纯白
```

将反例 4 从 ~15 行缩减到 5 行：
```markdown
### ❌ 问题案例 4：机械调整参数（不理解反馈意图）
Inspect 反馈"边缘过于锐利"时，应理解视觉意图选择合适宽度（0.02-0.05），而非机械增大 smoothstep。
```

- [ ] **Step 2: 精简"自然语言描述解析"章节**

将表格部分精简为引用 few-shot 示例：
```markdown
## 自然语言描述解析

> 参考"端到端示例"中各 effect_type 的实现方式。
> 关键映射关系已在示例代码中体现，此处仅列核心规则：

**fill_type → 实心 vs 空心（Critical！）**
[保留现有的 fill_type 对比表和常见错误代码块 — 这是唯一没被示例覆盖的关键信息]
```

- [ ] **Step 3: 验证总长度**

```bash
cd backend && python -c "
from app.services.context_assembler import load_prompt
p = load_prompt('generate_system')
print(f'Total lines: {len(p.splitlines())}')
# 所有关键内容仍然存在
checks = ['Few-shot', '示例 1', '示例 5', 'fill_type', 'abs(d)', 'Glow/Bloom', 'Self-check']
for c in checks:
    print(f'  {c}: {\"✅\" if c in p else \"❌\"}  ')
"
```

Expected: 总行数 ≤750，所有 checks ✅

- [ ] **Step 4: 提交**

```bash
git add backend/app/prompts/generate_system.md
git commit -m "refactor: trim redundant instructions in generate_system, net length under 750 lines"
```

---

### Task 3: 更新 generate_system.md 中 Step 1 的 Effect Type 表

**Files:**
- Modify: `backend/app/prompts/generate_system.md`

**目标:** 当前 Step 1 只列了 5 种 effect type，补全到 9 种

- [ ] **Step 1: 替换 Step 1 的表格**

将现有 5 行表格替换为 9 行：

```markdown
| Effect Type | Primary Technique | Few-shot 示例 |
|-------------|-------------------|--------------|
| `ripple` | sdCircle + sin(distance) expansion | 示例 4 |
| `glow` | exp(-abs(d) * intensity) multi-layer | 示例 1 |
| `gradient` | mix(c1, c2, t) + multi-stop | 示例 2 |
| `frosted` | noise + blur + alpha blend | 示例 9 |
| `flow` | FBM + domain warping | 示例 5 |
| `liquid` | alpha blend + refraction + fresnel | 示例 8 |
| `particle` | hash grid + point glow + flicker | 示例 6 |
| `warp` | domain warping + concentric lines | 示例 7 |
| `shape` | SDF + solid fill + edge glow | 示例 3 |
```

- [ ] **Step 2: 验证**

```bash
cd backend && python -c "
from app.services.context_assembler import load_prompt
p = load_prompt('generate_system')
types = ['ripple','glow','gradient','frosted','flow','liquid','particle','warp','shape']
for t in types:
    print(f'  {t}: {\"✅\" if t in p else \"❌\"}  ')
"
```

Expected: 全部 ✅

- [ ] **Step 3: 提交**

```bash
git add backend/app/prompts/generate_system.md
git commit -m "fix: expand Step 1 effect type table from 5 to 9, link to few-shot examples"
```

---

### Task 4: 快速冒烟测试

**目标:** 用 3 个样本快速验证 few-shot 是否改善 Generate 稳定性

- [ ] **Step 1: 重启后端（加载新 prompt）**

```bash
# 如果后端在运行，重启
./start.sh stop && ./start.sh start
```

- [ ] **Step 2: 跑 3 个样本（选 V2 中中低分、波动大的）**

```bash
cd backend && python -c "
import json, time, httpx, subprocess
from pathlib import Path

BACKEND = 'http://localhost:8000'
SAMPLES_DIR = Path('../test-samples')

samples = ['vortex-street', 'plasma-waves', 'heart-2d']

for name in samples:
    vp = SAMPLES_DIR / f'{name}.webm'
    with open(vp, 'rb') as f:
        resp = httpx.post(f'{BACKEND}/pipeline/run',
            files={'video': (f'{name}.webm', f, 'video/webm')},
            data={'max_iterations': '1', 'passing_threshold': '0.85'},
            timeout=30)
    pid = resp.json()['pipeline_id']
    print(f'{name}: {pid}')

    start = time.time()
    while time.time() - start < 300:
        try:
            s = httpx.get(f'{BACKEND}/pipeline/status/{pid}', timeout=10).json()
        except:
            time.sleep(3); continue
        status = s.get('status', 'running')
        if status not in ('running',):
            ifb = s.get('snapshot', {}).get('inspect_feedback') or {}
            print(f'  >>> score={ifb.get(\"overall_score\",0):.2f}  status={status}  {time.time()-start:.0f}s')
            break
        time.sleep(3)
"
```

- [ ] **Step 3: 对比**

| 样本 | V2 基线 | A/B NO_CV | 本次 | 判断 |
|------|---------|-----------|------|------|
| vortex-street | 0.81 | 0.00 | ? | 应该显著改善 |
| plasma-waves | 0.83 | 0.18 | ? | 应该显著改善 |
| heart-2d | 0.78 | 0.74 | ? | 应该稳定或改善 |

**通过标准**: 3 个样本中至少 2 个 ≥ V2 基线 - 0.10

---

## Summary

| Task | Priority | 修改文件 | 预期影响 |
|------|----------|----------|----------|
| Task 1: 添加 9 个 few-shot 示例 | P0 | generate_system.md | 核心改动：补齐端到端示例 |
| Task 2: 精简冗余指令 | P1 | generate_system.md | 控制 prompt 长度 ≤750 行 |
| Task 3: 补全 Step 1 表格 | P1 | generate_system.md | 从 5→9 种 effect type |
| Task 4: 冒烟测试 | P0 | (运行测试) | 验证改善效果 |

**执行顺序**: Task 1 → 2 → 3 → 4
**预计耗时**: Task 1-3 约 20 分钟（纯 prompt 修改），Task 4 约 15 分钟（3 样本重跑）
