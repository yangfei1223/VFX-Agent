# Visual Effect Dimension Analysis

Complete breakdown of evaluation dimensions with detailed check items.

## 1. Composition

### Position & Layout

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Center position** | Is subject centered? | "主体位置居中，坐标准确" | "主体偏离中心，位置偏差约[X]像素" |
| **Offset** | Is intentional offset correct? | "偏移位置符合设计意图" | "偏移位置错误，应向[方向]移动" |
| **Multiple subjects** | Are positions coordinated? | "多元素位置分布正确" | "元素位置冲突，重叠/间距不当" |

### Hierarchy & Depth

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Z-order** | Is layering correct? | "前后层次分明，Z-order正确" | "层次混乱，前景背景重叠" |
| **Depth separation** | Can elements be distinguished? | "深度分离清晰，可区分前后" | "元素融合，层次不清" |
| **Foreground/background** | Is subject-background relation correct? | "主体与背景关系正确" | "主体被背景遮挡/干扰" |

### Spacing & Distribution

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Gap width** | Is spacing consistent? | "间距均匀，约[X]像素" | "间距不均，过大/过小" |
| **Distribution** | Are elements evenly spread? | "元素分布均匀" | "分布不均，偏左/偏右" |
| **Density** | Is element density correct? | "密度适中，视觉平衡" | "密度过高/过低，拥挤/稀疏" |

### Proportion & Scale

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Element size** | Are sizes correct? | "元素尺寸正确，比例协调" | "元素过大/过小，比例失调" |
| **Relative size** | Are proportions correct? | "相对比例正确（主体:X，背景:Y）" | "比例错误，主体占比过高" |
| **Aspect ratio** | Is shape proportion correct? | "宽高比例正确" | "宽高比例失调，变形" |

### Visual Balance

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Symmetry** | Is balance achieved? | "对称性正确，左右平衡" | "不对称，视觉重心偏移" |
| **Weight distribution** | Is visual weight balanced? | "视觉重心平衡" | "重心偏移，不平衡" |
| **Negative space** | Is empty space appropriate? | "留白适当，呼吸感强" | "留白过多/过少" |

---

## 2. Geometry

### Basic Shape

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Shape type** | Is SDF type correct? | "SDF类型正确（圆形/矩形）" | "SDF类型不匹配，应为[类型]" |
| **Shape accuracy** | Does shape match reference? | "形状准确匹配设计参考" | "形状变形，与参考不符" |
| **Shape complexity** | Is complexity correct? | "形状复杂度适中" | "过于简单/复杂" |

### SDF Properties

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **SDF boundary** | Is edge smooth? | "SDF边界平滑，无突变" | "边界突变，有锯齿" |
| **SDF accuracy** | Is distance calculation correct? | "距离计算准确" | "距离计算偏差，边界不准" |
| **SDF blend** | Is shape blend correct? | "smooth union过渡自然" | "blend类型错误，硬切过渡" |

### Outline & Stroke

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Outline presence** | Does outline exist? | "描边效果存在，宽度适中" | "描边缺失" |
| **Outline width** | Is thickness correct? | "描边宽度约[X]像素，正确" | "描边过宽/过窄" |
| **Outline color** | Is color correct? | "描边颜色为[RGB]，正确" | "描边颜色不匹配" |
| **Outline position** | Is placement correct? | "描边位置正确（外描边）" | "描边位置错误（应为外描边）" |
| **Outline softness** | Is edge smooth? | "描边边缘柔和过渡" | "描边边缘硬切" |

### Edge Quality

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Edge smoothness** | Is transition smooth? | "边缘过渡自然，使用smoothstep" | "边缘锐利，缺少平滑" |
| **Antialiasing** | Is AA applied? | "抗锯齿正确，边缘清晰" | "锯齿明显，缺少AA" |
| **Edge sharpness** | Is sharpness level correct? | "边缘清晰度适中" | "边缘模糊/过度锐化" |

### Symmetry & Rotation

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Symmetry axis** | Is symmetry correct? | "对称轴正确，左右镜像" | "不对称，轴偏移" |
| **Rotation angle** | Is angle correct? | "旋转角度[X]度，正确" | "旋转角度偏差，应为[X]度" |
| **Orientation** | Is direction correct? | "方向正确（水平/垂直）" | "方向错误" |

---

## 3. Lighting & Shadow

### Highlight Analysis

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Highlight presence** | Does highlight exist? | "高光效果存在" | "高光缺失" |
| **Highlight type** | Is type correct? | "点状 specular高光，位置正确" | "高光类型错误（应为点状）" |
| **Highlight position** | Is location correct? | "高光位置在主体顶部偏左" | "高光位置偏移" |
| **Highlight intensity** | Is brightness correct? | "高光强度适中，不刺眼" | "高光过强/过弱" |
| **Highlight shape** | Is form correct? | "高光形态集中，边缘清晰" | "高光分散/模糊" |
| **Highlight color** | Is color correct? | "高光颜色为白色/暖色，正确" | "高光颜色不匹配" |

### Shadow Analysis

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Shadow presence** | Does shadow exist? | "阴影效果存在" | "阴影缺失" |
| **Shadow type** | Is type correct? | "柔和阴影，过渡自然" | "阴影类型错误（硬阴影）" |
| **Shadow direction** | Is angle correct? | "阴影方向为[左下方]，匹配光源" | "阴影方向错误" |
| **Shadow depth** | Is darkness correct? | "阴影深度适中，增强立体感" | "阴影过深/过浅" |
| **Shadow softness** | Is edge smooth? | "阴影边缘柔和过渡" | "阴影边缘过硬" |
| **Shadow range** | Is extent correct? | "阴影范围适中" | "阴影范围过大/过小" |

### Glow Effects

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Glow presence** | Does glow exist? | "光晕效果存在" | "光晕缺失" |
| **Glow radius** | Is spread correct? | "光晕半径约[X]像素，适中" | "光晕半径过小/过大" |
| **Glow intensity** | Is brightness correct? | "光晕强度适中，自然扩散" | "光晕过强刺眼/过弱不明显" |
| **Glow falloff** | Is decay correct? | "光晕衰减自然，渐变平滑" | "光晕衰减突兀，硬切" |
| **Glow color** | Is color correct? | "光晕颜色匹配主体色调" | "光晕颜色不匹配" |

### Rim Light

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Rim presence** | Does rim light exist? | "边缘光存在，增强轮廓" | "边缘光缺失" |
| **Rim width** | Is thickness correct? | "边缘光宽度适中，约[X]像素" | "边缘光过宽/过窄" |
| **Rim intensity** | Is brightness correct? | "边缘光强度适中" | "边缘光过强/过弱" |
| **Rim color** | Is color correct? | "边缘光颜色为[色]，正确" | "边缘光颜色不匹配" |

### Global Lighting

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Light direction** | Is source direction consistent? | "光照方向一致，全局统一" | "光照方向冲突，不一致" |
| **Light color** | Is color temperature correct? | "光照色温正确（暖/冷）" | "色温偏差，偏冷/偏暖" |
| **Ambient level** | Is base lighting correct? | "环境光强度适中" | "环境光过暗/过亮" |

---

## 4. Color & Tone

### Main Color

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Main hue** | Is primary color correct? | "主色调为蓝色，正确匹配" | "主色调偏差，偏红/偏绿" |
| **Color match** | Does color match reference? | "颜色匹配设计参考" | "颜色不匹配，应为[RGB]" |
| **Color accuracy** | Is RGB value correct? | "颜色值为RGB(0.2, 0.5, 1.0)，准确" | "颜色值偏差，误差[X]" |

### Saturation

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Saturation level** | Is intensity correct? | "饱和度适中，色彩鲜明" | "饱和度过高（过于鲜艳）/过低（灰暗）" |
| **Color purity** | Is color pure? | "色彩纯正，无混色" | "色彩混浊，纯度不足" |
| **Color vibrancy** | Is color lively? | "色彩活力强，视觉冲击" | "色彩沉闷，活力不足" |

### Color Layers

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Layer count** | Are color layers correct? | "多层色彩（3层）正确" | "色彩层次缺失，少于[X]层" |
| **Layer transition** | Is blending smooth? | "色彩层过渡自然" | "过渡突兀，有断层" |
| **Layer separation** | Can layers be distinguished? | "色彩层次分明" | "层次融合，难以区分" |

### Color Grading

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Color correction** | Is grading applied? | "调色正确，风格统一" | "调色缺失或错误" |
| **Tone mapping** | Is HDR conversion correct? | "色调映射正确" | "色调映射错误" |
| **Contrast** | Is light/dark difference correct? | "对比度适中，层次清晰" | "对比度不足/过高" |
| **Gamma** | Is brightness curve correct? | "Gamma校正正确" | "Gamma偏差，偏暗/偏亮" |

### Gradient Analysis

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Gradient presence** | Does gradient exist? | "渐变效果存在" | "渐变缺失，纯色背景" |
| **Gradient type** | Is type correct? | "线性渐变，方向正确" | "渐变类型错误（应为径向）" |
| **Gradient direction** | Is angle correct? | "渐变方向为[方向]，正确" | "渐变方向错误" |
| **Gradient smoothness** | Is transition smooth? | "渐变过渡平滑，无断层" | "渐变断层，过渡不连续" |
| **Gradient colors** | Are stop colors correct? | "渐变节点颜色正确" | "节点颜色不匹配" |

### Color Temperature

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Temperature** | Is warmth correct? | "色温正确（暖色调）" | "色温偏差，偏冷/偏暖" |
| **White balance** | Is balance correct? | "白平衡正确" | "白平衡偏差" |
| **Color mood** | Does color match mood? | "色彩情绪匹配（冷静/热情）" | "色彩情绪不匹配" |

---

## 5. Texture & Material

### Noise Analysis

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Noise presence** | Does noise exist? | "噪声效果存在" | "噪声缺失" |
| **Noise type** | Is type correct? | "Perlin噪声，类型正确" | "噪声类型错误（应为FBM）" |
| **Noise scale** | Is frequency correct? | "噪声尺度适中，细节可见" | "噪声过大/过小" |
| **Noise detail** | Is complexity correct? | "噪声细节丰富，octaves=X" | "噪声细节不足" |
| **Noise animation** | Is movement correct? | "噪声动态效果正确" | "噪声静态，缺少动画" |

### Blur Effects

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Blur presence** | Does blur exist? | "模糊效果存在" | "模糊缺失" |
| **Blur type** | Is type correct? | "高斯模糊，类型正确" | "模糊类型错误" |
| **Blur intensity** | Is strength correct? | "模糊强度适中，半径X像素" | "模糊过强/过弱" |
| **Blur area** | Is scope correct? | "模糊区域正确（局部/全局）" | "模糊区域错误" |

### Frosted Glass

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Frosted presence** | Does effect exist? | "磨砂效果存在" | "磨砂缺失" |
| **Frosted grain** | Is texture correct? | "磨砂颗粒细腻，强度适中" | "颗粒过大/过粗" |
| **Frosted transparency** | Is alpha correct? | "磨砂透明度正确" | "透明度错误" |

### Material Properties

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Material type** | Is type correct? | "材质类型正确（玻璃/金属）" | "材质类型不匹配" |
| **Material质感** | Is quality correct? | "材质质感真实" | "质感不真实" |
| **Reflection** | Is reflection correct? | "反射效果正确" | "反射缺失/错误" |

---

## 6. Animation & Motion

### Animation Type

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Animation presence** | Does animation exist? | "动画效果存在" | "动画缺失，静态图像" |
| **Animation type** | Is type correct? | "涟漪扩散动画，类型匹配" | "动画类型错误（应为涟漪而非呼吸）" |
| **Animation direction** | Is movement correct? | "动画方向正确（向外扩散）" | "动画方向错误" |

### Timing Curve

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Easing function** | Is curve correct? | "缓入缓出曲线，ease-in-out" | "曲线突兀，无缓入缓出" |
| **Start smoothness** | Is beginning smooth? | "动画启动平滑，无突变" | "启动突变，突然开始" |
| **End smoothness** | Is ending smooth? | "动画结束平滑，自然停止" | "结束突变，突然停止" |

### Rhythm & Pacing

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Animation speed** | Is rate correct? | "动画速度适中，节奏自然" | "节奏过快/过慢" |
| **Animation duration** | Is length correct? | "动画持续时间[X]秒，正确" | "持续时间错误，应调整为[X]秒" |
| **Animation intensity** | Is amplitude correct? | "动画幅度适中" | "幅度过大/过小" |

### Cycle & Loop

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Cycle period** | Is repeat interval correct? | "循环周期[X]秒，平滑衔接" | "周期不衔接，有断层" |
| **Loop smoothness** | Is transition smooth? | "循环无缝衔接" | "循环有跳变，不连续" |
| **Loop count** | Is repetition correct? | "循环次数正确" | "循环次数错误" |

### Motion Trajectory

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Trajectory type** | Is path correct? | "运动轨迹正确（直线/曲线）" | "轨迹不匹配" |
| **Trajectory smoothness** | Is path smooth? | "轨迹平滑，无拐点" | "轨迹有拐点，不平滑" |
| **Trajectory coverage** | Is extent correct? | "轨迹覆盖范围正确" | "覆盖范围过大/过小" |

### Multi-layer Animation

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Layer sync** | Are layers synchronized? | "多层动画同步协调" | "多层不同步，冲突" |
| **Layer timing** | Are delays correct? | "层间延迟正确" | "延迟错误，错位" |
| **Layer hierarchy** | Is ordering correct? | "动画层次正确" | "层次混乱" |

---

## 7. Background (Critical Focus)

### Background Color

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Background hue** | Is color correct? | "背景颜色为青色，与设计一致" | "背景颜色不匹配，应为[颜色]而非[当前]" |
| **Background RGB** | Is value accurate? | "背景RGB(X, Y, Z)，正确" | "RGB值偏差，误差[X]" |
| **Background uniformity** | Is color consistent? | "背景颜色均匀一致" | "背景颜色不均，有斑块" |

### Background Texture

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Texture presence** | Does texture exist? | "背景有渐变纹理，自然过渡" | "背景纹理缺失，纯色" |
| **Texture type** | Is pattern correct? | "纹理类型正确（渐变/噪声）" | "纹理类型不匹配" |
| **Texture scale** | Is pattern size correct? | "纹理尺度适中" | "纹理过大/过小" |
| **Texture intensity** | Is visibility correct? | "纹理强度适中，不干扰主体" | "纹理过强干扰/过弱不明显" |

### Background Transparency

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Background alpha** | Is transparency correct? | "背景透明度正确，衬托主体" | "透明度错误，遮挡/干扰主体" |
| **Background blending** | Is blend correct? | "背景与底层融合自然" | "背景硬切，不融合" |

### Subject-Background Relation

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Contrast ratio** | Is contrast correct? | "主体与背景对比鲜明，层次清晰" | "对比不足，主体融入背景" |
| **Subject isolation** | Can subject be distinguished? | "主体独立清晰，背景不干扰" | "主体与背景融合，难以区分" |
| **Background support** | Does background enhance subject? | "背景衬托主体，增强效果" | "背景干扰主体，分散注意力" |

### Background Dynamic

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Background animation** | Does background move? | "背景动态与主体同步" | "背景静态，缺少动态" |
| **Background rhythm** | Is timing correct? | "背景节奏与主体协调" | "背景节奏不协调，冲突" |

---

## 8. VFX Details

### Particle Effects

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Particle presence** | Do particles exist? | "粒子效果存在" | "粒子缺失" |
| **Particle density** | Is count correct? | "粒子密度适中，分布自然" | "密度过低/过高" |
| **Particle size** | Is scale correct? | "粒子尺寸适中" | "粒子过大/过小" |
| **Particle distribution** | Is spread correct? | "粒子分布均匀" | "分布不均，聚团/稀疏" |
| **Particle animation** | Is movement correct? | "粒子动态自然" | "粒子静态，缺少动画" |

### Flow Light Effects

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Flow presence** | Does flow light exist? | "流光效果存在" | "流光缺失" |
| **Flow trajectory** | Is path correct? | "流光轨迹正确" | "轨迹错误" |
| **Flow intensity** | Is brightness correct? | "流光强度适中" | "流光过强/过弱" |
| **Flow color** | Is color correct? | "流光颜色匹配主体" | "颜色不匹配" |

### Alpha Blending

| Check | Question | Correct Pattern | Problem Pattern |
|--------|----------|----------------|-----------------|
| **Alpha transition** | Is edge smooth? | "Alpha混合过渡自然" | "Alpha硬切，边缘突变" |
| **Alpha gradient** | Is fade correct? | "Alpha渐变正确" | "渐变错误，无过渡" |
| **Alpha consistency** | Is alpha uniform? | "Alpha值一致" | "Alpha不均，有斑块" |

---

## Scoring Calculation

### Per-Dimension Score Formula

```
score = (correct_items_count / total_check_items) * 0.7 
       + (no_problem_items_count / total_check_items) * 0.3
```

### Overall Score Formula

```
overall_score = sum(dimension_score * dimension_weight) / sum(weights)

Weights:
- Composition: 10%
- Geometry: 15%
- Lighting & Shadow: 20%
- Color & Tone: 20%
- Texture & Material: 10%
- Animation & Motion: 10%
- Background: 10%
- VFX Details: 5%
```

### Passing Threshold

- **0.9-1.0**: Excellent, passed=true
- **0.85-0.9**: Acceptable, passed=true
- **0.7-0.85**: Needs tweaking, passed=false
- **0.5-0.7**: Major changes needed, passed=false
- **0.0-0.5**: No match, passed=false