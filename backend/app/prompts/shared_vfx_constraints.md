# Shared VFX Constraints

> 三 Agent 共享的禁止项和约束规则

---

## P0 禁止项（必须避免 - 违反会导致失败）

### 1. 禁止 raymarching

- **检查对象**：Generate Agent 输出
- **禁止内容**：`rayDirection`、`ro`、`rd`、`sceneSDF(vec3)`、`marchRay`
- **理由**：超出 Mobile GPU 性能范围（需要数十次场景遍历，Frame time >2ms）
- **替代方案**：使用 2D SDF + layered composition

### 2. 禁止 texture fetch >8

- **检查对象**：Generate Agent 输出
- **禁止内容**：`texture()`、`texelFetch()` 调用次数 >8
- **理由**：Mobile GPU Texture fetch 限制
- **替代方案**：使用 SDF + noise 替代纹理

### 3. 禁止默认紫色

- **检查对象**：Decompose Agent 输出
- **禁止内容**：主色调 RGB ≈ (0.5, 0.2, 0.8)
- **理由**：AI 默认偏好，缺乏设计意图
- **替代方案**：使用用户指定颜色或 `{color.blue}` 等 Token

### 4. 禁止模糊描述

- **检查对象**：Decompose/Inspect Agent 输出
- **禁止内容**："颜色好看"、"动画自然"、"边缘柔和"、"效果不好"
- **理由**：Generate 无法理解参数，Inspect 无法定位问题
- **替代方案**：使用量化参数（如 RGB(0.2, 0.5, 1.0)、duration 3s）

### 5. 禁止背景约束缺失

- **检查对象**：Decompose Agent 输出
- **禁止内容**：用户强调纯白背景，但 `background.strict=false`
- **理由**：会导致 Inspect 评分从 0.9 → 0.4
- **替代方案**：根据用户要求设置 `strict=true/false`

### 6. 禁止动画时长缺失

- **检查对象**：Decompose Agent 输出
- **禁止内容**：动画描述无 `duration`
- **理由**：Generate 可能使用 1s 或 6s 不确定值
- **替代方案**：使用 `{anim.expand_3s}` Token 或指定 duration

### 7. 禁止 edge width 缺失

- **检查对象**：Decompose Agent 输出
- **禁止内容**：边缘描述无 `edge_width` 或 smoothstep width
- **理由**：Generate 不知道是 0.01 还是 0.05
- **替代方案**：使用 `{edge.soft_medium}` Token 或指定 edge_width

---

## P1 检查项（应该避免 - 违反会降低质量）

### 1. 单一颜色描述

- **检查对象**：Decompose Agent 输出
- **问题描述**：只有"蓝色"而无 RGB 值
- **建议修正**：补充 `primary_rgb` 字段

### 2. "玻璃质感"无参数

- **检查对象**：Decompose Agent 输出
- **问题描述**：描述"玻璃质感"但无 blur radius、alpha 值
- **建议修正**：补充 frosted glass 参数

### 3. lighting_definition 缺少强度值

- **检查对象**：Decompose Agent 输出
- **问题描述**：描述"fresnel"但无 intensity
- **建议修正**：补充 `fresnel_intensity`

---

## P2 提醒项（可选避免 - 提升质量）

### 1. suggested_technique 过于复杂

- **问题描述**：建议 3+ 算子组合
- **建议修正**：简化为 1-2 个核心算子

### 2. 未提供 suggested_technique

- **问题描述**：缺少技术建议
- **建议修正**：提供 1 个推荐算子

---

## 使用规则

1. **P0 禁止项必须遵循**：违反会导致编译失败或性能超标
2. **P1 检查项应该避免**：违反会降低首次生成质量
3. **Self-check 时检查**：输出前验证无 P0 禁止项

---

*参考：iq SDF 2D (iquilezles.org/articles/distfunctions2d/)*
*参考：iq SDF Operations (iquilezles.org/articles/distfunctions/)*