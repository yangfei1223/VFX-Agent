# VFX-Agent 端到端批量测试方案

> **目标**: 对 50 个 Shadertoy 样例进行分层抽样端到端测试，系统性识别 Pipeline 各环节问题，为针对性优化提供数据依据。
> 
> **日期**: 2026-05-18

---

## 1. 样本分层分类（基于多模态模型实际分析）

> 分类数据来源：`backend/test_e2e_results/sample_classifications.json`（使用 qwen3.5-plus 多模态模型分析 50 个样例帧）

按视觉特征实际分为 **9 个效果类别**：

| # | 类别 | 样本数 | 样本列表 | 抽样代表 | 选样理由 |
|---|------|--------|----------|----------|----------|
| **C1** | 发光/辉光 Glow | 14 | buffer-bloom, glow-shader-test2, glow-tutorial, liquid-glass-icon, magic-particles, multicolored-2d-metaball, particles4, plasma-waves, pulse-circle, shiny-circle, shiny-rectancle, strobe-light-trail, total-noob, waves-remix | **buffer-bloom**, **shiny-circle**, **plasma-waves** | 回归测试(solid/hollow) + hollow圆环 + medium复杂流动 |
| **C2** | 液态/玻璃 Liquid | 11 | akaeo-ether-liquid-glass, color-ripples, drive-home, flat-water-effects2, iterations-inversion2, liquid-galss-test, rainbow, vortex-street, warping-procedural2, water-color-blending, water-dropplet | **vortex-street**, **liquid-galss-test**, **water-color-blending** | 2D流体 + 玻璃折射 + 液态混合 |
| **C3** | 粒子/火花 Particle | 10 | dna-helis, electron, happy-diwali-2019, reactive-radial-ripples, space-rings, sparks-drifting, sparks-from-fire, star-tunnel, watch-it-burn, windows-95 | **sparks-drifting**, **happy-diwali-2019**, **electron** | 粒子飘散 + 混合场景 + 复杂能量球 |
| **C4** | 几何形状 Shape | 4 | 2d-physics-balls, glorious-line-algorithm, heart-2d, twitter-blue-check | **heart-2d**, **twitter-blue-check** | SDF心形 + 扁平形状 |
| **C5** | 光线/空间 Space | 4 | auroras, black-hole-with-accretion-risk, galaxy3, warp-speed2 | **auroras**, **warp-speed2** | 极光(复杂) + 光速穿梭(medium) |
| **C6** | 渐变/色彩 Gradient | 3 | 4-col-grad, color-gradient, supah-frosted-glass | **4-col-grad**, **supah-frosted-glass** | 多色渐变 + 磨砂玻璃 |
| **C7** | 扭曲/域变形 Warp | 2 | cool-s-distance, moon-distance-2d | **cool-s-distance**, **moon-distance-2d** | 全部测（仅2个） |
| **C8** | 涟漪 Ripple | 1 | hypnotic-ripples | **hypnotic-ripples** | 全部测（仅1个） |
| **C9** | 特殊/混合 Special | 1 | liquid-glass-ui | **liquid-glass-ui** | 全部测（仅1个） |

**总计抽样**: 9 类，**20 个代表样例**

### 抽样原则

- 大类（Glow/Liquid/Particle）选 3 个覆盖难度梯度（simple/medium/complex）
- 中类（Shape/Space/Gradient）选 2 个
- 小类（Warp/Ripple/Special）全部测试
- 包含已知问题样本（buffer-bloom 用于 fill_type 回归测试）
- 模型标记 `is_2d=False` 的样本仍保留测试（用于观察系统如何处理边界情况）

---

## 2. 测试配置

| 参数 | 值 | 说明 |
|------|---|------|
| **迭代次数** | max_iterations=3 | 允许最多 3 轮迭代 |
| **通过阈值** | passing_threshold=0.7 | 当前默认 |
| **截图尺寸** | 1024×1024 | 当前默认 |
| **关键帧数** | max_frames=6 | 从视频提取 6 帧 |
| **渲染时间点** | [0.0, 0.5, 1.0, 1.5, 2.0] | 5 个时间点截图 |
| **Pipeline 超时** | 300s (5 min/样例) | 单个样例最大执行时间 |
| **总超时** | 180min (3h) | 整批测试最大执行时间 |

---

## 3. 测试指标体系

### 3.1 Pipeline 可靠性指标

| 指标 | 采集点 | 度量 |
|------|--------|------|
| **完成率** | Pipeline 最终状态 | passed / completed / max_iterations / failed 的比例 |
| **编译成功率** | validate_shader 节点 | 首次编译通过率 vs 重试后通过率 |
| **平均迭代次数** | route_from_inspect | 收敛所需迭代轮数 |
| **超时率** | 单样例执行时间 | >300s 的样例比例 |
| **错误率** | 异常日志 | API 错误、Playwright 崩溃、FFmpeg 失败 |

### 3.2 Decompose 准确度指标

| 指标 | 采集点 | 度量 |
|------|--------|------|
| **effect_type 准确性** | visual_description.effect_type | 是否匹配参考视频的主要效果类别 |
| **shape_definition 完整性** | visual_description.shape_definition | 是否包含所有可见形状 |
| **fill_type 准确性** | visual_description.fill_type | 实心/空心是否正确 |
| **color_definition 准确性** | visual_description.color_definition | 主色调是否匹配参考 |
| **background_definition** | visual_description.background_definition | 背景类型和颜色是否匹配 |

### 3.3 Generate 质量指标

| 指标 | 采集点 | 度量 |
|------|--------|------|
| **Shadertoy 格式合规** | shader_code | 是否包含 `void mainImage` + `fragColor` |
| **代码长度** | shader_code 行数 | 是否合理（50-300 行区间） |
| **禁止项违规** | shader_code 文本匹配 | 是否含 raymarching、texture2D、粒子系统等禁止项 |
| **SDF 算子使用** | shader_code 文本匹配 | 使用了哪些 SDF 算子（sdCircle/sdBox/sdHeart 等） |

### 3.4 Inspect 评估质量指标

| 指标 | 采集点 | 度量 |
|------|--------|------|
| **评分分布** | inspect score | 全样例评分的均值/中位数/标准差 |
| **评分合理性** | score vs 视觉对比 | 高分样例是否真的更接近参考 |
| **反馈可操作性** | feedback 文本 | 反馈是否具体到参数级别（vs 模糊描述） |
| **维度分一致性** | 8 维度分 | 维度分加权和是否与总分一致 |

### 3.5 视觉对比指标

| 指标 | 采集点 | 度量 |
|------|--------|------|
| **参考帧截图** | FFmpeg 第 1 帧 | 作为参考基准 |
| **渲染帧截图** | Playwright 时间点 0.0 | 用于视觉对比 |
| **最终帧截图** | 最后迭代的渲染结果 | 迭代收敛效果 |

---

## 4. 测试执行流程

```
Phase 1: 环境准备 (~5 min)
  ├─ 确认 Backend + Frontend 运行中
  ├─ 确认 .env 配置正确（API keys 可用）
  ├─ 确认 Playwright Chromium 已安装
  └─ 创建输出目录结构

Phase 2: 预分析 (~10 min)
  ├─ 对 25 个样例提取第 1 帧截图（参考帧）
  ├─ 记录视频元信息（分辨率、时长、文件大小）
  └─ 按类别生成测试清单

Phase 3: 逐样例执行 (~25 × 3min = ~75 min)
  ├─ 对每个样例:
  │   ├─ POST /pipeline/run (video=xxx.webm, max_iterations=3)
  │   ├─ 轮询 GET /pipeline/status/{id} 直到完成/超时
  │   ├─ 采集各阶段输出和日志
  │   ├─ 保存中间产物（visual_description, shader_code, screenshots）
  │   └─ 记录问题标签
  └─ 全量执行期间自动收集错误日志

Phase 4: 分析与报告 (~15 min)
  ├─ 汇总所有样例结果
  ├─ 统计各指标分布
  ├─ 问题分类和严重度排序
  ├─ 识别系统性问题 vs 个案问题
  └─ 生成 HTML 可视化报告
```

---

## 5. 问题分类体系

测试过程中识别的问题按以下维度分类：

### 5.1 按严重度

| 等级 | 定义 | 示例 |
|------|------|------|
| **P0-Blocker** | Pipeline 无法完成 | API 崩溃、Playwright 超时、无限循环 |
| **P1-Critical** | 结果质量严重不达标 | 效果类型完全错误、shader 无法编译 |
| **P2-Major** | 结果有明显偏差 | 形状错误、颜色偏差大、动画不匹配 |
| **P3-Minor** | 结果基本可接受但有瑕疵 | 边缘不够平滑、动画速度略有偏差 |

### 5.2 按问题环节

| 环节 | 关注点 |
|------|--------|
| **D-Decompose** | 效果类型误判、形状遗漏、填充类型错误、颜色识别偏差 |
| **G-Generate** | 编译失败、禁止项违规、算子选择不当、性能超标 |
| **I-Inspect** | 评分虚高/虚低、反馈不具可操作性、维度权重失衡 |
| **P-Pipeline** | 路由死循环、状态丢失、超时、回滚失效 |
| **R-Render** | WebGL 编译失败、黑屏、截图异常 |

### 5.3 按效果类别关联

某些问题可能只在特定效果类别中出现：
- C1(涟漪): 动画参数（频率/振幅）匹配
- C2(发光): bloom/glow 算法实现、实心 vs 空心
- C3(渐变): 色彩插值、多色渐变
- C4(粒子): 粒子是否在系统禁止范围内
- C5(液态): 折射/模糊效果实现难度
- C6(扭曲): 域变换算子使用
- C7(形状): SDF 算子选择、形状组合
- C8(空间): 可能超出 2D 范围
- C9(噪声): 噪声类型选择（FBM/Voronoi/Perlin）
- C10(特殊): 复杂场景分析

---

## 6. 测试脚本设计

### 6.1 脚本结构

```
backend/
├── test_e2e_batch.py          # 主测试脚本
├── test_e2e_report.py         # HTML 报告生成器
└── test_e2e_results/          # 结果输出目录
    ├── index.html             # HTML 可视化报告
    ├── summary.json           # 汇总数据
    └── {sample_name}/         # 每个样例的详细结果
        ├── reference_frame.png    # 参考帧截图
        ├── rendered_frame.png     # 最终渲染帧截图
        ├── pipeline_state.json    # 完整 pipeline 状态
        ├── visual_description.json # Decompose 输出
        ├── shader_code.glsl       # 最终 GLSL 代码
        └── issues.json            # 识别的问题标签
```

### 6.2 核心测试逻辑

```python
# 伪代码
for sample in selected_samples:
    # 1. 预提取参考帧
    reference_frame = extract_first_frame(sample.video_path)
    
    # 2. 触发 Pipeline
    pipeline_id = POST /pipeline/run(video=sample.video, max_iterations=3)
    
    # 3. 轮询直到完成
    while status == "running":
        status = GET /pipeline/status/{pipeline_id}
        sleep(2s)
        if elapsed > 300s: timeout!
    
    # 4. 采集结果
    state = GET /pipeline/status/{pipeline_id}
    save_artifacts(sample, state)
    
    # 5. 自动问题检测
    issues = detect_issues(sample, state)
    save_issues(sample, issues)

# 6. 生成报告
generate_html_report(all_results)
```

### 6.3 自动问题检测规则

| 规则 | 检测方式 | 对应问题标签 |
|------|----------|-------------|
| shader 不含 `mainImage` | 文本匹配 | `G-format-invalid` |
| shader 含 `raymarching`/`castRay` | 文本匹配 | `G-raymarching-banned` |
| shader 含 `texture2D` | 文本匹配 | `G-texture-fetch` |
| shader 行数 > 400 | 计数 | `G-code-too-long` |
| effect_type 不在 Catalog 内 | 集合检查 | `D-effect-out-of-catalog` |
| fill_type 缺失 | 字段检查 | `D-fill-type-missing` |
| 评分 > 0.8 但视觉明显不匹配 | (人工或后续自动化) | `I-score-inflated` |
| pipeline 状态为 failed | 状态检查 | `P-pipeline-failed` |
| compile_retry_count >= 3 | 计数检查 | `G-compile-retry-exhausted` |
| 最终分数 < 0.3 | 数值检查 | `I-low-quality` |

---

## 7. 预期输出

### 7.1 HTML 可视化报告内容

1. **总览面板**
   - 完成率饼图（passed/failed/max_iterations/timeout）
   - 评分分布直方图
   - 各效果类别平均评分条形图
   - 平均迭代次数

2. **样例详情页**（每个样例一页）
   - 参考帧 vs 渲染帧 并排对比
   - Decompose 输出的 visual_description（格式化 JSON）
   - 最终 GLSL shader 代码（语法高亮）
   - Inspect 评分雷达图（8 维度）
   - 迭代历史（每轮评分变化曲线）
   - 问题标签列表

3. **问题分析页**
   - 按严重度排序的问题列表
   - 按环节（D/G/I/P/R）分类的问题统计
   - 高频问题 Top 10
   - 系统性问题 vs 个案问题标注

4. **优化建议页**
   - 基于测试数据的优化建议（按优先级排序）
   - 每条建议关联到具体问题证据

### 7.2 关键交付物

| 交付物 | 说明 |
|--------|------|
| `test_e2e_batch.py` | 可复用的批量测试脚本 |
| `test_e2e_report.py` | HTML 报告生成器 |
| `test_e2e_results/index.html` | 可视化测试报告 |
| `test_e2e_results/summary.json` | 结构化汇总数据 |

---

## 8. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| API 调用频率限制 | 中 | 测试中断 | 请求间加 2s 间隔；实现指数退避重试 |
| Playwright 崩溃 | 中 | 渲染失败 | 每个样例重启 browser context；捕获异常继续 |
| 长时间运行内存泄漏 | 低 | 系统变慢 | 每个样例后清理临时文件；监控内存 |
| 网络代理不稳定 | 中 | API 超时 | 3 次重试 + 标记为 timeout |
| 磁盘空间不足 | 低 | 截图保存失败 | 每个样例约 5MB 截图，25 样例约 125MB |

---

## 9. 测试通过/失败标准

### 系统可用性标准

| 指标 | 最低要求 | 目标 |
|------|----------|------|
| Pipeline 完成率 | ≥ 80% | ≥ 95% |
| 首次编译成功率 | ≥ 60% | ≥ 80% |
| 平均评分 | ≥ 0.4 | ≥ 0.6 |
| 无 P0-Blocker | 0 个 | 0 个 |

### 如果达不到最低要求

- 完成率 < 80%: 优先修复 Pipeline 稳定性问题
- 编译成功率 < 60%: 优先修复 Generate Agent prompt
- 平均评分 < 0.4: 优先修复 Decompose + Generate 准确度
- 存在 P0-Blocker: 立即修复阻断问题

---

## 10. 执行时间估算

| 阶段 | 时间 | 说明 |
|------|------|------|
| Phase 1: 环境准备 | ~5 min | 确认服务、安装依赖 |
| Phase 2: 预分析 | ~10 min | 提取参考帧、分类 |
| Phase 3: 执行测试 | ~75 min | 25 样例 × ~3 min/个 |
| Phase 4: 报告生成 | ~10 min | 数据汇总 + HTML 生成 |
| **总计** | **~100 min (~1.5h)** | |

如果抽样测试发现严重问题，可先暂停修复，再用全量测试验证修复效果。
