# VFX-Agent V2.0 Prompt Stack 优化 - 实施任务清单

> **REQUIRED SUBSKILL:** Use superpowers:executing-plans to execute this plan task-by-task.

**Goal:** 优化 VFX-Agent 三 Agent 架构，引入 Closed Vocabulary、量化 Token、强制步骤序列和 Self-check，提升首次生成质量和迭代效率。

**Key Concepts (从 open-design 借鉴并适配 Shader/GLSL 领域):**
- **Closed Vocabulary:** effect_type 只有 5 种（ripple/glow/gradient/frosted/flow），而非自由描述
- **Token Resolution:** `{effect.ripple}` → sdCircle + sin wave，`{edge.soft_medium}` → smoothstep(-0.02, 0.02)
- **P0/P1/P2 Anti-patterns:** P0: raymarching/texture>8；P1: 单色无RGB；P2: suggested_technique 过复杂
- **强制步骤序列:** Step 1 → Step 2 → Step 3 → Step 4，而非自由推理
- **Self-check before output:** Token Coverage + Anti-pattern Check，而非事后 Inspect
- **Prompt Stack:** Shared Constraints → Effect Catalog → Agent Steps → Self-check

**Required Fields (强制量化字段):**
- `color_definition.primary_rgb` (如 `(0.2, 0.5, 1.0)`)
- `animation_definition.duration` (如 `3s`)
- `shape_definition.edge_width` (如 `0.02-0.03 UV`)
- `background_definition.strict` (true/false)

---

## Task 1: 修复 re_decompose mode 传参 (P0 - 已完成)

**Status:** ✅ Completed (commit 485b576)

**Files:**
- Modify: `backend/app/pipeline/graph.py:node_decompose`
- Modify: `backend/app/agents/decompose.py:run_legacy`
- Test: `backend/test_re_decompose.py` (新建)

**Step 1: Write failing test**

```python
# backend/test_re_decompose.py
"""测试 re_decompose mode 是否正确传参"""
import pytest
from app.pipeline.graph import node_decompose
from app.pipeline.state import create_initial_state

def test_re_decompose_mode_passed_to_agent():
    """验证 re_decompose mode 正确传入 Agent"""
    # 创建触发 re_decompose 的状态
    state = create_initial_state(
        pipeline_id="test-re-decompose",
        input_type="image",
        image_paths=["example/demo.png"],
    )
    state["snapshot"]["iteration"] = 2
    state["checkpoint"]["best_score"] = 0.45  # <0.5 触发 re_decompose
    state["snapshot"]["inspect_feedback"] = {
        "overall_score": 0.45,
        "visual_issues": ["测试失败"],
        "re_decompose_trigger": True,
    }
    
    # 执行 node_decompose
    result = node_decompose(state)
    
    # 验证：Agent 应收到 mode="re_decompose"
    # 检查 session 文件或日志中是否包含 Failure Log
    assert "Failure Log" in result.get("details", "") or result.get("mode") == "re_decompose"
```

**Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest test_re_decompose.py -v`

Expected: FAIL - mode not passed, Failure Log not injected

**Step 3: Write minimal implementation**

```python
# backend/app/pipeline/graph.py (node_decompose)
def node_decompose(state: PipelineState) -> dict:
    # ...existing code...
    
    # 判断是否为 re_decompose 模式
    mode = "cold_start"
    if should_trigger_re_decompose(state) and iteration > 0:
        mode = "re_decompose"
        print(f"[Decompose Node] Re-decompose triggered at iteration {iteration}")
    
    # 创建完整 state 用于 Agent.run
    full_state = state
    
    # 直接调用 Agent 新接口（而非 legacy）
    from app.agents.decompose import DecomposeAgent
    agent = DecomposeAgent()
    result = agent.run(full_state, mode=mode, return_raw=True)
    
    # ...rest of code...
```

```python
# backend/app/agents/decompose.py (Agent.run)
def run(self, state: PipelineState, mode: str = "cold_start", return_raw: bool = False) -> dict:
    """分析输入的视觉参考，输出自然语言视效语义描述
    
    Args:
        state: PipelineState（包含 baseline + snapshot + gradient_window + checkpoint）
        mode: "cold_start" | "re_decompose"  # ← 新增参数
        return_raw: 是否返回原始响应
    """
    # 使用 ContextAssembler 组装上下文（传入 mode）
    system_prompt, user_prompt, image_paths = build_decompose_prompt(state, mode)
    
    # ...existing code...
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_re_decompose.py -v`

Expected: PASS - Failure Log injected, mode="re_decompose"

**Step 5: Commit**

```bash
git add backend/app/pipeline/graph.py backend/app/agents/decompose.py backend/test_re_decompose.py
git commit -m "fix: pass re_decompose mode to Decompose Agent, inject Failure Log"
```

---

## Task 2: 新增 Shared VFX Constraints (P1)

**Files:**
- Create: `backend/app/prompts/shared_vfx_constraints.md`
- Modify: `backend/app/services/context_assembler.py`
- Test: `backend/test_shared_constraints.py`

**Step 1: Write failing test**

```python
# backend/test_shared_constraints.py
"""测试 Shared VFX Constraints 是否注入三 Agent"""
from app.services.context_assembler import build_decompose_prompt, build_generate_prompt, build_inspect_prompt

def test_shared_constraints_injected():
    """验证所有 Agent prompt 包含 P0 禁止项"""
    state = {}  # minimal state
    
    # Decompose
    sys, user, images = build_decompose_prompt(state, "cold_start")
    assert "raymarching" in sys
    assert "texture fetch >8" in sys
    
    # Generate
    sys, user = build_generate_prompt(state)
    assert "raymarching" in sys
    
    # Inspect
    sys, user, images = build_inspect_prompt(state)
    assert "模糊描述" in sys
```

**Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest test_shared_constraints.py -v`

Expected: FAIL - constraints not injected

**Step 3: Write minimal implementation**

```markdown
# backend/app/prompts/shared_vfx_constraints.md

## P0 禁止项（三 Agent 必须遵循）

1. **禁止 raymarching**
   - Generate Agent 输出检查：shader 无 `rayDirection`、`ro`、`rd`
   - 理由：超出 Mobile GPU 性能范围

2. **禁止 texture fetch >8**
   - Generate Agent 输出检查：`texture()` 调用 ≤8
   - 理由：Mobile GPU 限制

3. **禁止模糊描述**
   - Decompose Agent 输出检查：无"颜色好看"、"动画自然"
   - Inspect Agent 输出检查：feedback 具体可操作

4. **禁止默认紫色**
   - Decompose Agent 输出检查：主色调 ≠ RGB(0.5, 0.2, 0.8)

5. **禁止背景约束缺失**
   - Decompose Agent 输出检查：background.strict 正确设置

6. **禁止动画时长缺失**
   - Decompose Agent 输出检查：animation.duration 存在

7. **禁止 edge width 缺失**
   - Decompose Agent 输出检查：shape.edge_width 存在
```

```python
# backend/app/services/context_assembler.py
def build_decompose_prompt(state, mode="cold_start"):
    constraints = load_prompt("shared_vfx_constraints")
    system_prompt = load_prompt("decompose_system") + "\n\n" + constraints
    # ...

def build_generate_prompt(state):
    constraints = load_prompt("shared_vfx_constraints")
    system_prompt = load_prompt("generate_system") + "\n\n" + constraints
    # ...

def build_inspect_prompt(state):
    constraints = load_prompt("shared_vfx_constraints")
    system_prompt = load_prompt("inspect_system") + "\n\n" + constraints
    # ...
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_shared_constraints.py -v`

Expected: PASS - constraints injected

**Step 5: Commit**

```bash
git add backend/app/prompts/shared_vfx_constraints.md backend/app/services/context_assembler.py backend/test_shared_constraints.py
git commit -m "feat: add shared VFX constraints for all agents (P0 banned items)"
```

---

## Task 3: 新增 VFX Effect Catalog (P1)

> **注意**：此 Catalog 定义参考 `docs/design/vfx-agent-v2-architecture.md` 的完整 Token 库。

**Files:**
- Create: `backend/app/prompts/vfx_effect_catalog.md`
- Modify: `backend/app/services/context_assembler.py`
- Test: `backend/test_effect_catalog.py`

**Step 1: Write failing test**

```python
# backend/test_effect_catalog.py
"""测试 VFX Effect Catalog 是否注入（完整 Token 库）"""
from app.services.context_assembler import build_decompose_prompt, build_generate_prompt

def test_effect_catalog_complete_tokens():
    """验证 Catalog 包含完整 Token 库（参考设计文档）"""
    state = {}
    sys, user, images = build_decompose_prompt(state, "cold_start")
    
    # 1. Effect Types (5 种基础 + 4 种粒子)
    assert "{effect.ripple}" in sys
    assert "{effect.glow}" in sys
    assert "{effect.gradient}" in sys
    assert "{effect.frosted}" in sys
    assert "{effect.flow}" in sys
    assert "{effect.particle_dots}" in sys  # 新增粒子
    assert "{effect.sparkle}" in sys
    
    # 2. SDF Shape Tokens (基础形状)
    assert "{sdf.circle}" in sys
    assert "{sdf.box}" in sys
    assert "{sdf.rounded_box}" in sys
    assert "{sdf.ring}" in sys
    assert "{sdf.arc}" in sys
    
    # 3. SDF Shape Tokens (多边形)
    assert "{sdf.triangle}" in sys
    assert "{sdf.hexagon}" in sys
    assert "{sdf.star}" in sys
    
    # 4. Boolean Operations
    assert "{sdf.union}" in sys
    assert "{sdf.smooth_union}" in sys
    assert "{sdf.subtraction}" in sys
    assert "{sdf.onion}" in sys
    
    # 5. Domain Operations
    assert "{sdf.rounded}" in sys
    assert "{sdf.repetition}" in sys
    assert "{sdf.symmetry_x}" in sys
    
    # 6. Particle Tokens
    assert "{particle.dots}" in sys
    assert "{particle.stars}" in sys
    assert "{particle.sparkle}" in sys
    
    # 7. Color/Gradient/Lighting/Noise
    assert "{color.blue}" in sys
    assert "{gradient.radial}" in sys
    assert "{lighting.glow}" in sys
    assert "{noise.perlin}" in sys
    assert "{noise.fbm}" in sys
    
    # 8. Edge/Animation/Background
    assert "{edge.soft_medium}" in sys
    assert "{anim.expand_3s}" in sys
    assert "{bg.white_strict}" in sys
    
    # 9. 禁止项说明
    assert "禁止自由发明" in sys

def test_generate_catalog_injected():
    """验证 Generate prompt 也包含完整 Catalog"""
    state = {}
    sys, user = build_generate_prompt(state)
    
    # Generate 需要的算子映射
    assert "{sdf.circle}" in sys
    assert "{sdf.smooth_union}" in sys
    assert "{noise.fbm}" in sys
```

**Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest test_effect_catalog.py -v`

Expected: FAIL - catalog not injected or incomplete

**Step 3: Write minimal implementation**

> **完整 Catalog 定义**（参考 `docs/design/vfx-agent-v2-architecture.md`，约 300 行）

```markdown
# backend/app/prompts/vfx_effect_catalog.md

## VFX Effect Catalog (Closed Vocabulary)

所有 visual_description 的值必须来自此库。**禁止自由发明。**

> 参考：docs/design/vfx-agent-v2-architecture.md（完整设计）
> 参考：iq SDF 2D (https://iquilezles.org/articles/distfunctions2d/)
> 参考：iq SDF Operations (https://iquilezles.org/articles/distfunctions/)

---

### Effect Types (必须选择其一)

**基础效果（5 种）**
| Token | Effect Name | SDF Technique | ALU |
|-------|-------------|---------------|-----|
| `{effect.ripple}` | 涟漪扩散 | sdCircle + sin(t) | ~80 |
| `{effect.glow}` | 光晕效果 | exp(-d * intensity) | ~40 |
| `{effect.gradient}` | 渐变背景 | mix() + radial/linear | ~20 |
| `{effect.frosted}` | 磨砂玻璃 | blur + noise + alpha | ~150 |
| `{effect.flow}` | 流光效果 | FBM + time offset | ~120 |

**粒子效果（4 种 - 新增）**
| Token | Description | ALU |
|-------|-------------|-----|
| `{effect.particle_dots}` | 点粒子散射效果 | ~60 |
| `{effect.particle_stars}` | 星光粒子效果 | ~100 |
| `{effect.sparkle}` | 高光闪烁效果 | ~80 |
| `{effect.particle_flow}` | 流光粒子效果 | ~150 |

---

### SDF Shape Tokens (参考 iq SDF 2D)

**基础形状（Primitives - 常用）**
| Token | SDF Function | Use Case |
|-------|-------------|---------|
| `{sdf.circle}` | sdCircle(p, r) | 涟漪、光晕、圆形主体 |
| `{sdf.box}` | sdBox(p, b) | 矩形、卡片、面板 |
| `{sdf.rounded_box}` | sdRoundedBox(p, b, r) | OS UI 元素 |
| `{sdf.ring}` | sdRing(p, r, w) | 进度环、选择框 |
| `{sdf.arc}` | sdArc(p, r, w, a1, a2) | 进度弧、仪表盘 |
| `{sdf.segment}` | sdSegment(p, a, b) | 线段、连接线 |

**多边形（Polygons - UI 图标）**
| Token | SDF Function | Use Case |
|-------|-------------|---------|
| `{sdf.triangle}` | sdEquilateralTriangle(p, r) | 提示图标 |
| `{sdf.pentagon}` | sdPentagon(p, r) | 五角形按钮 |
| `{sdf.hexagon}` | sdHexagon(p, r) | 蜂窝布局、六边形 |
| `{sdf.octagon}` | sdOctogon(p, r) | 停止图标、八角形 |
| `{sdf.star}` | sdStar(p, r, n, m) | 评分星星、五角星 |

**有机形状（Organic - 特殊效果）**
| Token | SDF Function | Use Case |
|-------|-------------|---------|
| `{sdf.ellipse}` | sdEllipse(p, ab) | 椭圆、卵形 |
| `{sdf.vesica}` | sdVesica(p, w, h) | 药丸形、胶囊 |
| `{sdf.capsule}` | sdUnevenCapsule(p, r1, r2, h) | 胶囊按钮 |
| `{sdf.heart}` | sdHeart(p) | 心形、情感图标 |

---

### Boolean Operations (参考 iq distfunctions)

**基础布尔操作**
| Token | Operation | Use Case |
|-------|-----------|---------|
| `{sdf.union}` | min(d1, d2) | 简单合并 |
| `{sdf.subtraction}` | max(-d1, d2) | 切割、镂空 |
| `{sdf.intersection}` | max(d1, d2) | 交集区域 |
| `{sdf.xor}` | max(min(d1,d2), -max(d1,d2)) | 异或区域 |

**Smooth 布尔操作**
| Token | Operation | Use Case |
|-------|-----------|---------|
| `{sdf.smooth_union}` | opSmoothUnion(d1, d2, k) | 柔和合并、blob |
| `{sdf.smooth_subtraction}` | opSmoothSubtraction(d1, d2, k) | 柔和切割 |
| `{sdf.smooth_intersection}` | opSmoothIntersection(d1, d2, k) | 柔和交集 |

---

### Domain Operations (参考 iq distfunctions)

**Rounding/Onion**
| Token | Operation | Use Case |
|-------|-----------|---------|
| `{sdf.rounded}` | sdShape(p) - r | 圆角化任何形状 |
| `{sdf.onion}` | abs(sdShape(p)) - thickness | 环形、描边 |

**Symmetry/Repetition**
| Token | Operation | Use Case |
|-------|-----------|---------|
| `{sdf.symmetry_x}` | p.x = abs(p.x) | X 轴对称 |
| `{sdf.symmetry_xy}` | p.xy = abs(p.xy) | XY 轴对称 |
| `{sdf.repetition}` | p - s * round(p/s) | 无限重复 |
| `{sdf.limited_repetition}` | p - s * clamp(round(p/s), -l, l) | 有限重复 |

---

### Particle Tokens (新增)

| Token | Technique | Use Case |
|-------|-----------|---------|
| `{particle.dots}` | hash21 + dist + alpha | 点粒子、雪花、灰尘 |
| `{particle.stars}` | hash21 + star_sdf + rotation | 星光、闪光 |
| `{particle.sparkle}` | hash21 + sin(t) + glow | 闪烁、高光点 |
| `{particle.bubbles}` | hash22 + sdCircle + float_anim | 气泡、漂浮 |
| `{particle.flow}` | hash21 + FBM + time_offset | 流光、粒子流 |
| `{particle.burst}` | hash21 + exp(-t) + radial_anim | 爆炸、散射 |
| `{particle.dust}` | voronoi + alpha_blend | 灰尘、烟雾 |

---

### Color/Gradient/Lighting/Noise Tokens

**Color Tokens（预设调色板）**
| Token | RGB | Use Case |
|-------|-----|---------|
| `{color.blue}` | (0.2, 0.5, 1.0) | 天空、科技感 |
| `{color.coral}` | (1.0, 0.5, 0.4) | 温暖、情感 |
| `{color.cyan}` | (0.0, 0.8, 0.9) | 清新、现代 |
| `{color.gold}` | (1.0, 0.8, 0.2) | 高端、奖励 |
| `{color.green}` | (0.3, 0.8, 0.4) | 成功、健康 |
| `{color.red}` | (0.9, 0.3, 0.3) | 错误、警告 |

**Gradient Tokens**
| Token | Gradient Function | Use Case |
|-------|-------------------|---------|
| `{gradient.linear}` | mix(c1, c2, t) | 线性渐变 |
| `{gradient.radial}` | mix(c1, c2, length(uv)) | 径向渐变 |
| `{gradient.angular}` | mix(c1, c2, atan(uv.y, uv.x)) | 角度渐变 |

**Lighting Tokens**
| Token | Lighting Function | Use Case |
|-------|-------------------|---------|
| `{lighting.glow}` | exp(-d * intensity) | 发光效果 |
| `{lighting.fresnel}` | pow(1.0 - dot(n, v), power) | 菲涅尔 |
| `{lighting.rim}` | 1.0 - dot(n, v) | 边缘光 |

**Noise Tokens**
| Token | Noise Function | ALU | Use Case |
|-------|----------------|-----|---------|
| `{noise.value}` | valueNoise(p) | ~20 | 简单纹理 |
| `{noise.perlin}` | perlinNoise(p) | ~40 | 自然纹理、云 |
| `{noise.simplex}` | simplexNoise(p) | ~50 | 高质量噪声 |
| `{noise.voronoi}` | voronoi(p) | ~60 | 蜂窝纹理 |
| `{noise.fbm}` | FBM(p, octaves) | ~80*octaves | 分形噪声 |

---

### Edge Tokens

| Token | Transition | Width |
|-------|------------|-------|
| `{edge.hard}` | step(d, 0) | 0.0 |
| `{edge.soft_thin}` | smoothstep(-0.01, 0.01) | 0.01 |
| `{edge.soft_medium}` | smoothstep(-0.02, 0.02) | 0.02-0.03 |
| `{edge.soft_wide}` | smoothstep(-0.05, 0.05) | 0.05 |
| `{edge.glow}` | exp(-d * 3.0) | varies |

---

### Animation Tokens

| Token | Duration | Easing |
|-------|----------|--------|
| `{anim.expand_3s}` | 3s | ease-out |
| `{anim.expand_4s}` | 4s | ease-out |
| `{anim.pulse_2s}` | 2s | sin |
| `{anim.flow}` | ∞ | linear |
| `{anim.static}` | none | none |

---

### Background Tokens

| Token | RGB | Strictness |
|-------|-----|------------|
| `{bg.white_strict}` | (1.0, 1.0, 1.0) | error <0.05 |
| `{bg.black_strict}` | (0.0, 0.0, 0.0) | error <0.05 |
| `{bg.gradient}` | varies | flexible |
| `{bg.flexible}` | any | any |

---

## 使用规则

1. **必须使用 Token**：所有字段引用此库，不能自由发明值
2. **禁止自由发明**：不能使用不在库中的值（如 "复杂效果"、"自定义形状"）
3. **量化验证**：输出前检查所有字段有对应 Token
4. **性能约束**：ALU 总和 ≤256，Texture fetch ≤8
```

```python
# backend/app/services/context_assembler.py
def build_decompose_prompt(state, mode="cold_start"):
    catalog = load_prompt("vfx_effect_catalog")
    constraints = load_prompt("shared_vfx_constraints")
    system_prompt = load_prompt("decompose_system") + "\n\n" + catalog + "\n\n" + constraints
    # ...

def build_generate_prompt(state):
    catalog = load_prompt("vfx_effect_catalog")  # Generate 也需要 Catalog 映射算子
    constraints = load_prompt("shared_vfx_constraints")
    system_prompt = load_prompt("generate_system") + "\n\n" + catalog + "\n\n" + constraints
    # ...
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_effect_catalog.py -v`

Expected: PASS - all tokens present in catalog

**Step 5: Commit**

```bash
git add backend/app/prompts/vfx_effect_catalog.md backend/app/services/context_assembler.py backend/test_effect_catalog.py
git commit -m "feat: add complete VFX effect catalog (30+ SDF, particles, operations)"
```

---

## Task 4: 修改 Decompose 强制步骤 (P1)

**Files:**
- Modify: `backend/app/prompts/decompose_system.md`
- Test: `backend/test_decompose_workflow.py`

**Step 1: Write failing test**

```python
# backend/test_decompose_workflow.py
"""测试 Decompose 强制步骤序列"""
from app.agents.decompose import DecomposeAgent
from app.pipeline.state import create_initial_state

def test_decompose_follows_workflow():
    """验证 Decompose 输出包含 Token 引用"""
    state = create_initial_state(
        pipeline_id="test-workflow",
        input_type="text",
        user_notes="涟漪效果，蓝色，纯白背景",
    )
    
    agent = DecomposeAgent()
    result = agent.run(state, mode="cold_start", return_raw=True)
    
    visual_desc = result.get("visual_description", {})
    
    # 验证强制字段
    assert visual_desc.get("effect_type") in ["ripple", "glow", "gradient", "frosted", "flow"]
    assert "rgb" in str(visual_desc.get("color_definition", {}))
    assert "duration" in str(visual_desc.get("animation_definition", {}))
    assert "edge_width" in str(visual_desc.get("shape_definition", {}))
    assert visual_desc.get("background_definition", {}).get("strict") is not None
```

**Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest test_decompose_workflow.py -v`

Expected: FAIL - missing required fields

**Step 3: Write minimal implementation**

Modify `backend/app/prompts/decompose_system.md` header section:

```markdown
# 视效解构 Agent V2.0

---

## 强制步骤序列（Agent MUST follow this workflow exactly）

### Step 1: 选择效果类型（Closed Vocabulary）

从以下 5 种选择其一：
- `{effect.ripple}` - 涟漪扩散
- `{effect.glow}` - 光晕效果
- `{effect.gradient}` - 渐变背景
- `{effect.frosted}` - 磨砂玻璃
- `{effect.flow}` - 流光效果

**禁止**：不能输出"复杂效果"、"组合效果"

### Step 2: 提取量化参数（必须包含）

| 字段 | 必须包含 |
|------|----------|
| `color_definition.primary_rgb` | RGB 值（如 `(0.2, 0.5, 1.0)`） |
| `animation_definition.duration` | 时长秒数（如 `3s`） |
| `shape_definition.edge_width` | smoothstep 宽度（如 `0.02-0.03 UV`） |
| `background_definition.strict` | true/false（根据用户要求） |

**禁止**："颜色好看"、"动画自然"、"边缘柔和"

### Step 3: 输出 visual_description

使用 VFX Effect Catalog 中的 Token。

### Step 4: 输出前自检（Self-check）

评分自己 1-5 分，任何维度 <3 分必须修复：

| Dimension | 评分标准 |
|-----------|----------|
| Effect Type 明确？ | 必须是 ripple/glow/gradient/frosted/flow |
| 所有参数量化？ | color 有 RGB、animation 有 duration、shape 有 edge_width |
| 无模糊描述？ | 不包含"颜色好看"等 |
| Background strict 正确？ | 用户强调纯白背景时 strict=true |
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_decompose_workflow.py -v`

Expected: PASS - required fields present

**Step 5: Commit**

```bash
git add backend/app/prompts/decompose_system.md backend/test_decompose_workflow.py
git commit -m "feat: add forced workflow steps + self-check to decompose_system.md"
```

---

## Task 5: 修改 Generate 强制步骤 (P1)

**Files:**
- Modify: `backend/app/prompts/generate_system.md`
- Test: `backend/test_generate_workflow.py`

**Step 1: Write failing test**

```python
# backend/test_generate_workflow.py
"""测试 Generate Self-check"""
from app.agents.generate import GenerateAgent
from app.pipeline.state import create_initial_state

def test_generate_anti_raymarching_check():
    """验证 Generate 输出无 raymarching"""
    state = create_initial_state(
        pipeline_id="test-gen",
        input_type="text",
    )
    state["snapshot"]["visual_description"] = {"effect_type": "ripple"}
    
    agent = GenerateAgent()
    result = agent.run(state, return_raw=True)
    shader = result.get("shader", "")
    
    # 验证禁止项
    assert "rayDirection" not in shader
    assert "ro" not in shader or "rotate" in shader  # ro 可能是 rotate
    
    # 验证 texture fetch ≤8
    texture_count = shader.count("texture(") + shader.count("texelFetch(")
    assert texture_count <= 8
```

**Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest test_generate_workflow.py -v`

Expected: FAIL - may contain raymarching (depending on current output)

**Step 3: Write minimal implementation**

Modify `backend/app/prompts/generate_system.md`:

```markdown
## 强制步骤序列（Agent MUST follow this workflow exactly）

### Step 1: 解析 visual_description

读取 effect_type → 选择对应算子：
- ripple → sdCircle + sin(t) expansion
- glow → exp(-d * intensity)
- gradient → mix()
- frosted → blur + noise

### Step 2: 选择算子（从 Operator Catalog）

使用 Operator Catalog 中的算子，不自由发明。

### Step 3: 输出 shader

遵循 Shadertoy 格式，禁止：
- 手动声明 iTime, iResolution
- raymarching 代码

### Step 4: 输出前自检

| Check | Requirement |
|-------|-------------|
| 编译检查 | 无语法错误 |
| Anti-raymarching | 无 rayDirection, ro, rd |
| Texture ≤8 | texture() 调用 ≤8 |
| ALU ≤256 | 算子复杂度估算 |
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_generate_workflow.py -v`

Expected: PASS - no raymarching, texture ≤8

**Step 5: Commit**

```bash
git add backend/app/prompts/generate_system.md backend/test_generate_workflow.py
git commit -m "feat: add forced workflow + anti-raymarching self-check to generate_system.md"
```

---

## Task 6: 修改 Inspect 强制步骤 (P1)

**Files:**
- Modify: `backend/app/prompts/inspect_system.md`
- Test: `backend/test_inspect_workflow.py`

**Step 1: Write failing test**

```python
# backend/test_inspect_workflow.py
"""测试 Inspect 反馈清晰度"""
from app.agents.inspect import InspectAgent
from app.pipeline.state import create_initial_state

def test_inspect_feedback_clarity():
    """验证 Inspect 反馈具体可操作"""
    state = create_initial_state(
        pipeline_id="test-inspect",
        input_type="image",
    )
    state["snapshot"]["visual_description"] = {
        "effect_type": "ripple",
        "background_definition": {"strict": True, "bg_rgb": "(1.0, 1.0, 1.0)"},
    }
    state["snapshot"]["render_screenshots"] = ["fake_render.png"]
    
    agent = InspectAgent()
    result = agent.run(state, return_raw=True)
    
    feedback = result.get("visual_issues", [])
    
    # 验证无模糊描述
    for issue in feedback:
        assert "不好" not in issue
        assert "不对" not in issue
    
    # 验证 background 严格性检查
    if state["snapshot"]["visual_description"]["background_definition"]["strict"]:
        bg_score = result.get("dimension_scores", {}).get("background", {}).get("score", 0)
        # 如果背景不匹配，background 维度应 <0.5
```

**Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest test_inspect_workflow.py -v`

Expected: FAIL - may contain vague feedback

**Step 3: Write minimal implementation**

Modify `backend/app/prompts/inspect_system.md`:

```markdown
## 强制步骤序列（Agent MUST follow this workflow exactly）

### Step 1: 解析 visual_description

读取 Token 作为对比基准：
- `{bg.white_strict}` → 检查 RGB 误差 <0.05
- `{edge.soft_medium}` → 检查 smoothstep 宽度

### Step 2: 8 维度评分

必须覆盖所有维度：composition, geometry, color, animation, background, lighting, texture, vfx_details

### Step 3: 定位视觉问题

反馈具体可操作：
- ✅ "颜色偏差：渲染 RGB(0.1, 0.3, 0.8)，应为 RGB(0.2, 0.5, 1.0)"
- ❌ "效果不好"

### Step 4: 输出前自检

| Check | Requirement |
|-------|-------------|
| 8 维度覆盖？ | 所有维度有评分 |
| Background 严格性？ | strict=true 时基于 RGB 误差评分 |
| 反馈清晰度？ | visual_issues 具体可操作 |
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_inspect_workflow.py -v`

Expected: PASS - feedback clear

**Step 5: Commit**

```bash
git add backend/app/prompts/inspect_system.md backend/test_inspect_workflow.py
git commit -m "feat: add forced workflow + feedback clarity self-check to inspect_system.md"
```

---

## Task 7: 增强 Output Schema (P2)

**Files:**
- Modify: `backend/app/pipeline/state.py`
- Test: `backend/test_schema_validation.py`

**Step 1: Write failing test**

```python
# backend/test_schema_validation.py
"""测试 visual_description 强制字段"""
from app.pipeline.state import create_initial_state

def test_visual_description_required_fields():
    """验证强制字段存在"""
    state = create_initial_state(
        pipeline_id="test-schema",
        input_type="text",
    )
    
    # 模拟 Decompose 输出
    visual_desc = {
        "effect_type": "ripple",  # ✓
        "color_definition": {"primary_rgb": "(0.2, 0.5, 1.0)"},  # ✓
        # ❌ 缺少 animation.duration
        # ❌ 缺少 shape.edge_width
    }
    
    # 验证应该失败
    required_fields = ["effect_type", "color_definition.primary_rgb", 
                       "animation_definition.duration", "shape_definition.edge_width",
                       "background_definition.strict"]
    
    for field in required_fields:
        # 检查字段存在
        parts = field.split(".")
        current = visual_desc
        for part in parts:
            assert part in current, f"Missing required field: {field}"
            current = current[part]
```

**Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest test_schema_validation.py -v`

Expected: FAIL - missing animation.duration and shape.edge_width

**Step 3: Write minimal implementation**

Modify `backend/app/pipeline/state.py`:

```python
class VisualDescriptionV2(TypedDict):
    """Visual Description V2.0 - Token-Based Schema"""
    
    # Effect Type (closed vocabulary)
    effect_type: str  # 必须为 ripple/glow/gradient/frosted/flow
    
    # Shape Definition (必须包含 edge_width)
    shape_definition: TypedDict("ShapeDef", {
        "sdf_type": str,
        "edge_type": str,  # {edge.xxx} Token
        "edge_width": str,  # 必须字段：如 "0.02-0.03 UV"
    })
    
    # Color Definition (必须包含 RGB)
    color_definition: TypedDict("ColorDef", {
        "primary_token": str,
        "primary_rgb": str,  # 必须字段：如 "(0.2, 0.5, 1.0)"
    })
    
    # Animation Definition (必须包含 duration)
    animation_definition: TypedDict("AnimDef", {
        "anim_token": str,
        "duration": str,  # 必须字段：如 "3s"
        "easing": str,
    })
    
    # Background Definition (必须包含 strict)
    background_definition: TypedDict("BgDef", {
        "bg_token": str,
        "bg_rgb": str,
        "strict": bool,  # 必须字段：true/false
    })
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest test_schema_validation.py -v`

Expected: PASS - all required fields validated

**Step 5: Commit**

```bash
git add backend/app/pipeline/state.py backend/test_schema_validation.py
git commit -m "feat: enhance visual_description schema with required fields"
```

---

## Task 8: 新增 Discovery Form UI (P2)

**Files:**
- Create: `frontend/src/components/VFXDiscoveryForm.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/test/DiscoveryForm.test.ts`

**Step 1: Write failing test**

```tsx
// frontend/src/test/DiscoveryForm.test.ts
import { render, screen } from '@testing-library/react';
import VFXDiscoveryForm from '../components/VFXDiscoveryForm';

test('discovery form renders effect types', () => {
  render(<VFXDiscoveryForm onSubmit={() => {}} />);
  
  // 验证效果类型选项
  expect(screen.getByText('涟漪扩散')).toBeInTheDocument();
  expect(screen.getByText('光晕效果')).toBeInTheDocument();
  expect(screen.getByText('纯白背景')).toBeInTheDocument();
});
```

**Step 2: Run to verify it fails**

Run: `cd frontend && npm test`

Expected: FAIL - component not exists

**Step 3: Write minimal implementation**

```tsx
// frontend/src/components/VFXDiscoveryForm.tsx
import React, { useState } from 'react';

interface DiscoveryAnswers {
  effect_type?: string;
  shape_type?: string;
  animation_type?: string;
  background_constraint?: string;
  edge_quality?: string;
}

const VFXDiscoveryForm: React.FC<{ onSubmit: (answers: DiscoveryAnswers) => void }> = ({ onSubmit }) => {
  const [answers, setAnswers] = useState<DiscoveryAnswers>({});
  
  const effectTypes = [
    { id: 'ripple', label: '涟漪扩散' },
    { id: 'glow', label: '光晕效果' },
    { id: 'gradient', label: '渐变背景' },
    { id: 'frosted', label: '磨砂玻璃' },
    { id: 'flow', label: '流光效果' },
  ];
  
  return (
    <div className="discovery-form">
      <h3>快速选择效果方向</h3>
      
      <div className="form-group">
        <label>效果类型</label>
        <div className="radio-group">
          {effectTypes.map(et => (
            <button
              key={et.id}
              onClick={() => setAnswers({ ...answers, effect_type: et.id })}
              className={answers.effect_type === et.id ? 'selected' : ''}
            >
              {et.label}
            </button>
          ))}
        </div>
      </div>
      
      <button onClick={() => onSubmit(answers)}>确认</button>
    </div>
  );
};

export default VFXDiscoveryForm;
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test`

Expected: PASS - form renders

**Step 5: Commit**

```bash
git add frontend/src/components/VFXDiscoveryForm.tsx frontend/src/App.tsx frontend/src/test/DiscoveryForm.test.ts
git commit -m "feat: add VFX Discovery Form UI component"
```