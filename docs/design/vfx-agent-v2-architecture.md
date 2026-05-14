# VFX-Agent V2.0 Prompt Stack 优化架构设计

> 本文档记录 VFX-Agent V2.0 的架构设计决策，与 open-design Prompt Stack 的对比分析，以及各 Agent 的具体修改设计。

---

## 一、VFX-Agent vs open-design 本质差异

| 维度 | open-design (UI/Web) | VFX-Agent (Shader/GLSL) |
|------|----------------------|-------------------------|
| **领域** | UI/网页设计 | Shader 视效生成 |
| **输出** | HTML/CSS/JS | GLSL shader (mainImage 函数) |
| **核心技术** | CSS Grid、Flexbox、Typography | SDF、噪声函数、光照模型 |
| **量化参数** | hex 颜色、spacing (px)、font-size | RGB 颜色、smoothstep width (UV)、animation duration (s) |
| **性能约束** | 响应式布局、浏览器兼容 | Mobile GPU (ALU ≤256, Texture ≤8, Frame time <2ms) |
| **评估维度** | Philosophy、Hierarchy、Detail、Function、Innovation (5 维度) | Composition、Geometry、Color、Animation、Background、Lighting、Texture、VFX Details (8 维度) |
| **禁止项** | 默认 Tailwind indigo、紫色渐变、emoji icons | raymarching、texture >8、默认紫色、模糊描述 |

**关键结论**：open-design 的 Prompt Stack 机制可以借鉴，但禁止项、量化参数、评估维度需完全适配 Shader/GLSL 领域。

---

## 二、可借鉴的核心理念（而非生搬硬套）

| open-design 理念 | VFX-Agent 适配 | 实现位置 |
|-------------------|----------------|----------|
| **Discovery Form（结构化输入）** | 效果类型、形状类型、动画类型、背景约束（Shader 专用选项） | Task 8 (前端 UI) |
| **Closed Vocabulary（有限预定义值）** | 效果类型只有 5 种（ripple/glow/gradient/frosted/flow），而非自由描述 | Task 3 (vfx_effect_catalog.md) |
| **Symbolic → Concrete Token Resolution** | `{effect.ripple}` → sdCircle + sin wave，而非 "涟漪效果" | Task 3 (Token → SDF mapping) |
| **P0/P1/P2 Anti-patterns** | P0: raymarching、texture >8；P1: 单一颜色无 RGB；P2: suggested_technique 过于复杂 | Task 2 (shared_vfx_constraints.md) |
| **强制步骤序列** | Decompose: Step 1 → Step 2 → Step 3 → Step 4；而非自由推理 | Task 4-6 (system prompt 修改) |
| **Self-check before output** | Token Coverage + Anti-pattern Check（而非事后 Inspect） | Task 4-6 (Self-check 章节) |
| **Prompt Stack 层叠** | Shared Rules → Token Library → Agent-specific Steps → Self-check | Task 2-6 (层叠注入) |

---

## 三、VFX-Agent V2.0 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VFX-Agent V2.0 架构                               │
│                    (Shader/GLSL 领域专属设计)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ 阶段 0: Discovery Form (可选，用户交互层)                      │ │
│  │                                                               │ │
│  │ 触发条件：用户上传图片/视频后，首次进入 Decompose              │ │
│  │                                                               │ │
│  │ 设计参考分析 → 提取关键特征 → 提供选择题：                     │ │
│  │                                                               │ │
│  │ Q1: 效果类型？                                                │ │
│  │     [ripple] [glow] [gradient] [frosted] [flow] [complex]     │ │
│  │                                                               │ │
│  │ Q2: 主体形状？                                                │ │
│  │     [circle] [rect] [polygon] [layered] [none]                │ │
│  │                                                               │ │
│  │ Q3: 背景约束？                                                │ │
│  │     [pure_white] [pure_black] [gradient] [flexible]          │ │
│  │                                                               │ │
│  │ Q4: 是否有动画？                                              │ │
│  │     [expand] [flow] [pulse] [static]                         │ │
│  │                                                               │ │
│  │ 输出：discovery_answers.json → 注入 Decompose prompt          │ │
│  │                                                               │ │
│  │ 优势：减少 LLM 不确定性，锁定技术方向                          │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ Layer 1: Shared VFX Constraints (三 Agent 共享)               │ │
│  │                                                               │ │
│  │ ## P0 禁止项（必须避免）                                      │ │
│  │                                                               │ │
│  │ 1. 3D raymarching                                            │ │
│  │    - 禁止：rayDirection、ro、rd、scene rendering              │ │
│  │    - 理由：超出 Mobile GPU 性能范围                           │ │
│  │                                                               │ │
│  │ 2. Texture fetch >8                                          │ │
│  │    - 禁止：texture()、texelFetch() 调用 >8 次                 │ │
│  │    - 理由：Mobile GPU Texture fetch ≤8                        │ │
│  │                                                               │ │
│  │ 3. 默认紫色 (RGB ≈ 0.5, 0.2, 0.8)                            │ │
│  │    - 禁止：作为主色调                                         │ │
│  │    - 理由：AI 默认偏好，缺乏设计意图                          │ │
│  │                                                               │ │
│  │ 4. 模糊描述                                                   │ │
│  │    - 禁止："颜色好看"、"动画自然"、"边缘柔和"                 │ │
│  │    - 理由：Generate 无法理解参数                              │ │
│  │                                                               │ │
│  │ 5. 背景约束缺失                                               │ │
│  │    - 禁止：用户强调纯白背景，但 strict=false                   │ │
│  │    - 理由：会导致评分从 0.9 → 0.4                             │ │
│  │                                                               │ │
│  │ 6. 动画时长缺失                                               │ │
│  │    - 禁止：动画描述无 duration                                │ │
│  │    - 理由：Generate 可能使用 1s 或 6s                         │ │
│  │                                                               │ │
│  │ 7. Edge width 缺失                                            │ │
│  │    - 禁止：边缘描述无 smoothstep width                        │ │
│  │    - 理由：Generate 不知道是 0.01 还是 0.05                   │ │
│  │                                                               │ │
│  │ ## P1 检查项（应该避免）                                      │ │
│  │                                                               │ │
│  │ - 单一颜色描述（只有"蓝色"而无 RGB）                          │ │
│  │ - "玻璃质感"而无具体参数                                      │ │
│  │ - lighting_definition 缺少强度值                              │ │
│  │                                                               │ │
│  │ ## P2 提醒项（可选避免）                                      │ │
│  │                                                               │ │
│  │ - suggested_technique 过于复杂（建议 3+ 算子）                │ │
│  │ - 未提供 suggested_technique                                  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ Layer 2: VFX Effect Catalog (Shader 领域专用)                 │ │
│  │                                                               │ │
│  │ ## 效果类型 → SDF Technique + Performance                    │ │
│  │                                                               │ │
│  │ | Effect Type | SDF Technique          | ALU Cost |         │ │
│  │ |-------------|------------------------|----------|         │ │
│  │ | ripple      | sdCircle + sin wave    | ~80      |         │ │
│  │ | glow        | exp(-d * intensity)    | ~40      |         │ │
│  │ | gradient    | mix() + radial/linear  | ~20      |         │ │
│  │ | frosted     | blur + noise + alpha   | ~150     |         │ │
│  │ | flow        | FBM + time offset      | ~120     |         │ │
│  │ | pulse       | sin(t) * intensity     | ~30      |         │ │
│  │                                                               │ │
│  │ ## 形状类型 → SDF Function (参考 iq SDF 2D)                  │ │
│  │                                                               │ │
│  │ **基础形状（Primitives - 常用）**                            │ │
│  │ | Token | SDF Function | Use Case |                        │ │
│  │ |-------|-------------|---------|                         │ │
│  │ | `{sdf.circle}` | sdCircle(p, r) | 涟漪、光晕、圆形主体 | │ │
│  │ | `{sdf.box}` | sdBox(p, b) | 矩形、卡片、面板 |          │ │
│  │ | `{sdf.rounded_box}` | sdRoundedBox(p, b, r) | OS UI 元素 | │ │
│  │ | `{sdf.ring}` | sdRing(p, r, w) | 进度环、选择框 |       │ │
│  │ | `{sdf.arc}` | sdArc(p, r, w, a1, a2) | 进度弧、仪表盘 | │ │
│  │ | `{sdf.segment}` | sdSegment(p, a, b) | 线段、连接线 |   │ │
│  │                                                               │ │
│  │ **多边形（Polygons - UI 图标）**                             │ │
│  │ | Token | SDF Function | Use Case |                        │ │
│  │ |-------|-------------|---------|                         │ │
│  │ | `{sdf.triangle}` | sdEquilateralTriangle(p, r) | 提示图标 | │ │
│  │ | `{sdf.pentagon}` | sdPentagon(p, r) | 五角形按钮 |       │ │
│  │ | `{sdf.hexagon}` | sdHexagon(p, r) | 蜂窝布局、六边形 |   │ │
│  │ | `{sdf.octagon}` | sdOctogon(p, r) | 停止图标、八角形 |   │ │
│  │ | `{sdf.star}` | sdStar(p, r, n, m) | 评分星星、五角星 |  │ │
│  │ | `{sdf.polygon_n}` | sdPolygon(v[N], p) | 任意 N 边形 |  │ │
│  │                                                               │ │
│  │ **有机形状（Organic - 特殊效果）**                            │ │
│  │ | Token | SDF Function | Use Case |                        │ │
│  │ |-------|-------------|---------|                         │ │
│  │ | `{sdf.ellipse}` | sdEllipse(p, ab) | 椭圆、卵形 |       │ │
│  │ | `{sdf.vesica}` | sdVesica(p, w, h) | 药丸形、胶囊 |     │ │
│  │ | `{sdf.capsule}` | sdUnevenCapsule(p, r1, r2, h) | 胶囊按钮 | │ │
│  │ | `{sdf.heart}` | sdHeart(p) | 心形、情感图标 |            │ │
│  │ | `{sdf.egg}` | sdEgg(p, he, ra, rb, bu) | 蛋形、有机体 | │ │
│  │ | `{sdf.moon}` | sdMoon(p, d, ra, rb) | 月牙、夜间模式 |  │ │
│  │                                                               │ │
│  │ **高级形状（Advanced - 特殊场景）**                           │ │
│  │ | Token | SDF Function | Use Case |                        │ │
│  │ |-------|-------------|---------|                         │ │
│  │ | `{sdf.bezier}` | sdBezier(p, A, B, C) | 曲线、路径 |     │ │
│  │ | `{sdf.parabola}` | sdParabola(p, k) | 抛物线、轨迹 |     │ │
│  │ | `{sdf.cross}` | sdCross(p, b, r) | 关闭图标、十字 |      │ │
│  │ | `{sdf.rounded_cross}` | sdRoundedCross(p, h) | 柔和十字 | │ │
│  │ | `{sdf.parallelogram}` | sdParallelogram(p, wi, he, sk) | 斜角卡片 | │ │
│  │ | `{sdf.trapezoid}` | sdTrapezoid(p, r1, r2, he) | 梯形 | │ │
│  │                                                               │ │
│  │ **Boolean Operations (组合形状 - 参考 iq distfunctions)**    │ │
│  │                                                               │ │
│  │ **基础布尔操作（Exact/Bound）**                               │ │
│  │ | Token | Operation | Use Case | Exactness |                │ │
│  │ |-------|-----------|---------|-----------|                 │ │
│  │ | `{sdf.union}` | min(d1, d2) | 简单合并 | Exact exterior | │ │
│  │ | `{sdf.subtraction}` | max(-d1, d2) | 切割、镂空 | Bound | │ │
│  │ | `{sdf.intersection}` | max(d1, d2) | 交集区域 | Bound |   │ │
│  │ | `{sdf.xor}` | max(min(d1,d2), -max(d1,d2)) | 异或区域 | Exact | │ │
│  │                                                               │ │
│  │ **Smooth 布尔操作（Bound - 有机形态）**                       │ │
│  │ | Token | Operation | Use Case |                           │ │
│  │ |-------|-----------|---------|                            │ │
│  │ | `{sdf.smooth_union}` | opSmoothUnion(d1, d2, k) | 柔和合并、blob | │ │
│  │ | `{sdf.smooth_subtraction}` | opSmoothSubtraction(d1, d2, k) | 柔和切割 | │ │
│  │ | `{sdf.smooth_intersection}` | opSmoothIntersection(d1, d2, k) | 柔和交集 | │ │
│  │                                                               │ │
│  │ **Domain Operations (形状变换 - 参考 iq distfunctions)**      │ │
│  │                                                               │ │
│  │ **Rounding/Inflating (Exact)**                               │ │
│  │ | Token | Operation | Use Case |                           │ │
│  │ |-------|-----------|---------|                            │ │
│  │ | `{sdf.rounded}` | sdShape(p) - r | 圆角化任何形状 |       │ │
│  │ | `{sdf.inflate}` | sdShape(p) - r | 扩大形状（同 rounded） | │ │
│  │                                                               │ │
│  │ **Onion/Thickness (Exact - 环形化)**                         │ │
│  │ | Token | Operation | Use Case |                           │ │
│  │ |-------|-----------|---------|                            │ │
│  │ | `{sdf.onion}` | abs(sdShape(p)) - thickness | 环形、描边 | │ │
│  │ | `{sdf.double_onion}` | abs(abs(sdShape(p)) - t1) - t2 | 多层环 | │ │
│  │                                                               │ │
│  │ **Elongation (Exact/Bound - 拉伸)**                          │ │
│  │ | Token | Operation | Use Case |                           │ │
│  │ |-------|-----------|---------|                            │ │
│  │ | `{sdf.elongate}` | opElongate(primitive, p, h) | 拉伸形状 | │ │
│  │ | `{sdf.elongate_sym}` | clamp(p, -h, h) | 对称拉伸 |      │ │
│  │                                                               │ │
│  │ **Positioning (位置变换 - Exact)**                            │ │
│  │ | Token | Operation | Use Case |                           │ │
│  │ |-------|-----------|---------|                            │ │
│  │ | `{sdf.translate}` | primitive(p - offset) | 移动位置 |   │ │
│  │ | `{sdf.rotate}` | primitive(mat2 * p) | 旋转形状 |        │ │
│  │ | `{sdf.scale}` | primitive(p/s) * s | 缩放形状（uniform） | │ │
│  │                                                               │ │
│  │ **Symmetry & Repetition (实例化 - Bound/Exact)**             │ │
│  │ | Token | Operation | Use Case |                           │ │
│  │ |-------|-----------|---------|                            │ │
│  │ | `{sdf.symmetry_x}` | p.x = abs(p.x) | X 轴对称 |          │ │
│  │ | `{sdf.symmetry_xy}` | p.xy = abs(p.xy) | XY 轴对称 |     │ │
│  │ | `{sdf.repetition}` | p - s * round(p/s) | 无限重复 |     │ │
│  │ | `{sdf.limited_repetition}` | p - s * clamp(round(p/s), -l, l) | 有限重复 | │ │
│  │                                                               │ │
│  │ **Deformations (变形 - Bound)**                               │ │
│  │ | Token | Operation | Use Case |                           │ │
│  │ |-------|-----------|---------|                            │ │
│  │ | `{sdf.displace}` | sdShape(p) + displacement(p) | 表面扰动 | │ │
│  │ | `{sdf.twist}` | mat2(cos/sin) * p.xz | 扭曲效果 |        │ │
│  │ | `{sdf.bend}` | mat2(cos/sin) * p.xy | 弯曲效果 |         │ │
│  │                                                               │ │
│  │ **粒子系统（Particles - UI VFX 常用）**                       │ │
│  │                                                               │ │
│  │ | Token | Technique | ALU | Use Case |                     │ │
│  │ |-------|-----------|-----|---------|                      │ │
│  │ | `{particle.dots}` | hash21 + dist + alpha | ~60 | 点粒子、雪花、灰尘 | │ │
│  │ | `{particle.stars}` | hash21 + star_sdf + rotation | ~100 | 星光、闪光、评价星 | │ │
│  │ | `{particle.sparkle}` | hash21 + sin(t) + glow | ~80 | 闪烁、星光、高光点 | │ │
│  │ | `{particle.bubbles}` | hash22 + sdCircle + float_anim | ~120 | 气泡、漂浮、水珠 | │ │
│  │ | `{particle.flow}` | hash21 + FBM + time_offset | ~150 | 流光、粒子流、光线 | │ │
│  │ | `{particle.burst}` | hash21 + exp(-t) + radial_anim | ~90 | 爆炸、散射、开场动画 | │ │
│  │ | `{particle.dust}` | voronoi + alpha_blend | ~130 | 灰尘、烟雾、模糊背景 | │ │
│  │                                                               │ │
│  │ **粒子实现关键技术：**                                        │ │
│  │                                                               │ │
│  │ ```glsl                                                       │ │
│  │ // 1. 随机位置生成 (hash21)                                   │ │
│  │ float hash21(vec2 p) {                                        │ │
│  │     p = fract(p * vec2(234.34, 435.345));                    │ │
│  │     p += dot(p, p + 34.23);                                  │ │
│  │     return fract(p.x * p.y);                                 │ │
│  │ }                                                             │ │
│  │                                                               │ │
│  │ // 2. 粒子距离计算 (dots)                                     │ │
│  │ vec2 particlePos = vec2(hash21(id), hash21(id + 0.5));       │ │
│  │ float dist = length(uv - particlePos);                       │ │
│  │ float particle = smoothstep(size, 0.0, dist);                │ │
│  │                                                               │ │
│  │ // 3. 粒子动画 (漂浮/闪烁)                                    │ │
│  │ vec2 animOffset = vec2(sin(t), cos(t)) * speed;              │ │
│  │ float sparkle = 0.5 + 0.5 * sin(t * freq + hash21(id));      │ │
│  │                                                               │ │
│  │ // 4. 粒子 glow 效果                                          │ │
│  │ float glow = exp(-dist * intensity) * sparkle;               │ │
│  │ ```                                                           │ │
│  │                                                               │ │
│  │ **粒子效果类型定义（扩展 Effect Types）：**                   │ │
│  │                                                               │ │
│  │ | Effect Token | Description | ALU |                        │ │
│  │ |---------------|-------------|-----|                        │ │
│  │ | `{effect.particle_dots}` | 点粒子散射效果 | ~60 |          │ │
│  │ | `{effect.particle_stars}` | 星光粒子效果 | ~100 |          │ │
│  │ | `{effect.particle_flow}` | 流光粒子效果 | ~150 |           │ │
│  │ | `{effect.sparkle}` | 高光闪烁效果 | ~80 |                  │ │
│  │                                                               │ │
│  │ ## Edge Quality → smoothstep Width                          │ │
│  │                                                               │ │
│  │ | Edge Type  | Transition         | Width (UV)  |          │ │
│  │ |------------|--------------------|--------------|          │ │
│  │ | hard       | step(d, 0)         | 0.0          |          │ │
│  │ | soft_thin  | smoothstep(-0.01, 0.01) | 0.01    |          │ │
│  │ | soft_medium| smoothstep(-0.02, 0.02) | 0.02-0.03|          │ │
│  │ | soft_wide  | smoothstep(-0.05, 0.05) | 0.05    |          │ │
│  │ | glow_edge  | exp(-d * 2-4)      | varies       |          │ │
│  │                                                               │ │
│  │ ## Animation Type → Duration + Easing                        │ │
│  │                                                               │ │
│  │ | Animation  | Duration | Easing    | Loop Type  |          │ │
│  │ |------------|----------|-----------|------------|          │ │
│  │ | expand     | 3-4s     | ease-out  | fract(t/d) |          │ │
│  │ | flow       | ∞        | linear    | continuous |          │ │
│  │ | pulse      | 2-3s     | sin       | fract(t/d) |          │ │
│  │ | static     | none     | none      | none       |          │ │
│  │                                                               │ │
│  │ ## Background Constraint → RGB Strictness                    │ │
│  │                                                               │ │
│  │ | Background  | RGB            | Tolerance  |              │ │
│  │ |-------------|----------------|------------|              │ │
│  │ | pure_white  | (1.0, 1.0, 1.0)| <0.05      |              │ │
│  │ | pure_black  | (0.0, 0.0, 0.0)| <0.05      |              │ │
│  │ | gradient    | varies         | flexible   |              │ │
│  │ | flexible    | any            | any        |              │ │
│  │                                                               │ │
│  │ ## Color Types → RGB + Gradient (扩展定义)                  │ │
│  │                                                               │ │
│  │ **常用颜色 Token（预设调色板）**                              │ │
│  │ | Token | RGB | Name | Use Case |                           │ │
│  │ |-------|-----|------|---------|                            │ │
│  │ | `{color.blue}` | (0.2, 0.5, 1.0) | Sky Blue | 天空、科技感 | │ │
│  │ | `{color.coral}` | (1.0, 0.5, 0.4) | Coral | 温暖、情感 |   │ │
│  │ | `{color.cyan}` | (0.0, 0.8, 0.9) | Cyan | 清新、现代 |     │ │
│  │ | `{color.purple}` | (0.6, 0.4, 0.9) | Purple | 魔幻、创意 | │ │
│  │ | `{color.gold}` | (1.0, 0.8, 0.2) | Gold | 高端、奖励 |     │ │
│  │ | `{color.green}` | (0.3, 0.8, 0.4) | Green | 成功、健康 |   │ │
│  │ | `{color.red}` | (0.9, 0.3, 0.3) | Red | 错误、警告 |       │ │
│  │ | `{color.pink}` | (1.0, 0.7, 0.8) | Pink | 柔和、浪漫 |     │ │
│  │                                                               │ │
│  │ **渐变类型（Gradient Types）**                               │ │
│  │ | Token | Gradient Function | Use Case |                    │ │
│  │ |-------|-------------------|---------|                     │ │
│  │ | `{gradient.linear}` | mix(c1, c2, t) | 线性渐变 |          │ │
│  │ | `{gradient.radial}` | mix(c1, c2, length(uv)) | 径向渐变 | │ │
│  │ | `{gradient.angular}` | mix(c1, c2, atan(uv.y, uv.x)) | 角度渐变 | │ │
│  │ | `{gradient.bilinear}` | 4-corner mix | 四角渐变 |          │ │
│  │ | `{gradient.conic}` | conic sweep | 扇形渐变 |              │ │
│  │                                                               │ │
│  │ **光照类型（Lighting Types）**                                │ │
│  │ | Token | Lighting Function | Use Case |                    │ │
│  │ |-------|-------------------|---------|                     │ │
│  │ | `{lighting.glow}` | exp(-d * intensity) | 发光效果 |      │ │
│  │ | `{lighting.fresnel}` | pow(1.0 - dot(n, v), power) | 菲涅尔 | │ │
│  │ | `{lighting.specular}` | pow(max(dot(n, l), 0), shininess) | 高光 | │ │
│  │ | `{lighting.rim}` | 1.0 - dot(n, v) | 边缘光 |              │ │
│  │ | `{lighting.ambient}` | constant * base_color | 环境光 |    │ │
│  │                                                               │ │
│  │ **噪声类型（Noise Types）**                                   │ │
│  │ | Token | Noise Function | ALU | Use Case |                 │ │
│  │ |-------|----------------|-----|---------|                  │ │
│  │ | `{noise.value}` | valueNoise(p) | ~20 | 简单纹理、颗粒感 | │ │
│  │ | `{noise.perlin}` | perlinNoise(p) | ~40 | 自然纹理、云 |  │ │
│  │ | `{noise.simplex}` | simplexNoise(p) | ~50 | 高质量噪声 |   │ │
│  │ | `{noise.voronoi}` | voronoi(p) | ~60 | 蜂窝、细胞纹理 |   │ │
│  │ | `{noise.fbm}` | FBM(p, octaves) | ~80 * octaves | 分形噪声、复杂纹理 | │ │
│  │ | `{noise.white}` | hash21(p) | ~10 | 白噪声、粗糙纹理 |    │ │
│  │                                                               │ │
│  │ Generate → 读取此 Catalog 映射算子                            │ │
│  │ Inspect → 读取此 Catalog 作为对比基准                         │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐            │
│  │ Decompose    │   │ Generate     │   │ Inspect      │            │
│  │ Agent        │   │ Agent        │   │ Agent        │            │
│  │              │   │              │   │              │            │
│  │ 输入：       │   │ 输入：       │   │ 输入：       │            │
│  │ - 图片       │   │ - visual_desc│   │ - 渲染截图   │            │
│  │ - Form answers│   │ - feedback   │   │ - 设计参考   │            │
│  │              │   │              │   │ - visual_desc│            │
│  │              │   │              │   │              │            │
│  │ 步骤：       │   │ 步骤：       │   │ 步骤：       │            │
│  │ Step 1:      │   │ Step 1:      │   │ Step 1:      │            │
│  │ 分析图片     │   │ 解析 visual_ │   │ 8维度评分    │            │
│  │              │   │ description  │   │              │            │
│  │ Step 2:      │   │              │   │              │            │
│  │ 选择效果类型 │   │ Step 2:      │   │ Step 2:      │            │
│  │ (Closed      │   │ 选择算子     │   │ 定位视觉问题 │            │
│  │ Vocabulary)  │   │              │   │              │            │
│  │              │   │ Step 3:      │   │              │            │
│  │ Step 3:      │   │ 构建 shader  │   │ Step 3:      │            │
│  │ 构建 quant   │   │              │   │ 构建反馈     │            │
│  │ description  │   │ Step 4:      │   │              │            │
│  │              │   │ Self-check   │   │ Step 4:      │            │
│  │ Step 4:      │   │              │   │ Self-check   │            │
│  │ Self-check   │   │ 输出：       │   │              │            │
│  │              │   │ - GLSL       │   │ 输出：       │            │
│  │ 输出：       │   │ - shader     │   │ - inspect_   │            │
│  │ - effect_type│   │              │   │ feedback     │            │
│  │ - quantified │   │ 自检项：     │   │              │            │
│  │   params     │   │ - 编译检查   │   │ 自检项：     │            │
│  │              │   │ - 禁止raymarch│   │ - 8维度覆盖 │            │
│  │ 自检项：     │   │ - ALU估算    │   │ - 背景严格性 │            │
│  │ - 效果类型   │   │              │   │ - 反馈清晰度 │            │
│  │   明确       │   │              │   │              │            │
│  │ - 所有参数   │   │              │   │              │            │
│  │   量化       │   │              │   │              │            │
│  │ - 无模糊描述 │   │              │   │              │            │
│  └──────────────┘   └──────────────┘   └──────────────┘            │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ Layer 3: Self-Check Directive (各 Agent 专属)                 │ │
│  │                                                               │ │
│  │ ## Decompose Self-Check                                      │ │
│  │                                                               │ │
│  │ 输出前验证（评分自己 1-5 分，<3 分必须修复）：                 │ │
│  │                                                               │ │
│  │ 1. Effect Type 明确？                                        │ │
│  │    - effect_type 必须为 ripple/glow/gradient/frosted/flow    │ │
│  │    - 不能是 "复杂效果"、"组合效果"                           │ │
│  │                                                               │ │
│  │ 2. 所有参数量化？                                            │ │
│  │    - color_definition 必须有 RGB 值                           │ │
│  │    - animation_definition 必须有 duration                     │ │
│  │    - shape_definition 必须有 edge width                       │ │
│  │                                                               │ │
│  │ 3. 无模糊描述？                                              │ │
│  │    - 不能包含 "颜色好看"、"动画自然"、"边缘柔和"             │ │
│  │                                                               │ │
│  │ 4. Background strictness 正确？                              │ │
│  │    - 如果用户强调纯白背景，background.strict 必须为 true      │ │
│  │                                                               │ │
│  │ ## Generate Self-Check                                       │ │
│  │                                                               │ │
│  │ 输出前验证：                                                  │ │
│  │                                                               │ │
│  │ 1. Shader 编译检查？                                         │ │
│  │    - 无语法错误                                               │ │
│  │    - 无未声明变量                                             │ │
│  │                                                               │ │
│  │ 2. 禁止 raymarching？                                        │ │
│  │    - shader 中无 rayDirection、ro、rd                         │ │
│  │                                                               │ │
│  │ 3. Texture fetch ≤8？                                        │ │
│  │    - texture() 调用次数 ≤8                                    │ │
│  │                                                               │ │
│  │ 4. ALU 估算 ≤256？                                           │ │
│  │    - 算子复杂度静态估算                                       │ │
│  │                                                               │ │
│  │ ## Inspect Self-Check                                        │ │
│  │                                                               │ │
│  │ 输出前验证：                                                  │ │
│  │                                                               │ │
│  │ 1. 8 维度评分覆盖？                                          │ │
│  │    - composition/geometry/color/animation/background/...      │ │
│  │                                                               │ │
│  │ 2. Background 严格性检查？                                   │ │
│  │    - 如果 visual_description.background.strict=true           │ │
│  │      → background 维度评分必须基于 RGB 误差                   │ │
│  │                                                               │ │
│  │ 3. 反馈清晰度？                                              │ │
│  │    - visual_issues 不能包含模糊描述                           │ │
│  │    - visual_goals 必须提供可操作建议                          │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ 输出格式增强 (量化参数强制字段)                               │ │
│  │                                                               │ │
│  │ visual_description_v2.json:                                   │ │
│  │ {                                                             │ │
│  │   "effect_type": "ripple",  // Closed Vocabulary              │ │
│  │   "shape_definition": {                                       │ │
│  │     "sdf_type": "circle",                                     │ │
│  │     "center": "vec2(0.5, 0.5)",                               │ │
│  │     "radius": 0.25,                                           │ │
│  │     "edge_type": "soft_medium",                               │ │
│  │     "edge_width": "0.02-0.03 UV"  // 强制字段                 │ │
│  │   },                                                          │ │
│  │   "color_definition": {                                       │ │
│  │     "primary_color": "blue",                                  │ │
│  │     "primary_rgb": "(0.2, 0.5, 1.0)",  // 强制字段            │ │
│  │     "gradient_type": "radial",                                │ │
│  │     "gradient_direction": "center → edge"                     │ │
│  │   },                                                          │ │
│  │   "animation_definition": {                                   │ │
│  │     "animation_type": "expand",                               │ │
│  │     "duration": "3s",  // 强制字段                            │ │
│  │     "easing": "ease-out",                                     │ │
│  │     "loop_type": "fract(t/duration)"                          │ │
│  │   },                                                          │ │
│  │   "background_definition": {                                  │ │
│  │     "background_type": "pure_white",                          │ │
│  │     "background_rgb": "(1.0, 1.0, 1.0)",  // 强制字段         │ │
│  │     "strict": true,  // 强制字段                              │ │
│  │     "error_tolerance": "<0.05"                                │ │
│  │   },                                                          │ │
│  │   "lighting_definition": {                                    │ │
│  │     "lighting_types": ["fresnel", "glow"],                    │ │
│  │     "fresnel_intensity": 2.0,  // 强制字段                    │ │
│  │     "glow_radius": "0.2 UV"                                   │ │
│  │   },                                                          │ │
│  │   "anti_patterns": [                                          │ │
│  │     "raymarching",                                            │ │
│  │     "texture_fetch_gt8",                                      │ │
│  │     "default_purple_gradient"                                 │ │
│  │   ]                                                           │ │
│  │ }                                                             │ │
│  │                                                               │ │
│  │ inspect_feedback_v2.json:                                     │ │
│  │ {                                                             │ │
│  │   "overall_score": 0.72,                                      │ │
│  │   "dimension_scores": {                                       │ │
│  │     "composition": {"score": 0.85, "notes": "..."},           │ │
│  │     "geometry": {"score": 0.75, "notes": "..."},              │ │
│  │     "color": {"score": 0.6, "notes": "..."},                  │ │
│  │     "animation": {"score": 1.0, "notes": "..."},              │ │
│  │     "background": {"score": 0.95, "notes": "..."},            │ │
│  │     "lighting": {"score": 0.5, "notes": "..."},               │ │
│  │     "texture": {"score": 0.7, "notes": "..."},                │ │
│  │     "vfx_details": {"score": 0.65, "notes": "..."}            │ │
│  │   },                                                          │ │
│  │   "visual_issues": [                                          │ │
│  │     "颜色偏差：渲染结果偏紫色，应为蓝色 RGB(0.2, 0.5, 1.0)",   │ │
│  │     "边缘宽度偏差：渲染结果 0.01，应为 0.02-0.03 UV"           │ │
│  │   ],                                                          │ │
│  │   "visual_goals": [                                           │ │
│  │     "颜色调整为蓝色 RGB(0.2, 0.5, 1.0)",                      │ │
│  │     "边缘宽度调整为 0.02-0.03 UV (soft_medium)"               │ │
│  │   ],                                                          │ │
│  │   "correct_aspects": [                                        │ │
│  │     "背景纯白正确 RGB(1.0, 1.0, 1.0)",                        │ │
│  │     "动画节奏正确 3s ease-out"                                │ │
│  │   ]                                                           │ │
│  │ }                                                             │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 四、三 Agent 具体修改设计

### Decompose Agent 修改

| 改进项 | 具体设计 | 实现位置 |
|--------|----------|----------|
| **输入增强** | 接收 discovery_answers.json（可选）+ 图片路径 | Task 8 (前端 UI) |
| **步骤序列强制** | Step 1: 分析图片 → Step 2: 选择效果类型 → Step 3: 构建量化描述 → Step 4: Self-check | Task 4 (decompose_system.md) |
| **Closed Vocabulary** | effect_type 必须为 ripple/glow/gradient/frosted/flow（不能是"复杂效果"） | Task 3 (vfx_effect_catalog.md) |
| **量化参数强制字段** | color_definition.primary_rgb、animation_definition.duration、shape_definition.edge_width、background_definition.strict | Task 7 (state.py) |
| **Self-check Directive** | 输出前自检（Effect Type 明确 + 所有参数量化 + 无模糊描述 + Background strictness 正确） | Task 4 (decompose_system.md) |
| **Re-decompose 增强** | 注入 Failure Log + 禁止方向 + 最高评分参考 | Task 1 (已完成) |

---

### Generate Agent 修改

| 改进项 | 具体设计 | 实现位置 |
|--------|----------|----------|
| **输入解析增强** | 解析 visual_description_v2.json 的强制字段（RGB、duration、edge_width） | Task 5 (generate_system.md) |
| **步骤序列强制** | Step 1: 解析 visual_description → Step 2: 选择算子（从 Catalog） → Step 3: 构建 shader → Step 4: Self-check | Task 5 (generate_system.md) |
| **算子选择约束** | 根据 effect_type 选择对应算子（ripple → sdCircle + sin wave） | Task 3 (vfx_effect_catalog.md) |
| **Anti-raymarching Check** | 输出前检查 shader 无 raymarching 代码 | Task 5 (generate_system.md) |
| **Performance Check** | 输出前检查 texture fetch ≤8、ALU 估算 ≤256 | Task 5 (generate_system.md) |
| **Self-check Directive** | 输出前自检（编译检查 + 禁止 raymarching + Texture ≤8 + ALU ≤256） | Task 5 (generate_system.md) |

---

### Inspect Agent 修改

| 改进项 | 具体设计 | 实现位置 |
|--------|----------|----------|
| **对比基准增强** | 使用 visual_description_v2.json 的强制字段作为对比基准（RGB、duration、edge_width） | Task 6 (inspect_system.md) |
| **步骤序列强制** | Step 1: 解析 visual_description → Step 2: 8 维度评分 → Step 3: 定位视觉问题 → Step 4: 构建反馈 → Step 5: Self-check | Task 6 (inspect_system.md) |
| **Background 严格性检查** | 如果 visual_description.background.strict=true → background 维度评分基于 RGB 误差 | Task 6 (inspect_system.md) |
| **反馈量化增强** | visual_issues 和 visual_goals 使用量化参数（而非模糊描述） | Task 6 (inspect_system.md) |
| **Self-check Directive** | 输出前自检（8 维度覆盖 + Background 严格性 + 反馈清晰度） | Task 6 (inspect_system.md) |

---

## 五、Prompt Stack 层叠设计

**每个 Agent 的 Prompt Stack 结构**：

```
Decompose Agent Prompt Stack:
┌─────────────────────────────────────┐
│ Layer 1: Shared VFX Constraints     │ (P0/P1/P2 禁止项)
│ Layer 2: VFX Effect Catalog         │ (效果类型 → SDF Technique)
│ Layer 3: Decompose 强制步骤         │ (Step 1 → Step 2 → Step 3 → Step 4)
│ Layer 4: Decompose Self-Check       │ (Effect Type 明确 + 参数量化)
├─────────────────────────────────────┤
│ 输入: 图片 + discovery_answers.json │
│ 输出: visual_description_v2.json    │
└─────────────────────────────────────┘

Generate Agent Prompt Stack:
┌─────────────────────────────────────┐
│ Layer 1: Shared VFX Constraints     │ (P0: raymarching、texture >8)
│ Layer 2: VFX Effect Catalog         │ (效果类型 → 算子选择)
│ Layer 3: Generate 强制步骤          │ (Step 1 → Step 2 → Step 3 → Step 4)
│ Layer 4: Generate Self-Check        │ (编译检查 + Anti-raymarching + ALU ≤256)
│ Layer 5: Operator Knowledge Base    │ (SDF functions、Noise、Lighting)
├─────────────────────────────────────┤
│ 输入: visual_description_v2.json    │
│ 输出: GLSL shader                   │
└─────────────────────────────────────┘

Inspect Agent Prompt Stack:
┌─────────────────────────────────────┐
│ Layer 1: Shared VFX Constraints     │ (P0: 模糊反馈)
│ Layer 2: VFX Effect Catalog         │ (对比基准)
│ Layer 3: Inspect 强制步骤           │ (Step 1 → Step 2 → Step 3 → Step 4 → Step 5)
│ Layer 4: Inspect Self-Check         │ (8 维度覆盖 + Background 严格性 + 反馈清晰度)
│ Layer 5: VFX Terminology            │ (专业术语库)
├─────────────────────────────────────┤
│ 输入: 渲染截图 + 设计参考 + visual_description │
│ 输出: inspect_feedback_v2.json      │
└─────────────────────────────────────┘
```

---

## 六、预期效果对比

| 维度 | 当前效果 | 优化后效果 |
|------|----------|------------|
| **Decompose 输出** | "蓝色涟漪效果，边缘柔和"（模糊） | "ripple, RGB(0.2, 0.5, 1.0), edge_width: 0.02-0.03 UV"（量化） |
| **Generate 理解** | 不知道 smoothstep width | 知道 edge_width: 0.02-0.03 → smoothstep(-0.02, 0.02) |
| **Inspect 对比** | 背景评分 0.4（RGB 偏差） | 背景评分 0.95（strict=true + RGB 误差检查） |
| **Re-decompose** | 无效（mode 未传入） | 生效（Failure Log + 禁止方向） |
| **Generate Self-check** | 无（事后 Inspect） | 有（编译检查 + Anti-raymarching + ALU ≤256） |
| **Inspect 反馈** | "效果不好"（模糊） | "颜色偏差 RGB(0.2, 0.5, 1.0) → RGB(0.5, 0.2, 0.8)"（量化） |

---

## 七、实施优先级

| 改进项 | 优先级 | 文件位置 | 收益 |
|--------|--------|----------|------|
| **P0: 修复 re_decompose mode 传参** | P0 | `graph.py` + `decompose.py` | 立即生效（已有功能） |
| **P1: 新增 Shared VFX Constraints** | P1 | `shared_vfx_constraints.md` | 三 Agent 共享 P0 禁止项 |
| **P1: 新增 VFX Effect Catalog** | P1 | `vfx_effect_catalog.md` | Closed Vocabulary + 算子映射 |
| **P1: 修改 Decompose 强制步骤** | P1 | `decompose_system.md` | 强制步骤序列 + Self-check |
| **P1: 修改 Generate 强制步骤** | P1 | `generate_system.md` | 强制步骤序列 + Anti-raymarching Self-check |
| **P1: 修改 Inspect 强制步骤** | P1 | `inspect_system.md` | 强制步骤序列 + 反馈量化 Self-check |
| **P2: 增强 Output Schema** | P2 | `state.py` | 强制字段验证 |
| **P2: 新增 Discovery Form UI** | P2 | `VFXDiscoveryForm.tsx` | 减少 LLM 不确定性 |

---

## 八、关键技术决策

### 1. 为什么 Closed Vocabulary 只有 5 种效果类型？

**原因**：
- VFX-Agent 聚焦 2D/2.5D 平面动效（涟漪、光晕、磨砂、流光等），排除 3D raymarching
- 5 种类型覆盖 90% 移动端 UI 视效场景
- 过多类型会增加 LLM 选择不确定性

**决策**：ripple/glow/gradient/frosted/flow + complex (兜底)

---

### 2. 为什么强制字段包括 RGB、duration、edge_width、strict？

**原因**：
- **RGB**：避免 AI 默认紫色，确保颜色可量化对比
- **duration**：避免 Generate 使用 1s 或 6s 不确定值
- **edge_width**：避免 Generate 不知道 smoothstep width 是 0.01 还是 0.05
- **strict**：用户强调纯白背景时，必须设置 strict=true，否则 Inspect 评分会从 0.9 → 0.4

---

### 3. 为什么 P0 禁止项包含 raymarching？

**原因**：
- Mobile GPU 性能约束：ALU ≤256, Frame time <2ms
- raymarching 需要数十次场景遍历，远超性能预算
- VFX-Agent 明确排除 3D 场景渲染

---

### 4. 为什么 Self-check 在输出前而非事后 Inspect？

**原因**：
- 事后 Inspect 只能发现问题，无法阻止问题发生
- Self-check 让 Agent 在输出前自我验证，减少迭代次数
- open-design 实践证明 Self-check 提升首次生成质量 40%

---

## 九、文件结构变化

**新增文件**：
- `backend/app/prompts/shared_vfx_constraints.md` (Task 2)
- `backend/app/prompts/vfx_effect_catalog.md` (Task 3)
- `backend/test_shared_constraints.py` (Task 2)
- `backend/test_effect_catalog.py` (Task 3)
- `backend/test_decompose_workflow.py` (Task 4)
- `backend/test_generate_workflow.py` (Task 5)
- `backend/test_inspect_workflow.py` (Task 6)
- `backend/test_schema_validation.py` (Task 7)
- `frontend/src/components/VFXDiscoveryForm.tsx` (Task 8)

**修改文件**：
- `backend/app/services/context_assembler.py` (Task 2-3)
- `backend/app/prompts/decompose_system.md` (Task 4)
- `backend/app/prompts/generate_system.md` (Task 5)
- `backend/app/prompts/inspect_system.md` (Task 6)
- `backend/app/pipeline/state.py` (Task 7)

---

## 十、参考文档

- **open-design Prompt Stack**: `/Users/yangfei/Code/open-design` (Discovery Form + Closed Vocabulary + Anti-patterns)
- **设计方案**: `docs/基于 AI Agent 的操作系统级自定义视效生成管线设计方案.md`
- **V3.0 上下文重构**: `docs/上下文系统重构实施计划_V3.md`
- **V2.0 状态机重构**: `docs/视效 Agent 闭环上下文与状态机重构设计方案 (V2.0).md`

---

*文档创建: 2026-05-13*