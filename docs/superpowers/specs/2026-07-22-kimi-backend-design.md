# Kimi Code Backend 设计

**日期**: 2026-07-22
**分支**: `feat/backend-ext`
**前置**: [Multi-Agent Backend Abstraction](./2026-07-17-multi-agent-backend-abstraction-design.md)
**状态**: Draft

---

## 1. 目标

将 Moonshot Kimi Code CLI（v0.28.1）作为第三个 backend 接入现有的 `BaseBackend` 抽象，跟 `CodexBackend` / `ClaudeCodeBackend` 同形。让用户能在 SettingsPanel 下拉里选择 "kimi" 作为 VFX pipeline 的执行 backend。

**非目标**：
- 不做 ACP stdio JSON-RPC 集成（架构跟现有 backend 不一致，YAGNI）
- 不绕过 kimi CLI 直接调 Moonshot Platform API（丢失 agent loop，违背 v2.0 codex OD 设计）
- 不暴露 kimi 的 hooks / background tasks / plugin 系统（不影响 VFX pipeline 核心流程）

---

## 2. 调研结论

### 2.1 环境实测（v0.28.1）

| 项 | 实测值 |
|---|---|
| Binary 位置 | `~/.kimi-code/bin/kimi`（**不在 PATH**，需特殊处理） |
| 版本 | 0.28.1 |
| 配置文件 | `~/.kimi-code/config.toml` |
| 默认模型 | `kimi-code/k3` (display "K3", max_context 1M, capabilities: thinking + always_thinking + image_in + video_in + tool_use, default effort "high") |
| 备选模型 | `kimi-code/kimi-for-coding` (K2.7), `kimi-code/kimi-for-coding-highspeed` (K2.7 Highspeed) |
| Auth | OAuth credentials 已存 `~/.kimi-code/credentials/kimi-code.json`（用户已配） |

### 2.2 CLI 行为

| 行为 | v0.28.1 实测 |
|---|---|
| 非交互 prompt 模式 | `kimi -p <prompt>` ✅ |
| 流式 JSON 输出 | `--output-format stream-json` ✅ |
| `--yolo` / `--auto` | **不能与 `-p` 组合**（实测报错 "Cannot combine --prompt with --yolo"） |
| 工具自动批准 | `-p` 模式实测会自动批准 Bash/Read/Write（无需 flag） |
| Workdir | 通过 `cwd=` 设置（无 `-C` flag，跟 claude-code 一致） |
| AGENTS.md 自动加载 | ✅ workdir root 的 AGENTS.md 被自动加载（实测前缀 `AGENTS_LOADED_OK` 生效） |
| 多模态 | k3 原生 image_in，agent 内置 `ReadMediaFile` tool 自主读取图片路径 |
| `--add-dir` | 可附加 workspace dir，但本项目 workdir 单一根目录足够 |

### 2.3 Event schema（OpenAI chat completion 风格 JSONL）

实测最小 agent loop（"写文件 + 验证"任务）输出：

```jsonl
{"role":"assistant","tool_calls":[{"type":"function","id":"tool_Q97...","function":{"name":"Bash","arguments":"{\"command\":\"printf 'hello' > /tmp/kimi-test/out.txt\"}"}}]}
{"role":"tool","tool_call_id":"tool_Q97...","content":"Command executed successfully."}
{"role":"assistant","tool_calls":[{"type":"function","id":"tool_VAH...","function":{"name":"Read","arguments":"{\"path\":\"/tmp/kimi-test/out.txt\"}"}}]}
{"role":"tool","tool_call_id":"tool_VAH...","content":"1\thello"}
{"role":"assistant","content":"Done. Wrote `hello` to ..."}
{"role":"meta","type":"session.resume_hint","session_id":"session_71b9...","command":"kimi -r session_71b9...","content":"To resume this session: kimi -r session_71b9..."}
```

**关键差异 vs claude-code / codex**：
- 无 `result` / `turn.completed` 终止事件（用最后一条 `meta` 标记 session 结束，但作为 noise drop）
- **无 token usage**（kimi v0.28.1 `-p` 模式不输出 token 计数）
- 无显式 error event 类型（错误通过 stderr + non-zero exit code 表达）
- 工具名跟 claude-code 同形：`Bash` / `Read` / `Write` / `Edit` / `Glob` / `Grep` / `ReadMediaFile`

---

## 3. 架构设计

### 3.1 KimiBackend 类（复用 BaseBackend 模板）

```
backend/app/backends/kimi.py
├── KimiBackend(BaseBackend)
│   ├── name = "kimi"
│   ├── ALLOWED_NOISE_TYPES: frozenset = {("meta", "session.resume_hint")}
│   ├── setup_workspace(workdir, skills_src)  # 同 CodexBackend 模式
│   ├── build_command(workdir, prompt, keyframes) -> argv
│   └── parse_event(raw) -> Optional[AgentEvent]
└── register_backend("kimi", KimiBackend)  # 自动注册
```

### 3.2 `setup_workspace`（与 CodexBackend 几乎一致）

```python
def setup_workspace(self, workdir, skills_src):
    # symlink skills/ 到 workdir root
    skills_link = workdir / "skills"
    if not skills_link.exists():
        skills_link.symlink_to(skills_src.absolute(), target_is_directory=True)
    
    # symlink AGENTS.md 到 workdir root（kimi 自动加载，已验证）
    agents_link = workdir / "AGENTS.md"
    if not agents_link.exists():
        agents_link.symlink_to((skills_src / "AGENTS.md").resolve())
    
    # symlink CLAUDE.md -> AGENTS.md（防御性，跟 codex/claude 一致；
    # AGENTS.md 已 backend-neutral，对所有 backend 通用）
    claude_link = workdir / "CLAUDE.md"
    if not claude_link.exists():
        claude_link.symlink_to((skills_src / "AGENTS.md").resolve())
```

### 3.3 `build_command`

```python
def build_command(self, workdir, prompt, keyframes):
    # KIMI_BIN_PATH 默认 ~/.kimi-code/bin/kimi，可用 env 覆盖
    bin_path = os.getenv("KIMI_BIN_PATH", os.path.expanduser("~/.kimi-code/bin/kimi"))
    return [
        bin_path,
        "-p", prompt,
        "--output-format", "stream-json",
    ]
    # NOTE: workdir 通过 subprocess cwd= 传递（base.stream() 已处理）
    # NOTE: keyframes 不通过 CLI flag 传递，列在 prompt 里绝对路径，agent 用 ReadMediaFile 读
    # NOTE: 无需 --yolo（实测 -p 模式自动批准工具调用）
```

### 3.4 `parse_event`（OpenAI chat completion → AgentEvent mapping）

| kimi 原始事件 | AgentEvent | 说明 |
|---|---|---|
| `{"role":"meta","type":"session.resume_hint",...}` | `None` (drop) | session-end marker，无价值 |
| `{"role":"assistant","tool_calls":[...]}` (有 tool_calls) | `{"type":"tool_call", "content":"<工具名 join>", ...}` | content 是工具名列表，跟 claude-code 一致 |
| `{"role":"assistant","content":"<text>"}` (无 tool_calls) | `{"type":"text", "content":"<text>", ...}` | 纯文本回答 |
| `{"role":"tool","tool_call_id":"...","content":"..."}` | `{"type":"tool_result", "content":"", ...}` | content 留空（raw 保留完整信息，前端如需可深读 raw.tool_call_id 关联） |
| `{"role":"assistant","content":"<text>","tool_calls":[...]}` | tool_call 优先 | 跟 claude-code 一致：assistant 同时有 text+tool_calls 时按 tool_call 分类 |
| 其他未知 | `{"type":"text", "content":"", ...}` | fallback，跟 codex/claude-code 一致 |

**Usage 字段**：kimi 不输出 token usage，`parse_event` 返回的所有 event `usage=None`。前端 usage panel 显示 "—"，不阻塞功能。

**完成信号**：kimi 无显式 `result` event，orchestrator 通过 `base.stream()` 的 `await proc.wait()` + `proc.returncode == 0` 判断成功完成（无需特殊处理）。

### 3.5 Binary Path 解析（`config.py`）

```python
# backend/app/config.py 加一行
KIMI_BIN_PATH = os.getenv("KIMI_BIN_PATH", os.path.expanduser("~/.kimi-code/bin/kimi"))
```

**默认绝对路径**覆盖 99% macOS 场景（用户实测就在 `~/.kimi-code/bin/kimi`）；用户如果用 `npm i -g @moonshot-ai/kimi-code` 装到 PATH，可设 `KIMI_BIN_PATH=kimi` 覆盖。

`KimiBackend.build_command()` 内部读 `KIMI_BIN_PATH`（不放在 `__init__`，避免 backend registry 实例化时机早于 env 加载）。

### 3.6 注册（`backends/__init__.py`）

```python
# 文件末尾加一行
from . import kimi as _kimi  # noqa: F401 (triggers register_backend on import)
```

注册后 `BACKEND_REGISTRY` 自动包含 `"kimi"`，frontend SettingsPanel dropdown / orchestrator / e2e scripts 全部自动识别（已 backend-neutral）。

---

## 4. 文件改动清单

### 新建

| 文件 | 行数估计 | 用途 |
|------|---------|------|
| `backend/app/backends/kimi.py` | ~120 | KimiBackend 实现 |
| `backend/tests/unit/test_kimi_backend.py` | ~80 | parse_event 单元测试 |

### 修改

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/backends/__init__.py` | 加 `from . import kimi as _kimi` | +1 |
| `backend/app/config.py` | 加 `KIMI_BIN_PATH = os.getenv(...)` | +1 |
| `backend/.env.example` | 加注释行示例 | +1 |

### 不改（已 backend-neutral）

- ❌ `backend/app/backends/base.py`（BaseBackend ABC 已抽象完）
- ❌ `backend/app/orchestrator.py`（已 backend-neutral）
- ❌ `backend/app/routers/pipeline.py`（router 通过 effective_backend fallback）
- ❌ `frontend/src/components/SettingsPanel.tsx`（dropdown 从 BACKEND_REGISTRY 自动列）
- ❌ `backend/app/skills/AGENTS.md`（已 backend-neutral 重写）
- ❌ `backend/app/skills/vfx-shader/SKILL.md`（已 backend-neutral）
- ❌ `backend/tests/e2e/*`（collect / generate / run 已支持 `--backend` flag）

---

## 5. 测试方案

### 5.1 单元测试（`test_kimi_backend.py`）

覆盖 `parse_event` 各种 event type：
- assistant with tool_calls → tool_call event
- assistant with content only → text event
- assistant with content + tool_calls → tool_call event（优先级）
- tool result → tool_result event
- meta session.resume_hint → None（drop）
- 完全未知 event → text fallback
- 空 dict / 缺字段 → text fallback（不 raise）

注册测试（已有 `test_backend_registry.py` 模板）：导入 `backends.kimi` 后 `BACKEND_REGISTRY` 包含 `"kimi"`。

### 5.2 烟雾测试（手动）

1. `cd backend && python -m pytest tests/unit/ -v` → 全绿（包括新加的 kimi tests + 现有 78 tests）
2. 启动 backend + frontend，SettingsPanel 下拉出现 "kimi"
3. 选 "kimi" → POST /run 一个简单 sample（4-col-grad）→ 观察 events 流式推送
4. 前端 AgentLog 正常渲染 kimi 事件
5. Pipeline 收敛 → render_final.png 正确生成

### 5.3 E2E 验证（可选）

跑 1-2 个简单 sample（4-col-grad + heart-2d）验证完整 6-phase 流程，对比 codex/claude-code 同 sample 结果。**不在 spec 范围**（属于 benchmark 阶段）。

---

## 6. 风险与限制

| 风险 | 影响 | 处理 |
|------|------|------|
| kimi 不在 PATH | build_command 找不到 binary | 默认绝对路径 `~/.kimi-code/bin/kimi`，env `KIMI_BIN_PATH` 可覆盖 |
| 无 token usage | 前端 usage panel / collect 报告 token 字段空 | 接受为已知限制，前端显示 "—"，collect 端 skip usage 渲染 |
| k3 thinking 模式可能慢 | 600s timeout 可能不够 | 沿用默认 600s（用户可调），benchmark 后按需调 |
| `-p` 模式不能加 `--yolo`/`--auto` | 无（实测自动批准） | 不阻塞，无需特殊处理 |
| kimi 升级到 v0.29+ 可能引入 breaking change | 未来风险 | 跟踪 moonshotai/kimi-code 升级；spec 文档锁定 v0.28.1 行为 |
| k3 effort 默认 "high" | 可能影响延迟 | 默认沿用 config.toml，不强制覆盖 |
| ReadMediaFile tool 行为依赖 k3 agent 自主决策 | 可能漏读关键帧 | SKILL.md Phase 1 已明确要求分析关键帧；prompt 也列路径 |

---

## 7. 实施顺序（writing-plans skill 详化）

1. 写 `backend/app/backends/kimi.py`（参考 claude_code.py 模板）
2. 修改 `backend/app/backends/__init__.py`（+1 行 import）
3. 修改 `backend/app/config.py`（+1 行 KIMI_BIN_PATH）
4. 修改 `backend/.env.example`（+1 行示例）
5. 写 `backend/tests/unit/test_kimi_backend.py`
6. 跑 `python -m pytest tests/unit/ -v` 验证 80+ tests 全绿
7. 烟雾测试（SettingsPanel + 1 sample run）

预计实施时间：30-45 分钟（fixer 单 lane 即可完成，所有改动都在 backend/backends/ 目录）。

---

## 8. 不在范围内

- Benchmark 20-sample 跑测（属于后续优化阶段）
- Token usage 兼容层（kimi 输出 → orchestrator/collect 兼容；当前接受为 None）
- kimi 升级到 v0.29+ 的 breaking change 适配（未来工作）
- 关键帧图片传递方式优化（当前 prompt 列路径 + ReadMediaFile 已工作）
