# Critique Examples

Good and bad description examples for visual effect critique.

## Comparison Table

### ✅ Good: Specific + Professional

| Dimension | Bad Description | Good Description |
|-----------|------------------|------------------|
| **Composition** | "位置不对" | "主体偏离中心约 20 像素，应向右移动居中" |
| **Geometry** | "形状有问题" | "SDF 边界过于锐利，缺少 smoothstep 过渡（宽度约 0.05）" |
| **Geometry** | "没有边" | "描边效果缺失，设计参考包含 2px 白色描边" |
| **Lighting** | "不够亮" | "点状 specular 高光缺失，导致主体缺乏立体感" |
| **Lighting** | "阴影不好" | "阴影方向错误（应为左下方），深度过浅约 0.3，缺少柔和过渡" |
| **Color** | "颜色不对" | "主色调偏差：设计参考 RGB(0.2, 0.5, 1.0) 蓝色，渲染 RGB(0.5, 0.2, 0.1) 红色" |
| **Color** | "背景颜色不对" | "背景颜色不匹配：设计参考青色 RGB(0.1, 0.8, 0.7)，渲染结果黑色 RGB(0, 0, 0)" |
| **Animation** | "动得太快" | "动画周期过快（约 1 秒），缺少 ease-in-out 缓动曲线，应调整为 3-4 秒周期" |
| **Background** | "背景有问题" | "背景缺失渐变纹理：设计参考有从中心向外的径向渐变，渲染结果为纯色" |

### ❌ Bad: Vague + Non-professional

| Problem Type | Bad Example | Why It's Bad |
|--------------|-------------|--------------|
| **Too vague** | "效果不好" | No specific dimension, no actionable info |
| **No terminology** | "颜色不对" | Doesn't use professional terms like "hue", "saturation", "RGB value" |
| **No location** | "有问题" | Doesn't specify where the problem is |
| **No comparison** | "应该改" | Doesn't reference design expectation |
| **No parameter** | "太亮了" | Doesn't give actionable direction (brighter? darker? how much?) |
| **Wrong focus** | "代码写错了" | Should describe visual effect, not code |

---

## Dimension-Specific Examples

### Composition Examples

#### ✅ Good

```
"主体位置居中（中心坐标 UV(0.5, 0.5)），布局合理，元素间距均匀约 10 像素，
前后层次分明（Z-order 正确），视觉平衡良好"
```

#### ❌ Bad

```
"位置有点偏"
"布局可以"
"东西太多"
```

#### Problem Description Examples

```
"主体偏离中心向左偏移约 30 像素，应向右移动居中"
"元素间距过大（约 50 像素），视觉空洞，应调整为 20-30 像素"
"前景背景层次混乱，Z-order 错误导致遮挡不当"
"视觉重心偏向左下角，右侧负空间过大，需要重新平衡"
```

---

### Geometry Examples

#### ✅ Good

```
"矩形 SDF 形状正确，尺寸 UV(0.2, 0.15) 准确，边缘使用 smoothstep 过渡
宽度 0.02，无锯齿，描边效果存在（白色，宽度 2 像素，外描边），
左右对称，旋转角度 0 度正确"
```

#### ❌ Bad

```
"形状还行"
"边不好看"
"大小有问题"
```

#### Problem Description Examples

```
"SDF 边界过于锐利（硬切），应改用 smoothstep(edge-0.05, edge+0.05, d) 模糊边缘"
"描边效果缺失：设计参考包含白色描边宽度约 2-3 像素，渲染结果无描边"
"形状变形：设计参考为标准矩形，渲染结果边缘弯曲，可能 SDF 计算错误"
"对称性错误：设计参考左右对称，渲染结果不对称，旋转角度偏差约 10 度"
"边缘锯齿明显：缺少抗锯齿（AA），应使用 fwidth(d) 控制 smoothstep 宽度"
```

---

### Lighting Examples

#### ✅ Good

```
"点状 specular 高光存在，位置在主体顶部偏左，强度适中不刺眼，
形态集中半径约 5 像素，边缘清晰自然；柔和阴影存在，
方向为左下方匹配光源，深度 0.6 增强立体感，边缘过渡平滑；
光晕效果存在，半径约 15 像素，衰减自然，边缘光宽度 3 像素正确"
```

#### ❌ Bad

```
"光线一般"
"有点亮"
"阴影看不清"
```

#### Problem Description Examples

```
"高光效果完全缺失：设计参考有明显的 specular highlight，渲染结果无高光，主体平面无立体感"
"高光位置错误：设计参考在顶部中央，渲染结果在左下方，位置偏移约 40 像素"
"高光过强刺眼：强度过高导致视觉不适，应降低强度约 50%"
"高光过于分散：设计参考为集中点状高光，渲染结果为大面积模糊光斑"
"阴影缺失：设计参考有柔和阴影增强立体感，渲染结果无阴影"
"阴影方向错误：设计参考光源从右上，阴影应向左下，渲染结果阴影向右"
"阴影过硬：边缘硬切无过渡，应使用 Gaussian blur 或 smoothstep 软化"
"光晕缺失：设计参考有柔和光晕环绕主体，渲染结果无光晕"
"边缘光缺失：设计参考有 rim light 增强轮廓，渲染结果无边缘光"
```

---

### Color Examples

#### ✅ Good

```
"主色调为蓝色系 RGB(0.2, 0.5, 1.0)，匹配设计参考，
饱和度适中约 0.8，色彩鲜明不灰暗；三层色彩过渡自然，
从中心蓝色渐变到边缘白色；色阶分布合理，
对比度适中；线性渐变方向正确（从上到下），
过渡平滑无断层"
```

#### ❌ Bad

```
"颜色差不多"
"有点红"
"背景颜色不对"
```

#### Problem Description Examples

```
"主色调偏差：设计参考 RGB(0.2, 0.5, 1.0) 蓝色系，渲染结果 RGB(0.5, 0.2, 0.1) 红色系，
色调完全不匹配"
"饱和度过低：设计参考色彩鲜明（饱和度约 0.8），渲染结果灰暗（饱和度约 0.3）"
"色彩层次缺失：设计参考有三层渐变，渲染结果为单色平面"
"渐变方向错误：设计参考为垂直渐变（上→下），渲染结果为水平渐变（左→右）"
"渐变断层：设计参考平滑过渡，渲染结果有明显的颜色断层，过渡不连续"
"背景颜色不匹配：设计参考青色 RGB(0.1, 0.8, 0.7)，渲染结果黑色 RGB(0, 0, 0)"
"对比度不足：设计参考主体与背景对比鲜明，渲染结果对比度低，主体融入背景"
```

---

### Texture Examples

#### ✅ Good

```
"Perlin 噪声存在，octaves=4，频率适中细节丰富，
动态效果正确（随时间流动）；磨砂效果存在，
颗粒细腻尺度约 0.01，强度适中不干扰主体；
材质质感为玻璃材质，折射效果正确"
```

#### ❌ Bad

```
"有纹理"
"磨砂效果不对"
"噪点太多"
```

#### Problem Description Examples

```
"噪声缺失：设计参考有 Perlin 噪声动态效果，渲染结果静态无噪声"
"噪声尺度错误：设计参考细节丰富（octaves=4），渲染结果噪声过大模糊"
"磨砂缺失：设计参考有磨砂玻璃效果，渲染结果为透明平面"
"磨砂颗粒过大：设计参考细腻颗粒，渲染结果颗粒粗大明显"
"材质质感不匹配：设计参考为玻璃材质，渲染结果质感类似金属"
```

---

### Animation Examples

#### ✅ Good

```
"涟漪扩散动画类型正确，方向为向外扩散；
ease-in-out 缓动曲线存在，启动和结束平滑无突变；
动画周期 3 秒，节奏适中自然；
循环无缝衔接，无跳变；运动轨迹为圆形向外，
覆盖范围正确（半径从 0 到 0.5 UV）"
```

#### ❌ Bad

```
"动画太快"
"动得不对"
"循环有问题"
```

#### Problem Description Examples

```
"动画类型错误：设计参考为涟漪扩散（向外），渲染结果为呼吸效果（大小变化）"
"动画节奏过快：设计参考周期约 3-4 秒，渲染结果周期约 1 秒，节奏过快"
"缺少缓入缓出：动画启动突变，结束突然停止，应添加 ease-in-out 曲线"
"循环不衔接：设计参考无缝循环，渲染结果有明显跳变"
"运动轨迹错误：设计参考为圆形扩散，渲染结果为线性移动"
"多层动画不同步：设计参考多层协调，渲染结果不同步冲突"
```

---

### Background Examples (Critical)

#### ✅ Good

```
"背景颜色为青色 RGB(0.1, 0.8, 0.7) 与设计一致，
从中心向外的径向渐变存在，过渡平滑自然；
透明度正确 0.5 衬托主体不遮挡；
主体与背景对比鲜明，层次清晰，背景动态与主体同步"
```

#### ❌ Bad

```
"背景不对"
"背景颜色错了"
"背景看起来有问题"
```

#### Problem Description Examples

```
"背景颜色不匹配：设计参考青色 RGB(0.1, 0.8, 0.7)，渲染结果黑色 RGB(0, 0, 0)"
"背景纹理缺失：设计参考有径向渐变，渲染结果为纯色无纹理"
"背景透明度错误：设计参考半透明 0.5，渲染结果透明度 1.0 完全遮挡"
"主体与背景对比不足：设计参考对比鲜明，渲染结果对比度低主体融入背景"
"背景动态缺失：设计参考背景有动态效果与主体同步，渲染结果背景静态"
"背景颜色偏差：设计参考青色偏蓝绿，渲染结果为纯蓝色，色调不对"
```

---

### VFX Details Examples

#### ✅ Good

```
"粒子效果存在，密度适中约 50 个/区域，分布自然，
尺寸约 3 像素，动画正确（向上飘动）；
流光效果存在，轨迹为螺旋向上，强度适中，
颜色为白色匹配主体；Alpha 混合过渡自然，
无硬切边缘"
```

#### ❌ Bad

```
"粒子不好"
"流光有问题"
"透明度不对"
```

#### Problem Description Examples

```
"粒子缺失：设计参考有粒子效果，渲染结果无粒子"
"粒子密度过低：设计参考约 50 个，渲染结果约 10 个，稀疏"
"粒子分布不均：设计参考均匀分布，渲染结果聚团分布"
"流光缺失：设计参考有流光效果，渲染结果无流光"
"Alpha 硬切：设计参考平滑过渡，渲染结果边缘硬切"
```

---

## Full Critique Example

### Input

**Design Reference**: Windows logo ripple animation
- Subject: Blue rectangular logo with 4 colored panes
- Background: Cyan gradient
- Animation: Ripple diffusion with 3-4 second cycle
- Effect: Outline + glow + shadow

**Rendered Output**:
- Subject: Red single rectangle
- Background: Black solid
- Animation: Fast pulse (~1 second)
- Effect: No outline, no glow, no shadow

### ✅ Good Critique Output

```json
{
  "passed": false,
  "overall_score": 0.3,
  
  "correct_aspects": {
    "composition": "主体位置居中，布局合理",
    "geometry": "矩形基础形状存在，边缘清晰"
  },
  
  "problem_aspects": {
    "geometry": "描边效果缺失，设计参考有白色描边约 2-3 像素",
    "lighting": "高光和阴影效果完全缺失，主体平面无立体感",
    "color": "主色调和背景颜色完全不匹配：设计参考为蓝色主体+青色背景，渲染结果为红色主体+黑色背景",
    "animation": "动画类型和节奏错误：设计参考为涟漪扩散（3-4秒周期），渲染结果为快速脉冲（约1秒）",
    "background": "背景颜色和纹理完全不匹配：设计参考青色渐变，渲染结果黑色纯色"
  },
  
  "dimension_scores": {
    "composition": {"score": 0.8, "correct": ["位置居中", "布局合理"], "problems": []},
    "geometry": {"score": 0.4, "correct": ["矩形形状存在"], "problems": ["描边缺失", "无glow"]},
    "lighting": {"score": 0.0, "correct": [], "problems": ["高光缺失", "阴影缺失", "光晕缺失"]},
    "color": {"score": 0.2, "correct": [], "problems": ["主色调不匹配", "背景颜色不匹配", "颜色层次缺失"]},
    "animation": {"score": 0.3, "correct": [], "problems": ["类型错误", "节奏过快", "缺少缓入缓出"]},
    "background": {"score": 0.0, "correct": [], "problems": ["颜色不匹配", "纹理缺失", "动态缺失"]}
  },
  
  "background_analysis": {
    "current": "黑色纯色背景 RGB(0, 0, 0)，无纹理，无渐变，静态",
    "expected": "青色渐变背景 RGB(0.1, 0.8, 0.7)，从中心向外径向渐变，有轻微动态",
    "gap": "颜色完全不匹配（应为青色），缺少渐变纹理，缺少动态效果"
  },
  
  "visual_issues": [
    "主色调偏差：设计参考为蓝色系 RGB(0.2, 0.5, 1.0)，渲染结果为红色系 RGB(0.5, 0.2, 0.1)",
    "背景颜色不匹配：设计参考青色 RGB(0.1, 0.8, 0.7)，渲染结果黑色 RGB(0, 0, 0)",
    "描边效果缺失：设计参考有白色描边约 2-3 像素，渲染结果无描边",
    "高光和阴影缺失：设计参考有 specular highlight 和柔和阴影增强立体感，渲染结果平面无立体感",
    "动画类型错误：设计参考为涟漪扩散（向外），渲染结果为快速脉冲（大小变化）",
    "动画节奏过快：设计参考周期 3-4 秒配合 ease-in-out，渲染结果周期约 1 秒无缓动曲线",
    "背景纹理缺失：设计参考有径向渐变，渲染结果为纯色背景"
  ],
  
  "visual_goals": [
    "主色调调整为蓝色系 RGB(0.2, 0.5, 1.0) 匹配设计参考",
    "背景调整为青色 RGB(0.1, 0.8, 0.7) 并添加径向渐变纹理",
    "添加白色描边效果，宽度约 2-3 像素，外描边位置",
    "添加 specular 高光和柔和阴影增强立体感",
    "动画改为涟漪扩散类型，周期调整为 3-4 秒",
    "添加 ease-in-out 缓动曲线使动画平滑自然",
    "背景添加动态效果与主体同步"
  ],
  
  "feedback_summary": "保持：位置居中、矩形形状。修改：颜色修正（蓝色主体+青色背景）、添加描边和高光、动画类型和节奏调整、背景纹理和动态。"
}
```

### ❌ Bad Critique Output

```json
{
  "passed": false,
  "overall_score": 0.5,
  "feedback": "效果不好，颜色不对，动画太快，背景有问题"
}
```

**Why it's bad**:
- No professional terminology
- No specific dimensions
- No actionable parameters
- No design reference comparison
- No correct/problem separation