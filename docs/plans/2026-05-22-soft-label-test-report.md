# 软标签效果分类测试报告

> 测试日期：2026-05-22
> 测试目标：验证软标签机制（effect_candidates）是否正确工作

---

## 测试概述

本次测试运行了部分样本，验证新实现的软标签机制：
- Decompose 输出 `effect_candidates`（候选类别 + 置信度）
- Generate 参考候选列表实现复合效果
- Inspect 通过 visual_feedback 触发 Re-decompose 纠正

---

## 测试结果汇总

### 已完成样本

| 样本 | 评分 | Primary Effect | Candidates | 状态 |
|------|------|----------------|------------|------|
| 4-col-grad | 0.45 | `{effect.gradient}` | gradient(0.95) | ❌ |
| heart-2d | 0.73 | `{effect.shape}` | shape(0.9), gradient(0.1) | ❌ |
| plasma-waves | 0.32 | `{effect.flow}` | flow(0.85), glow(0.6), particle(0.2) | ❌ |
| shiny-circle | N/A | `{effect.glow}` | glow(0.85), shape(0.6), ripple(0.2) | ❌ 失败 |
| cool-s-distance | 0.68 | `{effect.shape}` | shape(0.85), warp(0.7), glow(0.45) | ❌ |

---

## 软标签机制验证

### ✅ 成功项

| 验证项 | 说明 |
|-------|------|
| effect_candidates 输出 | 所有新测试样本均输出候选列表 |
| 置信度估算 | 置信度在合理范围（0.85-0.95 primary, 0.1-0.7 secondary） |
| 候选数量 | 根据置信度分布自动调整（1-3个） |
| cool-s-distance 类型纠正 | 从错误识别(warp) → 正确识别(shape) |

### ❌ 问题项

| 问题 | 样本 | 根因 |
|------|------|------|
| shiny-circle 失败 | shiny-circle | Decompose 描述"类似圆角三角形"误导 Generate |
| 评分偏低 | 多个样本 | Generate shader 质量问题，非类型问题 |
| Session 日志截断 | 所有样本 | 日志保存时截断 shader 到 500 chars（仅显示问题） |

---

## 效果类型分布分析

从 session 数据分析（共 350+ sessions）：

### 新格式（有 effect_candidates）

| Effect Type | 出现次数 | 平均置信度 |
|------------|---------|-----------|
| shape | 15 | 0.85 |
| glow | 10 | 0.90 |
| gradient | 5 | 0.95 |
| flow | 8 | 0.85 |
| warp | 6 | 0.75 |
| particle | 3 | 0.80 |
| liquid | 4 | 0.70 |
| ripple | 5 | 0.85 |

### 旧格式（无 effect_candidates）

约 300+ sessions 为旧格式（测试前运行），说明软标签机制是新功能。

---

## 关键改进对比

### cool-s-distance（之前 vs 现在）

| 版本 | Primary Effect | Candidates | 评分 |
|------|---------------|------------|------|
| 旧版本 | `{effect.warp}` ❌ | 无 | 0.00-0.35 |
| 新版本 | `{effect.shape}` ✅ | shape(0.85), warp(0.7), glow(0.45) | 0.68 |

**结论**：软标签机制成功纠正了类型识别错误。

---

## 建议改进

### 1. Decompose 描述规范

问题：shiny-circle 描述写"类似圆角三角形"导致 Generate 误用形状。

建议：在 decompose_system.md 增加规则：
```
禁止使用比喻性描述：
- ❌ "类似圆角三角形"
- ❌ "像是某种形状"
- ✅ "圆形，边缘柔和"
- ✅ "六边形，实心填充"
```

### 2. Generate 描述优先级

问题：Generate 在 sdf_type 与描述冲突时选择描述。

建议：明确优先级规则：
```
优先级：sdf_type > 描述文本
如果 sdf_type={sdf.circle}，必须使用圆形，即使描述写"类似三角形"
```

### 3. Session 日志完整性

问题：日志截断 shader 到 500 chars 影响调试。

建议：保存完整 shader 到单独文件，日志只存摘要。

---

## Git Commits

| Commit | 说明 |
|--------|------|
| `e3aab23` | feat: 软标签效果分类 + Inspect 纠正机制 |
| `7fb771d` | fix: 更新 validators.py Closed Vocabulary |
| `ba7a02f` | fix: _extract_glsl V6.0 处理无闭合代码块 |

---

## 下一步

1. 完成剩余 14 个样本测试
2. 优化 Decompose 描述规范
3. 增加 Generate sdf_type 优先级规则
4. 收集更多测试数据对比基线

---

*报告生成时间：2026-05-22 10:45*