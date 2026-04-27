# 人工迭代反馈功能设计

> 用户在自动工作流完成后，可输入检视命令触发人工迭代，系统综合用户指令和 Agent 检视结果生成反馈给 Generate Agent。

---

## 1. 需求概述

### 核心功能

- **前端**：Shader 显示模块下方增加对话框，支持用户输入自然语言检视命令，点击 Proceed 触发人工迭代
- **后端**：Inspect Agent 收到用户检视命令后，综合用户指令和 Agent 检视结果生成反馈，触发新一轮 generate→inspect 迭代
- **上下文共享**：人工迭代轮共享之前 generate_history 和 inspect_history 的完整记录

### 用户场景

```
自动迭代结束（passed / max_iterations / failed）
  ↓
显示 FeedbackPanel（输入框 + Proceed 按钮）
  ↓
用户输入自然语言反馈："让颜色更鲜艳，光晕范围更大"
  ↓
（可选）用户在 ShaderEditor 中直接修改代码
  ↓
点击 Proceed
  ↓
Backend 收到 human_feedback
  ↓
判断是否有 human_modified_shader？
  ├─ 有 → 直接 render → inspect（评估用户修改）
  └─ 无 → generate（综合 human_feedback）→ render → inspect
  ↓
更新 AgentLog，标记人工迭代（human_iteration: True）
  ↓
迭代结束，再次显示 FeedbackPanel（可继续触发）
```

---

## 2. 后端设计

### 2.1 PipelineState 扩展

在 `backend/app/pipeline/state.py` 中新增字段：

```python
class PipelineState(TypedDict, total=False):
    # ... 现有字段 ...
    
    # 用户人工干预相关
    human_feedback: str | None           # 用户自然语言检视命令
    human_modified_shader: str | None    # 用户在编辑器中修改的代码（可选）
    human_iteration_mode: bool           # 是否处于人工迭代模式
    human_iteration_count: int           # 人工迭代计数（用于日志区分）
```

### 2.2 新增 API 端点

在 `backend/app/routers/pipeline.py` 中新增：

```python
@router.post("/{pipeline_id}/human-iterate")
async def human_iterate(
    pipeline_id: str,
    feedback: str = Form(...),
    modified_shader: str | None = Form(None),
):
    """
    触发人工迭代。
    
    Args:
        feedback: 用户自然语言反馈
        modified_shader: 用户修改的代码（可选，如果用户在编辑器中修改了代码）
    
    Returns:
        Pipeline status
    """
    # 1. 检查 pipeline 是否存在且已结束
    if pipeline_id not in pipeline_results:
        return {"error": "Pipeline not found"}
    
    current_state = pipeline_results[pipeline_id]
    if current_state.get("status") == "running":
        return {"error": "Pipeline still running, cannot trigger human iteration"}
    
    # 2. 更新状态
    current_state["human_feedback"] = feedback
    current_state["human_modified_shader"] = modified_shader
    current_state["human_iteration_mode"] = True
    current_state["human_iteration_count"] = current_state.get("human_iteration_count", 0) + 1
    current_state["status"] = "running"
    current_state["phase_status"] = "running"
    
    # 3. 决定起始节点
    # 如果有用户修改的代码 → 直接从 render 开始
    # 否则 → 从 generate 开始
    if modified_shader:
        current_state["current_shader"] = modified_shader
        current_state["current_phase"] = "render"
        current_state["phase_message"] = "Rendering user-modified shader..."
    else:
        current_state["current_phase"] = "generate"
        current_state["phase_message"] = "Generating with human feedback..."
    
    # 4. 清除之前的错误状态
    current_state["compile_error"] = None
    current_state["validation_errors"] = None
    current_state["passed"] = False
    current_state["error"] = None
    
    # 5. 启动 Pipeline（后台任务）
    pipeline_results[pipeline_id] = current_state
    
    # 触发 Pipeline 执行（复用现有执行逻辑）
    BackgroundTasks.add_task(run_pipeline_from_state, pipeline_id, current_state)
    
    return {"status": "running", "pipeline_id": pipeline_id}
```

### 2.3 Pipeline 执行逻辑扩展

新增函数 `run_pipeline_from_state()`，复用现有 `astream()` 逻辑，但支持从指定阶段开始：

```python
async def run_pipeline_from_state(pipeline_id: str, initial_state: dict):
    """从指定状态启动 Pipeline（支持人工迭代触发）"""
    current_state = initial_state
    config = {"recursion_limit": 200}
    
    async for event in pipeline_app.astream(current_state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_output:
                print(f"[Pipeline {pipeline_id}] Node {node_name} completed")
                current_state = {**current_state, **node_output}
                result_dict = {k: v for k, v in current_state.items()}
                result_dict["status"] = "running"
                pipeline_results[pipeline_id] = result_dict
    
    # 完成后更新状态
    result_dict = {k: v for k, v in current_state.items()}
    if current_state.get("passed"):
        result_dict["status"] = "passed"
    elif current_state.get("error"):
        result_dict["status"] = "failed"
    else:
        result_dict["status"] = "completed"  # 人工迭代完成，可继续触发
    
    pipeline_results[pipeline_id] = result_dict
```

### 2.4 Generate Agent 扩展

在 `backend/app/agents/generate.py` 中新增参数：

```python
def run(
    self,
    visual_description: dict,
    previous_shader: str | None = None,
    feedback: str | None = None,
    context_history: list | None = None,
    human_feedback: str | None = None,  # NEW: 用户人工反馈
    return_raw: bool = False,
):
    """
    Generate Agent 运行。
    
    human_feedback: 用户自然语言检视命令，优先级高于 Agent 反馈。
    """
    user_parts = [...]
    
    # 注入用户人工反馈（优先级最高）
    if human_feedback:
        user_parts.append(f"\n---\n[用户检视指令]\n{human_feedback}")
    
    # ... 现有逻辑 ...
```

Prompt 调整：
- 如果 `human_feedback` 存在，将其作为首要修改依据
- 格式：`[用户检视指令]\n{human_feedback}`
- 历史上下文保持完整（不裁剪）

### 2.5 Inspect Agent 扩展

在 `backend/app/agents/inspect.py` 中新增参数：

```python
def run(
    self,
    design_images: list[str],
    render_screenshots: list[str],
    visual_description: dict | None = None,
    iteration: int = 0,
    previous_feedback: str | None = None,  # NEW: 上一轮反馈（包括用户反馈）
    human_feedback: str | None = None,     # NEW: 用户人工反馈
    context_history: list | None = None,
):
    """
    Inspect Agent 运行。
    
    human_feedback: 用户自然语言检视命令，作为评估参考。
    """
    # ... 现有逻辑 ...
    
    # 如果有 human_feedback，在 prompt 中注入
    if human_feedback:
        user_parts.append(f"\n---\n[用户检视指令]\n请评估渲染结果是否符合用户的期望：{human_feedback}")
```

### 2.6 Graph 节点调整

在 `backend/app/pipeline/graph.py` 中调整：

#### node_generate 调整

```python
async def node_generate(state: PipelineState) -> dict:
    """Generate Agent：生成或修正 GLSL 代码"""
    
    # ... 现有逻辑 ...
    
    # 收集反馈
    feedback_parts = []
    
    # 优先级：用户反馈 > Agent 反馈
    if state.get("human_feedback"):
        feedback_parts.append(f"[用户检视指令]\n{state['human_feedback']}")
    
    if state.get("inspect_result") and not state.get("passed"):
        feedback_parts.append(f"[Agent 反馈]\n{state['inspect_result'].get('feedback', '')}")
    
    # ... 传递给 Generate Agent ...
    
    result = generate_agent.run(
        visual_description=description,
        previous_shader=previous_shader,
        feedback="\n\n".join(feedback_parts) if feedback_parts else None,
        context_history=generate_history,
        human_feedback=state.get("human_feedback"),  # NEW
        return_raw=True,
    )
```

#### node_inspect 调整

```python
async def node_inspect(state: PipelineState) -> dict:
    """Inspect Agent：对比截图，输出评估"""
    
    # ... 现有逻辑 ...
    
    result = inspect_agent.run(
        design_images=design_imgs,
        render_screenshots=render_imgs,
        visual_description=description,
        iteration=iteration,
        context_history=inspect_history,
        human_feedback=state.get("human_feedback"),  # NEW: 用户反馈作为参考
    )
    
    # 记录人工迭代标记
    new_history_entry = {
        "iteration": iteration,
        "score": result.get("overall_score", 0),
        "passed": result.get("passed", False),
        "feedback": result.get("feedback", ""),
        "human_iteration": state.get("human_iteration_mode", False),  # NEW
        "human_feedback": state.get("human_feedback"),  # NEW
    }
```

---

## 3. 前端设计

### 3.1 FeedbackPanel 组件

新建 `frontend/src/components/FeedbackPanel.tsx`：

```tsx
interface FeedbackPanelProps {
  pipelineId: string;
  status: string;        // 'passed' | 'max_iterations' | 'failed' | 'completed'
  currentShader: string; // 当前 shader 代码（用于获取用户修改）
  disabled: boolean;     // 是否禁用（运行中）
}

export default function FeedbackPanel({ 
  pipelineId, 
  status, 
  currentShader,
  disabled 
}: FeedbackPanelProps) {
  const [feedback, setFeedback] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // 不显示的条件
  if (status === 'running' || status === 'not_found' || status === 'error') {
    return null;
  }
  
  const handleProceed = async () => {
    setIsSubmitting(true);
    
    // 获取用户修改的代码（如果有）
    const userModifiedShader = getModifiedShader(); // 从 ShaderEditor 获取
    
    try {
      const res = await fetch(
        `http://localhost:8000/pipeline/${pipelineId}/human-iterate`,
        {
          method: 'POST',
          body: new FormData()
            .append('feedback', feedback)
            .append('modified_shader', userModifiedShader || ''),
        }
      );
      
      if (res.ok) {
        setFeedback(""); // 清空输入
        // Pipeline 会自动更新状态（polling 或 stream）
      }
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const handleEndSession = () => {
    // 清空状态，结束会话
    clearPipelineState();
  };
  
  return (
    <div className="panel feedback-panel">
      <h3>人工迭代反馈</h3>
      <textarea
        placeholder="描述您想要的修改，如：让颜色更鲜艳，光晕范围更大"
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        disabled={disabled || isSubmitting}
      />
      <div className="actions">
        <button 
          onClick={handleProceed}
          disabled={disabled || isSubmitting || !feedback.trim()}
        >
          {isSubmitting ? "处理中..." : "Proceed"}
        </button>
        <button onClick={handleEndSession}>
          End Session
        </button>
      </div>
      <p className="hint">
        您也可以直接在代码编辑器中修改代码，或在参数面板调整参数
      </p>
    </div>
  );
}
```

### 3.2 App.tsx 集成

在 `frontend/src/App.tsx` 中添加 FeedbackPanel：

```tsx
// ShaderPreview 下方
<ShaderPreview ... />
<FeedbackPanel
  pipelineId={pipelineResult?.pipeline_id}
  status={pipelineResult?.status}
  currentShader={pipelineResult?.current_shader}
  disabled={pipelineResult?.status === 'running'}
/>
```

### 3.3 ShaderEditor 状态追踪

在 `frontend/src/components/ShaderEditor.tsx` 中新增：

```tsx
// 导出用户修改的代码
export function getModifiedShader(): string | null {
  // 如果用户修改了代码，返回修改后的版本
  // 否则返回 null（表示用户未修改）
  const editorContent = editorRef.current?.getValue();
  const originalShader = pipelineResult?.current_shader;
  
  if (editorContent !== originalShader) {
    return editorContent;
  }
  return null;
}
```

### 3.4 AgentLog 显示人工迭代

在 `frontend/src/components/AgentLog.tsx` 中调整：

```tsx
// 区分自动迭代和人工迭代
{log.human_iteration ? (
  <span className="badge human-iteration">人工迭代</span>
) : (
  <span className="badge auto-iteration">自动迭代</span>
)}

// 显示用户反馈
{log.human_feedback && (
  <div className="human-feedback">
    <strong>用户指令：</strong>
    {log.human_feedback}
  </div>
)}
```

---

## 4. 数据流图

```
[自动迭代结束]
    ↓
[显示 FeedbackPanel]
    ↓
用户输入: feedback + modified_shader (可选)
    ↓
POST /pipeline/{id}/human-iterate
    ↓
Backend 更新状态:
  - human_feedback
  - human_modified_shader
  - human_iteration_mode = True
    ↓
判断路径:
  ├─ modified_shader 存在 → [render] → [inspect]
  └─ modified_shader 不存在 → [generate] → [validate] → [render] → [inspect]
    ↓
Agent 使用完整历史:
  - generate_history (所有自动 + 人工迭代)
  - inspect_history (所有自动 + 人工迭代)
    ↓
[更新 AgentLog，标记 human_iteration]
    ↓
[迭代结束]
    ↓
[再次显示 FeedbackPanel] (可继续触发)
```

---

## 5. 关键约束

### 5.1 人工迭代无次数限制

用户可以无限次触发人工迭代，直到满意为止。

### 5.2 上下文完整保留

- `generate_history` 和 `inspect_history` 保留所有迭代记录
- 不裁剪历史（除非显式设置 sliding window）

### 5.3 用户修改代码直接评估

如果用户在 ShaderEditor 中修改了代码：
- **不经过 Generate Agent**
- **直接 render → inspect**
- Inspect Agent 使用 `human_feedback` 作为评估参考

### 5.4 用户反馈优先级最高

在 Generate Agent 的 prompt 中：
- 用户反馈 (`human_feedback`) 位于最前
- Agent 反馈 (`inspect_result.feedback`) 位于其后

---

## 6. 测试场景

### 场景 1：仅自然语言反馈

```
自动迭代结束 → 用户输入"让光晕更柔和" → Proceed
→ Generate Agent 收到 human_feedback → 生成新 shader → Inspect 评估
```

### 场景 2：用户修改代码 + 自然语言反馈

```
自动迭代结束 → 用户修改代码（调整颜色）→ 输入"这样差不多了" → Proceed
→ 直接 render 用户修改的 shader → Inspect 评估（参考 human_feedback）
```

### 场景 3：多轮人工迭代

```
自动迭代结束 → 人工迭代1 → 人工迭代2 → 人工迭代3 → ...
→ 每轮共享完整历史 → AgentLog 显示所有迭代
```

### 场景 4：用户结束会话

```
迭代结束 → 用户点击 "End Session" → 清空状态 → FeedbackPanel 隐藏
```

---

## 7. 实施优先级

| 模块 | 优先级 | 工作量 |
|------|--------|--------|
| PipelineState 扩展 | P0 | 低 |
| API 端点 `human-iterate` | P0 | 中 |
| Generate Agent 参数扩展 | P0 | 低 |
| Inspect Agent 参数扩展 | P0 | 低 |
| Graph 节点调整 | P0 | 中 |
| FeedbackPanel 组件 | P0 | 中 |
| ShaderEditor 状态追踪 | P1 | 低 |
| AgentLog 人工迭代标记 | P1 | 低 |

---

## 8. 风险与对策

| 风险 | 对策 |
|------|------|
| 上下文过长导致 LLM 响应慢 | 暂不处理，观察实际表现后考虑 sliding window |
| 用户修改代码导致编译错误 | 跳过 generate，直接 render → inspect 会检测到错误并反馈 |
| 人工迭代后用户不结束会话 | 提供 "End Session" 按钮，清空状态 |

---

## 9. 文件清单

### 后端

- `backend/app/pipeline/state.py` - PipelineState 扩展
- `backend/app/routers/pipeline.py` - 新增 `human-iterate` API
- `backend/app/agents/generate.py` - 新增 `human_feedback` 参数
- `backend/app/agents/inspect.py` - 新增 `human_feedback` 参数
- `backend/app/pipeline/graph.py` - 节点调整（generate, inspect）

### 前端

- `frontend/src/components/FeedbackPanel.tsx` - 新组件
- `frontend/src/components/ShaderEditor.tsx` - 新增状态追踪
- `frontend/src/components/AgentLog.tsx` - 人工迭代标记
- `frontend/src/App.tsx` - 集成 FeedbackPanel