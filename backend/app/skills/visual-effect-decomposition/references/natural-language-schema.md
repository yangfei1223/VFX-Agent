# 自然语言视效描述规范 (Natural Language Visual Effect Schema)

替代 DSL AST，采用自然语言分层结构化描述，保证完备性同时提升 LLM 理解效率。

---

## 一、核心设计原则

| 原 DSL 方案 | 新自然语言方案 |
|-------------|----------------|
| AST 结构 (operators/topology) | 分层语义描述 (visual/shape/color/animation/background) |
| 算子 ID 引用约束 | 建议技术方向（不强制） |
| 强制参数 Schema | 自然语言描述（灵活适配） |
| LLM 需解析 AST | LLM 直接理解语义 |

---

## 二、输出结构定义

### 必需字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `effect_name` | string | 效果名称（简洁描述） |
| `visual_identity` | object | 效果整体标识 |
| `shape_definition` | object | 形状定义 |
| `color_definition` | object | 颜色定义 |
| `animation_definition` | object | 动画定义 |
| `background_definition` | object | 背景定义（重点关注） |
| `constraints` | object | 性能约束 |

### 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `lighting_definition` | object | 光影定义 |
| `texture_definition` | object | 纹理定义 |
| `vfx_definition` | object | 特效定义 |
| `important_notes` | list[string] | 关键注意事项 |

---

## 三、字段详细规范

### 3.1 visual_identity（效果整体标识）

```json
{
  "visual_identity": {
    "summary": "一句话完整描述效果（包含形状、颜色、动画、背景）",
    "keywords": ["关键词1", "关键词2", "..."]
  }
}
```

**示例**：
```json
{
  "visual_identity": {
    "summary": "蓝色圆形涟漪从中心向外扩散，配合径向渐变光晕，纯白色背景",
    "keywords": ["涟漪", "扩散", "光晕", "径向渐变", "白色背景"]
  }
}
```

---

### 3.2 shape_definition（形状定义）

```json
{
  "shape_definition": {
    "description": "形状的自然语言描述（类型、边缘、比例、位置）",
    "suggested_technique": "建议的实现技术方向（可选）"
  }
}
```

**描述要点**：
- 形状类型（圆形/矩形/多边形/无形状）
- 边缘质量（锐利/柔和/描边）
- 比例大小（占画面比例、具体尺寸）
- 位置布局（中心/偏移/分布）

**示例**：
```json
{
  "shape_definition": {
    "description": "圆形涟漪，边缘柔和过渡，无描边，占画面中心约 30%",
    "suggested_technique": "可使用圆形 SDF + smoothstep 边缘过渡"
  }
}
```

---

### 3.3 color_definition（颜色定义）

```json
{
  "color_definition": {
    "description": "颜色的自然语言描述（主色、渐变、饱和度）",
    "suggested_technique": "建议的实现技术方向（可选）"
  }
}
```

**描述要点**：
- 主色调（颜色名称 + RGB 参考值）
- 渐变类型（线性/径向/无渐变）
- 渐变方向（从哪到哪）
- 颜色层次（单色/双色/多色）

**示例**：
```json
{
  "color_definition": {
    "description": "蓝色系主色 (RGB 约 0.2, 0.5, 1.0)，径向渐变从中心向外，配合光晕效果",
    "suggested_technique": "径向渐变 mix() + 光晕叠加"
  }
}
```

---

### 3.4 animation_definition（动画定义）

```json
{
  "animation_definition": {
    "description": "动画的自然语言描述（类型、方向、节奏、循环）",
    "suggested_technique": "建议的实现技术方向（可选）"
  }
}
```

**描述要点**：
- 动画类型（扩散/流动/呼吸/旋转/无动画）
- 运动方向（从哪到哪）
- 缓动曲线（ease-in/ease-out/线性）
- 循环周期（时长、无缝衔接）

**示例**：
```json
{
  "animation_definition": {
    "description": "涟漪扩散动画，从中心向外，ease-out 缓出曲线，约 3 秒无缝循环",
    "suggested_technique": "时间驱动 + 半径随时间扩展 + fract() 循环"
  }
}
```

---

### 3.5 background_definition（背景定义）

**⚠️ 重点关注字段**

```json
{
  "background_definition": {
    "description": "背景的自然语言描述（颜色、纹理、透明度）",
    "important": "关键约束（如有）"
  }
}
```

**描述要点**：
- 背景颜色（纯色/渐变/具体 RGB）
- 背景纹理（有无噪声/图案）
- 透明度（透明/半透明/不透明）
- 主体与背景关系

**示例**：
```json
{
  "background_definition": {
    "description": "纯白色背景 (RGB 1.0, 1.0, 1.0)，无纹理，不透明",
    "important": "背景必须纯白，不可有形状、阴影或渐变"
  }
}
```

---

### 3.6 lighting_definition（光影定义）

```json
{
  "lighting_definition": {
    "description": "光影效果描述（高光、阴影、光晕）",
    "suggested_technique": "建议技术方向（可选）"
  }
}
```

**示例**：
```json
{
  "lighting_definition": {
    "description": "边缘光晕效果，中等强度，向外扩散约 20 像素",
    "suggested_technique": "Glow 算子 + 指数衰减"
  }
}
```

---

### 3.7 constraints（性能约束）

```json
{
  "constraints": {
    "max_alu": 256,
    "target_fps": 60,
    "platform": "mobile"
  }
}
```

---

## 四、完整输出示例

### 示例 1：涟漪扩散效果

```json
{
  "effect_name": "涟漪扩散效果",
  
  "visual_identity": {
    "summary": "蓝色圆形涟漪从中心向外扩散，配合径向渐变光晕，纯白色背景",
    "keywords": ["涟漪", "扩散", "光晕", "径向渐变", "白色背景"]
  },
  
  "shape_definition": {
    "description": "圆形涟漪，边缘柔和过渡（约 2-3 像素宽度），无描边，占画面中心约 30%",
    "suggested_technique": "圆形 SDF + smoothstep 边缘过渡"
  },
  
  "color_definition": {
    "description": "蓝色系主色 (RGB 约 0.2, 0.5, 1.0)，径向渐变从中心向外（中心深蓝 → 边缘浅蓝），配合光晕",
    "suggested_technique": "mix() 径向渐变 + 光晕叠加"
  },
  
  "animation_definition": {
    "description": "涟漪扩散动画，从中心向外扩散，ease-out 缓出曲线，约 3 秒无缝循环",
    "suggested_technique": "iTime 驱动 + 半径随时间扩展 + fract() 循环"
  },
  
  "background_definition": {
    "description": "纯白色背景 (RGB 1.0, 1.0, 1.0)，无纹理，无噪声，不透明",
    "important": "背景必须纯白，不可有任何形状、阴影或渐变"
  },
  
  "lighting_definition": {
    "description": "边缘光晕效果，中等强度（约 0.5），向外扩散约 20 像素",
    "suggested_technique": "Glow 算子 + 指数衰减"
  },
  
  "constraints": {
    "max_alu": 200,
    "target_fps": 60
  },
  
  "important_notes": [
    "背景纯白是关键要求，不可有任何杂质",
    "边缘过渡必须柔和，不可锐利硬切"
  ]
}
```

---

### 示例 2：磨砂玻璃效果

```json
{
  "effect_name": "磨砂玻璃效果",
  
  "visual_identity": {
    "summary": "半透明磨砂玻璃效果，模糊背景，配合噪声纹理",
    "keywords": ["磨砂", "模糊", "半透明", "噪声", "玻璃"]
  },
  
  "shape_definition": {
    "description": "无固定形状，全屏效果",
    "suggested_technique": "全屏 shader"
  },
  
  "color_definition": {
    "description": "无主色调，依赖底层内容",
    "suggested_technique": "Texture sampling + 模糊"
  },
  
  "animation_definition": {
    "description": "静态效果，无动画"
  },
  
  "background_definition": {
    "description": "应用模糊和噪声纹理，模拟磨砂质感",
    "suggested_technique": "Gaussian blur + 噪声纹理叠加"
  },
  
  "texture_definition": {
    "description": "细腻噪声纹理，颗粒感适中，随机分布",
    "suggested_technique": "Value noise 或 Perlin noise"
  },
  
  "lighting_definition": {
    "description": "无光影效果"
  },
  
  "constraints": {
    "max_alu": 300,
    "target_fps": 30
  }
}
```

---

## 五、描述语言规范

### 5.1 必须包含的信息

每个 `definition` 字段必须包含：
1. **核心特征**：是什么（形状类型、颜色、动画方向）
2. **量化参考**：具体参数（RGB 值、时长、比例）
3. **关键约束**：重要注意事项（如有）

### 5.2 禁止的描述方式

| 错误描述 | 正确描述 |
|----------|----------|
| "颜色好看" | "蓝色系主色 (RGB 约 0.2, 0.5, 1.0)" |
| "动画自然" | "ease-out 缓出曲线，约 3 秒循环" |
| "背景不对" | "背景应为纯白色 (RGB 1.0, 1.0, 1.0)" |
| "效果不好" | "边缘过于锐利，缺少柔和过渡" |

### 5.3 suggested_technique 用途

- **非强制约束**：仅作为技术方向建议
- **LLM 可灵活选择**：可根据实际情况调整实现方式
- **降低理解成本**：帮助 Generate Agent 快速定位技术方向

---

## 六、与 Generate Agent 的协作

### 6.1 Generate Agent 接收 visual_description

Generate Agent 从 natural language visual_description 中提取：
- 形状语义 → 选择 SDF 类型
- 颜色语义 → 实现 gradient/mix
- 动画语义 → 设计 time driver
- 背景语义 → 设置背景颜色/纹理

### 6.2 Generate Agent 输出

Generate Agent 输出完整 GLSL shader，无需解析 AST。

---

## 七、与 Inspect Agent 的协作

### 7.1 Inspect Agent 对比基准

Inspect Agent 使用 visual_description 作为对比基准：
- shape_definition → geometry 维度评分
- color_definition → color 维度评分
- animation_definition → animation 维度评分
- background_definition → background 维度评分（重点）

### 7.2 Inspect 输出语义反馈

Inspect 输出自然语言语义描述，不局限于参数调整：
- visual_issues：描述具体视觉问题
- visual_goals：描述期望效果
- correct_aspects：描述正确保持的部分

---

## 八、自检清单

输出前验证：

- [ ] `effect_name` 简洁准确
- [ ] `visual_identity.summary` 一句话完整描述
- [ ] `background_definition` 包含 important 字段（如有约束）
- [ ] 所有 definition 包含具体参数参考（RGB、时长等）
- [ ] 无模糊描述（"效果不好"、"颜色不对"等）
- [ ] JSON 格式正确
- [ ] 无 markdown 包裹

---

*替代文档：dsl-schema.md*
*版本：V3.0*