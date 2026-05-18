# VFX Pipeline 质量优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 E2E 测试通过率（≥0.8 分）从 4/19 (21%) 提升至 12+/19 (63%+)

**Architecture:** 修改 5 个 prompt 文件 + 1 个 context_assembler，按 P0→P1→P2 优先级实施，每轮修改后用失败的 15 个样例中选 3-5 个回归验证。

**Tech Stack:** Markdown prompts, Python validation scripts, curl/httpx for API test

---

## 数据依据

E2E 测试 19 个样例结果：

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| ≥0.8 通过率 | 4/19 (21%) | 12/19 (63%+) |
| 平均分 | 0.75 | 0.82+ |
| Catalog 覆盖率 | 33% (5/9 类) | 89% (8/9 类) |
| Decompose 分类准确率 | 20% (不达标样本) | 60%+ |
| Lighting 维度均分 | 0.66 | 0.78+ |

**系统性问题（按影响面排序）：**

1. **Lighting 强度系统性偏低** — 73% 样本 (11/15) 存在亮度/光晕不足
2. **Decompose 分类太粗糙** — 60% 不达标样本被归为 `{effect.flow}`，分类准确率仅 20%
3. **VFX Details 丰富度不足** — 40% 样本 (6/15) 流动感弱、粒子密度低
4. **Color 饱和度不足** — 60% 样本颜色偏差，与 lighting 问题联动

**根因链：**
```
Catalog 只有 5 种 effect (缺 liquid/particle/warp/shape)
  → Decompose 无法精确分类，flow 成为万能垃圾桶
    → Generate 使用通用 FBM+time 方案
      → glow 强度低、噪声层次薄、颜色不鲜艳
        → Lighting/Color/VFX Details 三维度集体低分
```

---

## File Structure

```
修改文件：
├── backend/app/prompts/
│   ├── vfx_effect_catalog.md        # +4 种 effect type, +算子映射
│   ├── decompose_system.md           # +分类决策树, 减少flow滥用
│   ├── generate_system.md            # +glow强度规范, +fill_type警告强化
│   ├── shader_skill_reference.md     # +4 个效果模板, +火焰/粒子算子
│   └── shared_vfx_terminology.md     # +新效果类型术语

新增测试：
└── backend/test_catalog_coverage.py  # Catalog 覆盖率测试
```

---

### Task 1: 扩展 VFX Effect Catalog — 新增 4 种效果类型

**Files:**
- Modify: `backend/app/prompts/vfx_effect_catalog.md`

**目标:** Catalog 覆盖率从 33% (5/9) 提升到 89% (9/9)，新增 liquid、particle、warp、shape 四种效果类型

- [ ] **Step 1: 在 Catalog 效果类型表中新增 4 行**

在现有 5 行效果类型（ripple/glow/gradient/frosted/flow）之后，新增：

```markdown
| `{effect.liquid}` | 液态/玻璃 | sdVesica/sdCircle + alpha + blur + refract offset | ~120 |
| `{effect.particle}` | 粒子/点阵 | hash grid + point SDF + flicker + FBM drift | ~100 |
| `{effect.warp}` | 域扭曲/视错觉 | FBM domain warp + polar coords + line integral | ~100 |
| `{effect.shape}` | 几何形状 | sdHeart/sdStar/sdBox + solid fill + edge glow | ~40 |
```

- [ ] **Step 2: 为每种新效果添加 Operator Mapping 示例**

在 `## Effect → Operator Mapping` 节中新增：

```markdown
### {effect.liquid} 算子组合
```
d = sdVesica/sdCircle(pos, params)
alpha = smoothstep(edge, 0.0, d) * 0.4-0.6  // 半透明
blur_offset = FBM(pos * 3.0 + iTime * 0.2) * 0.02  // 折射偏移
color = mix(bg_color, tint_color, alpha)
highlight = pow(max(0.0, dot(normal, lightDir)), specular)  // 高光
```

### {effect.particle} 算子组合
```
cell_id = hash(floor(uv * grid_scale))       // 网格哈希
particle_pos = fract(cell_id.xy) + FBM_drift // FBM 漂移
d = length(uv - particle_pos)
brightness = glow * flicker(cell_id.z, iTime) // 闪烁
color = palette(cell_id.w) * brightness       // 颜色变化
```

### {effect.warp} 算子组合
```
warped_uv = uv + FBM(uv * freq + iTime * speed) * warp_strength
d = length(warped_uv - center)
pattern = sin(d * rings - iTime) * exp(-d * decay)
color = mix(color1, color2, pattern)
```

### {effect.shape} 算子组合
```
d = sdHeart/sdStar/sdBox(pos, params)
fill = 1.0 - smoothstep(0.0, edge_width, d)   // 实心填充用 d, NOT abs(d)
glow = exp(-abs(d) * glow_intensity) * glow_color
color = fill_color + glow
```
```

- [ ] **Step 3: 验证**

```bash
cd backend && python -c "
from app.prompts import load_prompt
cat = load_prompt('vfx_effect_catalog')
for t in ['ripple','glow','gradient','frosted','flow','liquid','particle','warp','shape']:
    found = f'{{effect.{t}}}' in cat
    print(f'  {t}: {\"✅\" if found else \"❌\"}  ')"
```

Expected: 全部 ✅

- [ ] **Step 4: Commit**

```bash
git add backend/app/prompts/vfx_effect_catalog.md
git commit -m "feat: add 4 new effect types to catalog (liquid/particle/warp/shape)"
```

---

### Task 2: 修复 Decompose 分类精度 — 添加决策树，减少 flow 滥用

**Files:**
- Modify: `backend/app/prompts/decompose_system.md`

**目标:** Decompose 分类准确率从 20% 提升至 60%+，核心是给 Decompose 一棵明确的分类决策树

- [ ] **Step 1: 在 Decompose Planning Instructions 中插入分类决策树**

在 Planning Instructions 的步骤中（分析阶段），添加效果分类决策树：

```markdown
## 效果分类决策树（必须严格遵循）

当分析视觉效果时，按以下顺序判断 effect_type：

1. **画面有明确的几何形状（心形/星形/方块/三角形）？**
   → `{effect.shape}` — 用 sdHeart/sdStar/sdBox 等精确 SDF

2. **画面有半透明/折射/模糊/磨砂质感的覆盖层？**
   → `{effect.liquid}` — 需要 alpha blend + blur/refraction

3. **画面有大量离散光点/粒子/火花/星星分布？**
   → `{effect.particle}` — 需要 hash grid + point SDF + flicker

4. **画面有同心圆/波纹从中心向外扩散？**
   → `{effect.ripple}` — sdCircle + sin(t) 扩散

5. **画面有明显发光体（光晕/bloom/霓虹）？**
   → `{effect.glow}` — exp(-d * intensity) glow

6. **画面有多色平滑渐变过渡（无明确形状）？**
   → `{effect.gradient}` — mix() + gradient function

7. **画面有磨砂/毛玻璃/模糊覆盖效果？**
   → `{effect.frosted}` — noise + blur + alpha

8. **画面有背景扭曲/线条弯曲/视错觉？**
   → `{effect.warp}` — domain warping + polar coords

9. **以上均不完全匹配时的 fallback：**
   → `{effect.flow}` — 仅用于确实无法归类的有机流动效果

⚠️ 严禁将 flow 作为默认选项！90% 的情况应该匹配上面的 1-8 之一。
```

- [ ] **Step 2: 在 Decompose Failure Examples 中添加 flow 滥用反例**

```markdown
### ❌ 反例 6: 将粒子效果误标为 flow

**输入**: 视频中大量发光粒子向上飘散
**错误输出**: `effect_type: {effect.flow}` — 因为有流动感
**正确输出**: `effect_type: {effect.particle}` — 有离散光点分布
**后果**: Generate 用 FBM 全屏流动代替粒子系统，渲染结果完全不对

### ❌ 反例 7: 将液态玻璃误标为 flow

**输入**: 视频中半透明液滴在背景上滑动
**错误输出**: `effect_type: {effect.flow}` — 因为有流动感
**正确输出**: `effect_type: {effect.liquid}` — 有透明/折射特征
**后果**: Generate 缺少 alpha blend 和折射偏移，液滴变成不透明色块

### ❌ 反例 8: 将域扭曲误标为 flow

**输入**: 视频中背景线条在物体周围弯曲
**错误输出**: `effect_type: {effect.flow}` — 因为有流动感
**正确输出**: `effect_type: {effect.warp}` — 背景被局部扭曲
**后果**: Generate 生成全屏流动而非局部域扭曲，空间关系错误
```

- [ ] **Step 3: 验证**

```bash
cd backend && python -c "
from app.prompts import load_prompt
p = load_prompt('decompose_system')
checks = ['决策树', '反例 6', '反例 7', '反例 8', '严禁将 flow 作为默认']
for c in checks:
    print(f'  {c}: {\"✅\" if c in p else \"❌\"}  ')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/prompts/decompose_system.md
git commit -m "fix: add classification decision tree to Decompose, reduce flow overuse"
```

---

### Task 3: 修复 Generate Lighting 强度 + Glow 参数规范

**Files:**
- Modify: `backend/app/prompts/generate_system.md`
- Modify: `backend/app/prompts/shader_skill_reference.md`

**目标:** 解决 73% 样本存在的"强度/亮度不足"问题，建立 glow/bloom 的强度基准

- [ ] **Step 1: 在 generate_system.md 添加 Glow 强度规范**

在 Planning Instructions 的代码生成阶段，添加：

```markdown
## Glow/Bloom 强度规范（强制）

### 核心规则：GLOW 必须明显可见

渲染结果中的光晕/glow 效果必须在截图中清晰可见，不能是微弱的灰色渐变。

### 强度基准值

| 效果类型 | 最低 glow 系数 | 推荐公式 |
|----------|---------------|----------|
| 霓虹发光 | 8.0-12.0 | `exp(-abs(d) * glow * 0.5) * intensity` |
| 柔和光晕 | 3.0-5.0 | `exp(-abs(d) * glow) * intensity` |
| Bloom 扩散 | 2.0-3.0 | `exp(-d * d * glow) * intensity` |
| 边缘高光 | 4.0-6.0 | `pow(1.0 - abs(dot(N, V)), fresnel_power) * intensity` |

**intensity 最低值**: `vec3(1.0, 0.9, 0.8)` — 不允许低于 0.6 的发光强度

### 常见错误

❌ `glow = exp(-d * 20.0) * vec3(0.2)` — 太暗！截图中几乎不可见
✅ `glow = exp(-d * 5.0) * vec3(1.2, 1.0, 0.9)` — 明亮可见的光晕

❌ 仅用一次 exp 衰减 — 层次单薄
✅ 多层叠加：`glow = core * 1.5 + mid * 0.8 + outer * 0.3` — 中心亮、外层柔和

### 自检方法

生成 shader 后自问：如果 d=0（形状边缘），glow 颜色值是否 >= vec3(0.8)？
如果不是，强度不够，需要调高 intensity 或降低衰减系数。
```

- [ ] **Step 2: 在 shader_skill_reference.md 的 Post Effects > Glow 章节强化**

将现有 Glow 章节替换为带强度基准的版本：

```markdown
### Glow (带强度基准)

**关键：Glow 在截图中必须清晰可见，不能是微弱灰色！**

```glsl
// ✅ 推荐：多层 glow，中心明亮
float d = sdf_shape(pos);
float core = exp(-abs(d) * 12.0);      // 核心亮线
float mid  = exp(-abs(d) * 4.0);        // 中层光晕  
float outer = exp(-abs(d) * 1.5);       // 外层扩散
vec3 glow = color * (core * 1.5 + mid * 0.8 + outer * 0.3);

// ❌ 错误：单层衰减、强度过低
// float glow = exp(-d * 10.0) * 0.2;  // 截图中几乎不可见
```

**强度自检：shape 边缘处 (d≈0) glow 值必须 >= 0.8**
```

- [ ] **Step 3: 在 generate_system.md 的 ❌ Failure Examples 中添加弱光反例**

```markdown
### ❌ 反例 6: Glow 强度过低

**错误代码:**
```glsl
float glow = exp(-d * 15.0) * 0.15;  // 系数 0.15 太暗
fragColor = vec4(baseColor + glowColor * glow, 1.0);
```

**问题**: 在 1024x1024 截图中，exp(-d*15) 衰减极快，叠加 0.15 系数导致光晕几乎不可见。
**修正**: 使用多层 glow，intensity >= 1.0，衰减系数 <= 8.0
```

- [ ] **Step 4: 验证**

```bash
cd backend && python -c "
from app.prompts import load_prompt
g = load_prompt('generate_system')
s = load_prompt('shader_skill_reference')
checks = [
    ('generate: 强度基准值', '强度基准' in g),
    ('generate: glow规范', 'Glow/Bloom 强度规范' in g),
    ('generate: 弱光反例', '反例 6' in g),
    ('skill: 多层glow', '多层 glow' in s),
    ('skill: 强度自检', '强度自检' in s),
]
for desc, ok in checks:
    print(f'  {desc}: {\"✅\" if ok else \"❌\"}  ')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompts/generate_system.md backend/app/prompts/shader_skill_reference.md
git commit -m "fix: enforce glow/bloom intensity standards, add multi-layer glow template"
```

---

### Task 4: 扩展 Shader Skill Reference — 新增效果模板

**Files:**
- Modify: `backend/app/prompts/shader_skill_reference.md`

**目标:** 为 Catalog 新增的 4 种效果类型提供完整的效果模板，Generate 可直接引用

- [ ] **Step 1: 在 Shader Templates 节新增 4 个模板**

在现有 Template: Glow Pulse 之后，新增：

````markdown
### Template: Liquid Glass (半透明 + 折射 + 高光)

适用于：液态玻璃、水滴、半透明覆盖层

```glsl
float sdShape(vec2 p) {
    // 使用 sdVesica/sdCircle 等有机形状
    return sdVesica(p - center, params);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    float d = sdShape(uv);
    
    // 半透明填充（实心用 d，空心用 abs(d)）
    float fill = 1.0 - smoothstep(0.0, edge_width, d);
    
    // 折射偏移（FBM 驱动）
    vec2 refract_offset = vec2(
        FBM(uv * 3.0 + iTime * 0.2) - 0.5,
        FBM(uv * 3.0 + vec2(5.2, 1.3) + iTime * 0.2) - 0.5
    ) * 0.03;
    
    // 背景采样（折射）
    vec3 bg = backgroundShader(uv + refract_offset);
    
    // 高光（菲涅尔）
    float highlight = pow(1.0 - abs(d) / 0.1, 3.0) * 0.8;
    
    // 混合
    vec3 tint = vec3(0.5, 0.7, 0.9);
    float alpha = fill * 0.5; // 半透明
    vec3 color = mix(bg, tint, alpha) + highlight;
    
    // 边缘光晕
    float glow = exp(-abs(d) * 8.0) * 0.3;
    color += glow_color * glow;
    
    fragColor = vec4(color, 1.0);
}
```

**关键参数:**
- alpha: 0.3-0.6（半透明范围）
- refract_offset: FBM * 0.02-0.05（微妙偏移）
- highlight: 菲涅尔 pow(x, 2-4) * 0.5-0.8
- fill 用 d（实心），不用 abs(d)（空心）

---

### Template: Particle Field (粒子点阵 + 闪烁 + 漂移)

适用于：粒子、星光、火花、尘埃

```glsl
// 网格哈希 — 粒子位置的基础
vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    float grid_scale = 20.0; // 粒子密度
    vec2 cell = floor(uv * grid_scale);
    vec2 local = fract(uv * grid_scale);
    
    // 每个网格一个粒子
    vec2 particle_offset = hash2(cell);
    vec2 particle_pos = particle_offset;
    
    // FBM 漂移（粒子随时间移动）
    particle_pos += vec2(
        FBM(cell * 0.1 + iTime * 0.3),
        FBM(cell * 0.1 + vec2(5.2, 1.3) + iTime * 0.2)
    ) * 0.3;
    particle_pos = fract(particle_pos); // wrap around
    
    // 粒子距离
    float d = length(local - particle_pos);
    
    // 粒子大小 + 闪烁
    float size = mix(0.02, 0.06, hash2(cell + 0.5).x);
    float flicker = 0.7 + 0.3 * sin(iTime * (2.0 + hash2(cell + 1.5).x * 4.0) + hash2(cell + 2.5).x * 6.28);
    
    // 点 SDF + glow
    float brightness = exp(-d * d / (size * size)) * flicker;
    
    // 颜色变化（按 cell_id 分配不同颜色）
    float hue = hash2(cell + 3.5).x;
    vec3 particle_color = palette(hue);
    
    vec3 color = particle_color * brightness * 1.2; // intensity >= 1.0
    
    fragColor = vec4(color, 1.0);
}
```

**关键参数:**
- grid_scale: 10-30（密度）
- size: 0.02-0.08（粒子大小）
- flicker: sin(time * freq + phase) * 0.3 振幅
- brightness intensity: >= 1.0（确保粒子清晰可见）
- palette: 按 hash 分配不同色相

---

### Template: Domain Warp (域扭曲 + 线条)

适用于：视错觉、背景扭曲、等高线

```glsl
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // 两级 domain warping
    vec2 q = vec2(FBM(uv + vec2(0.0, 0.0)), FBM(uv + vec2(5.2, 1.3)));
    vec2 r = vec2(FBM(uv + 4.0*q + vec2(1.7, 9.2) + iTime*0.15),
                  FBM(uv + 4.0*q + vec2(8.3, 2.8) + iTime*0.12));
    
    float f = FBM(uv + 4.0*r);
    
    // 线条叠加（等高线效果）
    float lines = abs(sin(f * 20.0)) * 0.3;
    
    // 颜色映射
    vec3 color = mix(color1, color2, clamp(f * f * 4.0, 0.0, 1.0));
    color = mix(color, color3, clamp(length(q), 0.0, 1.0));
    color = mix(color, color4, clamp(length(r.x), 0.0, 1.0));
    
    // 线条高亮
    color += lines * accent_color;
    
    fragColor = vec4(color, 1.0);
}
```

**关键参数:**
- warp strength: 4.0（两级叠加）
- FBM octaves: 4-5（丰富纹理）
- lines: sin(f * frequency) * amplitude
- 多层颜色 mix 增加深度感

---

### Template: Solid Shape (实心形状 + 渐变 + 边缘光)

适用于：心形、星形、几何图形、图标

```glsl
float sdShape(vec2 p) {
    // 选择对应 SDF：sdHeart / sdStar5 / sdBox / sdCircle
    return sdHeart(p - center, size);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    float d = sdShape(uv);
    
    // ⚠️ 实心填充用 d，不用 abs(d)
    //    abs(d) 会产生空心轮廓！
    float fill = 1.0 - smoothstep(0.0, edge_width, d);
    
    // 内部渐变
    vec2 grad_dir = normalize(vec2(1.0, -1.0));
    float gradient = dot(uv - center, grad_dir) * 0.5 + 0.5;
    vec3 fill_color = mix(color_dark, color_bright, gradient);
    
    // 边缘光（柔和 glow）
    float glow = exp(-abs(d) * 6.0) * vec3(0.8, 0.9, 1.0) * 0.5;
    
    // 最终合成
    vec3 color = fill * fill_color + (1.0 - fill) * bg_color + glow;
    
    fragColor = vec4(color, 1.0);
}
```

**关键参数:**
- fill: 用 `d`（实心），禁用 `abs(d)`（会产生空心）
- edge_width: 0.01-0.05 UV（柔和边缘）
- glow: exp(-abs(d) * 4-8) * intensity >= 0.5
- gradient: dot(uv, dir) 实现方向性渐变
````

- [ ] **Step 2: 验证模板完整性**

```bash
cd backend && python -c "
from app.prompts import load_prompt
s = load_prompt('shader_skill_reference')
templates = ['Liquid Glass', 'Particle Field', 'Domain Warp', 'Solid Shape']
for t in templates:
    found = f'Template: {t}' in s
    print(f'  {t}: {\"✅\" if found else \"❌\"}  ')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/prompts/shader_skill_reference.md
git commit -m "feat: add 4 effect templates (liquid glass/particle/domain warp/solid shape)"
```

---

### Task 5: 更新术语表 — 新增效果类型术语

**Files:**
- Modify: `backend/app/prompts/shared_vfx_terminology.md`

- [ ] **Step 1: 在术语表中新增 4 种效果类型定义**

```markdown
### Liquid Glass Effect (液态玻璃效果)
- **定义**: 具有半透明、折射、高光特征的流体/玻璃质感效果
- **识别特征**: alpha < 1.0、背景可见但扭曲、边缘高光反射
- **GLSL 关键词**: alpha blend, refraction offset, fresnel highlight, sdVesica
- **Token**: `{effect.liquid}`

### Particle Field Effect (粒子场效果)
- **定义**: 大量离散光点/粒子在空间中分布、移动、闪烁的效果
- **识别特征**: 离散点状元素、数量 > 20、有闪烁/漂移动画
- **GLSL 关键词**: hash grid, point SDF, flicker, FBM drift, palette per particle
- **Token**: `{effect.particle}`

### Domain Warp Effect (域扭曲效果)
- **定义**: 通过噪声函数扭曲 UV 坐标，产生线条弯曲/等高线/视错觉的效果
- **识别特征**: 背景线条弯曲、等高线图案、有机纹理变形
- **GLSL 关键词**: domain warping, polar coordinates, line integral, FBM warp
- **Token**: `{effect.warp}`

### Shape Effect (几何形状效果)
- **定义**: 以明确的几何图形（心形/星形/方块等）为主体，带渐变填充和边缘光的效果
- **识别特征**: 清晰可辨识的几何形状、实心或空心填充、可能有内部渐变
- **GLSL 关键词**: sdHeart/sdStar5/sdBox, solid fill (d) or hollow (abs(d)), edge glow
- **Token**: `{effect.shape}`
```

- [ ] **Step 2: 验证**

```bash
cd backend && python -c "
from app.prompts import load_prompt
t = load_prompt('shared_vfx_terminology')
for term in ['Liquid Glass', 'Particle Field', 'Domain Warp', 'Shape Effect']:
    print(f'  {term}: {\"✅\" if term in t else \"❌\"}  ')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/prompts/shared_vfx_terminology.md
git commit -m "feat: add terminology for 4 new effect types (liquid/particle/warp/shape)"
```

---

### Task 6: Inspect 维度权重微调 — 强化 Lighting 和 Color 维度

**Files:**
- Modify: `backend/app/prompts/inspect_system.md`

**目标:** Inspect 在 Lighting 维度对 glow 强度不足时更严格扣分

- [ ] **Step 1: 在 Inspect 的 Lighting 维度评分标准中添加 glow 强度判据**

在 Lighting 维度的评分指引中，添加：

```markdown
**Lighting 维度评分要点:**

| 分值 | 标准 |
|------|------|
| 0.9-1.0 | glow 明亮清晰，多层光晕叠加，中心过曝效果自然 |
| 0.7-0.8 | glow 可见但强度略低，可能是单层衰减 |
| 0.5-0.6 | glow 微弱可见，边缘光晕不明显 |
| **< 0.5** | **glow 几乎不可见 或 发光强度 < 0.3 — 必须明确指出** |

⚠️ 如果渲染截图中的发光效果看起来像"灰色模糊"而非"明亮光晕"，这是强度不足的信号，Lighting 维度应 <= 0.6。
```

- [ ] **Step 2: 在 Inspect 反馈模板中添加 Lighting 强度相关反馈语句**

在 visual_goals 示例中添加：

```markdown
- "Glow 强度不足：当前 exp(-d*X)*Y 系数太低，建议 intensity >= 1.0，衰减系数 <= 8.0，使用多层叠加"
- "中心亮度不够：形状边缘处 glow 颜色值应 >= 0.8，当前可能只有 0.2-0.3"
```

- [ ] **Step 3: 验证**

```bash
cd backend && python -c "
from app.prompts import load_prompt
p = load_prompt('inspect_system')
checks = ['glow 明亮清晰', '灰色模糊', 'Glow 强度不足', 'intensity >= 1.0']
for c in checks:
    print(f'  {c}: {\"✅\" if c in p else \"❌\"}  ')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/prompts/inspect_system.md
git commit -m "fix: strengthen Inspect Lighting dimension scoring for glow intensity"
```

---

### Task 7: 回归验证 — 选取 5 个代表样例重跑

**目标:** 验证修改后的 Pipeline 在之前不达标的样例上是否改善

- [ ] **Step 1: 选取 5 个回归样本**

从 15 个不达标样本中，每类选 1 个：

| 样本 | 原分数 | 原分类 | 预期改善 |
|------|--------|--------|----------|
| `buffer-bloom` | 0.79 | glow ✅ | Lighting 强化 → ≥0.82 |
| `plasma-waves` | 0.71 | glow→flow ❌ | 分类修正 → ≥0.75 |
| `liquid-galss-test` | 0.74 | liquid→flow ❌ | 新 Catalog → ≥0.78 |
| `sparks-drifting` | 0.38 | particle→flow ❌ | 新模板 → ≥0.50 |
| `vortex-street` | 0.71 | liquid→flow ❌ | 分类+模板 → ≥0.75 |

- [ ] **Step 2: 重跑回归测试**

```bash
cd backend && python test_e2e_batch.py --samples buffer-bloom plasma-waves liquid-galss-test sparks-drifting vortex-street --timeout 480
```

先清除旧结果（手动删除这 5 个样本在 test_e2e_results/ 下的目录和 test_results.json 中对应的条目）。

- [ ] **Step 3: 对比前后分数**

```bash
python -c "
import json
r = json.loads(open('test_e2e_results/test_results.json').read())
before = {'buffer-bloom': 0.79, 'plasma-waves': 0.71, 'liquid-galss-test': 0.74, 'sparks-drifting': 0.38, 'vortex-street': 0.71}
for name, old in before.items():
    new = r.get(name, {}).get('score', 0)
    delta = new - old
    print(f'  {name:25s} {old:.2f} → {new:.2f} ({delta:+.2f})')
"
```

**通过标准**: 5 个样本中有 3+ 个分数提升 >= 0.03

- [ ] **Step 4: Commit results**

```bash
git add backend/test_e2e_results/
git commit -m "test: regression validation after prompt optimization"
```

---

## Summary

| Task | Priority | 修改文件 | 预期影响 |
|------|----------|----------|----------|
| Task 1: 扩展 Catalog | P0 | vfx_effect_catalog.md | Catalog 覆盖率 33%→89% |
| Task 2: 修复 Decompose 分类 | P0 | decompose_system.md | 分类准确率 20%→60%+ |
| Task 3: 修复 Lighting 强度 | P0 | generate_system.md, shader_skill_reference.md | 解决 73% 样本亮度不足 |
| Task 4: 新增效果模板 | P1 | shader_skill_reference.md | 为新类型提供算子组合 |
| Task 5: 更新术语表 | P1 | shared_vfx_terminology.md | 新类型术语统一 |
| Task 6: Inspect 维度微调 | P2 | inspect_system.md | 强化 Lighting 低分检测 |
| Task 7: 回归验证 | P0 | (测试脚本) | 验证整体改善效果 |

**执行顺序**: Task 1 → 2 → 3 → 4 → 5 → 6 → 7
**预计耗时**: Task 1-6 约 30 分钟（纯 prompt 修改），Task 7 约 25 分钟（5 样例重跑）
