# 设计方案：软标签效果分类 + Inspect 纠正

> 日期：2026-05-21
> 状态：已确认，待实施

---

## 问题背景

当前 Decompose 的分类树只输出单一 `effect_type`（硬标签），存在以下问题：

| 问题 | 影响 |
|------|------|
| 单一类别 | 错了就全错，下游无法纠正 |
| 复合效果被强制归类 | cool-s-distance 同时有 shape + glow 特征，被强制归为 warp |
| 无置信度信息 | Generate 不知道 Decompose 的判断有多确定 |

---

## 设计目标

1. **软标签输出**：Decompose 输出候选类别 + 置信度，最多 3 个候选
2. **Generate 复合实现**：参考候选列表实现多效果叠加
3. **Inspect 间接触发纠正**：通过 visual_issues 反馈，Decompose 在 re-decompose 模式下自主判断类型错误

---

## 核心改动

### 1. Decompose Output Schema

**新结构**（保留 `effect_type` 兼容，增加 `effect_candidates`）：

```json
{
  "effect_type": "{effect.shape}",  // primary，指向 confidence 最高者
  
  "effect_candidates": [
    {"type": "{effect.shape}", "confidence": 0.75, "reason": "明确SDF几何形状"},
    {"type": "{effect.glow}", "confidence": 0.20, "reason": "边缘有光晕特征"},
    {"type": "{effect.warp}", "confidence": 0.05, "reason": "微弱扭曲感"}
  ],
  
  "shape_definition": {...},  // 其他字段不变
  "color_definition": {...},
  ...
}
```

**候选数量规则**：
- 最多 3 个候选
- 单一效果可只输出 1 个（不必硬凑）
- 置信度分布规则：
  - 最高置信度 >80% → 只输出 1 个候选
  - 最高置信度 60-80% → 输出前 2 个候选
  - 最高置信度 <60% → 输出前 3 个候选

---

### 2. Decompose Prompt 置信度规则

在 `decompose_system.md` 中增加：

```
## 置信度估算规则

在输出 effect_candidates 前，按以下规则估算置信度：

| 匹配程度 | 置信度范围 | 示例 |
|---------|-----------|------|
| 完全匹配某分类树分支 | 0.85-1.0 | 画面有清晰心形 → shape 分支完全匹配 |
| 部分匹配，存在歧义 | 0.50-0.80 | 画面有圆形但边缘模糊 → 可能是 ripple 或 glow |
| 仅符合 fallback 条件 | <0.50 | 无法归类到任何分支 → flow fallback |
```

---

### 3. Generate Prompt 候选类别使用说明

在 `generate_system.md` 中增加：

```
## effect_candidates 使用说明

Decompose 输出的 `effect_candidates` 包含多个候选类型及置信度：

- `effect_type` 是置信度最高的类型（primary），应优先参考
- 若 `effect_candidates` 包含多个类型，说明 Decompose 判断存在歧义
- 生成 shader 时可参考候选列表中的其他类型，实现复合效果

**示例**：
"effect_candidates": [
  {"type": "{effect.shape}", "confidence": 0.75},
  {"type": "{effect.glow}", "confidence": 0.20}
]
→ primary 是 shape，应使用 sdHeart/sdStar 实现
→ 次候选是 glow，可在形状边缘增加 exp(-d * intensity) 光晕
→ 复合实现：几何形状 + 边缘光晕（shape + glow）
```

---

### 4. Re-decompose 模式类型错误判断

Decompose 在重构模式下根据 Inspect 的 `visual_issues` 自主判断：

**类型错误判断信号**：
- 反馈中提及"形状不符"、"缺少几何特征"、"应该是XX形状" → 可能 effect_type 选择错误
- 反馈中提及"效果类型不对"、"不像是涟漪/流动/扭曲" → 类型判断有误
- 反馈中多次提及某个特定效果特征（如"光晕不足"但 effect_type=ripple） → 可能遗漏复合效果

**纠正策略**：
- 若判断为类型错误：调整 effect_candidates 顺序，将更匹配的类型提升为 primary
- 若判断为遗漏复合效果：增加候选类型，实现多效果叠加
- 若判断为参数问题（颜色/动画/边缘）：保持 effect_type 不变，仅调整其他字段

---

## 数据流

```
Decompose(冷启动)
  ↓
effect_type + effect_candidates (最多3个，置信度分布)
  ↓
Generate (参考 candidates 实现复合效果)
  ↓
Render
  ↓
Inspect (评分 + visual_issues)
  ↓ (评分低)
re_decompose_trigger + visual_issues
  ↓
Decompose(重构模式)
  ↓
分析 visual_issues → 判断是否类型错误 → 调整 effect_candidates
  ↓
再次 Generate → 循环直到收敛
```

---

## 改动文件清单

| 文件 | 改动内容 |
|------|---------|
| `backend/app/prompts/decompose_system.md` | 1. 置信度估算规则<br>2. 候选数量规则<br>3. 输出 schema 增加 `effect_candidates`<br>4. Re-decompose 模式类型错误判断逻辑 |
| `backend/app/prompts/generate_system.md` | effect_candidates 使用说明 |

---

## 不改动部分

- `Pipeline state`：无需改动，`effect_candidates` 作为 visual_description 的一部分传递
- `Inspect`：无需改动，只输出 visual_issues，不感知 effect_type
- `vfx_effect_catalog.md`：无需改动，9 种效果类型已定义

---

## 后续验证

实施完成后，使用 cool-s-distance 样本测试：
- 验证 Decompose 输出 effect_candidates
- 验证 Generate 能正确使用候选信息
- 验证 Re-decompose 能根据 visual_issues 判断类型错误