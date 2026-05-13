# VFX Effect Catalog (Closed Vocabulary)

所有 visual_description 的值必须来自此库。**禁止自由发明。**

> 参考：docs/design/vfx-agent-v2-architecture.md（完整设计）
> 参考：iq SDF 2D (https://iquilezles.org/articles/distfunctions2d/)
> 参考：iq SDF Operations (https://iquilezles.org/articles/distfunctions/)

---

## Effect Types (必须选择其一)

### 基础效果（5 种）

| Token | Effect Name | SDF Technique | ALU |
|-------|-------------|---------------|-----|
| `{effect.ripple}` | 涟漪扩散 | sdCircle + sin(t) | ~80 |
| `{effect.glow}` | 光晕效果 | exp(-d * intensity) | ~40 |
| `{effect.gradient}` | 渐变背景 | mix() + radial/linear | ~20 |
| `{effect.frosted}` | 磨砂玻璃 | blur + noise + alpha | ~150 |
| `{effect.flow}` | 流光效果 | FBM + time offset | ~120 |

### 粒子效果（4 种）

| Token | Description | ALU |
|-------|-------------|-----|
| `{effect.particle_dots}` | 点粒子散射效果 | ~60 |
| `{effect.particle_stars}` | 星光粒子效果 | ~100 |
| `{effect.sparkle}` | 高光闪烁效果 | ~80 |
| `{effect.particle_flow}` | 流光粒子效果 | ~150 |

---

## SDF Shape Tokens (参考 iq SDF 2D)

### 基础形状（Primitives - 常用）

| Token | SDF Function | Use Case |
|-------|-------------|---------|
| `{sdf.circle}` | sdCircle(p, r) | 涟漪、光晕、圆形主体 |
| `{sdf.box}` | sdBox(p, b) | 矩形、卡片、面板 |
| `{sdf.rounded_box}` | sdRoundedBox(p, b, r) | OS UI 元素 |
| `{sdf.ring}` | sdRing(p, r, w) | 进度环、选择框 |
| `{sdf.arc}` | sdArc(p, r, w, a1, a2) | 进度弧、仪表盘 |
| `{sdf.segment}` | sdSegment(p, a, b) | 线段、连接线 |

### 多边形（Polygons - UI 图标）

| Token | SDF Function | Use Case |
|-------|-------------|---------|
| `{sdf.triangle}` | sdEquilateralTriangle(p, r) | 提示图标 |
| `{sdf.pentagon}` | sdPentagon(p, r) | 五角形按钮 |
| `{sdf.hexagon}` | sdHexagon(p, r) | 蜂窝布局、六边形 |
| `{sdf.octagon}` | sdOctogon(p, r) | 停止图标、八角形 |
| `{sdf.star}` | sdStar(p, r, n, m) | 评分星星、五角星 |

### 有机形状（Organic - 特殊效果）

| Token | SDF Function | Use Case |
|-------|-------------|---------|
| `{sdf.ellipse}` | sdEllipse(p, ab) | 椭圆、卵形 |
| `{sdf.vesica}` | sdVesica(p, w, h) | 药丸形、胶囊 |
| `{sdf.capsule}` | sdUnevenCapsule(p, r1, r2, h) | 胶囊按钮 |
| `{sdf.heart}` | sdHeart(p) | 心形、情感图标 |

---

## Boolean Operations (参考 iq distfunctions)

### 基础布尔操作

| Token | Operation | Use Case |
|-------|-----------|---------|
| `{sdf.union}` | min(d1, d2) | 简单合并 |
| `{sdf.subtraction}` | max(-d1, d2) | 切割、镂空 |
| `{sdf.intersection}` | max(d1, d2) | 交集区域 |
| `{sdf.xor}` | max(min(d1,d2), -max(d1,d2)) | 异或区域 |

### Smooth 布尔操作

| Token | Operation | Use Case |
|-------|-----------|---------|
| `{sdf.smooth_union}` | opSmoothUnion(d1, d2, k) | 柔和合并、blob |
| `{sdf.smooth_subtraction}` | opSmoothSubtraction(d1, d2, k) | 柔和切割 |
| `{sdf.smooth_intersection}` | opSmoothIntersection(d1, d2, k) | 柔和交集 |

---

## Domain Operations (参考 iq distfunctions)

### Rounding/Onion

| Token | Operation | Use Case |
|-------|-----------|---------|
| `{sdf.rounded}` | sdShape(p) - r | 圆角化任何形状 |
| `{sdf.onion}` | abs(sdShape(p)) - thickness | 环形、描边 |

### Symmetry/Repetition

| Token | Operation | Use Case |
|-------|-----------|---------|
| `{sdf.symmetry_x}` | p.x = abs(p.x) | X 轴对称 |
| `{sdf.symmetry_xy}` | p.xy = abs(p.xy) | XY 轴对称 |
| `{sdf.repetition}` | p - s * round(p/s) | 无限重复 |
| `{sdf.limited_repetition}` | p - s * clamp(round(p/s), -l, l) | 有限重复 |

---

## Particle Tokens

| Token | Technique | Use Case |
|-------|-----------|---------|
| `{particle.dots}` | hash21 + dist + alpha | 点粒子、雪花、灰尘 |
| `{particle.stars}` | hash21 + star_sdf + rotation | 星光、闪光 |
| `{particle.sparkle}` | hash21 + sin(t) + glow | 闪烁、高光点 |
| `{particle.bubbles}` | hash22 + sdCircle + float_anim | 气泡、漂浮 |
| `{particle.flow}` | hash21 + FBM + time_offset | 流光、粒子流 |
| `{particle.burst}` | hash21 + exp(-t) + radial_anim | 爆炸、散射 |
| `{particle.dust}` | voronoi + alpha_blend | 灰尘、烟雾 |

---

## Color Tokens（预设调色板）

| Token | RGB | Use Case |
|-------|-----|---------|
| `{color.blue}` | (0.2, 0.5, 1.0) | 天空、科技感 |
| `{color.coral}` | (1.0, 0.5, 0.4) | 温暖、情感 |
| `{color.cyan}` | (0.0, 0.8, 0.9) | 清新、现代 |
| `{color.gold}` | (1.0, 0.8, 0.2) | 高端、奖励 |
| `{color.green}` | (0.3, 0.8, 0.4) | 成功、健康 |
| `{color.red}` | (0.9, 0.3, 0.3) | 错误、警告 |

---

## Gradient Tokens

| Token | Gradient Function | Use Case |
|-------|-------------------|---------|
| `{gradient.linear}` | mix(c1, c2, t) | 线性渐变 |
| `{gradient.radial}` | mix(c1, c2, length(uv)) | 径向渐变 |
| `{gradient.angular}` | mix(c1, c2, atan(uv.y, uv.x)) | 角度渐变 |

---

## Lighting Tokens

| Token | Lighting Function | Use Case |
|-------|-------------------|---------|
| `{lighting.glow}` | exp(-d * intensity) | 发光效果 |
| `{lighting.fresnel}` | pow(1.0 - dot(n, v), power) | 菲涅尔 |
| `{lighting.rim}` | 1.0 - dot(n, v) | 边缘光 |

---

## Noise Tokens

| Token | Noise Function | ALU | Use Case |
|-------|----------------|-----|---------|
| `{noise.value}` | valueNoise(p) | ~20 | 简单纹理 |
| `{noise.perlin}` | perlinNoise(p) | ~40 | 自然纹理、云 |
| `{noise.simplex}` | simplexNoise(p) | ~50 | 高质量噪声 |
| `{noise.voronoi}` | voronoi(p) | ~60 | 蜂窝纹理 |
| `{noise.fbm}` | FBM(p, octaves) | ~80*octaves | 分形噪声 |

---

## Edge Tokens

| Token | Transition | Width |
|-------|------------|-------|
| `{edge.hard}` | step(d, 0) | 0.0 |
| `{edge.soft_thin}` | smoothstep(-0.01, 0.01) | 0.01 |
| `{edge.soft_medium}` | smoothstep(-0.02, 0.02) | 0.02-0.03 |
| `{edge.soft_wide}` | smoothstep(-0.05, 0.05) | 0.05 |
| `{edge.glow}` | exp(-d * 3.0) | varies |

---

## Animation Tokens

| Token | Duration | Easing |
|-------|----------|--------|
| `{anim.expand_3s}` | 3s | ease-out |
| `{anim.expand_4s}` | 4s | ease-out |
| `{anim.pulse_2s}` | 2s | sin |
| `{anim.flow}` | ∞ | linear |
| `{anim.static}` | none | none |

---

## Background Tokens

| Token | RGB | Strictness |
|-------|-----|------------|
| `{bg.white_strict}` | (1.0, 1.0, 1.0) | error <0.05 |
| `{bg.black_strict}` | (0.0, 0.0, 0.0) | error <0.05 |
| `{bg.gradient}` | varies | flexible |
| `{bg.flexible}` | any | any |

---

## 使用规则

1. **必须使用 Token**：所有字段引用此库，不能自由发明值
2. **禁止自由发明**：不能使用不在库中的值（如 "复杂效果"、"自定义形状"）
3. **量化验证**：输出前检查所有字段有对应 Token
4. **性能约束**：ALU 总和 ≤256，Texture fetch ≤8

---

## 强制字段（Required Fields）

Decompose Agent 输出的 visual_description 必须包含：

- `color_definition.primary_rgb`（如 `(0.2, 0.5, 1.0)`）
- `animation_definition.duration`（如 `3s`）
- `shape_definition.edge_width`（如 `0.02-0.03 UV`）
- `background_definition.strict`（true/false）

---

*参考文档：docs/design/vfx-agent-v2-architecture.md*