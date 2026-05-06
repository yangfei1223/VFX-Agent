# 视效 Agent 闭环上下文与状态机重构设计方案 (V2.0)

## 一、 当前系统架构的致命缺陷排查

对原架构（基于 `state.py`、`graph.py` 与 Agent 执行逻辑）进行第一性原理审视，系统无法高效收敛的核心根源在于上下文与状态管理的失控。具体表现为三大工程缺陷：

1. **状态机伪回滚陷阱（A-B-A 振荡与持续劣化）**
   - **现象**：当新代码得分低于上一轮时，系统在逻辑层标记 `passed=False` 并建议回滚，但在底层的 `PipelineState` 中未执行物理快照覆盖，导致下一轮 LLM 依然基于劣化后的代码进行修改。
2. **上下文 Token 膨胀与注意力稀释（Lost in the Middle）**
   - **现象**：历史每一轮的完整 GLSL 代码 (`shader`) 被全量拼接注入到 Prompt 中，导致 Prompt 长度呈指数级暴涨。大模型的注意力被大量雷同的旧代码稀释，后期开始遗忘核心规则或产生幻觉。
3. **架构契约缺失（缺乏控制句柄）**
   - **现象**：Decompose Agent 未向 Generate Agent 传递明确的参数化控制域（`tunable_parameters_schema`），导致 Inspect Agent 的反馈无法精确映射到代码变量，迫使生成节点频繁进行“全局拓扑重写”而非“局部梯度寻优”。

------

## 二、 核心架构：中心化状态总线 (Centralized State Bus)

系统必须采用严格的**黑板模式（Blackboard Pattern）**，禁止 Agent 之间的点对点通信。所有状态流转由全局状态机控制，Agent 作为无状态纯函数运行：$State_{t+1} = Agent(State_t)$。

全局状态容器（`PipelineState`）物理划分为四个隔离数据区：

1. **只读基线区 (Read-Only Baseline)**：存放原始设计参考（图片/视频）、初始文本指令、System Prompt 及全局约束。单次任务内不可变。
2. **当前快照区 (Current Snapshot)**：存放最新单步状态，包括解构输出的 DSL（含拓扑与 `tunable_parameters`）、当前 Shader 代码、渲染截图、检视反馈 JSON。
3. **梯度记忆窗口 (Sliding Window History)**：限制最大长度（如 $N=3$），仅存放近 $N$ 轮的**纯文本梯度元数据**（迭代轮次、参数 Diff 日志、得分），绝对禁止存放全量历史代码。
4. **回滚锚点区 (Checkpointing)**：记录 `best_score` 与 `best_shader`。作为防劣化的物理隔离备份。

------

## 三、 细分 Agent 触发机制与上下文装配策略

每次调用 Agent 时，系统通过动态掩码严格按以下顺序组装专属上下文视图（Context View）。

**装配哲学：** `[超我：底线约束] -> [自我：技能字典] -> [本我：动态任务数据]`

### 1. 视效解构 Agent (Decompose Agent)

- **触发时机**：
  1. **冷启动 ($T=0$)**：任务初始化。
  2. **重构阻断 (Re-decompose)**：当检视 Agent 判定“基础拓扑完全错误且无法通过参数微调挽救”（如得分低于阈值或陷入改写死循环）时，由主控节点强制拉起。
- **上下文严格装配顺序**：
  1. `[System Prompt]`：解构约束规则（如强制提取参数空间）。
  2. `[Skill Context]`：动态注入 `visual-effect-decomposition`，包含具体 CoT 步骤、多维分析模板与合法算子边界。
  3. `[UX Reference]`：原始设计参考（多模态图片/视频）。
  4. `[Failure Log]` **(仅重构时注入)**：注入导致重构的错误拓扑及检视 Agent 的致命错误说明（如：“之前基于 sdCircle 堆叠未能实现流体，请更换拓扑为 Simplex Noise”），作为负样本防止重复试错。
- **隔离策略**：禁止接收任何生成的代码片段或代码级报错。

### 2. Shader 生成 Agent (Generate Agent)

- **触发时机**：每次有效迭代（$T \ge 1$）或发生编译错误时的内部重试。
- **上下文严格装配顺序**：
  1. `[System Prompt]`：三段式代码结构规范与 Shadertoy 环境红线。
  2. `[Skill Context]`：动态注入 `effect-dev`，包含 SDF 原语公式、噪声函数库及安全数学计算法则。
  3. `[Baseline Blueprint]`：解构产出的 `tunable_parameters_schema` 与宏观管线阶段定义，作为全局参数锚点。
  4. `[Current State]`：上一轮（或回滚后）的完整 Shader 代码。
  5. `[Feedback]`：检视 Agent 产出的量化梯度（`parameter_tuning`）或静态语法检查报错。
  6. `[Short-term Memory]`：局部修改日志（如：“Round 3: RADIUS 从 0.4 改为 0.5 -> 得分下降”），用于打破 A-B-A 循环。
- **隔离策略**：严禁注入原始设计图像或当前渲染截图，强制其作为“盲眼代码执行器”仅依赖文本指令工作。

### 3. 视效检视 Agent (Inspect Agent)

- **触发时机**：代码通过静态编译，且沙盒成功捕获渲染截图后。
- **上下文严格装配顺序**：
  1. `[System Prompt]`：多维评分标准与结构化量化反馈（Gradient）输出要求。
  2. `[Skill Context]`：动态注入 `visual-effect-critique`，提供专业的视觉术语词典与好坏评价示例。
  3. `[UX Reference]`：原始设计稿基准。
  4. `[Current Render]`：当前 Shader 的沙盒渲染截图。
  5. `[Current Code Header]`：**关键截断**。不传入 Shader 全量逻辑，仅截取代码顶部的 `TUNABLE PARAMETERS` 声明区。强制模型将注意力集中在“可用旋钮”的数值推演上。
  6. `[Momentum State]`：传入近 3 轮的 `overall_score`。若分数停滞，触发动量惩罚，强制放弃微调，输出拓扑修正指令或触发重构阻断。

------

## 四、 记忆裁剪与物理快照回滚机制

为应对 Token 膨胀并保证状态机单调收敛，在 Pipeline 层强制实施生命周期管理：

1. **梯度特征保留 (Memory Truncation)**：

   剥离 Generate 历史中的代码块，旧轮次信息坍缩为“参数动作 + 耗时 + 得分反馈”的轻量级日志。

2. **物理快照回滚 (Physical Checkpoint Rollback)**：

   - **状态拦截**：当 `node_inspect` 发现 `current_score < best_score` 时，逻辑层判负。
   - **底层覆盖**：系统控制流介入，强制将总线中的 `current_shader` 物理替换为锚点区的 `best_shader`。
   - **指令强注入**：在下发给 Generate Agent 的 `[Feedback]` 中强注入指令：“前置尝试导致得分从 {best_score} 跌至 {current_score}，系统已在底层回滚代码。请废弃刚才的修改方向，基于当前恢复的优质代码探索新参数。”

------

## 五、 控制流有向无环图 (Control Flow DAG)

单轮数据流及异常路由呈现严格的有向特征：

1. **Start** $\rightarrow$ `Decompose`：根据输入确立数学蓝图与参数空间 Schema。
2. `Decompose` $\rightarrow$ `Generate`：组装参数宏并生成初版代码。
3. `Generate` $\rightarrow$ `Validate (Static Validator)`：
   - 若语法/规范错误，环回 `Generate` 局部修正。
   - 若验证通过，进入 `Render`。
4. `Render` $\rightarrow$ `Inspect`：捕获截图进行多模态比对。
5. `Inspect` 路由分支：
   - **分支 A (Passed)**：得分达标，成功完结。
   - **分支 B (Parameter/Topology Tuning)**：得分未达标但拓扑未崩坏。输出梯度指令，执行快照校验与**可能触发的物理回滚**后，环回 `Generate`。
   - **分支 C (Re-decompose)**：触发重构阻断。记录致命错误日志，环回 `Decompose` 重新确立底层算子蓝图。