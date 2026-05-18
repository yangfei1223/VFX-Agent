# VFX Effect Catalog（Closed Vocabulary）

> 所有 visual_description 的值必须来自此库。**禁止自由发明。**

---

## Effect Types（必须选择其一）

> **Note**: Current scope is 2D/2.5D UI VFX. The 9 effect types listed below are available.

| Token | Effect Name | SDF Technique | ALU |
|-------|-------------|---------------|-----|
| `{effect.ripple}` | 涟漪扩散 | sdCircle + sin(t) | ~80 |
| `{effect.glow}` | 光晕效果 | exp(-d * intensity) | ~40 |
| `{effect.gradient}` | 渐变背景 | mix() + radial/linear | ~20 |
| `{effect.frosted}` | 磨砂玻璃 | blur + noise + alpha | ~150 |
| `{effect.flow}` | 流光效果 | FBM + time offset | ~120 |
| `{effect.liquid}` | 液态/玻璃 | sdVesica/sdCircle + alpha + blur + refract offset | ~120 |
| `{effect.particle}` | 粒子/点阵 | hash grid + point SDF + flicker + FBM drift | ~100 |
| `{effect.warp}` | 域扭曲/视错觉 | FBM domain warp + polar coords + line integral | ~100 |
| `{effect.shape}` | 几何形状 | sdHeart/sdStar/sdBox + solid fill + edge glow | ~40 |

---

## Effect → Operator Mapping

### {effect.ripple} 算子组合
```
d = sdCircle(pos, radius + sin(iTime * speed) * amplitude)
ring = abs(d) - thickness
color = palette * (1.0 - smoothstep(0.0, edge, ring))
```

### {effect.glow} 算子组合
```
d = sdShape(pos, params)
glow = exp(-max(d, 0.0) * intensity)
color = glow_color * glow
```

### {effect.gradient} 算子组合
```
t = clamp(coord, 0.0, 1.0)  // linear/radial/angular
color = mix(color1, color2, t)
```

### {effect.frosted} 算子组合
```
d = sdShape(pos, params)
mask = smoothstep(0.0, edge, d)
blurred = blur(texture, uv, radius)
color = mix(blurred, tint_color, mask * alpha)
noise_detail = FBM(uv * scale) * noise_strength
color += noise_detail
```

### {effect.flow} 算子组合
```
flow_uv = uv + vec2(iTime * speed_x, iTime * speed_y)
noise = FBM(flow_uv * frequency)
color = mix(color1, color2, noise)
brightness = smoothstep(threshold - width, threshold + width, noise)
color *= brightness
```

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

---

## SDF Shape Tokens（参考 iq SDF 2D）

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

## Boolean Operations（参考 iq distfunctions）

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

## Domain Operations（参考 iq distfunctions）

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

## Color/Gradient/Lighting/Noise Tokens

### Color Tokens（预设调色板）

| Token | RGB | Use Case |
|-------|-----|---------|
| `{color.blue}` | (0.2, 0.5, 1.0) | 天空、科技感 |
| `{color.coral}` | (1.0, 0.5, 0.4) | 温暖、情感 |
| `{color.cyan}` | (0.0, 0.8, 0.9) | 清新、现代 |
| `{color.gold}` | (1.0, 0.8, 0.2) | 高端、奖励 |
| `{color.green}` | (0.3, 0.8, 0.4) | 成功、健康 |
| `{color.red}` | (0.9, 0.3, 0.3) | 错误、警告 |

### Gradient Tokens

| Token | Gradient Function | Use Case |
|-------|-------------------|---------|
| `{gradient.linear}` | mix(c1, c2, t) | 线性渐变 |
| `{gradient.radial}` | mix(c1, c2, length(uv)) | 径向渐变 |
| `{gradient.angular}` | mix(c1, c2, atan(uv.y, uv.x)) | 角度渐变 |

### Lighting Tokens

| Token | Lighting Function | Use Case |
|-------|-------------------|---------|
| `{lighting.glow}` | exp(-d * intensity) | 发光效果 |
| `{lighting.fresnel}` | pow(1.0 - dot(n, v), power) | 菲涅尔 |
| `{lighting.rim}` | 1.0 - dot(n, v) | 边缘光 |

### Noise Tokens

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

## Fill Type Tokens

> **Critical**: fill_type 决定形状是实心（填充）还是空心（轮廓）。
> 错误选择会导致视觉效果完全偏离设计参考。

| Token | Meaning | SDF Usage | Visual Result |
|-------|---------|-----------|---------------|
| `{fill.solid}` | 实心填充 | 用 `d` 直接：`1.0 - smoothstep(0, w, d)` | 形状内部完全填满颜色 |
| `{fill.hollow}` | 空心轮廓 | 用 `abs(d)`：`1.0 - smoothstep(0, w, abs(d) - thickness)` | 仅在形状边缘出现细线/环 |

**关键代码差异**：
```glsl
// {fill.solid} 实心 — d 为负时在形状内部
float mask = 1.0 - smoothstep(0.0, 0.02, d);     // 内部=1, 外部=0
float glow = exp(-max(d, 0.0) * 3.0);              // 仅向外发光

// {fill.hollow} 空心 — abs(d) 忽略内外
float mask = 1.0 - smoothstep(0.0, 0.02, abs(d) - thickness); // 仅边缘
float glow = exp(-abs(d) * 3.0);                    // 双向发光
```

**默认值**：如果设计参考中形状看起来有明亮的内部区域，应选择 `{fill.solid}`。

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
| `{bg.black_strict}` | (0.02, 0.02, 0.05) | error <0.05 |
| `{bg.gradient}` | varies | flexible |
| `{bg.flexible}` | any | any |

---

## 使用规则

1. **必须使用 Token**: 所有字段引用此库，不能自由发明值
2. **禁止自由发明**: 不能使用不在库中的值（如 "复杂效果"、"自定义形状"）
3. **量化验证**: 输出前检查所有字段有对应 Token
4. **性能约束**: ALU 总和 ≤256，Texture fetch ≤8