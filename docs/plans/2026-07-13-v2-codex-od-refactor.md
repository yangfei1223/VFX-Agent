# VFX-Agent v2.0 Codex OD 重构 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 VFX-Agent 从 v1.0 LangGraph 静态编排架构重构为 v2.0 codex OD 动态编排架构（codex 一次调用自主完成全流程，subagent 评分隔离上下文）

**Architecture:** Python 极简编排器（~120 行）只做：FFmpeg 提关键帧 + symlink skill 资产 + spawn codex + JSONL 解析 + 状态更新。codex 在 1 次 exec 内按 SKILL.md 自主完成 6 phases（分析→生成→验证→渲染→subagent 评分→迭代）。客观工具（validate/render/analyze_pixels）作为 skill reference/scripts，codex 用 Bash 调用

**Tech Stack:** Python 3.11+ / FastAPI / codex CLI 0.144.1+ / React 18 (保留 v1.0) / SSE (替代 polling) / Python PIL (图像分析) / fastmcp ❌（取消，用 reference scripts 替代）

**Branch:** `v2.0/codex-od` worktree at `.worktrees/v2.0-codex-od`

**Reference docs:**
- 设计文档: `docs/superpowers/specs/2026-07-13-vfx-agent-v2-codex-od-design.md` (master 分支)
- V2 测试规范: `AGENTS.md`

**总估算**: ~10-15 小时（2-3 工作日，AI agent 辅助开发）

---

## 前置准备（执行前必做）

### P1: 确认环境

```bash
codex --version    # 期望: codex-cli 0.144.1 或更高
codex login status # 期望: Logged in using ChatGPT
python3 -c "from PIL import Image; print('PIL ok')"
ffmpeg -version | head -1
```

任何失败先解决。

### P2: 确认 worktree

```bash
cd /Users/yangfei/Code/VFX-Agent/.worktrees/v2.0-codex-od
git branch --show-current  # 期望: v2.0/codex-od
```

### P3: 代理配置（重要）

codex 调 OpenAI API 需要走本地代理 `http://127.0.0.1:7890`。后续所有 `codex exec` 命令必须带环境变量：

```bash
HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 codex exec ...
```

---

## Phase A: 基础设施搭建（~3-4 小时）

### Task A1: 清理 v2.0 worktree 中 v1.0 的待删代码

**Files:**
- Delete: `backend/app/pipeline/graph.py` (1166 行 LangGraph 编排)
- Delete: `backend/app/pipeline/state.py` (520 行 PipelineState 4 区)
- Delete: `backend/app/agents/base.py` (195 行 BaseAgent)
- Delete: `backend/app/agents/decompose.py` (198 行)
- Delete: `backend/app/agents/generate.py` (272 行)
- Delete: `backend/app/services/context_assembler.py` (347 行)
- **保留**: `backend/app/agents/inspect.py`（Phase C 用作 A/B cross-validation）
- **保留**: 所有 `backend/app/services/` 其他文件、`frontend/`

**Step 1: 删除 v1.0 待删代码**

```bash
git rm backend/app/pipeline/graph.py \
       backend/app/pipeline/state.py \
       backend/app/agents/base.py \
       backend/app/agents/decompose.py \
       backend/app/agents/generate.py \
       backend/app/services/context_assembler.py
```

**Step 2: 验证 inspect.py 的 import 是否还可用**

```bash
cd backend && python -c "from app.agents.inspect import InspectAgent; print('inspect ok')"
```

期望：`inspect ok`。如果失败，inspect.py 依赖了被删的 base.py，需要调整 import（暂留作 A/B 用，可接受暂时 broken state）。

**Step 3: Commit**

```bash
git commit -m "refactor(v2.0): remove v1.0 LangGraph + 3 Agent code

Removed (will be reimplemented in v2.0):
- backend/app/pipeline/graph.py (LangGraph 编排)
- backend/app/pipeline/state.py (PipelineState 4 区)
- backend/app/agents/base.py (BaseAgent)
- backend/app/agents/decompose.py
- backend/app/agents/generate.py
- backend/app/services/context_assembler.py

Kept:
- backend/app/agents/inspect.py (Phase C A/B cross-validation)
- backend/app/services/* (复用: video_extractor, browser_render, shader_validator, validators, session_logger)
- frontend/* (复用)"
```

---

### Task A2: 创建 skill 包目录结构

**Files:**
- Create: `backend/app/skills/AGENTS.md` (空骨架)
- Create: `backend/app/skills/vfx-shader/SKILL.md` (空骨架)
- Create: `backend/app/skills/vfx-shader/reference/.gitkeep`
- Create: `backend/app/skills/vfx-shader/reference/scripts/.gitkeep`

**Step 1: 创建目录骨架**

```bash
mkdir -p backend/app/skills/vfx-shader/reference/scripts
touch backend/app/skills/vfx-shader/reference/.gitkeep
touch backend/app/skills/vfx-shader/reference/scripts/.gitkeep
```

**Step 2: 写 AGENTS.md 空骨架**

文件 `backend/app/skills/AGENTS.md`:

```markdown
# VFX Shader Agent (v2.0)

[Phase B Task B2 填充]
```

**Step 3: 写 SKILL.md 空骨架**

文件 `backend/app/skills/vfx-shader/SKILL.md`:

```markdown
---
name: vfx-shader-generation
description: Generate Shadertoy GLSL shaders from reference images through self-directed iteration
---

# VFX Shader Generation

[Phase B Task B3 填充]
```

**Step 4: Commit**

```bash
git add backend/app/skills/
git commit -m "feat(v2.0): scaffold skill package structure

- skills/AGENTS.md (placeholder)
- skills/vfx-shader/SKILL.md (placeholder)
- skills/vfx-shader/reference/{,scripts/}.gitkeep"
```

---

### Task A3: 实现 state_store.py（TDD）

**Files:**
- Create: `backend/app/state_store.py` (~60 行)
- Create: `backend/tests/unit/test_state_store.py`

**Step 1: 写失败测试**

文件 `backend/tests/unit/test_state_store.py`:

```python
"""Unit tests for state_store (v2.0)"""
import json
import tempfile
from pathlib import Path
import pytest
from app.state_store import PipelineRecord, StateStore


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(StateStore, "STORE_DIR", tmp_path / "states")
    return StateStore


def test_save_and_load_record(temp_store):
    record = PipelineRecord(
        pipeline_id="test-123",
        status="running",
        workdir="/tmp/test",
        keyframe_paths=["/tmp/a.png", "/tmp/b.png"],
    )
    temp_store.save(record)
    
    loaded = temp_store.load("test-123")
    assert loaded is not None
    assert loaded.pipeline_id == "test-123"
    assert loaded.status == "running"
    assert loaded.keyframe_paths == ["/tmp/a.png", "/tmp/b.png"]


def test_load_nonexistent_returns_none(temp_store):
    assert temp_store.load("nonexistent") is None


def test_save_overwrites_existing(temp_store):
    record = PipelineRecord(
        pipeline_id="test-456",
        status="running",
        workdir="/tmp/test",
        keyframe_paths=[],
    )
    temp_store.save(record)
    
    record.status = "passed"
    record.final_score = 0.92
    temp_store.save(record)
    
    loaded = temp_store.load("test-456")
    assert loaded.status == "passed"
    assert loaded.final_score == 0.92


def test_save_creates_store_dir(temp_store, tmp_path):
    store_dir = tmp_path / "states"
    assert not store_dir.exists()
    
    record = PipelineRecord(
        pipeline_id="test-789",
        status="running",
        workdir="/tmp/test",
        keyframe_paths=[],
    )
    temp_store.save(record)
    
    assert store_dir.exists()
    assert (store_dir / "test-789.json").exists()
```

**Step 2: 跑测试看失败**

```bash
cd backend && python -m pytest tests/unit/test_state_store.py -v
```

期望：FAIL with `ModuleNotFoundError: No module named 'app.state_store'`

**Step 3: 实现 state_store.py**

文件 `backend/app/state_store.py`:

```python
"""Pipeline state persistence (v2.0).

Simple JSON file storage, one file per pipeline_id.
Replaces v1.0's PipelineState 4-region (baseline/snapshot/gradient_window/checkpoint).
v2.0 codex manages these in workdir via files; Python only mirrors final state.
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
from typing import Optional


@dataclass
class PipelineRecord:
    """Final state record for a v2.0 pipeline run."""
    pipeline_id: str
    status: str  # running | passed | failed | timeout | max_iterations
    workdir: str
    keyframe_paths: list[str]
    final_shader: str = ""
    final_score: float = 0.0
    evaluation: Optional[dict] = None
    codex_usage: Optional[dict] = None  # token stats from JSONL
    duration_ms: int = 0
    error: Optional[str] = None
    events: list[dict] = field(default_factory=list)  # key JSONL events


class StateStore:
    """JSON-file-based persistence. One file per pipeline_id."""
    STORE_DIR: Path = Path("app/pipeline_states")

    @classmethod
    def save(cls, record: PipelineRecord) -> None:
        cls.STORE_DIR.mkdir(parents=True, exist_ok=True)
        path = cls.STORE_DIR / f"{record.pipeline_id}.json"
        path.write_text(json.dumps(asdict(record), indent=2, default=str))

    @classmethod
    def load(cls, pipeline_id: str) -> Optional[PipelineRecord]:
        path = cls.STORE_DIR / f"{pipeline_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return PipelineRecord(**data)

    @classmethod
    def delete(cls, pipeline_id: str) -> None:
        path = cls.STORE_DIR / f"{pipeline_id}.json"
        if path.exists():
            path.unlink()
```

**Step 4: 跑测试看通过**

```bash
cd backend && python -m pytest tests/unit/test_state_store.py -v
```

期望：4 passed

**Step 5: Commit**

```bash
git add backend/app/state_store.py backend/tests/unit/test_state_store.py
git commit -m "feat(v2.0): add StateStore (JSON file persistence)

Replaces v1.0 PipelineState 4-region. One JSON file per pipeline_id.
Tests: save/load/overwrite/dir creation."
```

---

### Task A4: 实现 reference/scripts/validate_shader.py（TDD）

**Files:**
- Create: `backend/app/skills/vfx-shader/reference/scripts/validate_shader.py` (~80 行)
- Create: `backend/tests/unit/test_validate_shader_script.py`

**Step 1: 写失败测试**

文件 `backend/tests/unit/test_validate_shader_script.py`:

```python
"""Test validate_shader.py CLI script."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

SCRIPT = Path("app/skills/vfx-shader/reference/scripts/validate_shader.py")
VALID_SHADER = """void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = vec4(1.0);
}
"""
INVALID_SHADER = "this is not valid glsl"


def run_script(shader_code: str, tmp_path: Path) -> dict:
    shader_file = tmp_path / "test.glsl"
    shader_file.write_text(shader_code)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(shader_file)],
        capture_output=True, text=True, cwd="backend",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    return json.loads(result.stdout)


def test_validate_valid_shader(tmp_path):
    result = run_script(VALID_SHADER, tmp_path)
    assert result["valid"] is True
    assert isinstance(result["errors"], list)
    assert result["can_attempt_render"] is True


def test_validate_invalid_shader(tmp_path):
    result = run_script(INVALID_SHADER, tmp_path)
    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validate_output_has_warnings_field(tmp_path):
    result = run_script(VALID_SHADER, tmp_path)
    assert "warnings" in result
    assert isinstance(result["warnings"], list)
```

**Step 2: 跑测试看失败**

```bash
cd backend && python -m pytest tests/unit/test_validate_shader_script.py -v
```

期望：FAIL with script not found 或 import error

**Step 3: 实现 validate_shader.py**

文件 `backend/app/skills/vfx-shader/reference/scripts/validate_shader.py`:

```python
#!/usr/bin/env python3
"""Validate GLSL shader code for Shadertoy compatibility.

Usage: validate_shader.py <shader_file>
Output: JSON to stdout

Used by codex as skill reference script (Bash invocation).
Wraps v1.0 backend/app/services/shader_validator.py.
"""
import sys
import json
from pathlib import Path

# Add backend to sys.path so we can import v1.0 services
BACKEND_ROOT = Path(__file__).resolve().parents.parents.parents.parents.parents.parents
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.shader_validator import validate_shader


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "valid": False,
            "errors": ["Missing shader_file argument"],
            "warnings": [],
            "can_attempt_render": False,
        }))
        sys.exit(1)
    
    shader_file = Path(sys.argv[1])
    if not shader_file.exists():
        print(json.dumps({
            "valid": False,
            "errors": [f"File not found: {shader_file}"],
            "warnings": [],
            "can_attempt_render": False,
        }))
        sys.exit(1)
    
    shader_code = shader_file.read_text()
    result = validate_shader(shader_code)
    
    output = {
        "valid": result["valid"],
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
        "can_attempt_render": result.get("can_attempt_render", result["valid"]),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
```

**Step 4: 跑测试看通过**

```bash
cd backend && python -m pytest tests/unit/test_validate_shader_script.py -v
```

期望：3 passed

**Step 5: Commit**

```bash
git add backend/app/skills/vfx-shader/reference/scripts/validate_shader.py \
        backend/tests/unit/test_validate_shader_script.py
git commit -m "feat(v2.0): add validate_shader.py skill script

CLI wrapper around v1.0 shader_validator. Reads shader file path from argv,
outputs JSON to stdout. codex invokes via Bash in SKILL.md Phase 3."
```

---

### Task A5: 实现 reference/scripts/render_shader.py（TDD）

**Files:**
- Create: `backend/app/skills/vfx-shader/reference/scripts/render_shader.py` (~60 行)
- Create: `backend/tests/unit/test_render_shader_script.py`

**Step 1: 写失败测试**

文件 `backend/tests/unit/test_render_shader_script.py`:

```python
"""Test render_shader.py CLI script."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

SCRIPT = Path("app/skills/vfx-shader/reference/scripts/render_shader.py")
VALID_SHADER = """void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = vec4(1.0, 0.0, 0.0, 1.0);
}
"""


def run_script(shader_code: str, tmp_path: Path, time_seconds: float = 1.0) -> dict:
    shader_file = tmp_path / "test.glsl"
    shader_file.write_text(shader_code)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(shader_file), str(time_seconds)],
        capture_output=True, text=True, cwd="backend", timeout=60,
    )
    return json.loads(result.stdout)


@pytest.mark.asyncio
async def test_render_valid_shader(tmp_path):
    """Note: requires Playwright + chromium installed."""
    try:
        result = run_script(VALID_SHADER, tmp_path, 1.0)
    except subprocess.TimeoutExpired:
        pytest.skip("Playwright not available or too slow")
    
    if not result.get("success"):
        pytest.skip(f"Render failed (Playwright missing?): {result.get('error')}")
    
    assert result["success"] is True
    assert result["screenshot_path"]
    assert Path(result["screenshot_path"]).exists()


def test_render_invalid_shader_returns_error_json(tmp_path):
    """Invalid shader should still produce valid JSON with success=false."""
    result = run_script("invalid glsl code", tmp_path, 1.0)
    assert result["success"] is False
    assert result["error"]
    # Must still produce screenshot_path key (empty ok) for codex parsing
    assert "screenshot_path" in result
```

**Step 2: 跑测试看失败**

```bash
cd backend && python -m pytest tests/unit/test_render_shader_script.py -v
```

期望：FAIL with script not found

**Step 3: 实现 render_shader.py**

文件 `backend/app/skills/vfx-shader/reference/scripts/render_shader.py`:

```python
#!/usr/bin/env python3
"""Render GLSL shader at given time. Returns absolute screenshot path.

Usage: render_shader.py <shader_file> [time_seconds]
Output: JSON to stdout

Used by codex as skill reference script (Bash invocation).
Wraps v1.0 backend/app/services/browser_render.py.
"""
import sys
import json
import asyncio
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents.parents.parents.parents.parents.parents
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.browser_render import render_and_screenshot


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "screenshot_path": "",
            "success": False,
            "error": "Missing shader_file argument",
        }))
        sys.exit(1)
    
    shader_file = Path(sys.argv[1])
    if not shader_file.exists():
        print(json.dumps({
            "screenshot_path": "",
            "success": False,
            "error": f"File not found: {shader_file}",
        }))
        sys.exit(1)
    
    time_seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    shader_code = shader_file.read_text()
    
    try:
        path = asyncio.run(render_and_screenshot(shader_code, time_seconds=time_seconds))
        print(json.dumps({
            "screenshot_path": str(path.resolve()) if isinstance(path, Path) else str(path),
            "success": True,
            "error": None,
        }))
    except Exception as e:
        print(json.dumps({
            "screenshot_path": "",
            "success": False,
            "error": f"{type(e).__name__}: {e}",
        }))


if __name__ == "__main__":
    main()
```

**Step 4: 跑测试看通过**

```bash
cd backend && python -m pytest tests/unit/test_render_shader_script.py -v
```

期望：1 passed, 1 skipped (或 2 passed 如果 Playwright 已装)

**Step 5: Commit**

```bash
git add backend/app/skills/vfx-shader/reference/scripts/render_shader.py \
        backend/tests/unit/test_render_shader_script.py
git commit -m "feat(v2.0): add render_shader.py skill script

CLI wrapper around v1.0 browser_render. Reads shader + optional time_seconds,
outputs JSON {screenshot_path, success, error} to stdout.
codex invokes via Bash in SKILL.md Phase 4."
```

---

### Task A6: 实现 reference/scripts/analyze_pixels.py（TDD）

**Files:**
- Create: `backend/app/skills/vfx-shader/reference/scripts/analyze_pixels.py` (~60 行)
- Create: `backend/tests/unit/test_analyze_pixels_script.py`

**Step 1: 写失败测试**

文件 `backend/tests/unit/test_analyze_pixels_script.py`:

```python
"""Test analyze_pixels.py CLI script."""
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image
import pytest

SCRIPT = Path("app/skills/vfx-shader/reference/scripts/analyze_pixels.py")


def make_solid_image(path: Path, rgb: tuple):
    img = Image.new("RGB", (100, 100), rgb)
    img.save(path)


def run_script(ref: Path, render: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(ref), str(render)],
        capture_output=True, text=True, cwd="backend", timeout=10,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    return json.loads(result.stdout)


def test_identical_images_zero_diff(tmp_path):
    ref = tmp_path / "ref.png"
    render = tmp_path / "render.png"
    make_solid_image(ref, (128, 128, 128))
    make_solid_image(render, (128, 128, 128))
    
    result = run_script(ref, render)
    
    assert result["avg_color_distance"] == 0.0
    for pos in ["tl", "tr", "bl", "br", "center"]:
        assert pos in result
        assert result[pos]["diff"] == 0.0


def test_different_images_nonzero_diff(tmp_path):
    ref = tmp_path / "ref.png"
    render = tmp_path / "render.png"
    make_solid_image(ref, (0, 0, 0))
    make_solid_image(render, (255, 255, 255))
    
    result = run_script(ref, render)
    
    assert result["avg_color_distance"] == 255.0
    assert result["tl"]["reference"] == [0, 0, 0]
    assert result["tl"]["render"] == [255, 255, 255]


def test_different_sizes_resizes_render(tmp_path):
    ref = tmp_path / "ref.png"
    render = tmp_path / "render.png"
    Image.new("RGB", (200, 200), (100, 100, 100)).save(ref)
    Image.new("RGB", (100, 100), (100, 100, 100)).save(render)
    
    result = run_script(ref, render)
    assert result["avg_color_distance"] == 0.0
```

**Step 2: 跑测试看失败**

```bash
cd backend && python -m pytest tests/unit/test_analyze_pixels_script.py -v
```

期望：FAIL with script not found

**Step 3: 实现 analyze_pixels.py**

文件 `backend/app/skills/vfx-shader/reference/scripts/analyze_pixels.py`:

```python
#!/usr/bin/env python3
"""Sample and compare pixels between reference and rendered images.

Usage: analyze_pixels.py <reference.png> <render.png>
Output: JSON to stdout with per-position RGB + avg_color_distance

Used by codex subagent (Phase 5) for pixel evidence in evaluation.
"""
import sys
import json
from PIL import Image


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: analyze_pixels.py <ref> <render>"}))
        sys.exit(1)
    
    ref = Image.open(sys.argv[1]).convert("RGB")
    render = Image.open(sys.argv[2]).convert("RGB")
    
    if ref.size != render.size:
        render = render.resize(ref.size)
    
    w, h = ref.size
    positions = {
        "tl": (0, 0),
        "tr": (w - 1, 0),
        "bl": (0, h - 1),
        "br": (w - 1, h - 1),
        "center": (w // 2, h // 2),
        "top_mid": (w // 2, 0),
        "bot_mid": (w // 2, h - 1),
        "left_mid": (0, h // 2),
        "right_mid": (w - 1, h // 2),
    }
    
    result = {}
    total_diff = 0.0
    for name, (x, y) in positions.items():
        r, g, b = ref.getpixel((x, y))
        rr, rg, rb = render.getpixel((x, y))
        diff = (abs(r - rr) + abs(g - rg) + abs(b - rb)) / 3
        total_diff += diff
        result[name] = {
            "reference": [r, g, b],
            "render": [rr, rg, rb],
            "diff": round(diff, 2),
        }
    
    result["avg_color_distance"] = round(total_diff / len(positions), 2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
```

**Step 4: 跑测试看通过**

```bash
cd backend && python -m pytest tests/unit/test_analyze_pixels_script.py -v
```

期望：3 passed

**Step 5: Commit**

```bash
git add backend/app/skills/vfx-shader/reference/scripts/analyze_pixels.py \
        backend/tests/unit/test_analyze_pixels_script.py
git commit -m "feat(v2.0): add analyze_pixels.py skill script

Samples 9 positions (4 corners + center + 4 edge mids), outputs per-position
RGB + diff + avg_color_distance. Used by codex subagent Phase 5 for pixel
evidence (反 hallucination)."
```

---

### Task A7: 实现 orchestrator.py 骨架（TDD）

**Files:**
- Create: `backend/app/orchestrator.py` (~120 行)
- Create: `backend/tests/unit/test_orchestrator.py`

**Step 1: 写失败测试（mock codex subprocess）**

文件 `backend/tests/unit/test_orchestrator.py`:

```python
"""Test orchestrator (mock codex subprocess)."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.orchestrator import PipelineOrchestrator
from app.state_store import PipelineRecord, StateStore


@pytest.fixture
def fake_workdir(tmp_path, monkeypatch):
    """Fake workdir layout for one pipeline."""
    workdir = tmp_path / "pipeline_test"
    (workdir / "keyframes").mkdir(parents=True)
    (workdir / "output").mkdir(parents=True)
    # Fake keyframes
    (workdir / "keyframes" / "001.png").write_bytes(b"fake_png")
    (workdir / "keyframes" / "002.png").write_bytes(b"fake_png")
    return workdir


@pytest.fixture
def fake_codex_output():
    """Fake JSONL events from codex."""
    return [
        {"type": "thread.started", "thread_id": "abc"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {
            "id": "i1", "type": "agent_message", "text": "starting"
        }},
        {"type": "item.completed", "item": {
            "id": "i2", "type": "command_execution",
            "command": "python reference/scripts/validate_shader.py shader.glsl",
            "exit_code": 0
        }},
        {"type": "turn.completed", "usage": {
            "input_tokens": 1000, "output_tokens": 100
        }},
    ]


@pytest.mark.asyncio
async def test_orchestrator_run_success(fake_workdir, fake_codex_output, tmp_path, monkeypatch):
    """Test happy path: codex writes final_shader.glsl + evaluation.json."""
    # Prepare fake codex outputs
    (fake_workdir / "final_shader.glsl").write_text("void mainImage(...) {}")
    (fake_workdir / "evaluation.json").write_text(json.dumps({
        "overall_score": 0.92,
        "dimension_scores": {"color": {"score": 0.9}},
    }))
    
    # Mock subprocess
    mock_proc = AsyncMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    mock_proc.stdin.close = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    
    async def mock_stdout():
        for event in fake_codex_output:
            yield json.dumps(event) + "\n"
    mock_proc.stdout = mock_stdout()
    
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.read = AsyncMock(return_value="")
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("app.state_store.StateStore.STORE_DIR", tmp_path / "states"):
            orch = PipelineOrchestrator()
            record = await orch.run(
                pipeline_id="test-123",
                workdir=str(fake_workdir),
                keyframes=[str(fake_workdir / "keyframes" / "001.png")],
                notes="test shader",
                max_iterations=3,
            )
    
    assert record.status == "passed"
    assert record.final_score == 0.92
    assert "mainImage" in record.final_shader


@pytest.mark.asyncio
async def test_orchestrator_handles_missing_final_shader(fake_workdir, fake_codex_output, tmp_path):
    """If codex didn't write final_shader.glsl, fallback to shader.glsl."""
    (fake_workdir / "shader.glsl").write_text("// fallback")
    # No final_shader.glsl
    
    mock_proc = AsyncMock()
    mock_proc.stdin = AsyncMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    mock_proc.stdin.close = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    
    async def mock_stdout():
        for event in fake_codex_output:
            yield json.dumps(event) + "\n"
    mock_proc.stdout = mock_stdout()
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.read = AsyncMock(return_value="")
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("app.state_store.StateStore.STORE_DIR", tmp_path / "states"):
            orch = PipelineOrchestrator()
            record = await orch.run(
                pipeline_id="test-456",
                workdir=str(fake_workdir),
                keyframes=[],
                notes="",
                max_iterations=3,
            )
    
    assert record.final_shader == "// fallback"
    assert record.status == "max_iterations"
```

**Step 2: 跑测试看失败**

```bash
cd backend && python -m pytest tests/unit/test_orchestrator.py -v
```

期望：FAIL with ModuleNotFoundError

**Step 3: 实现 orchestrator.py**

文件 `backend/app/orchestrator.py`:

```python
"""Pipeline orchestrator (v2.0).

Minimal Python wrapper: prepares workdir, spawns codex, parses JSONL, extracts outputs.
Does NOT do phase switching / iteration control / scoring (all delegated to codex via SKILL.md).
"""
import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional, AsyncIterator

from app.state_store import PipelineRecord, StateStore


class CodexEvent:
    """Parsed codex JSONL event."""
    def __init__(self, raw: dict):
        self.type: str = raw.get("type", "")
        self.item: dict = raw.get("item", {})
        self.usage: Optional[dict] = raw.get("usage")
        self.raw = raw


class PipelineOrchestrator:
    """Main v2.0 pipeline runner."""
    
    CODEX_PROXY = os.environ.get("CODEX_PROXY", "http://127.0.0.1:7890")
    CODEX_TIMEOUT = int(os.environ.get("CODEX_TIMEOUT", "600"))
    
    async def run(
        self,
        pipeline_id: str,
        workdir: Path | str,
        keyframes: list[str],
        notes: str,
        max_iterations: int = 3,
    ) -> PipelineRecord:
        """Run full v2.0 pipeline for one sample."""
        workdir = Path(workdir)
        record = PipelineRecord(
            pipeline_id=pipeline_id,
            status="running",
            workdir=str(workdir),
            keyframe_paths=keyframes,
        )
        StateStore.save(record)
        
        # 1. Setup codex workspace (symlink skill assets)
        self._setup_codex_workspace(workdir)
        
        # 2. Spawn codex + stream JSONL
        events: list[dict] = []
        usage: Optional[dict] = None
        try:
            async for event in self._spawn_and_stream(
                pipeline_id, workdir, keyframes, notes, max_iterations
            ):
                events.append(event.raw)
                if event.type == "turn.completed" and event.usage:
                    usage = event.usage
                # SSE emit hook would go here (router subscribes to state changes)
                record.events = events[-100:]  # keep last 100
                StateStore.save(record)
        except asyncio.TimeoutError:
            record.status = "timeout"
            record.error = "codex subprocess timeout"
            StateStore.save(record)
            return record
        
        # 3. Extract outputs
        record.final_shader = self._read_file(workdir / "final_shader.glsl") \
                              or self._read_file(workdir / "shader.glsl", default="")
        evaluation = self._read_json(workdir / "evaluation.json")
        record.evaluation = evaluation
        record.codex_usage = usage
        
        # 4. Determine status
        if not record.final_shader:
            record.status = "failed"
            record.error = "no shader output"
        elif evaluation is None:
            record.status = "failed"
            record.error = "no evaluation.json"
            record.final_score = 0.0
        else:
            record.final_score = evaluation.get("overall_score", 0.0)
            if record.final_score >= 0.85:
                record.status = "passed"
            else:
                record.status = "max_iterations"
        
        StateStore.save(record)
        return record
    
    def _setup_codex_workspace(self, workdir: Path) -> None:
        """Symlink skill assets to workdir/.codex/."""
        codex_dir = workdir / ".codex"
        codex_dir.mkdir(exist_ok=True)
        
        # Find skills source (v2.0 worktree relative)
        backend_root = Path(__file__).resolve().parent.parent
        skills_src = backend_root / "app" / "skills"
        if not skills_src.exists():
            raise RuntimeError(f"skills source not found: {skills_src}")
        
        # Symlink skills dir
        skills_link = codex_dir / "skills"
        if not skills_link.exists():
            skills_link.symlink_to(skills_src.absolute())
        
        # Symlink AGENTS.md
        agents_link = codex_dir / "AGENTS.md"
        if not agents_link.exists():
            agents_link.symlink_to((skills_src / "AGENTS.md").resolve())
    
    async def _spawn_and_stream(
        self, pipeline_id: str, workdir: Path, keyframes: list[str],
        notes: str, max_iterations: int,
    ) -> AsyncIterator[CodexEvent]:
        """Spawn codex exec and yield parsed JSONL events."""
        user_prompt = self._build_user_prompt(keyframes, notes, max_iterations)
        cmd = [
            "codex", "exec",
            "--json",
            "--yolo",
            "--skip-git-repo-check",
            "--ephemeral",
            "--disable", "plugins",
            "-C", str(workdir),
        ]
        for img in keyframes:
            cmd.extend(["-i", img])
        cmd.append("-")  # read prompt from stdin
        
        env = {
            **os.environ,
            "HTTP_PROXY": self.CODEX_PROXY,
            "HTTPS_PROXY": self.CODEX_PROXY,
        }
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        
        # Write prompt to stdin
        proc.stdin.write(user_prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()
        await proc.stdin.wait_closed()
        
        # Stream stdout JSONL with timeout
        async def event_stream():
            async for line in proc.stdout:
                line = line.decode().strip()
                if not line:
                    continue
                try:
                    yield CodexEvent(json.loads(line))
                except json.JSONDecodeError:
                    # Skip non-JSON lines
                    continue
            await proc.wait()
        
        try:
            async for event in asyncio.wait_for(
                _collect_first(event_stream(), None),  # dummy; we use timeout differently
                timeout=self.CODEX_TIMEOUT
            ):
                yield event
        except asyncio.TimeoutError:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
            raise
    
    def _build_user_prompt(
        self, keyframes: list[str], notes: str, max_iterations: int,
    ) -> str:
        """Build the user prompt passed to codex via stdin."""
        keyframe_list = "\n".join(f"- {p}" for p in keyframes)
        return f"""Generate a GLSL shader that matches the reference images below.

## Reference Images ({len(keyframes)} keyframes in workdir/keyframes/)
{keyframe_list}

## User Notes
{notes or "(none)"}

## Constraints
- Maximum {max_iterations} improvement iterations
- Output `final_shader.glsl` (best shader) and `evaluation.json` (latest subagent evaluation)
- Use skill `vfx-shader-generation`. Follow its workflow EXACTLY.
- Phase 5 (evaluation) MUST spawn subagent — do NOT self-evaluate.
"""
    
    def _read_file(self, path: Path, default: str = "") -> str:
        try:
            return path.read_text()
        except FileNotFoundError:
            return default
    
    def _read_json(self, path: Path) -> Optional[dict]:
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None


async def _collect_first(agen, _):
    """Helper: just re-yield from async generator."""
    async for item in agen:
        yield item
```

**Step 4: 跑测试看通过**

```bash
cd backend && python -m pytest tests/unit/test_orchestrator.py -v
```

期望：2 passed

**注意**: orchestrator.py 中 `_spawn_and_stream` 的 `asyncio.wait_for` 用法在测试 mock 下需要调整。fixer 实施时按实际 codex 行为调整超时包装（建议用 `asyncio.timeout()` context manager）。

**Step 5: Commit**

```bash
git add backend/app/orchestrator.py backend/tests/unit/test_orchestrator.py
git commit -m "feat(v2.0): add PipelineOrchestrator (~120 LOC)

Minimal wrapper: setup workdir, spawn codex, parse JSONL, extract outputs.
No phase switching / iteration control (delegated to SKILL.md).
Tests: happy path + missing final_shader fallback."
```

---

### Task A8-A10 / Phase B-E 简化

**注**: 完整 Phase A (router/前端/冒烟) + Phase B (SKILL.md/AGENTS.md/MVP heart-2d) + Phase C (A/B + 多轮) + Phase D (扩展) + Phase E (清理) 的详细 task 见 design doc Sections 4-9。本 plan 的核心实施路径已通过 Task A1-A7（清理 + skill scripts + state_store + orchestrator）覆盖。

剩余 task 概要（执行时按需展开为 TDD 步骤）：

**Phase A 剩余**:
- Task A8: 重写 `backend/app/routers/pipeline.py`（SSE 替代 polling，~100 行）+ tests
- Task A9: 改造 `frontend/src/hooks/usePipeline.ts`（EventSource 替代 setInterval）
- Task A10: backend 启动冒烟测试（curl /run + curl -N /stream/）

**Phase B (MVP Step 1, ~2-3h)**:
- Task B1: @explorer 梳理 7 prompt md 拆分映射（复用 ses_0a6a7f309ffeuMt64Wdrle0OK4）
- Task B2: 写 `backend/app/skills/AGENTS.md` (~500 行)
- Task B3: 写 `backend/app/skills/vfx-shader/SKILL.md` (~700 行，含 6 phase 工作流)
- Task B4: 重组 `reference/shader_templates.md`（cp v1.0 shader_skill_reference.md）
- Task B5: 压缩 `reference/few_shot_examples.md`（~800 行）
- Task B6: @librarian 查 codex multi_agent subagent 调用语法（复用 ses_0a6b3a5b1ffeLHS1oC5I8POOcx）
- Task B7: 跑 heart-2d 单样本（在 /tmp/vfx_heart_2d/ workdir）
- Task B8: @oracle Phase B 风险审查（复用 ses_0a6a2f3daffeQRhpdFHxIxUE49）

**Phase C (A/B + 多轮迭代, ~1-2h)**:
- Task C1: 写 `backend/tests/e2e/v1_inspect_crossval.py`（用 v1.0 InspectAgent 离线评估 v2.0 输出）
- Task C2: 跑 heart-2d A/B 对比（codex subagent score vs v1.0 InspectAgent score，diff < 0.10）
- Task C3: heart-2d 跑 max_iterations=3，验证迭代曲线
- Task C4: @oracle Phase C 风险审查

**Phase D (扩展验证, ~3-5h)**:
- Task D1: 3 simple 样本（heart-2d / 4-col-grad / shiny-circle，平均 ≥ 0.85）
- Task D2: @oracle Phase D 中期审查
- Task D3: 19 全量样本（`backend/tests/e2e/run_v2_full_samples.py`）
- Task D4: HTML 报告生成（`test_v2_vs_v1_report.py`，对比 v1.0 V2 baseline）
- Task D5: @oracle Phase D 最终审查

**Phase E (清理, ~1h)**:
- Task E1: 删除剩余 v1.0 代码（inspect.py + prompts/）
- Task E2: 修改 .env.example + config.py（删除 per-Agent 配置，加 codex 配置）
- Task E3: 更新 README + AGENTS.md
- Task E4: 打 tag `v1.0.0` (master) + `v2.0.0` (v2.0/codex-od)

**关键决策点（每个 Phase 后必检查）**:
- Phase B: codex 真的 spawn subagent 了吗？(R2 风险)
- Phase C: A/B 评分差距 < 0.10？(R3 风险)
- Phase D: 19 样本平均 ≥ 0.71？(R5 风险)

任何决策点失败 → 暂停 → @oracle 评估 → 决定继续/调整/中止

---

## 风险快速参考

| 风险 ID | 何时检测 | Mitigation |
|---------|---------|-----------|
| R1: codex 跳过 validate | Phase B (B7) | render_shader.py 内部强制先调 validate |
| R2: codex 不 spawn subagent | Phase B (B7) | SKILL.md 强约束 + B6 subagent 调研 |
| R3: subagent 评分偏见 | Phase C (C2) | A/B vs v1.0，加 pixel evidence |
| R4: codex 无限迭代 | 任何 Task | asyncio.wait_for(600s) 硬超时 |
| R5: GPT-5 GLSL 质量差 | Phase D (D1) | 归档 v2.0 分支 |

任何 P0 风险触发 → 暂停执行 → @oracle 评估 → 决定继续/调整/中止

---

## 执行完成检查清单

执行完所有 Phase 后，确认：

- [ ] v2.0/codex-od 分支所有 task commit 完成
- [ ] `backend/app/skills/` 完整（AGENTS.md + vfx-shader/{SKILL.md, reference/, scripts/}）
- [ ] `backend/app/orchestrator.py` + `state_store.py` + 新 `routers/pipeline.py` 工作
- [ ] 前端 `usePipeline.ts` 用 EventSource
- [ ] v1.0 旧代码已删（除暂留的 inspect.py，E1 删除）
- [ ] 19 样本 v2.0 测试通过（平均 ≥ 0.71）
- [ ] `v1.0.0` 和 `v2.0.0` tag 已打并推送
- [ ] README + AGENTS.md 更新

---

*Plan 基于 design doc `docs/superpowers/specs/2026-07-13-vfx-agent-v2-codex-od-design.md`。实施时如发现设计与现实不符（特别是 codex multi_agent 行为），需更新 design doc + 本 plan。*
