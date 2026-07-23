# Benchmark

VFX-Agent 的 benchmark 工作目录，包含测试数据集、运行脚本（作为 opencode skill reference）、所有历史 benchmark 归档。

---

## 目录结构

```
benchmark/
├── README.md                          # 本文档
├── skills/
│   └── vfx-benchmark/
│       ├── SKILL.md                   # opencode skill 定义（benchmark 执行流程）
│       └── reference/                 # benchmark 执行脚本
│           ├── run_v2_samples.py             # 通过 orchestrator 直接跑（无需 backend/frontend 起服务）
│           ├── run_v2_samples_via_ui.py      # 通过 Playwright UI 模拟真实用户路径
│           ├── collect_v2_results.py         # 收集 run results + v1.0 baseline → JSON
│           ├── generate_v2_report.py         # 生成 HTML 可视化报告
│           ├── rerender_samples.py           # 用最终 shader 重渲染截图（debug 用）
│           ├── v1_inspect_crossval.py        # v1.0 inspect agent cross-validation
│           └── v2_auto_finalize.sh           # 后台 wait + collect + generate 一条龙
├── test-samples/                      # 测试数据集（git submodule）
│   └── data/
│       ├── 4-col-grad.webm / 4-col-grad.json
│       ├── shiny-circle.webm / shiny-circle.json
│       └── ... (共 50 sample，每个 .webm + .json)
└── test_results/                      # 历史 benchmark 归档（.gitignore）
    ├── 2026-07-15_v2-codex-od-20samples/
    ├── 2026-07-16_v2-codex-od-50samples/
    ├── 2026-07-17_multi-backend-acceptance/
    ├── 2026-07-21_v2-claude-code-20samples/ (+ .tar.gz)
    └── 2026-07-23_v2-kimi-20samples/ (+ .tar.gz)
```

---

## 测试数据集（submodule）

`benchmark/test-samples/` 是 git submodule，remote: [`yangfei1223/vfx-shader-dataset`](https://github.com/yangfei1223/vfx-shader-dataset)。

每个 sample 由两个文件组成：
- `<name>.webm` — UX 视效参考视频
- `<name>.json` — 样本元信息（effect_type / difficulty / dominant_colors 等）

共 **50 samples**，覆盖 gradient / glow / shape / liquid / particle / warp / ripple / flow 等 9 类效果。

### Clone 后初始化 submodule

```bash
# 已 clone repo 后
git submodule update --init --recursive

# 或新 clone 时直接拉 submodule
git clone --recurse-submodules <repo-url>
```

---

## Benchmark skill

`skills/vfx-benchmark/SKILL.md` 是 opencode user-level skill 的副本。skill 描述了完整 benchmark 执行流程：sample 选择 → backend 选择 → 跑 → 收集 → 报告 → 归档。

skill 默认从 `~/.config/opencode/skills/vfx-benchmark/SKILL.md` 加载（用户级），repo 内的副本用于团队共享和版本控制。两边同步即可。

---

## 快速跑 benchmark

### 前置

1. **后端服务**：`uvicorn` 在 `:8000`（必须）
2. **前端服务**：`vite` 在 `:5173`（仅 `run_v2_samples_via_ui.py` 需要）
3. **Backend 配置**：在 `backend/.env` 设 `BACKEND=codex|claude-code|kimi`，或前端 SettingsPanel 切换
4. **submodule**：已初始化（见上）

### 标准流程（推荐：UI 模式 + 三步）

```bash
# 1. 跑样本（20-sample 标准集，--backend 指定 codex/claude-code/kimi）
cd <repo-root>
python benchmark/skills/vfx-benchmark/reference/run_v2_samples_via_ui.py \
    --backend codex \
    --samples 4-col-grad shiny-circle heart-2d ...

# 2. 收集结果（合并 v1.0 baseline + state files）
python benchmark/skills/vfx-benchmark/reference/collect_v2_results.py \
    --backend codex \
    --output /tmp/v2_report_data.json

# 3. 生成 HTML 报告（保存到 benchmark/test_results/<date>_<desc>/）
python benchmark/skills/vfx-benchmark/reference/generate_v2_report.py \
    --input /tmp/v2_report_data.json \
    --output benchmark/test_results/$(date +%Y-%m-%d)_v2-codex-20samples/index.html

# 打开
open benchmark/test_results/$(date +%Y-%m-%d)_v2-codex-20samples/index.html
```

### 不通过 UI 的简化模式（仅 orchestrator）

```bash
# 直接调 orchestrator，不起 frontend，速度快但无 UI 截图
python benchmark/skills/vfx-benchmark/reference/run_v2_samples.py 4-col-grad shiny-circle
```

### 一条龙后台模式

```bash
# 后台启动 run，前台 wait + collect + generate
python benchmark/skills/vfx-benchmark/reference/run_v2_samples.py 4-col-grad &
bash benchmark/skills/vfx-benchmark/reference/v2_auto_finalize.sh
```

---

## 测试参数（统一标准）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_iterations` | **3** | 单 pipeline 最大迭代次数 |
| `passing_threshold` | **0.85** | ≥0.85 PASS / 0.80-0.85 ACCEPTABLE / <0.80 FAIL |
| `timeout` | **600s** | orchestrator 级硬超时 |

---

## test_results 归档命名约定

```
benchmark/test_results/<YYYY-MM-DD>_<backend-or-context>-<N>samples/
```

例如：
- `2026-07-15_v2-codex-od-20samples/`
- `2026-07-21_v2-claude-code-20samples/`
- `2026-07-23_v2-kimi-20samples/`

每个归档目录结构：

```
<archive>/
├── index.html                # 主报告（reference vs render 对比）
├── test_results.json         # 汇总数据
└── <sample_name>/
    ├── pipeline_state.json   # 完整 pipeline state 快照
    ├── reference_frame.png   # 参考 keyframe
    ├── render_0.png ~ N.png  # 各迭代渲染截图
    ├── ui_pre.png            # UI 截图（pre-run，仅 UI 模式）
    ├── ui_post.png           # UI 截图（post-run，仅 UI 模式）
    ├── shader.glsl           # 最终 shader 源码
    ├── visual_description.json
    └── evaluation.json       # Phase 5 subagent 评分
```

`benchmark/test_results/` 整目录 gitignored（数据量大，每归档 50-300MB）。重要归档会单独打 tar.gz 上传到 GitHub Release。

---

## Release 归档

历史 benchmark report 通过 GitHub Release 分发：

| Tag | Backend | Model | Samples | Release |
|-----|---------|-------|---------|---------|
| `v2.0.2-kimi` | kimi | Kimi K3 | 20 | [link](https://github.com/yangfei1223/VFX-Agent/releases/tag/v2.0.2-kimi) |
| `v2.0.2-claude-code` | claude-code | DeepSeek V4 Pro | 20 | [link](https://github.com/yangfei1223/VFX-Agent/releases/tag/v2.0.2-claude-code) |
| `v2.0.1` | codex | GPT-5.6 Sol | 50（全量） | [link](https://github.com/yangfei1223/VFX-Agent/releases/tag/v2.0.1) |
| `v2.0.0` | codex | GPT-5.6 Sol | 20 | [link](https://github.com/yangfei1223/VFX-Agent/releases/tag/v2.0.0) |

下载 release tar.gz 后解压可直接打开 `index.html` 看完整报告。

---

## 索引：基准对比

| Backend | Model | Passed (≥0.85) | Avg score | Δ vs v1.0 (0.715) |
|---------|-------|----------------|-----------|-------------------|
| **codex**（默认） | GPT-5.6 Sol | **6/20** | **0.762** | +0.047 |
| kimi | Kimi K3 | 4/20 | 0.689 | -0.026 |
| claude-code | DeepSeek V4 Pro | 2/20 | 0.469 | -0.246 |

详见根 `README.md` 的 Multi-backend 对比章节。
