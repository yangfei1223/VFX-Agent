# CV Feature Extraction — Dimension-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 Decompose/Inspect 的评估维度，注入对应的 CV 量化数据。每个 CV 特征必须服务一个具体的 Agent 评估维度，而不是孤立地"做 CV"。

**Architecture:** 新增 `perception.py` 服务模块，在 pipeline 节点中调用，结果按维度注入 Agent prompt。不改变三 Agent 架构，只在每个 Agent 的输入端增加量化数据。

**Tech Stack:** Python, PIL + numpy + scipy（已有），不引入 OpenCV

---

## 设计原则：维度驱动特征

每个 CV 特征必须回答一个问题：**"它帮助 Agent 做了什么原本做不好的事？"**

### Decompose Agent 的维度需求

Decompose 输出 DSL 包含 7 个定义域，每个需要 CV 辅助的维度：

| DSL 维度 | LLM 能做的 | LLM 做不准的 | CV 应提供的 |
|----------|-----------|-------------|------------|
| **颜色** (color_definition) | 识别"蓝色"、"绿色" | 精确 RGB 值、渐变方向 | 色板 RGB、渐变类型/方向 |
| **形状** (shape_definition) | 识别"圆形"、"心形" | edge_width 精确值、实心/空心 | 边缘锐度量值、fill_ratio |
| **亮度** (lighting_definition) | 判断"有发光" | 发光中心位置、半径、强度 | 发光中心坐标 + 半径 |
| **纹理** (texture_definition) | 判断"有纹理" | FBM octaves/frequency 参数 | FFT → octaves/frequency 映射 |
| **背景** (background_definition) | 识别背景颜色 | 主体颜色混入背景 | 主体/背景分离 → 各自颜色 |
| **空间** (composition) | 看到位置 | 不在画面中心时偏移量 | 主体 bbox + 偏心量 |

### Inspect Agent 的维度需求

Inspect 评估 8 个维度，每个需要 CV 对比指标：

| Inspect 维度 | 权重 | 当前 CV 对比 | 需要的 CV 对比 |
|-------------|------|-------------|---------------|
| **Geometry** | 0.15 | Edge IoU | ✅ 保留 |
| **Color & Tone** | 0.15 | 直方图相似度 + 通道偏差 | ✅ 保留 |
| **Lighting** | 0.15 | ❌ 无 | **新增：亮度直方图差异 + 高亮面积差** |
| **Texture** | 0.10 | ❌ 无 | **新增：FFT 频谱差异** |
| **Animation** | 0.15 | ❌ 无 | 标注"需视频对比"（单帧限制） |
| **Background** | 0.10 | 3x3 区域 MSE | **改为：基于前景 mask 的背景区 MSE** |
| **Composition** | 0.10 | 3x3 区域 MSE（间接） | **改为：基于前景 mask 的主体区 MSE** |
| **VFX Details** | 0.10 | ❌ 无 | 边缘 alpha 质量间接反映 |
| **Overall** | — | SSIM | ✅ 保留 |

---

## 特征架构

### Decompose 特征 (extract_features)

```
extract_features(image_path)
├── color                    # 颜色维度 → color_definition
│   ├── palette              #   K-means top-5 色 [{rgb, hex, percentage}]
│   ├── gradient             #   渐变类型 + 方向 + 强度
│   ├── subject_color        #   主体区主色 rgb + 占比
│   └── background_color     #   背景区主色 rgb + 占比
├── geometry                 # 几何维度 → shape_definition
│   ├── edges                #   Sobel 密度/锐度/方向
│   ├── shape                #   圆度/凸度/对称性/估计类型
│   └── fill                 #   实心/空心比 + 估计
├── luminance                # 亮度维度 → lighting_definition
│   ├── distribution         #   均值/标准差/双峰/峰位
│   └── glow                 #   发光中心 + 半径 + 强度 + 是否检测到
├── frequency                # 频率维度 → texture_definition
│   └── fft                  #   高频比/主方向/纹理级别
└── spatial                  # 空间维度 → composition + background
    ├── subject              #   bbox + center + area_pct
    └── foreground_mask      #   前景 mask (内部用，不输出到 prompt)
```

### Inspect 对比 (compare_images)

```
compare_images(reference_path, rendered_path)
├── overall                  # 整体
│   └── ssim                 #   结构相似度 0-1
├── geometry                 # 几何维度对比 → Geometry score
│   ├── edge_iou             #   边缘 IoU
│   └── edge_diff_detail     #   边缘差异描述
├── color                    # 颜色维度对比 → Color & Tone score
│   ├── color_similarity     #   直方图余弦相似度
│   └── color_diff_detail    #   通道偏差描述
├── luminance                # 亮度维度对比 → Lighting score  [NEW]
│   ├── histogram_kl_div     #   亮度直方图 KL 散度
│   ├── highlight_area_diff  #   高亮区域面积差
│   └── highlight_diff_detail #  差异描述
├── frequency                # 频率维度对比 → Texture score  [NEW]
│   ├── spectrum_diff        #   FFT 频谱整体差异
│   ├── band_diffs           #   低/中/高频分别差异
│   └── texture_match        #   good/acceptable/poor
└── spatial                  # 空间维度对比 → Composition + Background score
    ├── subject_mse          #   主体区 MSE  [REPLACES 3x3 regional]
    ├── background_mse       #   背景区 MSE  [REPLACES 3x3 regional]
    └── spatial_diff_detail  #   差异描述
```

---

## File Structure

```
新增:
├── backend/app/services/perception.py    # CV特征提取 + 像素对比服务 (~400行)

修改:
├── backend/app/pipeline/state.py        # +cv_features, +cv_comparison 字段
├── backend/app/pipeline/graph.py        # 调用perception注入节点
├── backend/app/services/context_assembler.py  # 按维度注入CV数据到prompt
├── backend/app/prompts/decompose_system.md    # CV 数据使用指导
├── backend/app/prompts/inspect_system.md      # CV 对比使用指导
```

---

### Task 1: 创建 perception.py — 维度驱动的 CV 特征提取服务

**Files:**
- Create: `backend/app/services/perception.py`

**目标:** 提供两个核心函数，按维度组织

- [ ] **Step 1: 创建 perception.py 框架 + 辅助函数**

```python
"""CV Feature Extraction Service — 维度驱动的量化视觉特征提取

按 Decompose/Inspect Agent 的评估维度组织，每个特征服务于一个具体的 Agent 维度。
"""

import numpy as np
from PIL import Image
from pathlib import Path
from collections import Counter


# ─── Sobel 核（共用） ───────────────────────────────────────────

_SOBEL_X = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64)
_SOBEL_Y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float64)


def _to_gray(arr: np.ndarray) -> np.ndarray:
    """RGB [0,1] → grayscale"""
    return np.mean(arr, axis=2)


def _sobel(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (gx, gy, magnitude)"""
    from scipy.signal import convolve2d
    gx = convolve2d(gray, _SOBEL_X, mode="same", boundary="symm")
    gy = convolve2d(gray, _SOBEL_Y, mode="same", boundary="symm")
    return gx, gy, np.sqrt(gx**2 + gy**2)


def _otsu_threshold(gray: np.ndarray) -> float:
    """Otsu 自动阈值"""
    hist, bin_edges = np.histogram(gray.flatten(), bins=256, range=(0, 1))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    total = hist.sum()
    sum_total = np.sum(bin_centers * hist)
    sum_bg = 0.0
    weight_bg = 0
    max_variance = 0.0
    threshold = 0.5

    for i in range(256):
        weight_bg += hist[i]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += bin_centers[i] * hist[i]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg
        variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if variance > max_variance:
            max_variance = variance
            threshold = bin_centers[i]

    return float(threshold)


# ─── Decompose: extract_features ────────────────────────────────

def extract_features(image_path: str) -> dict:
    """从参考帧提取量化特征，按维度组织，供 Decompose 使用

    Returns:
        {
            "color": {
                "palette": [...],
                "gradient": {"type", "direction", "strength"},
                "subject_color": {"rgb", "percentage"},
                "background_color": {"rgb", "percentage"},
            },
            "geometry": {
                "edges": {"density", "sharpness", "dominant_angle"},
                "shape": {"circularity", "convexity", "symmetry_h", "symmetry_v", "estimated_type"},
                "fill": {"edge_interior_ratio", "estimated_fill"},
            },
            "luminance": {
                "distribution": {"mean", "std", "is_bimodal", "peaks"},
                "glow": {"detected", "center", "radius", "intensity"},
            },
            "frequency": {
                "high_freq_ratio", "dominant_direction", "texture_level",
            },
            "spatial": {
                "subject": {"bbox", "center", "area_pct"},
            },
        }
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img, dtype=np.float64) / 255.0  # [H, W, 3], 0-1
    gray = _to_gray(arr)

    # 先做前景分离（后续多维度共用）
    fg_mask = _compute_foreground_mask(gray)

    return {
        "color": _extract_color(arr, fg_mask),
        "geometry": _extract_geometry(arr, gray, fg_mask),
        "luminance": _extract_luminance(arr, gray, fg_mask),
        "frequency": _extract_frequency(gray),
        "spatial": _extract_spatial(gray, fg_mask),
    }


# ─── Inspect: compare_images ────────────────────────────────────

def compare_images(reference_path: str, rendered_path: str) -> dict:
    """像素级对比参考帧与渲染帧，按 Inspect 评估维度组织

    Returns:
        {
            "overall": {"ssim": float},
            "geometry": {"edge_iou", "edge_diff_detail"},
            "color": {"similarity", "diff_detail"},
            "luminance": {"histogram_kl_div", "highlight_area_diff", "diff_detail"},
            "frequency": {"spectrum_diff", "band_diffs", "texture_match"},
            "spatial": {"subject_mse", "background_mse", "diff_detail"},
        }
    """
    ref = Image.open(reference_path).convert("RGB")
    rnd = Image.open(rendered_path).convert("RGB")

    if ref.size != rnd.size:
        rnd = rnd.resize(ref.size, Image.LANCZOS)

    ref_arr = np.array(ref, dtype=np.float64) / 255.0
    rnd_arr = np.array(rnd, dtype=np.float64) / 255.0
    ref_gray = _to_gray(ref_arr)

    # 用参考帧的前景 mask 分离主体/背景
    ref_fg = _compute_foreground_mask(ref_gray)

    return {
        "overall": {"ssim": _compute_ssim(ref_arr, rnd_arr)},
        "geometry": _compare_geometry(ref_arr, rnd_arr),
        "color": _compare_color(ref_arr, rnd_arr),
        "luminance": _compare_luminance(ref_arr, rnd_arr),
        "frequency": _compare_frequency(ref_arr, rnd_arr),
        "spatial": _compare_spatial(ref_arr, rnd_arr, ref_fg),
    }
```

- [ ] **Step 2: 实现 Foreground Mask `_compute_foreground_mask`**

```python
def _compute_foreground_mask(gray: np.ndarray) -> np.ndarray:
    """Otsu 阈值分割前景（亮区=前景）"""
    threshold = _otsu_threshold(gray)
    return gray > threshold
```

- [ ] **Step 3: 实现 Color 维度 `_extract_color`**

```python
def _extract_color(arr: np.ndarray, fg_mask: np.ndarray) -> dict:
    """颜色维度：色板 + 渐变方向 + 主体色/背景色分离"""
    h, w = arr.shape[:2]

    # --- 色板 (K-means) ---
    palette = _extract_palette(arr)

    # --- 主体色 vs 背景色 ---
    fg_pixels = arr[fg_mask]
    bg_pixels = arr[~fg_mask]

    subject_rgb = np.clip(np.mean(fg_pixels, axis=0) * 255, 0, 255).astype(int).tolist() if len(fg_pixels) > 0 else [128, 128, 128]
    bg_rgb = np.clip(np.mean(bg_pixels, axis=0) * 255, 0, 255).astype(int).tolist() if len(bg_pixels) > 0 else [0, 0, 0]

    subject_pct = round(float(np.sum(fg_mask)) / fg_mask.size * 100, 1)
    bg_pct = round(100.0 - subject_pct, 1)

    # --- 渐变方向 ---
    gradient = _extract_gradient_direction(arr)

    return {
        "palette": palette,
        "gradient": gradient,
        "subject_color": {"rgb": subject_rgb, "percentage": subject_pct},
        "background_color": {"rgb": bg_rgb, "percentage": bg_pct},
    }


def _extract_palette(arr: np.ndarray, n_colors: int = 5) -> list[dict]:
    """K-means 聚类提取主要颜色"""
    from scipy.cluster.vq import kmeans2

    pixels = arr.reshape(-1, 3)
    if len(pixels) > 10000:
        idx = np.random.choice(len(pixels), 10000, replace=False)
        sample = pixels[idx]
    else:
        sample = pixels

    centroids, labels = kmeans2(sample, n_colors, minit="++")
    counts = Counter(labels)
    total = len(labels)

    palette = []
    for i, centroid in enumerate(centroids):
        rgb = np.clip(centroid * 255, 0, 255).astype(int)
        pct = counts.get(i, 0) / total * 100
        palette.append({
            "rgb": rgb.tolist(),
            "hex": "#{:02x}{:02x}{:02x}".format(*rgb),
            "percentage": round(pct, 1)
        })

    palette.sort(key=lambda x: -x["percentage"])
    return palette


def _extract_gradient_direction(arr: np.ndarray) -> dict:
    """亮度梯度分析 → 渐变类型/方向"""
    gray = _to_gray(arr)
    _, _, magnitude = _sobel(gray)

    # 计算梯度场的平均方向
    h, w = gray.shape
    cy, cx = h / 2, w / 2
    y, x = np.mgrid[:h, :w].astype(np.float64)
    dx = (x - cx) / cx
    dy = (y - cy) / cy
    radial_dist = np.sqrt(dx**2 + dy**2) + 1e-10
    radial_dir_x = dx / radial_dist
    radial_dir_y = dy / radial_dist

    # Sobel 方向
    gx = convolve2d(gray, _SOBEL_X, mode="same", boundary="symm") if False else None
    from scipy.signal import convolve2d
    gx = convolve2d(gray, _SOBEL_X, mode="same", boundary="symm")
    gy = convolve2d(gray, _SOBEL_Y, mode="same", boundary="symm")

    # 径向相关性：梯度方向与径向方向的相关性
    radial_corr = float(np.mean(gx * radial_dir_x + gy * radial_dir_y))

    # 线性方向
    avg_gx = float(np.mean(gx))
    avg_gy = float(np.mean(gy))

    if abs(radial_corr) > 0.008:
        grad_type = "radial"
        direction = "center_outward" if radial_corr > 0 else "center_inward"
    elif abs(avg_gx) > abs(avg_gy) * 1.5:
        grad_type = "linear"
        direction = "left_to_right" if avg_gx > 0 else "right_to_left"
    elif abs(avg_gy) > abs(avg_gx) * 1.5:
        grad_type = "linear"
        direction = "top_to_bottom" if avg_gy > 0 else "bottom_to_top"
    else:
        grad_type = "uniform"
        direction = "none"

    strength = round(float(np.sqrt(avg_gx**2 + avg_gy**2)), 4)

    return {
        "type": grad_type,
        "direction": direction,
        "strength": strength,
    }
```

- [ ] **Step 4: 实现 Geometry 维度 `_extract_geometry`**

```python
def _extract_geometry(arr: np.ndarray, gray: np.ndarray, fg_mask: np.ndarray) -> dict:
    """几何维度：边缘 + 形状分类 + 实心/空心"""
    _, _, magnitude = _sobel(gray)

    # --- 边缘特征 ---
    threshold = np.mean(magnitude) + np.std(magnitude)
    edge_mask = magnitude > threshold
    density = float(np.mean(edge_mask))

    edge_vals = magnitude[edge_mask]
    sharpness = "hard" if len(edge_vals) > 0 and np.mean(edge_vals) > 0.3 else \
                ("medium" if len(edge_vals) > 0 and np.mean(edge_vals) > 0.1 else "soft")

    # 主方向
    gx, gy, _ = _sobel(gray)
    angles = np.arctan2(gy, gx) * 180 / np.pi
    edge_angles = angles[edge_mask]
    if len(edge_angles) > 0:
        angle_bins = np.histogram(edge_angles, bins=8, range=(-180, 180))[0]
        directions = ["→", "↗", "↑", "↖", "←", "↙", "↓", "↘"]
        dominant_angle = directions[np.argmax(angle_bins)]
    else:
        dominant_angle = "none"

    edges = {"density": round(density, 3), "sharpness": sharpness, "dominant_angle": dominant_angle}

    # --- 形状分类 ---
    shape = _extract_shape_features(gray, fg_mask)

    # --- 实心/空心 ---
    total_fg = max(float(np.sum(fg_mask)), 1)
    edge_in_fg = float(np.sum(edge_mask & fg_mask))
    edge_interior_ratio = edge_in_fg / total_fg
    estimated_fill = "hollow" if edge_interior_ratio > 0.3 else "solid"

    fill = {"edge_interior_ratio": round(edge_interior_ratio, 3), "estimated_fill": estimated_fill}

    return {"edges": edges, "shape": shape, "fill": fill}


def _extract_shape_features(gray: np.ndarray, fg_mask: np.ndarray) -> dict:
    """从前景 mask 提取形状特征：圆度/凸度/对称性"""
    from scipy import ndimage

    labeled, num_features = ndimage.label(fg_mask)
    if num_features == 0:
        return {"circularity": 0, "convexity": 0, "symmetry_h": 0, "symmetry_v": 0, "estimated_type": "none"}

    # 最大连通域
    sizes = ndimage.sum(fg_mask, labeled, range(1, num_features + 1))
    largest = (labeled == (np.argmax(sizes) + 1))

    # 圆度 = 4π·area / perimeter²
    area = float(np.sum(largest))
    # 周长：边缘像素数（前景与背景的交界）
    eroded = ndimage.binary_erosion(largest)
    perimeter = float(np.sum(largest & ~eroded))
    circularity = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0
    circularity = min(float(circularity), 1.0)  # cap at 1.0

    # 凸度 = area / convex_hull_area
    try:
        from scipy.spatial import ConvexHull
        ys, xs = np.where(largest)
        points = np.column_stack([xs, ys])
        if len(points) > 2:
            hull = ConvexHull(points)
            convexity = area / hull.volume  # 2D: volume = area
        else:
            convexity = 1.0
    except Exception:
        convexity = 1.0

    # 对称性：翻转后重叠率
    flipped_h = np.flip(largest, axis=1)
    symmetry_h = float(np.sum(largest & flipped_h)) / max(area, 1)
    flipped_v = np.flip(largest, axis=0)
    symmetry_v = float(np.sum(largest & flipped_v)) / max(area, 1)

    # 估计类型
    if circularity > 0.85:
        est_type = "circle"
    elif circularity > 0.7:
        est_type = "rounded"
    elif circularity > 0.5:
        est_type = "organic"
    else:
        est_type = "irregular"

    return {
        "circularity": round(circularity, 3),
        "convexity": round(min(float(convexity), 1.0), 3),
        "symmetry_h": round(symmetry_h, 3),
        "symmetry_v": round(symmetry_v, 3),
        "estimated_type": est_type,
    }
```

- [ ] **Step 5: 实现 Luminance 维度 `_extract_luminance`**

```python
def _extract_luminance(arr: np.ndarray, gray: np.ndarray, fg_mask: np.ndarray) -> dict:
    """亮度维度：分布 + 发光检测"""
    # --- 亮度分布 ---
    hist, _ = np.histogram(gray.flatten(), bins=50, range=(0, 1))
    hist = hist / hist.sum()

    mean = float(np.mean(gray))
    std = float(np.std(gray))

    peaks = []
    for i in range(1, len(hist) - 1):
        if hist[i] > hist[i-1] and hist[i] > hist[i+1] and hist[i] > 0.02:
            peaks.append(round(float(i / 50), 2))

    is_bimodal = len(peaks) >= 2 and (peaks[-1] - peaks[0]) > 0.3

    distribution = {
        "mean": round(mean, 3),
        "std": round(std, 3),
        "is_bimodal": is_bimodal,
        "distribution": "bimodal" if is_bimodal else ("uniform" if std > 0.25 else "concentrated"),
        "peaks": peaks[:3],
    }

    # --- 发光检测 ---
    glow = _detect_glow(gray, fg_mask)

    return {"distribution": distribution, "glow": glow}


def _detect_glow(gray: np.ndarray, fg_mask: np.ndarray) -> dict:
    """检测发光中心：最亮区域的中心 + 半径 + 强度"""
    from scipy import ndimage

    # Top 5% 亮度区域
    threshold = np.percentile(gray, 95)
    bright_mask = gray >= threshold

    if not np.any(bright_mask):
        return {"detected": False, "center": [0.5, 0.5], "radius": 0, "intensity": 0}

    h, w = gray.shape
    cy, cx = ndimage.center_of_mass(bright_mask)
    center = [round(float(cx) / w, 3), round(float(cy) / h, 3)]

    # 半径：90th percentile 距离
    ys, xs = np.where(bright_mask)
    distances = np.sqrt((xs - cx)**2 + (ys - cy)**2)
    radius = round(float(np.percentile(distances, 90)) / max(h, w), 3)

    # 强度：最亮区域最大值 / 全图均值
    max_brightness = float(np.max(gray[bright_mask]))
    mean_brightness = max(float(np.mean(gray)), 0.01)
    intensity = round(max_brightness / mean_brightness, 2)

    detected = intensity > 1.5

    return {"detected": detected, "center": center, "radius": radius, "intensity": intensity}
```

- [ ] **Step 6: 实现 Frequency 维度 `_extract_frequency`**

```python
def _extract_frequency(gray: np.ndarray) -> dict:
    """FFT 分析空间频率"""
    fft = np.fft.fft2(gray)
    fft_shift = np.fft.fftshift(fft)
    magnitude = np.abs(fft_shift)

    h, w = gray.shape
    cy, cx = h // 2, w // 2

    total_energy = np.sum(magnitude ** 2)
    radius = min(h, w) // 4

    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx)**2 + (y - cy)**2)

    low_freq_energy = np.sum(magnitude[dist <= radius] ** 2)
    high_freq_energy = total_energy - low_freq_energy
    high_freq_ratio = float(high_freq_energy / total_energy)

    # 主方向
    h_freq = np.sum(magnitude[cy-2:cy+2, :] ** 2)
    v_freq = np.sum(magnitude[:, cx-2:cx+2] ** 2)

    if h_freq > v_freq * 1.5:
        dominant = "vertical"
    elif v_freq > h_freq * 1.5:
        dominant = "horizontal"
    else:
        dominant = "isotropic"

    return {
        "high_freq_ratio": round(high_freq_ratio, 3),
        "dominant_direction": dominant,
        "texture_level": "fine" if high_freq_ratio > 0.7 else ("medium" if high_freq_ratio > 0.4 else "smooth"),
    }
```

- [ ] **Step 7: 实现 Spatial 维度 `_extract_spatial`**

```python
def _extract_spatial(gray: np.ndarray, fg_mask: np.ndarray) -> dict:
    """空间布局：主体位置 + 面积"""
    h, w = gray.shape
    rows = np.any(fg_mask, axis=1)
    cols = np.any(fg_mask, axis=0)

    if rows.any():
        y1, y2 = int(np.where(rows)[0][0]), int(np.where(rows)[0][-1])
        x1, x2 = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1])
        center = [round((x1 + x2) / 2 / w, 3), round((y1 + y2) / 2 / h, 3)]
        area_pct = round(float(np.sum(fg_mask)) / fg_mask.size * 100, 1)
    else:
        x1, y1, x2, y2 = 0, 0, w, h
        center = [0.5, 0.5]
        area_pct = 100.0

    return {
        "subject": {
            "bbox": [x1, y1, x2, y2],
            "center": center,
            "area_pct": area_pct,
        }
    }
```

- [ ] **Step 8: 实现 Inspect 对比 — Overall SSIM**

```python
# ─── Inspect 对比函数 ────────────────────────────────────────────

def _compute_ssim(ref: np.ndarray, rnd: np.ndarray, window_size: int = 11) -> float:
    """结构相似度"""
    C1 = (0.01) ** 2
    C2 = (0.03) ** 2

    ref_gray = _to_gray(ref)
    rnd_gray = _to_gray(rnd)

    from scipy.ndimage import uniform_filter
    mu1 = uniform_filter(ref_gray, size=window_size)
    mu2 = uniform_filter(rnd_gray, size=window_size)

    sigma1_sq = uniform_filter(ref_gray ** 2, size=window_size) - mu1 ** 2
    sigma2_sq = uniform_filter(rnd_gray ** 2, size=window_size) - mu2 ** 2
    sigma12 = uniform_filter(ref_gray * rnd_gray, size=window_size) - mu1 * mu2

    ssim_map = ((2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)) / \
               ((mu1 ** 2 + mu2 ** 2 + C1) * (sigma1_sq + sigma2_sq + C2))

    return round(float(np.mean(ssim_map)), 4)
```

- [ ] **Step 9: 实现 Inspect 对比 — Geometry `_compare_geometry`**

```python
def _compare_geometry(ref: np.ndarray, rnd: np.ndarray) -> dict:
    """几何维度对比：边缘 IoU + 差异描述"""
    ref_edges = _get_edge_map(ref)
    rnd_edges = _get_edge_map(rnd)

    intersection = np.sum(ref_edges & rnd_edges)
    union = np.sum(ref_edges | rnd_edges)
    edge_iou = round(float(intersection / max(union, 1)), 4)

    ref_count = int(np.sum(ref_edges))
    rnd_count = int(np.sum(rnd_edges))

    if ref_count > rnd_count * 1.5:
        detail = f"参考帧{ref_count}像素边缘，渲染{rnd_count}像素，缺少{int((1-rnd_count/max(ref_count,1))*100)}%边缘细节"
    elif rnd_count > ref_count * 1.5:
        detail = f"渲染边缘{rnd_count}像素过多，参考帧{ref_count}像素，可能有不必要的纹理"
    else:
        detail = f"边缘密度接近（参考{ref_count}，渲染{rnd_count}）"

    return {"edge_iou": edge_iou, "edge_diff_detail": detail}


def _get_edge_map(arr: np.ndarray) -> np.ndarray:
    """Sobel 边缘二值图"""
    gray = _to_gray(arr)
    _, _, magnitude = _sobel(gray)
    threshold = np.mean(magnitude) + np.std(magnitude)
    return magnitude > threshold
```

- [ ] **Step 10: 实现 Inspect 对比 — Color `_compare_color`**

```python
def _compare_color(ref: np.ndarray, rnd: np.ndarray) -> dict:
    """颜色维度对比：直方图相似度 + 通道偏差"""
    sim_scores = []
    for c in range(3):
        ref_hist, _ = np.histogram(ref[:,:,c].flatten(), bins=64, range=(0, 1))
        rnd_hist, _ = np.histogram(rnd[:,:,c].flatten(), bins=64, range=(0, 1))
        dot = np.dot(ref_hist, rnd_hist)
        norm = np.sqrt(np.sum(ref_hist**2)) * np.sqrt(np.sum(rnd_hist**2))
        sim_scores.append(dot / max(norm, 1e-10))

    similarity = round(float(np.mean(sim_scores)), 4)

    # 通道偏差
    diffs = []
    channels = ["Red", "Green", "Blue"]
    for c in range(3):
        ref_mean = np.mean(ref[:,:,c])
        rnd_mean = np.mean(rnd[:,:,c])
        diff = rnd_mean - ref_mean
        if abs(diff) > 0.05:
            direction = "偏高" if diff > 0 else "偏低"
            pct = abs(diff) / max(ref_mean, 0.01) * 100
            diffs.append(f"{channels[c]}通道{direction}{pct:.0f}%")

    diff_detail = "; ".join(diffs) if diffs else "色彩基本匹配"

    return {"similarity": similarity, "diff_detail": diff_detail}
```

- [ ] **Step 11: 实现 Inspect 对比 — Luminance `_compare_luminance` (NEW)**

```python
def _compare_luminance(ref: np.ndarray, rnd: np.ndarray) -> dict:
    """亮度维度对比：直方图 KL 散度 + 高亮面积差"""
    ref_gray = _to_gray(ref)
    rnd_gray = _to_gray(rnd)

    # 直方图 KL 散度
    ref_hist, _ = np.histogram(ref_gray.flatten(), bins=50, range=(0, 1), density=True)
    rnd_hist, _ = np.histogram(rnd_gray.flatten(), bins=50, range=(0, 1), density=True)
    eps = 1e-10
    ref_hist = ref_hist + eps
    rnd_hist = rnd_hist + eps
    kl_div = round(float(np.sum(ref_hist * np.log(ref_hist / rnd_hist))), 4)

    # 高亮面积差 (>0.8 = 高亮)
    ref_bright = float(np.sum(ref_gray > 0.8)) / ref_gray.size
    rnd_bright = float(np.sum(rnd_gray > 0.8)) / rnd_gray.size
    highlight_area_diff = round(ref_bright - rnd_bright, 4)

    if highlight_area_diff > 0.05:
        detail = f"参考帧高亮区域占{ref_bright*100:.1f}%，渲染帧占{rnd_bright*100:.1f}%，渲染缺少{abs(highlight_area_diff)*100:.1f}%的亮度区域"
    elif highlight_area_diff < -0.05:
        detail = f"渲染帧高亮区域偏多：参考帧{ref_bright*100:.1f}%，渲染帧{rnd_bright*100:.1f}%"
    else:
        detail = "亮度分布基本匹配"

    return {
        "histogram_kl_div": kl_div,
        "highlight_area_diff": highlight_area_diff,
        "diff_detail": detail,
    }
```

- [ ] **Step 12: 实现 Inspect 对比 — Frequency `_compare_frequency` (NEW)**

```python
def _compare_frequency(ref: np.ndarray, rnd: np.ndarray) -> dict:
    """频率维度对比：FFT 频谱差异（逐频带）"""
    ref_gray = _to_gray(ref)
    rnd_gray = _to_gray(rnd)

    ref_fft = np.abs(np.fft.fftshift(np.fft.fft2(ref_gray))) ** 2
    rnd_fft = np.abs(np.fft.fftshift(np.fft.fft2(rnd_gray))) ** 2

    h, w = ref_gray.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx)**2 + (y - cy)**2)

    r_low = min(h, w) // 8
    r_mid = min(h, w) // 4
    r_high = min(h, w) // 2

    def band_energy(spectrum, r_inner, r_outer):
        mask = (dist >= r_inner) & (dist < r_outer)
        return float(np.sum(spectrum[mask]))

    ref_low = band_energy(ref_fft, 0, r_low)
    ref_mid = band_energy(ref_fft, r_low, r_mid)
    ref_high = band_energy(ref_fft, r_mid, r_high)
    rnd_low = band_energy(rnd_fft, 0, r_low)
    rnd_mid = band_energy(rnd_fft, r_low, r_mid)
    rnd_high = band_energy(rnd_fft, r_mid, r_high)

    ref_total = max(ref_low + ref_mid + ref_high, 1e-10)
    rnd_total = max(rnd_low + rnd_mid + rnd_high, 1e-10)

    low_diff = abs(ref_low/ref_total - rnd_low/rnd_total)
    mid_diff = abs(ref_mid/ref_total - rnd_mid/rnd_total)
    high_diff = abs(ref_high/ref_total - rnd_high/rnd_total)
    spectrum_diff = round((low_diff + mid_diff + high_diff) / 3, 4)

    if spectrum_diff < 0.05:
        match = "good"
    elif spectrum_diff < 0.15:
        match = "acceptable"
    else:
        match = "poor"

    return {
        "spectrum_diff": spectrum_diff,
        "band_diffs": {"low": round(low_diff, 4), "mid": round(mid_diff, 4), "high": round(high_diff, 4)},
        "texture_match": match,
    }
```

- [ ] **Step 13: 实现 Inspect 对比 — Spatial `_compare_spatial` (REPLACES 3x3 regional)**

```python
def _compare_spatial(ref: np.ndarray, rnd: np.ndarray, ref_fg: np.ndarray) -> dict:
    """空间维度对比：基于前景 mask 的主体/背景分别 MSE"""
    ref_gray = _to_gray(ref)
    rnd_gray = _to_gray(rnd)
    bg_mask = ~ref_fg

    # 主体区 MSE
    if np.any(ref_fg):
        subject_mse = round(float(np.mean((ref_gray[ref_fg] - rnd_gray[ref_fg]) ** 2)), 4)
    else:
        subject_mse = 0.0

    # 背景区 MSE
    if np.any(bg_mask):
        background_mse = round(float(np.mean((ref_gray[bg_mask] - rnd_gray[bg_mask]) ** 2)), 4)
    else:
        background_mse = 0.0

    worse = "subject" if subject_mse > background_mse else "background"
    detail = f"主体区MSE={subject_mse:.4f}，背景区MSE={background_mse:.4f}"
    if worse == "subject" and subject_mse > 0.05:
        detail += " — 主体区域差异较大"
    elif worse == "background" and background_mse > 0.05:
        detail += " — 背景区域差异较大"

    return {
        "subject_mse": subject_mse,
        "background_mse": background_mse,
        "diff_detail": detail,
    }
```

- [ ] **Step 14: 验证 perception.py**

```bash
cd /Users/yangfei/Code/VFX-Agent/backend && python -c "
from app.services.perception import extract_features, compare_images
import os

# 使用测试样本中的任意一个截图
test_dirs = ['/tmp/vfx-frames']
frames = []
for d in test_dirs:
    if os.path.exists(d):
        frames = [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.png')]
        break

if not frames:
    # 尝试用 test_e2e_results 中的截图
    for d in ['test_e2e_results_v2']:
        for root, dirs, files in os.walk(d):
            for f in files:
                if f.endswith('.png') and 'reference' in f:
                    frames.append(os.path.join(root, f))
            if frames:
                break

if frames:
    path = frames[0]
    print(f'Testing with: {path}')
    features = extract_features(path)
    print('Extract features OK:')
    for dim, data in features.items():
        print(f'  [{dim}] {data}')

    # Self-comparison (should be perfect)
    comp = compare_images(path, path)
    print('\nSelf-comparison (should be ~1.0):')
    for dim, data in comp.items():
        print(f'  [{dim}] {data}')
else:
    print('No test images found. Manual test needed after first pipeline run.')
    print('Import test:')
    from app.services.perception import extract_features, compare_images
    print('  extract_features: OK')
    print('  compare_images: OK')
"
```

Expected: SSIM ≈ 1.0, color_similarity ≈ 1.0, edge_iou ≈ 1.0, spectrum_diff ≈ 0.0

- [ ] **Step 15: Commit**

```bash
git add backend/app/services/perception.py
git commit -m "feat: add dimension-driven CV feature extraction service"
```

---

### Task 2: 扩展 Pipeline State — 新增 cv_features 和 cv_comparison 字段

**Files:**
- Modify: `backend/app/pipeline/state.py`

- [ ] **Step 1: 在 BaselineRegion 中新增 cv_features**

在 `BaselineRegion` TypedDict 中新增:

```python
class BaselineRegion(TypedDict, total=False):
    # ... existing fields ...
    cv_features: dict | None  # CV extracted features (organized by dimension)
```

- [ ] **Step 2: 在 SnapshotRegion 中新增 cv_comparison**

在 `SnapshotRegion` TypedDict 中新增:

```python
class SnapshotRegion(TypedDict, total=False):
    # ... existing fields ...
    cv_comparison: dict | None  # CV pixel-level comparison (organized by dimension)
```

- [ ] **Step 3: 在 create_initial_state 中初始化新字段**

在 `create_initial_state()` 的 baseline 和 snapshot 初始化中:

```python
baseline: BaselineRegion = {
    # ... existing ...
    "cv_features": None,
}

snapshot: SnapshotRegion = {
    # ... existing ...
    "cv_comparison": None,
}
```

- [ ] **Step 4: 验证**

```bash
cd /Users/yangfei/Code/VFX-Agent/backend && python -c "
from app.pipeline.state import create_initial_state
s = create_initial_state('test', 'text')
print('baseline.cv_features:', s['baseline'].get('cv_features'))
print('snapshot.cv_comparison:', s['snapshot'].get('cv_comparison'))
print('OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/state.py
git commit -m "feat: add cv_features and cv_comparison to pipeline state"
```

---

### Task 3: 在 Pipeline Graph 中注入 CV 特征提取

**Files:**
- Modify: `backend/app/pipeline/graph.py`

**目标:** 在 `node_extract_keyframes` 后提取参考帧特征，在 `node_render_and_screenshot` 后做像素对比

- [ ] **Step 1: 在 node_extract_keyframes 末尾注入特征提取**

找到 `node_extract_keyframes` 函数中，keyframes 提取完成后的位置（大约在写入 `baseline.keyframe_paths` 之后），添加:

```python
    # CV Feature Extraction for reference frames (by dimension)
    if keyframe_paths:
        from app.services.perception import extract_features
        cv_features_list = []
        for kf_path in keyframe_paths:
            try:
                features = extract_features(kf_path)
                cv_features_list.append(features)
            except Exception as e:
                print(f"[Pipeline {pipeline_id}] CV feature extraction failed for {kf_path}: {e}")

        if cv_features_list:
            updates["baseline"] = {
                **baseline,
                "cv_features": {
                    "frames": cv_features_list,
                    "primary": cv_features_list[0],
                },
            }
```

- [ ] **Step 2: 在 node_render_and_screenshot 末尾注入像素对比**

找到 `node_render_and_screenshot` 函数中，screenshots 返回后的位置，添加:

```python
    # CV Pixel Comparison (reference vs rendered, by dimension)
    cv_comparison = None
    if screenshots and baseline.get("keyframe_paths"):
        from app.services.perception import compare_images
        ref_path = baseline["keyframe_paths"][0]
        rnd_path = screenshots[0]
        try:
            cv_comparison = compare_images(ref_path, rnd_path)
            o = cv_comparison.get("overall", {})
            g = cv_comparison.get("geometry", {})
            c = cv_comparison.get("color", {})
            l = cv_comparison.get("luminance", {})
            f = cv_comparison.get("frequency", {})
            print(f"[Pipeline {pipeline_id}] CV: SSIM={o.get('ssim',0):.3f} EdgeIoU={g.get('edge_iou',0):.3f} Color={c.get('similarity',0):.3f} KL={l.get('histogram_kl_div',0):.3f} FreqDiff={f.get('spectrum_diff',0):.3f}")
        except Exception as e:
            print(f"[Pipeline {pipeline_id}] CV comparison failed: {e}")

    if cv_comparison:
        updates["snapshot"] = {
            **snapshot,
            "cv_comparison": cv_comparison,
        }
```

- [ ] **Step 3: 验证 Pipeline 仍可正常启动**

```bash
# Quick smoke test - just trigger and check status
curl -X POST http://localhost:8000/pipeline/run \
  -F "notes=test cv features" \
  --max-time 10 2>&1 | python3 -m json.tool
```

Expected: `{"pipeline_id": "...", "status": "running"}`

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipeline/graph.py
git commit -m "feat: inject dimension-driven CV into pipeline nodes"
```

---

### Task 4: 在 Context Assembler 中按维度注入 CV 数据到 Agent Prompt

**Files:**
- Modify: `backend/app/services/context_assembler.py`

**目标:** 把 cv_features 按 Decompose 维度注入，把 cv_comparison 按 Inspect 维度注入

- [ ] **Step 1: 新增 `_format_cv_features` — 按 Decompose 维度格式化**

```python
def _format_cv_features(cv_features: dict) -> str:
    """将 CV 特征按维度格式化为 Decompose Agent 可读文本"""
    if not cv_features:
        return ""

    primary = cv_features.get("primary", {})
    if not primary:
        return ""

    lines = ["\n## 参考帧量化特征（CV提取，必须参考）\n"]

    # ── 颜色维度 → color_definition ──
    color = primary.get("color", {})
    if color:
        lines.append("### 颜色维度 → color_definition")

        palette = color.get("palette", [])
        if palette:
            lines.append("  色板（精确值，不要用模糊描述）:")
            for c in palette[:5]:
                lines.append(f"    - RGB{c['rgb']} ({c['hex']}) 占比 {c['percentage']}%")

        subj = color.get("subject_color", {})
        bg = color.get("background_color", {})
        if subj:
            lines.append(f"  主体色: RGB{subj.get('rgb',[])} (占画面{subj.get('percentage',0)}%)")
        if bg:
            lines.append(f"  背景色: RGB{bg.get('rgb',[])} (占画面{bg.get('percentage',0)}%)")

        grad = color.get("gradient", {})
        if grad and grad.get("type") != "uniform":
            lines.append(f"  渐变类型: {grad.get('type')} {grad.get('direction')} (强度={grad.get('strength',0)})")

        lines.append("")

    # ── 几何维度 → shape_definition ──
    geometry = primary.get("geometry", {})
    if geometry:
        lines.append("### 几何维度 → shape_definition")

        edges = geometry.get("edges", {})
        if edges:
            lines.append(f"  边缘: 密度={edges.get('density',0):.3f} 锐度={edges.get('sharpness','?')}")
            lines.append(f"    → sharpness=hard→edge_width 0.005-0.01, soft→0.03-0.08")

        shape = geometry.get("shape", {})
        if shape:
            lines.append(f"  形状: 圆度={shape.get('circularity',0)} 凸度={shape.get('convexity',0)} 对称H={shape.get('symmetry_h',0)} 对称V={shape.get('symmetry_v',0)} 估计={shape.get('estimated_type','?')}")

        fill = geometry.get("fill", {})
        if fill:
            lines.append(f"  填充: 边缘/内部比={fill.get('edge_interior_ratio',0):.3f} → 估计={fill.get('estimated_fill','?')}")

        lines.append("")

    # ── 亮度维度 → lighting_definition ──
    luminance = primary.get("luminance", {})
    if luminance:
        lines.append("### 亮度维度 → lighting_definition")

        dist = luminance.get("distribution", {})
        if dist:
            lines.append(f"  亮度分布: 均值={dist.get('mean',0):.2f} 标准差={dist.get('std',0):.2f} 类型={dist.get('distribution','?')}")
            if dist.get("is_bimodal"):
                lines.append("  ⚠️ 双峰 — 画面有明显的亮暗区域分离（发光体+暗背景）")

        glow = luminance.get("glow", {})
        if glow and glow.get("detected"):
            lines.append(f"  发光中心: ({glow.get('center',[0,0])[0]:.2f}, {glow.get('center',[0,0])[1]:.2f}) 半径={glow.get('radius',0):.3f} 强度比={glow.get('intensity',0):.1f}x")

        lines.append("")

    # ── 频率维度 → texture_definition ──
    frequency = primary.get("frequency", {})
    if frequency:
        lines.append("### 频率维度 → texture_definition")
        lines.append(f"  纹理级别={frequency.get('texture_level','?')} 主方向={frequency.get('dominant_direction','?')} 高频占比={frequency.get('high_freq_ratio',0):.3f}")
        lines.append(f"    → fine→octaves 5-6 freq 4-6, medium→3-4 freq 2-4, smooth→2-3 freq 1-2")
        lines.append("")

    # ── 空间维度 → composition ──
    spatial = primary.get("spatial", {})
    if spatial:
        subj = spatial.get("subject", {})
        if subj:
            lines.append("### 空间维度 → composition")
            lines.append(f"  主体位置: center=({subj.get('center',[0,0])[0]:.2f}, {subj.get('center',[0,0])[1]:.2f}) 占画面{subj.get('area_pct',0)}%")
            lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 2: 新增 `_format_cv_comparison` — 按 Inspect 维度格式化**

```python
def _format_cv_comparison(cv_comparison: dict) -> str:
    """将 CV 对比按 Inspect 评估维度格式化"""
    if not cv_comparison:
        return ""

    lines = ["\n## 像素级定量对比（CV计算，必须参考）\n"]

    # ── Overall ──
    overall = cv_comparison.get("overall", {})
    ssim = overall.get("ssim", 0)
    lines.append(f"### Overall: SSIM={ssim:.3f} (>0.8=优秀, >0.6=良好, <0.4=差)")
    lines.append("")

    # ── Geometry → Geometry score (0.15) ──
    geometry = cv_comparison.get("geometry", {})
    if geometry:
        edge_iou = geometry.get("edge_iou", 0)
        lines.append(f"### Geometry: Edge IoU={edge_iou:.3f}")
        detail = geometry.get("edge_diff_detail", "")
        if detail and "接近" not in detail:
            lines.append(f"  {detail}")
        lines.append("")

    # ── Color → Color & Tone score (0.15) ──
    color = cv_comparison.get("color", {})
    if color:
        lines.append(f"### Color & Tone: 相似度={color.get('similarity',0):.3f}")
        detail = color.get("diff_detail", "")
        if detail and "匹配" not in detail:
            lines.append(f"  {detail}")
        lines.append("")

    # ── Luminance → Lighting score (0.15) ──
    luminance = cv_comparison.get("luminance", {})
    if luminance:
        kl = luminance.get("histogram_kl_div", 0)
        ha_diff = luminance.get("highlight_area_diff", 0)
        lines.append(f"### Lighting: 亮度KL散度={kl:.4f} 高亮面积差={ha_diff:+.4f}")
        detail = luminance.get("diff_detail", "")
        if detail and "匹配" not in detail:
            lines.append(f"  {detail}")
        lines.append("")

    # ── Frequency → Texture score (0.10) ──
    frequency = cv_comparison.get("frequency", {})
    if frequency:
        sd = frequency.get("spectrum_diff", 0)
        match = frequency.get("texture_match", "?")
        bands = frequency.get("band_diffs", {})
        lines.append(f"### Texture: 频谱差异={sd:.4f} ({match})")
        if bands:
            lines.append(f"  低频差={bands.get('low',0):.4f} 中频差={bands.get('mid',0):.4f} 高频差={bands.get('high',0):.4f}")
        lines.append("")

    # ── Spatial → Composition + Background ──
    spatial = cv_comparison.get("spatial", {})
    if spatial:
        lines.append(f"### Spatial: 主体MSE={spatial.get('subject_mse',0):.4f} 背景MSE={spatial.get('background_mse',0):.4f}")
        detail = spatial.get("diff_detail", "")
        if detail:
            lines.append(f"  {detail}")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 3: 在 build_decompose_prompt 中注入 CV 特征**

在 `build_decompose_prompt` 函数中，构建 user_prompt 的部分，添加:

```python
    # Inject CV features (by dimension)
    cv_features = state.get("baseline", {}).get("cv_features")
    cv_text = _format_cv_features(cv_features)
    if cv_text:
        user_parts.append(cv_text)
```

- [ ] **Step 4: 在 build_inspect_prompt 中注入 CV 对比**

在 `build_inspect_prompt` 函数中，构建 user_prompt 的部分，添加:

```python
    # Inject CV comparison (by dimension)
    cv_comparison = state.get("snapshot", {}).get("cv_comparison")
    cv_text = _format_cv_comparison(cv_comparison)
    if cv_text:
        user_parts.append(cv_text)
```

- [ ] **Step 5: 验证 prompt 格式化**

```bash
cd /Users/yangfei/Code/VFX-Agent/backend && python -c "
from app.services.context_assembler import _format_cv_features, _format_cv_comparison

# Test feature formatting
test_features = {
    'primary': {
        'color': {
            'palette': [
                {'rgb': [10, 20, 50], 'hex': '#0a1432', 'percentage': 45.2},
                {'rgb': [30, 200, 100], 'hex': '#1ec864', 'percentage': 30.1},
            ],
            'subject_color': {'rgb': [30, 200, 100], 'percentage': 35.0},
            'background_color': {'rgb': [10, 20, 50], 'percentage': 65.0},
            'gradient': {'type': 'radial', 'direction': 'center_outward', 'strength': 0.012},
        },
        'geometry': {
            'edges': {'density': 0.12, 'sharpness': 'soft', 'dominant_angle': '↓'},
            'shape': {'circularity': 0.88, 'convexity': 0.95, 'symmetry_h': 0.92, 'symmetry_v': 0.91, 'estimated_type': 'circle'},
            'fill': {'edge_interior_ratio': 0.08, 'estimated_fill': 'solid'},
        },
        'luminance': {
            'distribution': {'mean': 0.25, 'std': 0.18, 'is_bimodal': True, 'distribution': 'bimodal', 'peaks': [0.1, 0.6]},
            'glow': {'detected': True, 'center': [0.5, 0.5], 'radius': 0.15, 'intensity': 2.3},
        },
        'frequency': {'high_freq_ratio': 0.65, 'dominant_direction': 'vertical', 'texture_level': 'medium'},
        'spatial': {'subject': {'bbox': [100, 80, 400, 380], 'center': [0.5, 0.48], 'area_pct': 35.0}},
    }
}
print(_format_cv_features(test_features))

# Test comparison formatting
test_comp = {
    'overall': {'ssim': 0.45},
    'geometry': {'edge_iou': 0.31, 'edge_diff_detail': '参考帧1200像素边缘，渲染400像素，缺少67%边缘细节'},
    'color': {'similarity': 0.72, 'diff_detail': 'Blue通道偏高18%'},
    'luminance': {'histogram_kl_div': 0.35, 'highlight_area_diff': 0.15, 'diff_detail': '参考帧高亮区域占25.0%，渲染帧占10.0%，渲染缺少15.0%的亮度区域'},
    'frequency': {'spectrum_diff': 0.22, 'band_diffs': {'low': 0.05, 'mid': 0.08, 'high': 0.53}, 'texture_match': 'poor'},
    'spatial': {'subject_mse': 0.12, 'background_mse': 0.03, 'diff_detail': '主体区MSE=0.1200，背景区MSE=0.0300 — 主体区域差异较大'},
}
print(_format_cv_comparison(test_comp))
"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/context_assembler.py
git commit -m "feat: inject dimension-organized CV data into Agent prompts"
```

---

### Task 5: 更新 System Prompt — 让 Agent 理解维度化的 CV 数据

**Files:**
- Modify: `backend/app/prompts/decompose_system.md`
- Modify: `backend/app/prompts/inspect_system.md`

- [ ] **Step 1: 在 Decompose prompt 新增维度化 CV 使用指导**

在 Planning Instructions 的分析阶段（Step 2: 观察视觉特征 之后），新增:

```markdown
## 量化特征使用指南（如果 prompt 中有"参考帧量化特征"节）

当 prompt 中包含 CV 提取的量化特征时，按维度使用精确数据替代主观判断：

### 颜色维度 → color_definition
- **色板**: 直接使用 RGB 值，不要凭印象。
  - ❌ "主色调绿色"
  - ✅ "主色 RGB(30, 200, 100) 占比 30%，辅色 RGB(10, 20, 50) 占比 45%"
- **主体色/背景色**: 已通过前景分离计算，直接使用。
- **渐变**: type=radial/linear/angular → 对应 gradient token。

### 几何维度 → shape_definition
- **边缘锐度**: sharpness=hard → edge_width 0.005-0.01 UV, soft → 0.03-0.08 UV
- **形状估计**: estimated_type 辅助判断 sdf_type（circle→sdCircle, rounded→sdRoundedBox, organic→sdVesica）
- **填充**: estimated_fill=solid → fill.solid, hollow → fill.hollow

### 亮度维度 → lighting_definition
- **双峰分布**: is_bimodal=true → 画面有发光体和暗背景，需要 glow 效果
- **发光中心**: 直接使用 center 坐标和 radius 作为 glow 参数参考

### 频率维度 → texture_definition
- **纹理级别**: fine → octaves 5-6, frequency 4-6; medium → 3-4, 2-4; smooth → 2-3, 1-2
- **方向**: dominant_direction → 纹理流动方向参数
```

- [ ] **Step 2: 在 Inspect prompt 新增维度化 CV 对比使用指导**

在 Inspect prompt 的评分指导中（Dimension Analysis 部分之后），新增:

```markdown
## 像素级对比使用指南（如果 prompt 中有"像素级定量对比"节）

当 prompt 中包含 CV 定量对比时，**这些数据按维度校准评分**：

### Overall 校准
| SSIM | 整体质量 | overall_score 建议 |
|------|---------|------------------|
| > 0.8 | 优秀 | ≥ 0.85 |
| 0.6-0.8 | 良好 | 0.70-0.84 |
| 0.4-0.6 | 有差异 | 0.50-0.69 |
| < 0.4 | 差 | < 0.50 |

### Geometry 维度 (weight: 0.15)
- Edge IoU < 0.3 → Geometry score ≤ 0.5
- Edge IoU > 0.7 → Geometry score ≥ 0.8
- 使用 edge_diff_detail 中的精确数据写 visual_issues

### Color 维度 (weight: 0.15)
- similarity < 0.7 → Color score ≤ 0.5
- 使用 diff_detail 中"XX通道偏高/偏低"写具体修正建议

### Lighting 维度 (weight: 0.15) — 关键改进
- highlight_area_diff > 0.1 → 渲染缺少高亮区域 → Lighting score -0.2
- histogram_kl_div > 0.2 → 亮度分布差异大 → 检查 glow 强度
- ⚠️ "灰色模糊"而非"明亮光晕" = highlight_area_diff 大 → 明确指出

### Texture 维度 (weight: 0.10) — 关键改进
- spectrum_diff > 0.15 → texture_match=poor → Texture score ≤ 0.5
- high频差大 → 缺少细节纹理 → 建议 increase FBM octaves/frequency
- low频差大 → 整体色调/大结构不匹配

### Spatial 维度 (Composition + Background)
- subject_mse > 0.05 且 background_mse < 0.03 → 主体有问题，背景OK
- background_mse > 0.05 且 subject_mse < 0.03 → 背景有问题，主体OK
- 精确定位问题区域，避免笼统的"效果不对"
```

- [ ] **Step 3: 验证**

```bash
cd /Users/yangfei/Code/VFX-Agent/backend && python -c "
# 验证 prompt 中包含 CV 指导
import os
for name in ['decompose_system.md', 'inspect_system.md']:
    path = os.path.join('app/prompts', name)
    with open(path) as f:
        content = f.read()
    has_cv = '量化特征' in content or '像素级' in content
    print(f'{name}: {\"✅\" if has_cv else \"❌\"} CV guidance')
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/prompts/decompose_system.md backend/app/prompts/inspect_system.md
git commit -m "feat: add dimension-based CV guidance to Decompose/Inspect prompts"
```

---

### Task 6: 端到端验证 — 重跑 5 个低分样例

**目标:** 验证 CV 特征注入后低分样例是否改善

- [ ] **Step 1: 重启 Backend**

```bash
pkill -f "uvicorn app.main"; sleep 2
cd /Users/yangfei/Code/VFX-Agent/backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/vfx-backend.log 2>&1 &
sleep 8 && curl -s http://localhost:8000/config --max-time 5 | head -1
```

- [ ] **Step 2: 选取 5 个低分样例测试**

```bash
cd /Users/yangfei/Code/VFX-Agent/backend && python test_e2e_batch.py \
  --samples auroras cool-s-distance electron liquid-galss-test vortex-street \
  --output-dir test_e2e_results_v3 \
  --threshold 0.85 \
  --timeout 600
```

- [ ] **Step 3: 对比 V2 vs V3**

```bash
python -c "
import json
v2 = json.loads(open('test_e2e_results_v2/test_results.json').read())
v3 = json.loads(open('test_e2e_results_v3/test_results.json').read())
samples = ['auroras', 'cool-s-distance', 'electron', 'liquid-galss-test', 'vortex-street']
for name in samples:
    v2s = v2.get(name, {}).get('score', 0)
    v3s = v3.get(name, {}).get('score', 0)
    delta = v3s - v2s
    arrow = '↑' if delta > 0 else '↓'
    print(f'  {name:25s} V2={v2s:.2f}  V3={v3s:.2f}  ({arrow}{abs(delta):.2f})')
"
```

**通过标准**: 5 个中有 3+ 个分数提升

- [ ] **Step 4: Commit results**

```bash
git add backend/test_e2e_results_v3/
git commit -m "test: e2e validation with dimension-driven CV feature extraction"
```

---

## Summary

| Task | Priority | 新增/修改文件 | 说明 |
|------|----------|-------------|------|
| Task 1 | P0 | 新增 `perception.py` (~400行) | 维度驱动 CV 特征提取 + 像素对比 |
| Task 2 | P0 | 修改 `state.py` | +cv_features, +cv_comparison |
| Task 3 | P0 | 修改 `graph.py` | 在 extract/render 节点注入 CV |
| Task 4 | P0 | 修改 `context_assembler.py` | 按维度格式化注入 Agent prompt |
| Task 5 | P0 | 修改 2 个 prompt 文件 | 维度化 CV 使用指导 |
| Task 6 | P0 | 测试 | 重跑 5 个低分样例验证效果 |

### 与旧 Plan 的差异

| 变化 | 旧 Plan | 新 Plan | 原因 |
|------|---------|---------|------|
| **特征组织** | 扁平 list（color_palette, edges, ...） | 按维度 dict（color, geometry, luminance, ...） | 对齐 Agent 维度 |
| **前景分离** | 3x3 固定网格 | Otsu 阈值 → 自适应主体/背景 | 3x3 无法区分主体/背景 |
| **区域 MSE** | 3x3 格子 MSE | 基于 fg_mask 的主体 MSE + 背景 MSE | 语义明确的区域划分 |
| **新增渐变方向** | ❌ | ✅ Sobel 梯度 → radial/linear/angular | 色板只有颜色值，没有空间分布 |
| **新增发光检测** | ❌ | ✅ Top-5% 亮度 → 中心/半径/强度 | 辅助 lighting_definition |
| **新增频谱对比** | ❌ | ✅ FFT 逐频带差异 | Inspect 的 Texture 维度没有 CV 指标 |
| **新增亮度对比** | ❌ | ✅ KL 散度 + 高亮面积差 | Inspect 的 Lighting 维度没有 CV 指标 |
| **新增形状分类** | ❌ | ✅ 圆度/凸度/对称性 | 辅助 shape_type 判断 |
| **新增填充检测** | ❌ | ✅ 边缘/内部像素比 | 辅助 fill_type 判断 |

**预计耗时**: Task 1-5 约 60 分钟, Task 6 约 30 分钟, 总计 ~90 分钟
