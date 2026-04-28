---
name: visual-effect-critique
description: |
  Professional visual effect critique methodology for shader quality assessment.
  
  Use when Inspect Agent needs to:
  (1) Compare rendered shader output with design reference
  (2) Provide structured visual analysis with positive + negative descriptions
  (3) Use professional VFX terminology (outline, highlight, shadow, gradient, SDF, bloom, etc.)
  (4) Evaluate all dimensions: composition, geometry, lighting, color, texture, animation, background, VFX details
  (5) Generate actionable feedback for Generate Agent
  
  Provides: evaluation dimensions, terminology, analysis patterns, example critiques, background analysis focus.
---

# Visual Effect Critique Skill

Professional methodology for evaluating shader-generated visual effects against design references.

## Core Philosophy

**Inspect Agent outputs professional visual analysis, Generate Agent decides code modifications.**

Critique must:
- ✅ Cover ALL dimensions (no partial evaluation)
- ✅ Include BOTH positive (what to keep) and negative (what to fix)
- ✅ Use PROFESSIONAL terminology (not vague descriptions)
- ✅ Focus on BACKGROUND consistency (critical for iteration)
- ❌ NOT specify code modifications (that's Generate Agent's job)

## Evaluation Dimensions

### Quick Reference

| Dimension | Key Checks | Priority |
|-----------|------------|----------|
| Composition | Position, hierarchy, spacing, proportion | High |
| Geometry | Shape, SDF, outline, edge, symmetry | High |
| Lighting & Shadow | Highlight type/shape, shadow type/depth, glow, rim light | High |
| Color & Tone | Main hue, saturation, gradient, levels | High |
| Texture & Material | Noise, blur, frosted, grain | Medium |
| Animation & Motion | Type, curve, rhythm, cycle, trajectory | Medium |
| Background | Color, texture, transparency, subject relation | **Critical** |
| VFX Details | Particle, flow light, alpha blend | Medium |

**See detailed dimension analysis:** [references/dimension-analysis.md](references/dimension-analysis.md)

## Workflow

### Step 1: Load Reference Terminology

Read [references/vfx-terminology.md](references/vfx-terminology.md) for professional vocabulary.

Key terms to use:
- **Lighting**: specular highlight, diffuse, ambient, rim light, global illumination, bloom, glow
- **Color**: hue, saturation, luminance, gradient, color grading, tone mapping
- **Geometry**: SDF (signed distance field), outline, stroke, edge transition, antialiasing
- **Animation**: easing curve, timing function, cycle period, motion trajectory

### Step 2: Structured Dimension Analysis

For each dimension, provide:

```json
{
  "dimension_name": {
    "score": 0.0-1.0,
    "correct": ["list of correct aspects"],
    "problems": ["list of problem aspects"]
  }
}
```

**Rule**: Every dimension MUST have at least one `correct` OR `problems` entry. Empty dimension = incomplete evaluation.

### Step 3: Background Analysis (Special Focus)

Background is critical for iteration consistency. Always include:

```json
{
  "background_analysis": {
    "current": "Describe current background state",
    "expected": "Describe expected background from reference",
    "gap": "Describe mismatch between current and expected"
  }
}
```

**Common background issues**:
- Color mismatch (should be cyan, but is black)
- Missing texture (gradient, noise, pattern)
- Wrong transparency (should be semi-transparent)
- Subject-background conflict (wrong contrast ratio)

### Step 4: Generate Actionable Feedback

Combine analysis into structured output:

```json
{
  "correct_aspects": {
    "composition": "...",
    "geometry": "...",
    "color": "..."
  },
  "problem_aspects": {
    "geometry": "描边缺失，边缘呈现锐利硬切而非柔和过渡",
    "lighting": "高光效果完全缺失，导致主体缺乏立体感",
    "background": "背景颜色不匹配，设计参考为青色背景，渲染结果为黑色背景"
  },
  "visual_issues": ["具体问题描述列表"],
  "visual_goals": ["期望效果描述列表"],
  "feedback_summary": "简洁总结：保持什么，修改什么"
}
```

## Professional Description Examples

### ✅ Good: Specific + Professional

| Dimension | Good Description |
|-----------|------------------|
| Geometry | "描边缺失，边缘呈现锐利硬切而非柔和的 smoothstep 过渡" |
| Lighting | "高光类型应为点状 specular，但当前缺失，导致缺乏立体感" |
| Color | "主色调偏差，设计参考为 RGB(0.2, 0.5, 1.0) 蓝色系，渲染结果偏向 RGB(0.5, 0.2, 0.1) 红色系" |
| Animation | "动画节奏过快（约 1 秒循环），缺少缓入缓出曲线，应调整为 3-4 秒周期配合 ease-in-out" |
| Background | "背景颜色不匹配：设计参考为青色渐变（偏蓝绿），渲染结果为黑色纯色背景" |

### ❌ Bad: Vague + Non-professional

| Dimension | Bad Description | Problem |
|-----------|------------------|---------|
| Geometry | "形状不对" | ❌ Too vague, no terminology |
| Lighting | "不够亮" | ❌ No specific lighting type |
| Color | "颜色不对" | ❌ Doesn't specify which color, which area |
| Animation | "动得太快" | ❌ Missing specific timing parameters |
| Background | "背景有问题" | ❌ Doesn't describe the actual mismatch |

**See more examples:** [references/critique-examples.md](references/critique-examples.md)

## Scoring Guidelines

| Score | Interpretation | Action |
|-------|---------------|--------|
| 0.9-1.0 | Excellent match | passed=true, minor issues only |
| 0.85-0.9 | Acceptable | passed=true, small adjustments needed |
| 0.7-0.85 | Needs tweaking | passed=false, several issues |
| 0.5-0.7 | Needs major changes | passed=false, fundamental issues |
| 0.0-0.5 | No match | passed=false, complete mismatch |

**Per-dimension scoring**:
- **0.9-1.0**: All correct, no problems
- **0.7-0.85**: Mostly correct, one problem
- **0.5-0.7**: Half correct, half problems
- **0.0-0.5**: All problems, no correct

## Common Problem Patterns

### Pattern 1: Missing Effect Component

**Detection**: Design has effect X, render doesn't.

**Example**: "Design has outline/stroke effect, render is sharp edge without outline"

**Description**: "[效果类型]缺失：设计参考包含[具体效果]，渲染结果完全缺少该效果"

### Pattern 2: Wrong Parameter Value

**Detection**: Effect exists but parameter is wrong.

**Example**: "Outline width is 5px in design, 1px in render"

**Description**: "[参数名]不匹配：设计参考为[期望值]，渲染结果为[当前值]，[差距描述]"

### Pattern 3: Animation Timing Issue

**Detection**: Animation type correct but timing wrong.

**Example**: "Ripple animation is too fast, should be slow wave"

**Description**: "动画节奏不匹配：周期为[当前秒数]，应为[期望秒数]，缺少缓入缓出曲线"

### Pattern 4: Background Inconsistency

**Detection**: Background doesn't match reference.

**Example**: "Background color wrong, texture missing"

**Description**: "背景不一致：颜色为[当前]，应为[期望]；纹理[缺失/不匹配]"

## Special Cases

### Text-Only Mode (No Design Reference)

When no design reference available:
- Skip visual comparison
- Focus on shader correctness (compiles, renders, animates)
- Check FPS (should be > 30 FPS)
- Pass if shader runs correctly

### User Feedback Integration

When user provides natural language feedback:
- Convert user description to professional terminology
- Add user feedback to `visual_issues` as top priority
- Mark user-identified correct aspects in `correct_aspects`
- Generate Agent will prioritize user feedback

## Output Template

```json
{
  "passed": false,
  "overall_score": 0.7,
  
  "correct_aspects": {
    "composition": "主体位置居中，布局合理",
    "geometry": "矩形基础形状正确，边缘清晰",
    "animation": "动画类型为涟漪扩散，符合预期"
  },
  
  "problem_aspects": {
    "geometry": "描边效果缺失，边缘呈现锐利硬切",
    "lighting": "高光效果缺失，无点状 specular highlight",
    "color": "背景颜色不匹配，应为青色而非黑色",
    "animation": "动画节奏过快（1秒循环），应调整为3-4秒"
  },
  
  "dimension_scores": {
    "composition": {"score": 0.8, "correct": ["位置居中"], "problems": []},
    "geometry": {"score": 0.6, "correct": ["形状正确"], "problems": ["描边缺失", "边缘锐利"]},
    "lighting": {"score": 0.4, "correct": [], "problems": ["高光缺失"]},
    "color": {"score": 0.5, "correct": ["主色调正确"], "problems": ["背景颜色不匹配"]},
    "animation": {"score": 0.7, "correct": ["类型正确"], "problems": ["节奏过快"]}
  },
  
  "background_analysis": {
    "current": "黑色纯色背景，无纹理，无渐变",
    "expected": "青色背景（偏蓝绿色 RGB(0.1, 0.8, 0.7)），可能有轻微渐变",
    "gap": "颜色完全不匹配，缺少渐变纹理"
  },
  
  "visual_issues": [
    "描边效果缺失，边缘呈现锐利硬切而非柔和 smoothstep 过渡",
    "高光效果完全缺失，应为点状 specular highlight 增强立体感",
    "背景颜色不匹配：设计参考为青色（偏蓝绿），渲染结果为黑色",
    "动画周期过快（1秒），应调整为 3-4 秒配合 ease-in-out 曲线"
  ],
  
  "visual_goals": [
    "添加描边效果，宽度约 2-3 像素，颜色与主体协调",
    "添加点状高光，位置在主体顶部，强度适中",
    "背景调整为青色系 RGB(0.1, 0.8, 0.7)，添加轻微渐变",
    "动画周期调整为 3-4 秒，添加缓入缓出曲线"
  ],
  
  "feedback_summary": "保持：位置居中、形状正确、涟漪类型。修改：添加描边和高光、调整背景青色、放缓动画。"
}
```

## References

- [VFX Terminology](references/vfx-terminology.md) - Professional vocabulary
- [Dimension Analysis](references/dimension-analysis.md) - Detailed dimension breakdown
- [Critique Examples](references/critique-examples.md) - Good/bad description examples