# DSL 过程化效果扩展方案

> **目标**: 扩展 visual_description DSL，使其能精确描述噪声/流体/光影等过程化效果，缩小 Decompose→Generate 的信息损失
> 
> **原则**: 在架构内解决——增强 DSL 描述能力，不绕过 Decompose

---

## 1. 问题分析

### 当前 DSL 的局限

现有 `visual_description` 的字段设计以 SDF 形状为中心：

```json
{
  "shape_definition": { "sdf_type": "{sdf.circle}", "edge_width": "0.02" },
  "color_definition":  { "primary_rgb": "(0.3, 0.7, 1.0)" },
  "animation_definition": { "animation_type": "pulse", "duration": "3s" }
}
```

这对"一个发光的圆"够用，但对"蓝紫色漩涡状流体"不够——因为漩涡由 **噪声参数 × 域扭曲 × 颜色映射 × 空间分布** 组合决定，现有字段无法编码。

### 从测试数据看缺失

| 低分样例 | Decompose 输出 | Inspect 反馈的关键问题 |
|----------|---------------|----------------------|
| auroras (0.42) | texture_def: "FBM 噪声驱动极光形态" | 纯绿色块，无流动效果，颜色混合缺失 |
| cool-s-distance (0.52) | texture_def: "同心圆波纹" | 颜色颠倒，波纹间距不对 |
| electron (0.68) | texture_def: "FBM 驱动粒子漂移" | 亮度不足，渐变缺失 |
| moon-distance-2d (0.72) | texture_def: "sin(distance*frequency)" | 域扭曲不足 |

**共性**: texture_definition 是自由文本描述，Generate 无法从中精确提取参数。需要**结构化字段**。

---

## 2. DSL 扩展设计

### 新增字段

在 `VisualDescriptionV2` 中新增 3 个结构化字段：

```
现有:
  shape_definition     ← 形状（已有，适合有形状的效果）
  color_definition      ← 颜色
  animation_definition  ← 动画
  background_definition ← 背景

新增:
  texture_definition    ← 纹理/噪声参数（结构化）
  spatial_definition    ← 空间分布/构图
  color_mapping         ← 颜色映射（梯度/调色板）
```

### 2.1 texture_definition（纹理/噪声参数）

```json
{
  "texture_definition": {
    "base_pattern": "{pattern.voronoi}",   // 基础图案类型
    "noise": {
      "type": "{noise.fbm}",               // 噪声类型
      "octaves": 5,                         // 层数
      "frequency": 3.0,                     // 基础频率
      "amplitude": 0.5,                     // 振幅
      "lacunarity": 2.0,                    // 频率倍增
      "gain": 0.5                           // 振幅衰减
    },
    "warp": {
      "enabled": true,
      "strength": 4.0,                      // 扭曲强度
      "iterations": 2,                      // 扭曲级数
      "base_noise": "{noise.fbm}"           // 扭曲用噪声
    },
    "line_pattern": {
      "type": "{line.concentric}",          // 线条类型
      "spacing": "0.02-0.03 UV",            // 间距
      "thickness": "0.005 UV"               // 线宽
    }
  }
}
```

**Catalog Tokens 新增:**

| 分类 | Token | 说明 |
|------|-------|------|
| base_pattern | `{pattern.voronoi}` | Voronoi 细胞 |
| base_pattern | `{pattern.stripe}` | 条纹 |
| base_pattern | `{pattern.concentric}` | 同心圆 |
| base_pattern | `{pattern.dot_grid}` | 点阵 |
| base_pattern | `{pattern.organic}` | 有机形态（FBM 直接输出） |
| base_pattern | `{pattern.none}` | 无纹理 |
| line_pattern | `{line.concentric}` | 同心线 |
| line_pattern | `{line.radial}` | 径向线 |
| line_pattern | `{line.parallel}` | 平行线 |
| line_pattern | `{line.spiral}` | 螺旋线 |
| line_pattern | `{line.contour}` | 等高线 |

**设计原则**: 
- `texture_definition` 与 `shape_definition` 互斥——有明确形状用 shape，无形状用 texture
- noise 和 warp 可组合（FBM + domain warping 是最常见的组合）
- line_pattern 用于 cool-s-distance 那类"线条+扭曲"效果

### 2.2 spatial_definition（空间分布）

```json
{
  "spatial_definition": {
    "coverage": "fullscreen",               // fullscreen / partial / centered
    "density_gradient": {
      "direction": "radial_outward",        // 密度梯度方向
      "center_density": 1.0,                // 中心密度
      "edge_density": 0.2                   // 边缘密度
    },
    "layer_count": 2,                       // 层叠数量
    "layer_blend": "additive"               // additive / mix / screen
  }
}
```

**解决场景**: auroras 需要描述"极光层 + 星空层 + 水面反射层"的多层叠加；electron 需要描述"中心密、边缘疏"的密度梯度。

### 2.3 color_mapping（颜色映射）

```json
{
  "color_mapping": {
    "type": "{cmap.gradient_stops}",        // 映射类型
    "stops": [
      { "position": 0.0, "rgb": "(0.1, 0.4, 1.0)", "label": "深蓝中心" },
      { "position": 0.5, "rgb": "(0.0, 0.8, 0.9)", "label": "青色中层" },
      { "position": 1.0, "rgb": "(0.0, 0.5, 0.4)", "label": "暗绿边缘" }
    ],
    "mapping_source": "noise_value",        // 颜色由什么驱动
    "contrast": "high"                      // low / medium / high
  }
}
```

**Catalog Tokens 新增:**

| Token | 说明 |
|-------|------|
| `{cmap.gradient_stops}` | 渐变色标 |
| `{cmap.palette_function}` | iq 调色板函数 |
| `{cmap.distance_based}` | 基于距离的颜色 |
| `{cmap.angle_based}` | 基于角度的颜色 |
| `{cmap.uniform}` | 单色 |

**解决场景**: auroras 需要精确描述"极光绿→深蓝"的颜色映射；electron 需要描述"中心深蓝→边缘青绿"的径向渐变。当前只有 `primary_rgb` 一个颜色，完全不够。

---

## 3. 各效果类别的 DSL 模式

### 3.1 漩涡/流体 (vortex-street, water-color-blending)

```json
{
  "effect_type": "{effect.warp}",
  "shape_definition": { "sdf_type": "none" },
  "texture_definition": {
    "base_pattern": "{pattern.organic}",
    "noise": { "type": "{noise.fbm}", "octaves": 5, "frequency": 3.0, "amplitude": 0.5 },
    "warp": { "enabled": true, "strength": 4.0, "iterations": 2 }
  },
  "color_mapping": {
    "type": "{cmap.gradient_stops}",
    "stops": [
      { "position": 0.0, "rgb": "(0.15, 0.15, 0.4)" },
      { "position": 0.5, "rgb": "(0.4, 0.4, 0.9)" },
      { "position": 1.0, "rgb": "(0.8, 0.8, 1.0)" }
    ],
    "contrast": "high"
  }
}
```

### 3.2 极光/大气 (auroras)

```json
{
  "effect_type": "{effect.flow}",
  "texture_definition": {
    "base_pattern": "{pattern.organic}",
    "noise": { "type": "{noise.fbm}", "octaves": 5, "frequency": 4.0, "amplitude": 0.6 },
    "warp": { "enabled": true, "strength": 2.0, "iterations": 1 }
  },
  "spatial_definition": {
    "coverage": "fullscreen",
    "layer_count": 3,
    "layer_blend": "additive"
  },
  "color_mapping": {
    "type": "{cmap.gradient_stops}",
    "stops": [
      { "position": 0.0, "rgb": "(0.02, 0.02, 0.05)" },
      { "position": 0.3, "rgb": "(0.1, 0.9, 0.5)" },
      { "position": 0.7, "rgb": "(0.05, 0.05, 0.15)" }
    ],
    "mapping_source": "noise_value",
    "contrast": "high"
  }
}
```

### 3.3 等高线/扭曲 (cool-s-distance, moon-distance-2d)

```json
{
  "effect_type": "{effect.warp}",
  "texture_definition": {
    "base_pattern": "{pattern.none}",
    "line_pattern": {
      "type": "{line.concentric}",
      "spacing": "0.02-0.03 UV",
      "thickness": "0.005 UV"
    },
    "warp": { "enabled": true, "strength": 3.0, "iterations": 1 }
  },
  "color_mapping": {
    "type": "{cmap.distance_based}",
    "stops": [
      { "position": 0.0, "rgb": "(0.3, 0.55, 0.75)" },
      { "position": 1.0, "rgb": "(0.85, 0.55, 0.25)" }
    ]
  }
}
```

### 3.4 粒子场 (electron, happy-diwali-2019)

```json
{
  "effect_type": "{effect.particle}",
  "texture_definition": {
    "base_pattern": "{pattern.dot_grid}",
    "noise": { "type": "{noise.fbm}", "octaves": 3, "frequency": 2.0, "amplitude": 0.3 }
  },
  "spatial_definition": {
    "coverage": "partial",
    "density_gradient": {
      "direction": "radial_outward",
      "center_density": 1.0,
      "edge_density": 0.1
    }
  },
  "color_mapping": {
    "type": "{cmap.gradient_stops}",
    "stops": [
      { "position": 0.0, "rgb": "(0.1, 0.4, 1.0)" },
      { "position": 1.0, "rgb": "(0.0, 0.6, 0.5)" }
    ],
    "mapping_source": "distance"
  }
}
```

---

## 4. 修改清单

### 4.1 state.py — 扩展 TypedDict

```python
class NoiseParams(TypedDict, total=False):
    type: str          # {noise.fbm}, {noise.voronoi}, etc.
    octaves: int
    frequency: float
    amplitude: float
    lacunarity: float
    gain: float

class WarpParams(TypedDict, total=False):
    enabled: bool
    strength: float
    iterations: int
    base_noise: str

class LinePattern(TypedDict, total=False):
    type: str          # {line.concentric}, {line.parallel}, etc.
    spacing: str
    thickness: str

class TextureDefinitionV2(TypedDict, total=False):
    base_pattern: str  # {pattern.organic}, {pattern.voronoi}, etc.
    noise: NoiseParams
    warp: WarpParams
    line_pattern: LinePattern

class DensityGradient(TypedDict, total=False):
    direction: str     # radial_outward, top_to_bottom, etc.
    center_density: float
    edge_density: float

class SpatialDefinitionV2(TypedDict, total=False):
    coverage: str      # fullscreen, partial, centered
    density_gradient: DensityGradient
    layer_count: int
    layer_blend: str   # additive, mix, screen

class ColorStop(TypedDict, total=False):
    position: float    # 0.0 - 1.0
    rgb: str           # "(r, g, b)"
    label: str

class ColorMappingV2(TypedDict, total=False):
    type: str          # {cmap.gradient_stops}, {cmap.palette_function}, etc.
    stops: list[ColorStop]
    mapping_source: str # noise_value, distance, angle
    contrast: str      # low, medium, high

# Add to VisualDescriptionV2:
class VisualDescriptionV2(TypedDict, total=False):
    # ... existing fields ...
    texture_definition: TextureDefinitionV2
    spatial_definition: SpatialDefinitionV2
    color_mapping: ColorMappingV2
```

### 4.2 vfx_effect_catalog.md — 新增 tokens

新增 3 组 token:
- `base_pattern` tokens: 6 个
- `line_pattern` tokens: 5 个
- `cmap` tokens: 5 个

### 4.3 decompose_system.md — 输出指导

新增输出指导：
- 当 `sdf_type = "none"` 时，**必须**填写 `texture_definition`
- `color_mapping.stops` 至少 2 个色标
- 噪声参数必须具体数值，不能写"适中"

### 4.4 generate_system.md — 参数使用指导

新增映射表：
- `noise.frequency → FBM(uv * frequency + iTime * speed)`
- `warp.strength → uv + FBM(uv) * warp_strength`
- `line_pattern.spacing → sin(length(uv - center) * PI / spacing)`
- `color_mapping.stops → mix(color[i], color[i+1], smoothstep(...))`

### 4.5 shader_skill_reference.md — 新增模板

新增 2 个参数化模板：
- `Template: Procedural Noise (参数化 FBM + warp + color mapping)`
- `Template: Line Pattern (参数化 线条 + 域扭曲)`

### 4.6 shared_vfx_terminology.md — 新增术语

新增 noise params、warp params、color mapping 相关术语定义。

### 4.7 inspect_system.md — 新增维度

Texture 维度增加结构化检查：
- noise 参数是否与描述匹配
- color mapping 是否正确应用
- warp 强度是否足够

---

## 5. 预期效果

| 样例 | 当前分数 | 预期提升 | 原因 |
|------|---------|---------|------|
| auroras | 0.42 | 0.60+ | 3 层叠加 + 噪声参数精确化 |
| cool-s-distance | 0.52 | 0.70+ | 线条间距/厚度参数化 + 颜色映射精确 |
| electron | 0.68 | 0.78+ | 密度梯度 + 径向颜色映射 |
| moon-distance-2d | 0.72 | 0.78+ | 同心线参数 + 扭曲强度精确 |
| vortex-street | 0.81 | 0.85+ | 噪声参数精确 + 对比度标注 high |

---

## 6. 实施顺序

1. **state.py** — 新增 TypedDict 定义
2. **catalog** — 新增 tokens
3. **decompose** — 输出指导
4. **generate** — 参数映射 + 模板
5. **skill_reference** — 参数化模板
6. **terminology** — 新增术语
7. **inspect** — 新增检查维度
8. **验证** — 重跑 auroras, vortex-street, cool-s-distance

预计修改 7 个文件，纯 prompt + schema 修改，无需代码逻辑变更。
