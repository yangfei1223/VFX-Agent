---
name: vfx-benchmark
description: VFX-Agent v2.0 系统 benchmark 标准测试方法。用 Playwright 模拟前端用户路径跑 20 samples（v1.0 baseline 19 + windows-95），完整归档每 sample 的视效分析、shader、渲染截图、前端 UI 截图、codex 关键日志，输出 HTML 主报告。用于系统迭代后的回归测试 + 动态 pipeline 编排优化分析。
---

# VFX-Agent v2.0 Benchmark

## When to Use

- v2.0 系统 prompt/skill/orchestrator 改动后做回归测试
- 评估系统迭代效果（对比上次 baseline）
- 排查性能/质量回归（找哪些 sample 退步了）
- 动态 pipeline 编排优化分析（codex_events.md 是核心数据源）

## 前置条件

1. **Backend 运行中**（默认 :8000）
   ```bash
   cd /Users/yangfei/Code/VFX-Agent/.worktrees/v2.0-codex-od/backend && \
     python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
   ```
2. **Frontend 运行中**（默认 :5173）
   ```bash
   cd /Users/yangfei/Code/VFX-Agent/.worktrees/v2.0-codex-od/frontend && npm run dev &
   ```
3. **API key 已配置**（`backend/.env`）
4. **代理可用**（codex 调 OpenAI 需要 `http://127.0.0.1:7890`）
5. **测试样本完整**（`/Users/yangfei/Code/VFX-Agent/test-samples/data/`，20 个 `.webm` + `.json`）

健康检查：
```bash
curl -s -o /dev/null -w "backend: %{http_code}\n" http://localhost:8000/pipeline/status/test
curl -s -o /dev/null -w "frontend: %{http_code}\n" http://localhost:5173/
```
两者必须 200。

## 测试样本（20 samples）

v1.0 baseline 19 + windows-95（新增）。完整列表见 `run_v2_samples_via_ui.py:DEFAULT_SAMPLES`。

| 难度 | 数量 | 示例 |
|------|------|------|
| simple | 6 | 4-col-grad, heart-2d, shiny-circle, twitter-blue-check, hypnotic-ripples, buffer-bloom |
| medium | 9 | plasma-waves, supah-frosted-glass, vortex-street, warp-speed2, cool-s-distance, liquid-galss-test, liquid-glass-ui, water-color-blending, windows-95 |
| complex | 5 | auroras, electron, happy-diwali-2019, sparks-drifting |

## 执行步骤（三步走）

### Step 1: 跑测试（前端路径，2-3 小时）

```bash
cd /Users/yangfei/Code/VFX-Agent/.worktrees/v2.0-codex-od/backend && \
  nohup python tests/e2e/run_v2_samples_via_ui.py --all > /tmp/vfx-benchmark.log 2>&1 &
disown
```

**单 sample 或子集测试**：
```bash
python tests/e2e/run_v2_samples_via_ui.py 4-col-grad heart-2d
python tests/e2e/run_v2_samples_via_ui.py windows-95  # 单独测新样本
```

**输出**：
- `/tmp/vfx_v2_runs/sample_pipeline_map.json` — sample → pipeline_id 映射
- `/tmp/vfx_v2_runs/<sample>_keyframe.png` — 提取的关键帧
- `/tmp/vfx_v2_runs/<sample>_ui_pre.png` — 触发前 UI 截图
- `/tmp/vfx_v2_runs/<sample>_ui_post.png` — 完成后 UI 截图

**进度监控**（不阻塞测试）：
```bash
tail -f /tmp/vfx-benchmark.log
# 或看 map 文件
watch -n 30 'cat /tmp/vfx_v2_runs/sample_pipeline_map.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"done: {len(d)}/20\"); [print(f\"  {r[\\\"sample\\\"]:<25} {r[\\\"status\\\"]:<15} {r.get(\\\"score\\\", 0):.3f}\") for r in d]"'
```

**中断后恢复**：脚本每次完整重跑（map-file 被覆盖）。要保留之前的部分结果，先备份 `sample_pipeline_map.json`。

### Step 2: 收集归档

```bash
cd /Users/yangfei/Code/VFX-Agent/.worktrees/v2.0-codex-od/backend && \
  python tests/e2e/collect_v2_results.py
```

**输入**：`/tmp/vfx_v2_runs/sample_pipeline_map.json`（必须存在）
**输出**：`backend/test_results/<YYYY-MM-DD>_v2-codex-od-20samples/`

归档结构（v1.0 baseline 兼容 + v2.0 扩展）：
```
backend/test_results/2026-07-15_v2-codex-od-20samples/
├── index.html                       # 主 HTML 报告（来自 Step 3）
├── test_results.json                # 20 samples 汇总（AGENTS.md schema）
├── sample_classifications.json      # 样本元数据汇总
└── <sample_name>/                   # 每 sample 子目录
    ├── pipeline_state.json          # PipelineRecord 完整状态
    ├── reference_frame.png          # 参考关键帧
    ├── shader.glsl                  # 最终 shader
    ├── visual_description.json      # Phase 1 输出
    ├── evaluation.json              # Phase 5 subagent 评分
    ├── render_final.png             # 最终渲染
    ├── render_iter_*.png            # 各迭代渲染（如有）
    ├── ui_pre.png                   # 触发前前端 UI 截图（v2.0 新增）
    ├── ui_post.png                  # 完成后前端 UI 截图（v2.0 新增）
    └── codex_events.md              # codex 关键事件时间线（v2.0 新增）
```

### Step 3: 生成 HTML 报告

```bash
cd /Users/yangfei/Code/VFX-Agent/.worktrees/v2.0-codex-od/backend && \
  python tests/e2e/generate_v2_report.py
```

**输入**：`/tmp/v2_report_data.json`（Step 2 已生成）
**输出**：`backend/test_results/<YYYY-MM-DD>_v2-codex-od-20samples/index.html`

打开报告：
```bash
open backend/test_results/$(date +%Y-%m-%d)_v2-codex-od-20samples/index.html
```

## 关键评估指标

| 指标 | 公式 | 目标 |
|------|------|------|
| **平均 score** | mean(v2_scores) | ≥ 0.75（v1.0 baseline 0.715） |
| **通过率** | count(score ≥ 0.85) / 20 | ≥ 30% |
| **v1.0 delta** | v2_avg - v1_avg | ≥ 0 |
| **timeout 率** | count(status=timeout) / 20 | ≤ 20% |
| **平均耗时** | mean(elapsed_s) | ≤ 400s |
| **平均 token** | mean(input_tokens) | ≤ 50k |

## 结果分析维度

### 1. 全局视图（HTML 报告）

`index.html` 包含：
- 摘要面板（passed/failed/avg score/v1 delta）
- 评分分布表（按 v2 score 降序）
- 每 sample 卡片：reference vs render 对比 + 8 维 dimension scores + issues + effect_type

### 2. 按 effect_type 分类分析

```bash
python3 -c "
import json
d = json.load(open('backend/test_results/$(date +%Y-%m-%d)_v2-codex-od-20samples/test_results.json'))
from collections import defaultdict
by_type = defaultdict(list)
for s, r in d.items():
    by_type[r.get('effect_type', 'unknown')].append(r['score'])
for et, scores in sorted(by_type.items()):
    print(f'{et:<25} n={len(scores)} avg={sum(scores)/len(scores):.3f} pass={sum(1 for s in scores if s>=0.85)}/{len(scores)}')
"
```

### 3. codex_events.md 人审（动态编排优化核心）

每个 sample 的 `codex_events.md` 是优化动态 pipeline 编排的核心数据。看以下模式：

- **Phase 1 视觉分析是否准确**：codex 识别的效果类型、颜色、动画特征
- **Phase 5 subagent 评分质量**：与 reference 的对比是否合理
- **迭代效率**：每次迭代后 score 提升多少？哪次迭代收益最大？
- **失败模式**：
  - 编译失败（validate_shader.py 报错后 codex 怎么修）
  - 渲染黑屏（codex 怎么诊断）
  - 评分误判（subagent 给出过高/过低分）
- **时间分布**：哪个 phase 耗时最长？是否有时间浪费

### 4. UI 截图对比

`ui_pre.png` vs `ui_post.png` 验证前端是否正确显示：
- STATUS / PIPELINE PROGRESS 是否更新到最终状态
- EVALUATION 是否展示 score + dimension
- USAGE 是否展示 token 用量
- PREVIEW 是否渲染 shader

UI 显示滞后或不更新是潜在 bug 来源。

## 常见问题

### Q: 单 sample 测试失败怎么 debug？

```bash
# 1. 跑单 sample 看完整日志
python tests/e2e/run_v2_samples_via_ui.py <sample> 2>&1 | tee /tmp/debug.log

# 2. 看具体 workdir 的 codex events
cat /tmp/vfx_workdirs/p<id>-*/shader.glsl
cat /tmp/vfx_workdirs/p<id>-*/evaluation.json

# 3. 直接复现前端操作（agent-browser 交互式）
agent-browser open http://localhost:5173
agent-browser upload "input[type=file]" /tmp/vfx_v2_runs/<sample>_keyframe.png
agent-browser fill "textarea[placeholder*='Describe']" "test <sample>"
agent-browser click "button:has-text('Generate Shader')"
```

### Q: 测试中途挂了怎么办？

map-file 是 interruption-safe 的，每个 sample 跑完就写一次。已经跑完的 sample 数据在 map-file 里。可以：

1. **看哪些 sample 还没跑**：
   ```bash
   python3 -c "
   import json
   done = {r['sample'] for r in json.load(open('/tmp/vfx_v2_runs/sample_pipeline_map.json'))}
   all_samples = ['4-col-grad', 'auroras', 'buffer-bloom', 'cool-s-distance', 'electron', 'happy-diwali-2019', 'heart-2d', 'hypnotic-ripples', 'liquid-galss-test', 'liquid-glass-ui', 'moon-distance-2d', 'plasma-waves', 'shiny-circle', 'sparks-drifting', 'supah-frosted-glass', 'twitter-blue-check', 'vortex-street', 'warp-speed2', 'water-color-blending', 'windows-95']
   remaining = [s for s in all_samples if s not in done]
   print(' '.join(remaining))
   "
   ```
2. **跑剩下的**（map-file 会被覆盖，需要先合并）：
   ```bash
   cp /tmp/vfx_v2_runs/sample_pipeline_map.json /tmp/map_backup.json
   python tests/e2e/run_v2_samples_via_ui.py <remaining samples...>
   # 然后手动合并 map_backup + 新 map
   ```

### Q: backend 或 frontend 挂了？

测试脚本不会自动重启 backend/frontend。需要手动恢复后从中断 sample 续跑（见上）。

### Q: 测试结果怎么对比上次？

```bash
# 列出历次结果
ls -d backend/test_results/*v2-codex-od-20samples/ | sort

# 手动对比指标
python3 -c "
import json
runs = ['2026-07-14', '2026-07-15']  # 改成实际日期
for r in runs:
    f = f'backend/test_results/{r}_v2-codex-od-20samples/test_results.json'
    try:
        d = json.load(open(f))
        scores = [s['score'] for s in d.values()]
        passed = sum(1 for s in d.values() if s['status'] == 'passed')
        print(f'{r}: avg={sum(scores)/len(scores):.3f} passed={passed}/{len(scores)}')
    except FileNotFoundError:
        print(f'{r}: not found')
"
```

## 迭代优化工作流

```
[系统改动]
   ↓
跑 benchmark
   ↓
分析 index.html + codex_events.md + UI 截图
   ↓
找到瓶颈（哪个 effect_type 退步 / 哪个 phase 卡住）
   ↓
针对性优化（skill prompt / orchestrator / few-shot examples）
   ↓
跑 benchmark 对比
   ↓
循环
```

**核心原则**：每次改动后必须跑完整 benchmark 验证不退步，不能只跑 smoke test。

## 测试参数（如需调整）

| 参数 | 默认值 | 位置 |
|------|--------|------|
| `max_iterations` | 3 | `app/routers/config.py` (runtime config) |
| `passing_threshold` | 0.85 | `PipelineOrchestrator.PASSING_SCORE` |
| `CODEX_TIMEOUT` | 600s | `orchestrator.py` 或环境变量 |
| sample 超时 | 600s | `run_v2_samples_via_ui.py:poll_pipeline_status()` |

调整方法：
- 临时：改环境变量 + 重启 backend
- 永久：通过 `PUT /config` API（如已实现）

## 输出归档保留策略

- **保留所有历次 benchmark 结果**（不要删除 `backend/test_results/<date>_v2-codex-od-20samples/`）
- 单次归档约 50-200 MB（含截图 + HTML base64 嵌入）
- 关键 benchmark 打 git tag：`git tag benchmark-2026-07-15-avg0.75`
- `backend/test_results/` 已在 `.gitignore`，commit 历史只看 tag

## 参考

- **v1.0 baseline 报告**：`/Users/yangfei/Code/VFX-Agent/backend/test_results/2026-05-18_e2e-v2-baseline-19samples/index.html`
- **v2.0 设计文档**：`docs/superpowers/specs/2026-07-13-vfx-agent-v2-codex-od-design.md`
- **AGENTS.md 测试规范**：v2.0 worktree `AGENTS.md` 的"测试规范"章节
- **脚本源码**：
  - `backend/tests/e2e/run_v2_samples_via_ui.py` — 前端 UI 驱动测试
  - `backend/tests/e2e/collect_v2_results.py` — 归档收集
  - `backend/tests/e2e/generate_v2_report.py` — HTML 报告生成
