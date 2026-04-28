# P0 任务实施计划：Harness Loop 约束系统

> 目标：实现设计方案核心的约束迭代系统（The Harness Loop），提升生成质量和收敛效率。

---

## 一、任务概述

| 任务 | 目标 | 预估工作量 |
|------|------|-----------|
| **1. Mask 提取服务** | 从渲染截图/设计参考提取 SDF Mask | 2h |
| **2. IoU 计算服务** | 形态收敛评估（交并比） | 1h |
| **3. 光流计算服务** | 动态拟合评估（光流 MSE） | 2h |
| **4. GLSL AST 审计** | 性能剪枝（ALU/Texture 计数） | 3h |
| **5. Inspect Agent 增强** | 注入量化评估到 feedback | 1h |
| **6. DSL 输出验证** | 强制 Decompose 输出 operators/topology | 1h |

**总预估：10h**

---

## 二、任务详情

### Task 1: Mask 提取服务

**目标**：从图片中提取形态场 Mask（二值轮廓图）

**技术方案**：
- 使用 OpenCV 边缘检测 + 阈值分割
- 输出为二值 Mask（0/1）

**文件位置**：
```
backend/app/services/mask_extractor.py
```

**核心函数**：
```python
def extract_mask(image_path: str) -> np.ndarray:
    """
    从图片提取形态场 Mask。
    
    步骤：
    1. 转灰度
    2. Canny 边缘检测
    3. 膨胀/腐蚀填充
    4. 阈值二值化
    
    Returns:
        np.ndarray: 二值 Mask (H, W)
    """
```

**验证方法**：
```bash
python -c "from app.services.mask_extractor import extract_mask; mask = extract_mask('test.png'); print(mask.shape)"
```

---

### Task 2: IoU 计算服务

**目标**：计算渲染 Mask 与设计 Mask 的交并比

**技术方案**：
- 两张二值 Mask 的 IoU = intersection / union
- IoU < 0.95 时触发形态修正

**文件位置**：
```
backend/app/services/iou_calculator.py
```

**核心函数**：
```python
def calculate_iou(mask1: np.ndarray, mask2: np.ndarray) -> float:
    """
    计算两个 Mask 的 IoU。
    
    IoU = (mask1 & mask2) / (mask1 | mask2)
    
    Returns:
        float: IoU 值 (0.0 - 1.0)
    """

def compare_masks(render_path: str, design_path: str) -> dict:
    """
    对比渲染截图与设计参考的形态一致性。
    
    Returns:
        dict: {
            "iou": 0.85,
            "shape_diff_regions": [...],  # 差异区域
            "recommendation": "增大半径或调整 blend 参数"
        }
    """
```

---

### Task 3: 光流计算服务

**目标**：计算帧间光流矢量，用于动画一致性评估

**技术方案**：
- OpenCV `calcOpticalFlowFarneback`
- 输出光流场 (H, W, 2)

**文件位置**：
```
backend/app/services/optical_flow.py
```

**核心函数**：
```python
def calculate_optical_flow(frame1_path: str, frame2_path: str) -> np.ndarray:
    """
    计算两帧之间的光流场。
    
    Returns:
        np.ndarray: 光流场 (H, W, 2) - (dx, dy)
    """

def calculate_flow_mse(flow1: np.ndarray, flow2: np.ndarray) -> float:
    """
    计算两个光流场的 MSE。
    
    Returns:
        float: MSE 值
    """

def compare_animation(render_frames: list[str], design_frames: list[str]) -> dict:
    """
    对比渲染动画与设计动画的动态一致性。
    
    Returns:
        dict: {
            "flow_mse": 0.05,
            "phase_shift": 0.1,  # 相位差
            "recommendation": "调整时间函数为 ease_in_out"
        }
    """
```

---

### Task 4: GLSL AST 审计服务

**目标**：静态分析 GLSL 代码的指令复杂度

**技术方案**：
- 解析 GLSL 代码，统计：
  - ALU instructions（算术运算次数）
  - Texture fetch（纹理采样次数）
  - Loop iterations（循环次数）
  - Function calls（函数调用）

**文件位置**：
```
backend/app/services/performance_audit.py
```

**核心函数**：
```python
def audit_glsl(shader_code: str) -> dict:
    """
    静态审计 GLSL shader 的性能预算。
    
    Returns:
        dict: {
            "alu_instructions": 120,
            "texture_fetch": 4,
            "loop_iterations": 16,
            "estimated_frame_time_ms": 1.5,
            "within_budget": True,
            "warnings": ["FBM octaves=5, 推荐降级到4"]
        }
    """

def check_performance_budget(shader_code: str, budget: dict) -> dict:
    """
    检查 shader 是否符合性能预算。
    
    Args:
        budget: {
            "max_alu": 256,
            "max_texture_fetch": 8,
            "max_loop_iterations": 32
        }
    
    Returns:
        dict: {
            "passed": True/False,
            "violations": [...],
            "recommendations": [...]
        }
    """
```

---

### Task 5: Inspect Agent 增强

**目标**：注入量化评估到 Inspect Agent 的输出

**修改文件**：
```
backend/app/agents/inspect.py
backend/app/pipeline/graph.py
```

**核心修改**：

1. **node_inspect 增加量化评估**：
```python
# 在 node_inspect 中增加量化指标计算
render_mask = extract_mask(render_screenshots[-1])
design_mask = extract_mask(design_images[0])
iou = calculate_iou(render_mask, design_mask)

flow_mse = compare_animation(render_screenshots, design_images)

perf_audit = audit_glsl(state["current_shader"])

# 注入到 Inspect Agent user prompt
quantitative_metrics = {
    "iou": iou,
    "flow_mse": flow_mse,
    "alu_instructions": perf_audit["alu_instructions"],
    "texture_fetch": perf_audit["texture_fetch"],
}
```

2. **Inspect Agent 输出格式更新**：
```json
{
  "passed": false,
  "quantitative_metrics": {
    "iou": 0.85,
    "flow_mse": 0.05,
    "performance_audit": {
      "alu_instructions": 120,
      "texture_fetch": 4,
      "within_budget": true
    }
  },
  "feedback_commands": [...]
}
```

---

### Task 6: DSL 输出验证

**目标**：强制 Decompose Agent 输出 `operators` + `topology` 字段

**修改文件**：
```
backend/app/agents/decompose.py
```

**核心修改**：

1. **添加 JSON Schema 验证**：
```python
DSL_SCHEMA = {
    "required": ["effect_name", "operators", "topology", "shape", "color", "animation"],
    "properties": {
        "operators": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["type", "params"]
            }
        },
        "topology": {
            "type": "string",
            "minLength": 10
        }
    }
}

def validate_dsl(dsl: dict) -> dict:
    """验证 DSL 输出是否符合 schema"""
    # 检查必填字段
    # 如果缺失，构造默认值或 retry
```

2. **Retry 机制**：
```python
# 如果 DSL 不符合 schema，重新调用 Decompose Agent
# 在 user prompt 中注入："上次输出缺少 operators 字段，必须输出算子组合描述"
```

---

## 三、实施顺序

1. **Task 1 + 2**（并行）：Mask 提取 + IoU 计算 → 形态收敛
2. **Task 3**：光流计算 → 动态拟合
3. **Task 4**：AST 审计 → 性能剪枝
4. **Task 5**：集成到 Inspect Agent
5. **Task 6**：DSL 输出验证

---

## 四、依赖安装

```bash
pip install opencv-python numpy scikit-image
```

---

## 五、验证标准

| 功能 | 验证方法 |
|------|---------|
| Mask 提取 | 输入测试图片，输出二值 Mask |
| IoU 计算 | 两张相同图片 IoU=1.0，不同图片 IoU<0.9 |
| 光流计算 | 两帧连续图片，输出光流场 |
| AST 审计 | 输入 shader，输出指令计数 |
| Pipeline 验证 | 运行完整 pipeline，Inspect 输出包含量化指标 |

---

## 七、新增任务（关键机制修正）

### Task 7: 评分对比机制

**问题**：当前接受所有 passed=True 的更改，但应该只在评分更高时才接受。

**修改方案**：
1. 在 `node_inspect` 中获取上一轮评分（从 inspect_history）
2. 只有当前评分 >= 上一轮评分时才 accept
3. 如果评分降低，即使 passed=True 也标记为需要改进

**核心逻辑**：
```python
# 获取上一轮评分
last_score = 0
if inspect_history:
    last_entry = inspect_history[-1]
    last_score = last_entry.get("overall_score", 0)

current_score = result.get("overall_score", 0)

# 评分对比：只有评分更高才接受
if passed and current_score >= last_score:
    passed = True  # 接受更改
elif passed and current_score < last_score:
    passed = False  # 评分降低，拒绝更改，继续迭代
    result["feedback_commands"].append({
        "target": "overall",
        "action": "rollback",
        "reason": f"评分降低（{current_score:.2f} < {last_score:.2f}），回滚到上一版本"
    })
```

---

### Task 8: 用户检视轮跳过 Agent 检视

**问题**：用户检视轮（human_iteration_mode）时 Agent 自动检视会覆盖用户指令。

**修改方案**：
1. human_iteration_mode=True 时跳过 inspect_agent.run()
2. 直接将 human_feedback 转换为结构化 feedback_commands
3. passed=False（继续迭代），让 Generate Agent 处理用户指令

**核心逻辑**：
```python
if state.get("human_iteration_mode"):
    # 用户检视轮：跳过 Agent 检视
    # 直接将用户反馈转为 feedback_commands
    user_feedback_commands = [{
        "target": "user_directive",
        "action": "apply",
        "value": state.get("human_feedback"),
        "reason": "用户直接指令"
    }]
    
    result = {
        "passed": False,  # 继续迭代让 Generate Agent 处理
        "overall_score": None,  # 用户检视轮无评分
        "feedback_commands": user_feedback_commands,
        "feedback_summary": state.get("human_feedback"),
        "human_iteration": True,
    }
    
    # 不调用 inspect_agent.run()
    return {...}
```

---

## 八、更新后的优先级

| 任务 | 优先级 | 说明 |
|------|--------|------|
| **Task 7: 评分对比机制** | P0 | 防止评分降低的更改被接受 |
| **Task 8: 用户检视轮跳过 Agent** | P0 | 防止 Agent 覆盖用户指令 |
| Task 1-6 | P1 | Harness Loop 量化评估 |

---

## 六、预期效果

- **形态收敛**：IoU < 0.95 时自动反馈 SDF 参数调整
- **动态拟合**：光流 MSE > 阈值时反馈时间函数修正
- **性能剪枝**：ALU > 256 或 Texture > 8 时反馈算子降级
- **DSL 增强**：所有输出包含 operators + topology
- **评分对比**：评分降低时自动拒绝更改
- **用户检视**：用户指令优先，Agent 不覆盖