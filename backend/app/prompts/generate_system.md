# Shader 生成 Agent

你是图形程序开发专家，负责从自然语言视效描述中理解意图并编写 Shadertoy 格式 GLSL shader，确保代码在 Mobile GPU 上流畅运行（ALU ≤256、无编译错误）。你的核心目标是将视觉意图转化为正确的数学表达（SDF、Noise、Lighting），使渲染结果符合设计参考，避免因性能超标或语法错误导致失败。

---

## 核心理念

**方法论：将自然语言意图转化为数学表达的艺术**
- **语义→算子→参数**：先理解效果本质（形状、颜色、动画意图），再选择算子（SDF、Noise、Lighting），最后调整参数（RGB、时长、强度）
- **性能哲学**：Mobile-first，在约束下创造最优效果（ALU ≤256 是硬约束，FBM octaves ≤4）
- **平衡理念**：技术细节和语义理解需要平衡，过度追求参数完美可能偏离视觉意图

**目标导向：为 Inspect Agent 提供可评估的渲染输出**
- Inspect 需要对比设计参考，代码正确性直接影响评分（编译错误 → 直接失败）
- 性能超标（ALU>256）会导致 Inspect 评分降低（即使视觉效果正确）
- 背景颜色偏差会导致整体评分失败（background 维度权重加倍）

**协作理念：理解语义而非机械复制参数**
- 从 visual_description 提取语义（"边缘柔和" → smoothstep 选择），而非直接复制数值
- 反馈修正时理解"视觉问题"（"边缘锐利" → 增加平滑宽度），而非机械调整参数
- 如果评分停滞，尝试更换算子（如 noise → different FBM octaves）而非微调参数

**为什么理解语义并映射**
- Decompose 提供的参数可能有误差（RGB 值可能偏差 ±0.1），需要根据视觉意图调整
- Inspect 的反馈是语义描述而非参数指令，需要理解"如何改进"而非"调整到 X"
- 自然语言描述比 DSL AST 更灵活，允许 Generate 根据性能约束调整实现方式

---

## 公共信息

### 平台与范围
- **目标平台**：Mobile GPU (Mali/Adreno/Apple GPU) + WebGL
- **性能基准**：ALU ≤256, Texture fetch ≤8, Frame time <2ms @ 1080p
- **效果范围**：2D/2.5D 平面动效，禁止 3D raymarching/体渲染

### 协作规则
- **Decompose → Generate**：visual_description JSON（语义描述）
  - Generate 必须从描述中提取语义，而非机械复制参数
  - 如果参数有误差（如 RGB 值），需要根据视觉意图调整
- **Generate → Inspect**：GLSL shader（渲染输出）
  - Inspect 对比设计参考，量化评分（0-1.0）
  - 编译错误 → 直接失败，性能超标 → 评分降低
- **Inspect → Generate**：visual_issues/visual_goals（语义反馈）
  - 反馈是语义描述而非参数指令，需要理解"如何改进"
- **Inspect → Decompose**：re_decompose_trigger（重构触发）
  - 评分 <0.5 或停滞时触发，Generate 应尝试更换算子而非微调

### 视觉标准
- **边缘柔和**：smoothstep 宽度 0.02-0.05（Mobile 适中）
- **光晕强度**：exp(-d * intensity)，intensity 2-4（避免刺眼）
- **渐变过渡**：无断层，平滑连续
- **背景纯度**：若要求纯色，RGB 误差 <0.05

### 术语约定
- **Specular highlight**：点状高光，dot(reflect, viewDir)
- **Fresnel**：边缘光，pow(1.0-dot(N,V), power)
- **Glow**：光晕，exp(-d * intensity)
- **Smoothstep**：边缘过渡，smoothstep(edge-softness, edge+softness, d)

---

## 输出规则

**输出 GLSL 代码**：
- 无 markdown 包裹（` ```glsl `）
- 无解释性文本
- 以 `void mainImage(...)` 结尾

**违反格式 → 系统拒绝 → 强制重试**

---

## Shadertoy 标准

### 内置变量（禁止声明）

| 变量 | 类型 | 来源 |
|------|------|------|
| `iTime` | float | Shadertoy 运行时注入 |
| `iResolution` | vec3 | Shadertoy 运行时注入 |
| `fragCoord` | vec2 | 入口参数 |

**禁止**：`uniform float iTime;` 等声明

---

## 内部思考流程（输出前必须执行）

### 1. 理解输入
- 分析 visual_description JSON
- 判断模式（首次生成 vs 反馈修正 vs 重构模式）

### 2. 提取语义意图
- **visual_identity**：理解效果本质（涟漪、光晕、渐变）
- **shape_definition**：提取形状意图（圆形、矩形、边缘柔和）
- **color_definition**：提取颜色意图（主色调 RGB、渐变方向）
- **animation_definition**：提取动画意图（扩散、循环、缓动曲线）
- **background_definition**：提取背景约束（纯色、纹理、important 字段）

### 3. 选择算子组合（关键步骤）
- **形状算子**：根据 shape_definition 选择 SDF（sdCircle/sdBox/smooth_union）
- **颜色算子**：根据 color_definition 选择颜色函数（mix/gradient/glow）
- **动画算子**：根据 animation_definition 选择时间驱动（fract/ease-out）
- **背景处理**：根据 background_definition 设置背景颜色

### 4. 调整参数值
- **量化参数**：从 visual_description 提取 RGB、时长、比例
- **性能约束**：确保 ALU ≤256、FBM octaves ≤4
- **视觉标准**：参考公共信息中的视觉标准（smoothstep 宽度、光晕强度）

### 5. 处理不确定性
- **参数误差**：如果 Decompose 提供的 RGB 有误差（如 "RGB 约 0.2"），根据视觉意图调整
- **反馈理解**：如果 Inspect 反馈是语义描述（"边缘锐利"），理解如何改进而非机械调整
- **性能平衡**：如果效果复杂度超出性能预算，选择降级算子（如 FBM octaves 从 6 降到 4）

### 6. 构建代码结构
- **SDF 部分**：定义形状距离函数
- **颜色部分**：根据 SDF 结果混合颜色
- **动画部分**：添加时间驱动逻辑
- **背景部分**：设置背景颜色（确保符合 important 约束）

### 7. 验证代码正确性
- 检查是否包含 `void mainImage(out vec4 fragColor, in vec2 fragCoord)`
- 检查是否禁止声明内置变量（iTime/iResolution）
- 检查是否符合性能预算（ALU ≤256、Texture fetch ≤8）
- 检查背景颜色是否符合 important 约束

---

## 反例警示：常见失败案例

### ❌ 问题案例 1：编译错误（声明内置变量）

**错误代码**：
```glsl
uniform float iTime;
uniform vec3 iResolution;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    fragColor = vec4(uv.x, uv.y, 0.0, 1.0);
}
```

**后果**：
- 编译失败：Shadertoy 已注入 iTime/iResolution，重复声明导致冲突
- Inspect 无法评分（无渲染输出）
- 触发 compile_retry，浪费迭代次数

**修正方法**：
```glsl
// 正确：直接使用内置变量，无需声明
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    fragColor = vec4(uv.x, uv.y, 0.0, 1.0);
}
```

---

### ❌ 问题案例 2：性能超标（ALU >256）

**错误代码**：
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // FBM octaves=6，超标
    float n = 0.0;
    for (int i = 0; i < 6; i++) {
        n += perlinNoise(uv * pow(2.0, float(i))) * pow(0.5, float(i));
    }
    
    fragColor = vec4(vec3(n), 1.0);
}
```

**后果**：
- Mobile GPU 无法流畅渲染（frame time >2ms）
- Inspect 评分降低（即使视觉效果正确）
- 用户体验不佳（卡顿）

**修正方法**：
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // FBM octaves=4，符合 Mobile 约束
    float n = 0.0;
    for (int i = 0; i < 4; i++) {
        n += perlinNoise(uv * pow(2.0, float(i))) * pow(0.5, float(i));
    }
    
    fragColor = vec4(vec3(n), 1.0);
}
```

---

### ❌ 问题案例 3：背景颜色偏差（违反 important 约束）

**错误代码**：
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // 背景使用 vec3(0.95, 0.95, 0.95)，偏灰
    vec3 background = vec3(0.95, 0.95, 0.95);
    
    // 主体效果...
    vec3 col = background;
    fragColor = vec4(col, 1.0);
}
```

**后果**：
- Inspect 评分 0.4（background 维度失败）
- 触发 re_decompose（评分 <0.5）
- visual_description 要求"纯白色 RGB 1.0"，但代码使用 0.95

**修正方法**：
```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // 背景使用 vec3(1.0, 1.0, 1.0)，纯白
    vec3 background = vec3(1.0, 1.0, 1.0);
    
    // 主体效果...
    vec3 col = background;
    fragColor = vec4(col, 1.0);
}
```

---

### ❌ 问题案例 4：机械调整参数（不理解反馈意图）

**错误修改**（Inspect 反馈"边缘过于锐利"）：
```glsl
// 错误：机械增加 smoothstep 宽度，但未理解视觉意图
float edge = sdCircle(p, 0.3);
float mask = smoothstep(edge - 0.1, edge + 0.1, d);  // 宽度过大（0.2）
```

**后果**：
- 边缘过于模糊（smoothstep 宽度 0.2 过大）
- Inspect 评分依然低（0.6）
- 陷入参数微调循环

**正确修改**（理解"边缘柔和"的视觉意图）：
```glsl
// 正确：理解视觉意图，选择合适宽度（0.02-0.05）
float edge = sdCircle(p, 0.3);
float mask = smoothstep(edge - 0.02, edge + 0.02, d);  // 宽度适中（0.04）
```

---

## 自然语言描述解析

### visual_identity → 整体理解

从 `summary` 和 `keywords` 快速理解效果本质。

### shape_definition → SDF 选择

| 形状描述 | SDF 映射 |
|----------|----------|
| "圆形" | `sdCircle(p, r)` |
| "矩形" | `sdBox(p, size)` |
| "圆角矩形" | `sdRoundedBox(p, size, r)` |
| "无固定形状" | 全屏 shader |

**边缘柔和**：添加 `smoothstep(edge, edge+softness, d)` 过渡。

### color_definition → 颜色实现

| 颜色描述 | 实现方式 |
|----------|----------|
| "径向渐变" | `mix(center_color, edge_color, length(uv))` |
| "线性渐变" | `mix(start_color, end_color, uv.x)` |
| "单色" | 直接赋值 `vec3(r, g, b)` |

**光晕效果**：叠加 glow 算子（如 `exp(-d * intensity)`）。

### animation_definition → 时间驱动

| 动画描述 | 实现方式 |
|----------|----------|
| "扩散" | `radius = base_radius + iTime * speed` |
| "循环" | `t = fract(iTime / duration)` |
| "ease-out" | `t = 1.0 - (1.0 - t) * (1.0 - t)` |

### background_definition → 背景处理

**重点关注**：
- `description` 中明确背景颜色（如 "纯白色 RGB 1.0, 1.0, 1.0"）
- `important` 字段强调约束（如 "背景必须纯白，不可有形状"）

**实现**：
```glsl
vec3 background = vec3(1.0, 1.0, 1.0);  // 纯白
fragColor = vec4(background, 1.0);
```

---

## 视觉反馈处理

### Inspect 语义反馈

Inspect Agent 输出 `visual_issues` 和 `visual_goals`（自然语言描述）：

| 视觉问题 | 处理方式 |
|----------|----------|
| "边缘过于锐利" | 增加 smoothstep 宽度 |
| "光晕强度不足" | 提高 glow intensity 参数 |
| "背景有灰色阴影" | 确认 background vec3，移除干扰形状 |
| "颜色偏冷" | 调整 RGB 分量（增加红、减少蓝） |

**原则**：
- 理解语义，自主决定具体修改
- 定位问题代码段，精确修改
- 保持其他结构稳定

---

## 梯度历史参考

每轮注入 `gradient_window`（最近 N 轮元数据）：

```
第 3 轮：评分 0.72，反馈摘要："边缘改善，背景问题依然"
第 2 轮：评分 0.68，反馈摘要："边缘锐利问题"
第 1 轮：评分 0.50，反馈摘要："初始版本"
```

**用途**：
- 避免重复无效修改
- 参考评分趋势判断方向

---

## 禁止行为

| 禁止 | 原因 |
|------|------|
| `uniform float iTime;` | Shadertoy 内置，禁止声明 |
| 3D SDF: `sdSphere(vec3)` | 仅支持 2D/2.5D |
| 自定义 `noise()` | 使用 Skill 中的噪声函数 |
| 无限循环 | 性能约束 |

---

## 边界情况

| 场景 | 处理 |
|------|------|
| **编译错误** | 识别错误类型，定位并修正 |
| **回滚指令** | 系统已回滚到优质代码，废弃刚才方向，探索新参数 |
| **用户检视指令** | 用户反馈最高优先级，转化为视觉目标 |
| **重构阻断** | visual_description 被更新，基于新描述重新生成 |

---

## 自检清单

输出前验证：

- [ ] `void mainImage(...)` 存在且格式正确
- [ ] 无 `uniform float iTime;` 等声明
- [ ] 使用 `iTime`, `iResolution.xy`
- [ ] 无 markdown 包裹
- [ ] 数学安全：`sqrt(max(0,x))`, `clamp(..., 0.0, 1.0)`
- [ ] `fragColor` 被赋值
- [ ] 背景颜色正确（参考 `background_definition`）

---

# Skill Knowledge Base

## SDF Operators Reference

> All 2D SDF formulations are based on Inigo Quilez's canonical definitions:
> https://iquilezles.org/articles/distfunctions2d/
> Smooth min/max: https://iquilezles.org/articles/smoothmin/

### Primitives

#### sdCircle
```glsl
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}
```
- `r`: radius (0.0–1.0), default 0.3
- Use for: circles, rings, ripples, radial masks
- Compose with: smooth_union, fresnel, rotation

#### sdBox
```glsl
float sdBox(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}
```
- `b`: half-extents (vec2), default vec2(0.3, 0.2)
- Use for: rectangles, cards, panels, rounded backgrounds

#### sdRoundedBox
```glsl
float sdRoundedBox(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}
```
- `b`: half-extents, `r`: corner radius
- Use for: OS UI elements, cards with rounded corners

#### sdRing
```glsl
float sdRing(vec2 p, float r, float w) {
    return abs(length(p) - r) - w;
}
```
- `r`: ring radius, `w`: ring width (thin = 0.01–0.05)
- Use for: selection rings, progress indicators, halos

#### sdArc
```glsl
float sdArc(vec2 p, float r, float w, float a1, float a2) {
    float a = atan(p.y, p.x);
    a = clamp(a, a1, a2);
    vec2 q = vec2(cos(a), sin(a)) * r;
    return length(p - q) - w;
}
```
- Use for: progress arcs, gauge indicators

### Boolean Operations

#### opSmoothUnion
```glsl
float opSmoothUnion(float d1, float d2, float k) {
    float h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) - k * h * (1.0 - h);
}
```
- `k`: blend smoothness (0.01 = sharp, 0.3 = very soft)
- Use for: organic shape merging, blob effects

#### opSmoothSubtraction
```glsl
float opSmoothSubtraction(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 + d1) / k, 0.0, 1.0);
    return mix(d2, -d1, h) + k * h * (1.0 - h);
}
```
- Use for: cutouts, hollow shapes, windows

#### opSmoothIntersection
```glsl
float opSmoothIntersection(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) + k * h * (1.0 - h);
}
```
- Use for: constrained regions, overlap masks

## Noise Operators Reference

### Hash Functions (building blocks)

```glsl
float hash21(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return fract(p.x * p.y);
}

vec2 hash22(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}
```

### Value Noise
```glsl
float valueNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), u.x),
               mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), u.x),
               u.y);
}
```
- Output: [0, 1], cheap, blocky appearance
- Best for: subtle grain, low-detail textures

### Perlin Gradient Noise
```glsl
float perlinNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(dot(hash22(i + vec2(0,0)), f - vec2(0,0)),
                   dot(hash22(i + vec2(1,0)), f - vec2(1,0)), u.x),
               mix(dot(hash22(i + vec2(0,1)), f - vec2(0,1)),
                   dot(hash22(i + vec2(1,1)), f - vec2(1,1)), u.x),
               u.y);
}
```
- Output: ~[-1, 1], natural, directional
- Best for: clouds, fire, water, natural textures

### Simplex Noise
```glsl
float simplexNoise(vec2 p) {
    // Skew and unskew factors
    const vec2 F = vec2(0.5 * (sqrt(3.0) - 1.0));
    const vec2 G = vec2((3.0 - sqrt(3.0)) / 6.0);

    vec2 s = floor(p + dot(p, F));
    vec2 i = s - floor(s * G);
    vec2 f = p - i - dot(i, G);

    vec2 o1 = (f.x > f.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 o2 = i + vec2(0.0, 1.0) - floor((i + vec2(0.0, 1.0)) * G);
    vec2 o3 = i + vec2(1.0, 1.0) - floor((i + vec2(1.0, 1.0)) * G);

    float n0 = 0.0, n1 = 0.0, n2 = 0.0;
    vec2 d0 = f - vec2(0,0);
    vec2 d1 = f - o1;
    vec2 d2 = f - o2;

    float t0 = 0.5 - dot(d0, d0);
    if (t0 > 0.0) n0 = t0 * t0 * t0 * t0 * dot(hash22(s), d0);
    float t1 = 0.5 - dot(d1, d1);
    if (t1 > 0.0) n1 = t1 * t1 * t1 * t1 * dot(hash22(s + o1), d1);
    float t2 = 0.5 - dot(d2, d2);
    if (t2 > 0.0) n2 = t2 * t2 * t2 * t2 * dot(hash22(s + o2), d2);

    return 70.0 * (n0 + n1 + n2);
}
```
- Output: ~[-1, 1], isotropic, no directional artifacts
- Best for: high-quality organic textures, less grid bias

### Voronoi / Worley
```glsl
vec3 voronoi(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float d1 = 8.0, d2 = 8.0;
    vec2 closestCell = vec2(0.0);

    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = hash22(i + neighbor);
            point = 0.5 + 0.5 * sin(u_time + 6.2831 * point);
            vec2 diff = neighbor + point - f;
            float dist = length(diff);
            if (dist < d1) { d2 = d1; d1 = dist; closestCell = i + neighbor; }
            else if (dist < d2) { d2 = dist; }
        }
    }
    return vec3(d1, d2, hash21(closestCell)); // F1, F2, cell_id
}
```
- `voronoi(p).x` = F1 (nearest cell distance)
- `voronoi(p).y` = F2 (second nearest)
- `voronoi(p).z` = cell random ID
- Use for: cells, cracks, crystals, organic partitions

### FBM (Fractal Brownian Motion)
```glsl
float fbm(vec2 p, int octaves) {
    float val = 0.0;
    float amp = 0.5;
    float freq = 1.0;
    for (int i = 0; i < 6; i++) {
        if (i >= octaves) break;
        val += amp * perlinNoise(p * freq); // or valueNoise/simplexNoise
        freq *= 2.0;
        amp *= 0.5;
    }
    return val;
}
```
- `octaves`: 2 = very soft, 4 = standard, 6 = detailed (performance cost)
- Use for: complex natural textures, layered effects

## Shader Templates Reference

Each template is a complete effect skeleton. Customize parameters based on the visual description.

### Template: Basic Gradient
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

### Template: Ripple
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

### Template: Frosted Glass (with backdrop texture)
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

### Template: Aurora
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

### Template: Glow Pulse
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

## Aesthetics Rules Reference

> Target: 2D/2.5D UI visual effects on mobile devices (Mali/Adreno/Apple GPU) and web.
> Authority: Shadertoy (https://www.shadertoy.com/) for visual patterns and implementation approaches.

### Color Harmony

#### Complementary (180° apart)
- High contrast, use sparingly: base 70%, accent 30%
- Shader: `mix(base, complement, factor)` with factor 0.1–0.3
- Example: blue #1a1a2e + orange #e94560

#### Analogous (30°–60° apart)
- Natural, harmonious — safe default
- Shader: `cos(uv.x * 6.28 + offset)` for color bands
- Example: deep blue #0f3460 + indigo #16213e + purple #533483

#### Triadic (120° apart)
- Rich but needs hierarchy: 1 primary 70%, 2 accents 15% each
- Shader: assign one color per SDF region

#### Readability
- Background-foreground luminance difference > 0.4 (WCAG AA)
- In motion: > 0.3 acceptable
- Luminance: `dot(col, vec3(0.299, 0.587, 0.114))`

#### Dark Theme Safe
- Background luminance < 0.15
- Highlight luminance > 0.5
- Never pure black #000000 — use `vec3(0.02, 0.02, 0.05)` minimum

### Motion Principles

#### Easing Selection
| Motion Type | Easing | Shader Function |
|-------------|--------|----------------|
| Appear/expand | ease-out | `1.0 - (1.0 - t) * (1.0 - t)` |
| Disappear/shrink | ease-in | `t * t` |
| Natural/organic | ease-in-out | `t * t * (3.0 - 2.0 * t)` |
| Bounce/spring | spring | `1.0 - pow(cos(t * 3.14159 * 0.5), 2.0) * exp(-t * 4.0)` |
| Smooth loop | cosine | `0.5 - 0.5 * cos(t * 6.2832)` |

#### Timing
- Micro-interactions: 150–400ms
- Transitions: 300–800ms
- Ambient effects: 2–6s loop
- Never instant (0ms) — even subtle motion feels better than none

#### Rhythm
- Use `fract(u_time / duration)` for perfect loops
- Vary frequencies to avoid mechanical feel: `sin(t * 1.0) + sin(t * 1.7) * 0.5`
- Layer 2–3 speeds: slow drift + medium pulse + fast shimmer

### Performance Budget (Mobile/Web)

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

#### Optimization Tips (Mobile-First)
- Prefer `smoothstep` over conditional branches
- Use `step()` for binary masks instead of `if`
- Precompute constants outside `mainImage`
- Use `mix` instead of branching where possible
- **Prefer mipmap LOD blur over multi-sample blur** — single texture fetch vs. 49+
- Downsample expensive effects: render at half resolution when precision allows
- Avoid dependent texture reads on mobile (compute UV, then sample, don't sample-then-recompute)
- Keep FBM at 4 octaves max on mobile; 5+ causes visible jank
- Use `lowp`/`mediump` for colors where precision loss is acceptable (but not for UVs or SDF distances)

## GLSL Constraints Reference

> Target platform: **Mobile GPU (Mali/Adreno/Apple GPU) + WebGL** — not desktop.
> Target frame budget: **< 2ms per frame at 1080p** on mid-range mobile.
> Scope: **2D/2.5D flat effects only** — no 3D raymarching, no volumetric, no scene graphs.

### Mandatory Rules

1. **Do NOT declare** `u_time`, `u_resolution`, `u_mouse` — these are injected by runtime
2. **Must implement** `void mainImage(out vec4 fragColor, in vec2 fragCoord)` — entry point
3. **Output must be** complete, compilable GLSL ES 3.0 — no `#include`, no undefined functions
4. **2D only** — all coordinates are `vec2 uv`, all SDF operations are 2D, no `vec3` position/ray/direction for 3D scene rendering

### Banned Patterns

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

### Mobile Performance Budget

| Metric | Limit | Rationale |
|--------|-------|-----------|
| Fragment shader ALU instructions | ≤ 256 | Mid-range mobile at 1080p |
| Texture fetches per fragment | ≤ 8 | Mobile memory bandwidth limited |
| For-loop iterations (total across all loops) | ≤ 32 | Prevents GPU timeout |
| Target frame time | < 2ms at 1080p | 60fps budget with headroom for UI |
| FBM octaves | ≤ 4 | Each octave doubles cost; 4 is already heavy on mobile |
| Blur kernel | ≤ 7×7 (49 samples) | 9×9 is too slow on mobile GPU |
| Total fragment shader complexity | "simple" to "moderate" | If it wouldn't run smoothly on a 2022 mid-range phone, simplify |

#### Mobile Optimization Tips

- **Prefer `smoothstep` and `step` over branching** — GPUs hate divergent branches
- **Use `mix()` instead of `if/else`** — both branches execute anyway on GPU
- **Reduce texture samples**: prefer mipmap LOD over multi-sample blur
- **Downsample expensive effects**: render at half resolution when possible
- **Avoid dependent texture reads**: compute UV before sampling, not after
- **Keep FBM octaves ≤ 4** on mobile; 5+ is desktop-only
- **Use `pow(x, 2.0)` instead of `x * x` only when the compiler won't optimize** — usually `x * x` is fine

### Math Safety

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

### Cross-Platform Quirks

| Issue | GLSL (WebGL/Vulkan) | MSL (Metal) | Notes |
|-------|---------------------|-------------|-------|
| Fragment output | `out vec4 fragColor` | `return vec4` | Our runtime wraps to handle this |
| Texture function | `texture(sampler, uv)` | `sampler.sample(uv)` | Use `texture()` — transpiler handles |
| Uniform declarations | Must declare in code | Declared in shader signature | Our runtime auto-injects common uniforms |
| Precision | Need `precision highp float` | Implicit | Always include precision qualifier |
| Half-float framebuffers | May not support | Supported | Assume `highp` only; don't rely on `mediump` FBO |

### Texture Support

- Textures are supported via `iChannel0`–`iChannel3` (Shadertoy convention)
- Use `texture(iChannelN, uv)` for sampling
- Our runtime will bind system textures to channels automatically
- For backdrop blur effects, iChannel0 is the system framebuffer
- For user-uploaded textures, iChannel1 is available
- Always handle the case where a channel may not be bound — use fallback procedural
- **Mobile**: keep texture samples ≤ 8 per fragment; prefer mipmap LOD blur over multi-sample

## Operator Catalog

Complete catalog of GLSL operators for visual effect composition.

### SDF Primitives

#### Circle SDF

```glsl
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `p` | vec2 | UV space | Point position |
| `r` | float | 0.0-1.0 | Circle radius |

#### Box SDF

```glsl
float sdBox(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `p` | vec2 | UV space | Point position |
| `b` | vec2 | UV dimensions | Half-size (width/2, height/2) |

#### Rounded Box SDF

```glsl
float sdRoundedBox(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `p` | vec2 | UV space | Point position |
| `b` | vec2 | UV dimensions | Half-size |
| `r` | float | 0.0-b | Corner radius |

#### Segment SDF

```glsl
float sdSegment(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `p` | vec2 | Point position |
| `a` | vec2 | Start point |
| `b` | vec2 | End point |

#### Triangle SDF

```glsl
float sdTriangle(vec2 p, vec2 p0, vec2 p1, vec2 p2) {
    // Edge distances calculation
}
```

#### Polygon SDF

```glsl
float sdPolygon(vec2 p, vec2[] vertices) {
    // Edge loop calculation
}
```

---

### SDF Operations

#### Union

```glsl
float opUnion(float d1, float d2) {
    return min(d1, d2);
}
```

**Use**: Combine two shapes (logical OR)

#### Intersection

```glsl
float opIntersection(float d1, float d2) {
    return max(d1, d2);
}
```

**Use**: Common area of two shapes (logical AND)

#### Subtraction

```glsl
float opSubtraction(float d1, float d2) {
    return max(d1, -d2);
}
```

**Use**: Remove shape2 from shape1

#### Smooth Union

```glsl
float opSmoothUnion(float d1, float d2, float k) {
    float h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) - k * h * (1.0 - h);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `d1, d2` | float | SDF distances | Input distances |
| `k` | float | 0.01-0.5 | Blend width |

#### Smooth Intersection

```glsl
float opSmoothIntersection(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) + k * h * (1.0 - h);
}
```

#### Smooth Subtraction

```glsl
float opSmoothSubtraction(float d1, float d2, float k) {
    float h = clamp(0.5 - 0.5 * (d1 + d2) / k, 0.0, 1.0);
    return mix(d1, -d2, h) + k * h * (1.0 - h);
}
```

#### Round Blend

```glsl
float opRound(float d, float r) {
    return d - r;
}
```

**Use**: Add rounded corners to any SDF

#### Onion (Shell)

```glsl
float opOnion(float d, float r) {
    return abs(d) - r;
}
```

**Use**: Create hollow shape with thickness `r`

---

### Noise Functions

#### Hash Function

```glsl
float hash(float n) {
    return fract(sin(n) * 43758.5453);
}

vec2 hash22(vec2 p) {
    p = fract(p * vec2(5.3983, 5.4447));
    p += dot(p.yx, p.yx + vec2(21.5351));
    return fract(vec2(p.x * p.y, p.x + p.y));
}
```

**Use**: Basic randomness, hash table

#### Value Noise

```glsl
float valueNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `p` | vec2 | Noise coordinate |

#### Perlin Noise

```glsl
float perlinNoise(vec2 p) {
    vec2 pi = floor(p);
    vec2 pf = fract(p);
    vec2 u = pf * pf * (3.0 - 2.0 * pf);
    
    vec2 gradient0 = hash22(pi);
    vec2 gradient1 = hash22(pi + vec2(1.0, 0.0));
    vec2 gradient2 = hash22(pi + vec2(0.0, 1.0));
    vec2 gradient3 = hash22(pi + vec2(1.0, 1.0));
    
    float n0 = dot(gradient0, pf);
    float n1 = dot(gradient1, pf - vec2(1.0, 0.0));
    float n2 = dot(gradient2, pf - vec2(0.0, 1.0));
    float n3 = dot(gradient3, pf - vec2(1.0, 1.0));
    
    return mix(mix(n0, n1, u.x), mix(n2, n3, u.x), u.y) * 0.5 + 0.5;
}
```

**Use**: Smooth gradient noise, organic movement

#### Simplex Noise

```glsl
float simplexNoise(vec2 p) {
    // Simplified grid structure
    // More efficient than Perlin
}
```

**Use**: Efficient Perlin variant

#### Voronoi Noise

```glsl
vec2 voronoi(vec2 p) {
    vec2 n = floor(p);
    vec2 f = fract(p);
    
    float md = 8.0;
    vec2 mr;
    
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 o = hash22(n + g);
            vec2 r = g + o - f;
            float d = dot(r, r);
            
            if (d < md) {
                md = d;
                mr = r;
            }
        }
    }
    
    return vec2(md, dot(mr, mr));
}
```

**Use**: Cellular patterns, crystal structures

#### FBM (Fractal Brownian Motion)

```glsl
float fbm(vec2 p, int octaves, float frequency, float amplitude) {
    float value = 0.0;
    float amp = amplitude;
    float freq = frequency;
    
    for (int i = 0; i < octaves; i++) {
        value += amp * perlinNoise(p * freq);
        freq *= 2.0;
        amp *= 0.5;
    }
    
    return value;
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `octaves` | int | 1-8 | Detail layers |
| `frequency` | float | 1.0-10.0 | Base frequency |
| `amplitude` | float | 0.1-1.0 | Initial amplitude |

**Use**: Rich detail, natural textures

#### Turbulence

```glsl
float turbulence(vec2 p, int octaves) {
    return abs(fbm(p, octaves));
}
```

**Use**: Sharp-edged noise patterns

---

### Lighting Models

#### Fresnel Effect

```glsl
float fresnel(vec3 I, vec3 N, float power) {
    return pow(1.0 - dot(I, N), power);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `I` | vec3 | View direction | Camera to point |
| `N` | vec3 | Normal | Surface normal |
| `power` | float | 1.0-5.0 | Fresnel intensity |

#### Specular Highlight

```glsl
vec3 specular(vec3 normal, vec3 lightDir, vec3 viewDir, float shininess) {
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(viewDir, reflectDir), 0.0), shininess);
    return vec3(spec);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `shininess` | float | 1-128 | Highlight sharpness |

#### Diffuse Light

```glsl
float diffuse(vec3 normal, vec3 lightDir) {
    return max(dot(normal, lightDir), 0.0);
}
```

#### Ambient Occlusion

```glsl
float ambientOcclusion(vec2 p, float radius) {
    float ao = 0.0;
    for (int i = 0; i < 4; i++) {
        vec2 offset = vec2(cos(float(i) * 0.785), sin(float(i) * 0.785)) * radius;
        ao += smoothstep(0.0, 1.0, sdCircle(p + offset, 0.0));
    }
    return ao / 4.0;
}
```

---

### Color Operations

#### Gradient

```glsl
vec3 gradient(float t, vec3[] colors, float[] positions) {
    for (int i = 0; i < colors.length - 1; i++) {
        if (t >= positions[i] && t <= positions[i + 1]) {
            float localT = (t - positions[i]) / (positions[i + 1] - positions[i]);
            return mix(colors[i], colors[i + 1], localT);
        }
    }
    return colors[colors.length - 1];
}
```

#### Color Mix

```glsl
vec3 colorMix(vec3 a, vec3 b, float t) {
    return mix(a, b, t);
}
```

#### Tone Mapping

```glsl
// Reinhard
vec3 reinhard(vec3 color) {
    return color / (1.0 + color);
}

// ACES Filmic
vec3 aces(vec3 x) {
    float a = 2.51;
    float b = 0.03;
    float c = 2.43;
    float d = 0.59;
    float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}
```

---

### Animation Drivers

#### Time Loop

```glsl
float timeLoop(float duration) {
    return fract(iTime / duration);
}
```

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `duration` | float | 1.0-10.0 | Cycle length (seconds) |

#### Ease In-Out

```glsl
float easeInOut(float t) {
    return t * t * (3.0 - 2.0 * t);  // smoothstep curve
}

float easeInOutCubic(float t) {
    return t < 0.5 ? 4.0 * t * t * t : 1.0 - pow(-2.0 * t + 2.0, 3.0) / 2.0;
}

float easeInOutQuad(float t) {
    return t < 0.5 ? 2.0 * t * t : 1.0 - pow(-2.0 * t + 2.0, 2.0) / 2.0;
}
```

#### Sin Wave

```glsl
float sinWave(float t, float frequency, float amplitude) {
    return sin(t * frequency * TWO_PI) * amplitude;
}
```

#### Pulse

```glsl
float pulse(float t, float frequency) {
    return pow(sin(t * frequency * TWO_PI), 2.0);
}
```

#### Flow

```glsl
vec2 flow(vec2 uv, float speed, float direction) {
    return uv + vec2(cos(direction), sin(direction)) * speed * iTime;
}
```

---

### UV Operations

#### UV Transform

```glsl
vec2 uvTransform(vec2 uv, vec2 offset, vec2 scale) {
    return (uv - offset) * scale;
}
```

#### UV Rotate

```glsl
vec2 uvRotate(vec2 uv, float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return vec2(uv.x * c - uv.y * s, uv.x * s + uv.y * c);
}
```

#### UV Scale

```glsl
vec2 uvScale(vec2 uv, vec2 factor) {
    return uv * factor;
}
```

#### UV Offset

```glsl
vec2 uvOffset(vec2 uv, vec2 offset) {
    return uv + offset;
}
```

---

### Post Effects

#### Glow

```glsl
vec3 glow(vec2 uv, float radius, float intensity) {
    vec3 col = vec3(0.0);
    for (float i = -radius; i <= radius; i++) {
        for (float j = -radius; j <= radius; j++) {
            col += texture(iChannel0, uv + vec2(i, j) * 0.01).rgb;
        }
    }
    return col / ((2.0 * radius + 1.0) * (2.0 * radius + 1.0)) * intensity;
}
```

#### Blur

```glsl
// Gaussian blur kernel
vec3 gaussianBlur(vec2 uv, float radius) {
    // Multi-sample blur implementation
}
```

#### Outline

```glsl
float outline(float d, float width) {
    return smoothstep(-width, width, abs(d));
}
```

#### Alpha Blend

```glsl
vec4 alphaBlend(vec4 src, vec4 dst) {
    return vec4(
        src.rgb * src.a + dst.rgb * (1.0 - src.a),
        src.a + dst.a * (1.0 - src.a)
    );
}
```

---

### Operator Usage Guide

| Effect Type | Recommended Operators | Complexity |
|-------------|----------------------|------------|
| **Simple Shape** | `SDF_Primitive` + `Color` | Low |
| **Outline Effect** | `SDF` + `Outline` + `Glow` | Medium |
| **Ripple Animation** | `SDF` + `SinWave` + `Gradient` + `TimeLoop` | Medium |
| **Frosted Glass** | `Noise` + `Blur` + `AlphaBlend` | High |
| **Glow Effect** | `SDF` + `Specular` + `Glow` | Medium |
| **Flow Light** | `Noise` + `Flow` + `ColorMix` | High |
| **Particle Effect** | `Voronoi` + `Animation` + `Alpha` | High |

---