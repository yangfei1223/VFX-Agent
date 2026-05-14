# Shared VFX Constraints（三 Agent 共享）

> 此文档为 VFX-Agent V2.0 的共享约束层，所有 Agent 必须遵循。

---

## P0 禁止项（必须避免）

### 1. 禁止 raymarching

- **Generate Agent**: shader 输出无 `rayDirection`、`ro`、`rd`
- **理由**: 超出 Mobile GPU 性能范围（2D/2.5D 平面动效专用）

### 2. 禁止 texture fetch >8

- **Generate Agent**: `texture()` 调用 ≤8 次
- **理由**: Mobile GPU Texture fetch ≤8

### 3. 禁止默认紫色 (RGB ≈ 0.5, 0.2, 0.8)

- **Decompose Agent**: 主色调 ≠ 默认紫色
- **理由**: AI 默认偏好，缺乏设计意图

### 4. 禁止模糊描述

- **Decompose Agent**: 输出无"颜色好看"、"动画自然"、"边缘柔和"
- **Inspect Agent**: feedback 具体可操作（含量化参数）
- **理由**: Generate 无法理解模糊参数

### 5. 禁止背景约束缺失

- **Decompose Agent**: 如果用户强调纯白背景，`background.strict` 必须为 `true`
- **理由**: 会导致评分从 0.9 → 0.4

### 6. 禁止动画时长缺失

- **Decompose Agent**: `animation.duration` 必须存在
- **理由**: Generate 可能使用 1s 或 6s 不确定值

### 7. 禁止 edge width 缺失

- **Decompose Agent**: `shape.edge_width` 必须存在
- **理由**: Generate 不知道 smoothstep width 是 0.01 还是 0.05

---

## P1 检查项（应该避免）

- **单一颜色描述**: 只有"蓝色"而无 RGB 值
- **"玻璃质感"无参数**: 缺少具体参数（折射率、透明度）
- **lighting 缺少强度值**: lighting_definition 缺少 intensity 参数

---

## P2 提醒项（可选避免）

- **suggested_technique 过复杂**: 建议 3+ 算子组合
- **未提供 suggested_technique**: Generate 需自行推断算子选择

---

## 强制字段（Decompose Agent 必须输出）

| 字段 | 要求 | 示例 |
|------|------|------|
| `effect_type` | Closed Vocabulary (5种) | `ripple` |
| `color_definition.primary_rgb` | RGB 值 | `(0.2, 0.5, 1.0)` |
| `animation_definition.duration` | 时长秒数 | `3s` |
| `shape_definition.edge_width` | smoothstep 宽度 | `0.02-0.03 UV` |
| `background_definition.strict` | true/false | `true` |