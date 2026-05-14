# VFX-Agent V2.0 代码审查报告（更新版）

> 审查日期：2026-05-14
> 审查范围：Agent Pipeline 编排、上下文装配策略、系统提示词实现
> 状态：部分问题已修复

---

## 修复状态汇总

| 问题 | 原状态 | 当前状态 | 修复位置 |
|------|--------|----------|----------|
| effect_type/effect_name 字段名不匹配 | 🔴 Critical | ✅ 已修复 | graph.py:259-260 |
| Prompt 文件缺失无提示 | 🔴 Critical | ✅ 已修复 | context_assembler.py:26-28 |
| Failure Log 不完整 | 🔴 High | ✅ 已修复 | context_assembler.py:91-142 |
| 回滚状态未注入 Generate | 🔴 High | ✅ 已修复 | context_assembler.py:218-234 |
| Inspect 未注入 Catalog | 🟡 Medium | ✅ 已修复 | context_assembler.py:299-304 |
| Self-check 未被验证利用 | 🔴 Critical | ❌ 未修复 | decompose.py:122-124 |
| Effect Catalog Token 未验证 | 🔴 Critical | ❌ 未修复 | decompose.py:139 |
| 迭代计数双写混乱 | 🔴 High | ❌ 未修复 | graph.py:330-339 |
| Inspect 评分未由代码计算 | 🟡 Medium | ❌ 未修复 | inspect.py |

---

## 一、已修复问题

### 1. ✅ effect_type/effect_name 字段名兼容

**修复代码**：

```python
# graph.py:259-260
# V2.0: 优先使用 effect_type，兼容旧版 effect_name
effect_type = visual_description.get("effect_type") or visual_description.get("effect_name", "unknown")
```

**评价**：正确实现了向后兼容，优先使用新字段名。

---

### 2. ✅ Prompt 文件缺失警告

**修复代码**：

```python
# context_assembler.py:26-28
# Prompt 文件缺失警告
print(f"WARNING: Prompt file not found: {prompt_path}")
print(f"  Agent will receive empty system prompt!")
return ""
```

**评价**：添加了警告日志，开发者可以及时发现缺失问题。

**建议**：可以进一步改为抛出异常或在启动时预验证所有必需文件。

---

### 3. ✅ Failure Log 多轮历史增强

**修复代码**：

```python
# context_assembler.py:109-116
# V2.0: 提取多轮失败历史
recent_scores = [e.get("score", 0) for e in gradient_window[-3:]] if gradient_window else []
recent_issues = []
for entry in gradient_window[-3:]:
    issues = entry.get("issues_remaining", [])
    if issues:
        recent_issues.extend(issues)
```

**评价**：Failure Log 现在包含：
- 多轮评分趋势
- 累积未解决问题
- 最高评分参考

这解决了之前"单轮信息不完整"的问题。

---

### 4. ✅ 回滚标记注入 Generate Agent

**修复代码**：

```python
# context_assembler.py:218-234
if state.get("rollback_triggered"):
    rollback_info = f"""
[SYSTEM ROLLBACK]
系统已回滚到第 {checkpoint.get('best_iteration', 0)} 轮的优质代码。

**回滚原因**：当前评分低于上一轮，质量退化
**建议**：
- 废弃刚才尝试的方向
- 探索新的参数组合
"""
    user_parts.append(rollback_info)
```

**评价**：Generate Agent 现在知道回滚状态，不会继续尝试失败方向。

---

### 5. ✅ Inspect Agent 注入 Effect Catalog

**修复代码**：

```python
# context_assembler.py:299-304
# V2.0: Inspect 也注入 Effect Catalog，用于验证 effect_type、sdf_type 等 Token
constraints = load_prompt("shared_vfx_constraints")
catalog = load_prompt("vfx_effect_catalog")
base_system = load_prompt("inspect_system")

system_prompt = f"{base_system}\n\n---\n\n{constraints}\n\n---\n\n{catalog}"
```

**评价**：Inspect Agent 现有完整的 Token 定义作为评分基准。

---

## 二、未修复问题

### 1. ❌ Self-check 未被验证利用（Critical）

**当前代码**：

```python
# decompose.py:122-124
self_check_idx = text.find('[Self-check]')
if self_check_idx > 0:
    text = text[:self_check_idx].strip()  # ← 只是丢弃，未验证
```

**问题**：系统提示词要求 Agent 自评，但代码只是丢弃 Self-check，没有：
- 解析评分内容
- 验证评分是否 ≥3
- 触发重试逻辑

**建议**：

```python
def _parse_with_self_check(text: str) -> tuple[dict, dict]:
    """解析 JSON + Self-check"""
    self_check_idx = text.find('[Self-check]')
    
    if self_check_idx > 0:
        json_text = text[:self_check_idx].strip()
        self_check_text = text[self_check_idx:]
        
        # 解析 Self-check 评分
        overall_match = re.search(r'Overall:\s*(\d+)/5', self_check_text)
        if overall_match:
            score = int(overall_match.group(1))
            if score < 3:
                print(f"WARNING: Agent self-check score {score} < 3, quality may be low")
        
        return json.loads(json_text), {"self_check_score": score}
    
    return json.loads(text), {}
```

---

### 2. ❌ Closed Vocabulary Token 未验证（Critical）

**当前代码**：

```python
# decompose.py:139
return json.loads(text)  # ← 直接返回，无 Token 验证
```

**问题**：Agent 可能输出不在 Catalog 中的值（如 `effect_type: "ripple_advanced"`）。

**建议**：

```python
# 建议添加验证函数
VALID_EFFECT_TYPES = ["ripple", "glow", "gradient", "frosted", "flow"]

def validate_visual_description(visual_description: dict) -> dict:
    """验证 visual_description 符合 Closed Vocabulary"""
    errors = []
    
    effect_type = visual_description.get("effect_type")
    if effect_type not in VALID_EFFECT_TYPES:
        errors.append(f"Invalid effect_type: {effect_type}, must be one of {VALID_EFFECT_TYPES}")
    
    # 验证其他 Token...
    
    return {"valid": len(errors) == 0, "errors": errors}
```

---

### 3. ❌ 迭代计数双写依然存在（High）

**当前代码**：

```python
# graph.py:330-339
iteration = snapshot.get("iteration", 0)  # ← 四区字段

# ...

"iteration": iteration,  # ← 向后兼容字段（graph.py:505）
"iteration": updated_snapshot.get("iteration", iteration),  # ← graph.py:1012
```

**问题**：
- `snapshot.iteration` 和 `state.iteration` 双写
- 代码中多处读取不同位置
- 状态不一致风险

**建议**：
- 明确迁移计划：删除 `state.iteration`，只使用 `snapshot.iteration`
- 或添加迁移警告日志

---

### 4. ❌ Inspect 评分未由代码计算（Medium）

**当前代码**：

```python
# inspect.py
current_score = result.get("overall_score", 0)  # ← 直接使用 LLM 返回值
```

**问题**：系统提示词定义了加权公式：

```
overall_score = sum(dimension_score * dimension_weight) / sum(weights)
Weights: composition=0.10, geometry=0.10, color=0.15, background=0.20...
```

但代码没有验证 LLM 是否正确计算。

**建议**：

```python
def calculate_overall_score(dimension_scores: dict) -> float:
    """根据权重计算 overall_score"""
    weights = {
        "composition": 0.10,
        "geometry": 0.10,
        "color": 0.15,
        "animation": 0.10,
        "background": 0.20,
        "lighting": 0.10,
        "texture": 0.10,
        "vfx_details": 0.15,
    }
    
    total = 0.0
    for dim, data in dimension_scores.items():
        score = data.get("score", 0)
        weight = weights.get(dim, 0.10)
        total += score * weight
    
    return total / sum(weights.values())
```

---

## 三、新发现问题

### 1. 🟡 rollback_triggered 状态未同步到 state

**问题**：

```python
# graph.py:904-909
rollback_triggered = True
rollback_update = rollback_to_checkpoint({...})
rollback_snapshot = rollback_update.get("snapshot", snapshot)
```

但 `rollback_triggered` 只用于日志打印，没有写入 state：

```python
# context_assembler.py:219
if state.get("rollback_triggered"):  # ← 这个字段从哪来？
```

**影响**：回滚标记注入依赖 `state.get("rollback_triggered")`，但 graph.py 没有写入这个字段。

**建议**：在 graph.py node_inspect 返回中添加：

```python
"rollback_triggered": rollback_triggered,
```

---

### 2. 🟡 gradient_window issues_remaining 可能为空

**修复代码**：

```python
# context_assembler.py:113-116
for entry in gradient_window[-3:]:
    issues = entry.get("issues_remaining", [])
    if issues:
        recent_issues.extend(issues)
```

但 gradient_window 的 issues_remaining 来自：

```python
# graph.py:927
"issues_remaining": result.get("visual_issues"),
```

**问题**：如果 Inspect Agent 返回的 `visual_issues` 为空列表，gradient_window 的 `issues_remaining` 也为空，Failure Log 会缺少累积问题。

**建议**：在 Inspect Agent 中确保 visual_issues 非空（除非 passed=true）。

---

## 四、修复优先级建议

| 问题 | 优先级 | 建议修复方式 |
|------|--------|--------------|
| Self-check 未验证 | 🔴 P0 | 解析评分，<3 时打印警告或触发重试 |
| Token 未验证 | 🔴 P0 | 添加 validate_visual_description 函数 |
| rollback_triggered 未同步 | 🟡 P1 | graph.py 返回中添加字段 |
| 迭代计数双写 | 🟡 P1 | 添加迁移警告，计划删除旧字段 |
| Inspect 评分计算 | 🟡 P2 | 添加验证计算函数 |

---

## 五、总结

**已修复 5 个问题**：
- 字段名兼容 ✅
- Prompt 缺失警告 ✅
- Failure Log 增强 ✅
- 回滚标记注入 ✅
- Inspect 注入 Catalog ✅

**未修复 4 个关键问题**：
- Self-check 验证机制 ❌
- Token Closed Vocabulary 验证 ❌
- 迭代计数统一 ❌
- 评分计算验证 ❌

**整体评价**：修复覆盖了主要的上下文装配问题，但 Agent 输出验证机制（Self-check、Token）仍缺失。这两项是 Critical 级别，建议优先修复。