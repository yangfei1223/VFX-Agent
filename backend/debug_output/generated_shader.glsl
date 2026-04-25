// 效果名称：windows95_pixel_wave

// ---- Uniforms（由运行时注入，不需要声明）----
// uniform float u_time;       // 全局时间（秒）
// uniform vec2  u_resolution; // 视窗分辨率（像素）
// uniform vec2  u_mouse;      // 鼠标位置（像素，左下角原点）

// ---- 用户自定义函数区 ----

// 颜色常量，根据语义描述中的调色板定义
const vec3 PALETTE_DARK_TEAL    = vec3(0.129, 0.478, 0.478); // #217A7A
const vec3 PALETTE_RED_ORANGE   = vec3(0.906, 0.392, 0.357); // #E7645B
const vec3 PALETTE_LIGHT_GREEN  = vec3(0.596, 0.788, 0.388); // #98C963
const vec3 PALETTE_LIGHT_BLUE   = vec3(0.388, 0.663, 0.816); // #63A9D0
// const vec3 PALETTE_YELLOW       = vec3(0.941, 0.886, 0.306); // #F0E24E (未在主窗口或像素流中使用)
const vec3 PALETTE_BLACK        = vec3(0.0, 0.0, 0.0);       // #000000

// 2D SDF for a box (rectangle)
// 来源于 Inigo Quilez (iq) 的 SDF 算法定义
float sdBox(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

// Hash function，用于生成伪随机数，常用于噪声或随机化像素属性
// 来源于 Inigo Quilez (iq) 的 Shadertoy 示例
float hash(vec2 p) {
    p = fract(p * 0.3183099 + vec2(0.113, 0.113));
    p *= p + 71.0;
    return fract(p.x * p.y);
}

// ---- 主着色函数 ----
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // 1. 坐标初始化与屏幕比例校正
    // 将屏幕坐标转换为归一化的 UV 坐标 (0.0 到 1.0)
    vec2 uv = fragCoord / u_resolution.xy;
    // 将 UV 坐标中心移至屏幕中央 (-0.5 到 0.5)
    uv -= 0.5;
    // 根据屏幕宽高比校正 UV 坐标，确保图形不变形
    uv.x *= u_resolution.x / u_resolution.y;

    vec3 final_color = vec3(0.0); // 初始化背景颜色为黑色

    // --- 2. 绘制 Windows 95 风格的主体窗口 ---
    // 应用波浪形形变，模拟旗帜飘动效果
    vec2 window_uv = uv; // 用于窗口形变的 UV 副本
    float wave_amplitude_x = 0.05; // 水平波浪振幅
    float wave_amplitude_y = 0.02; // 垂直波浪振幅 (较小)
    float wave_frequency = 5.0;    // 波浪频率
    float wave_speed = 2.0;        // 波浪动画速度

    // 基于 Y 坐标和时间，对 X 坐标进行水平波浪形变
    // (1.0 - abs(window_uv.y * 2.0)) 使形变在窗口中央最强，边缘减弱
    window_uv.x += sin(window_uv.y * wave_frequency + u_time * wave_speed) * wave_amplitude_x * (1.0 - abs(window_uv.y * 2.0));
    // 基于 X 坐标和时间，对 Y 坐标进行垂直波浪形变 (更微妙)
    window_uv.y += cos(window_uv.x * wave_frequency * 0.5 + u_time * wave_speed * 0.7) * wave_amplitude_y * (1.0 - abs(window_uv.x * 2.0));

    // 定义四个矩形的大小和相对位置
    vec2 rect_half_size = vec2(0.1, 0.075); // 每个矩形的一半尺寸
    float gap = 0.005; // 矩形之间的间隙

    // 计算每个矩形的中心点相对于窗口中心的偏移
    vec2 offset_tl = vec2(-rect_half_size.x - gap, rect_half_size.y + gap); // 左上
    vec2 offset_tr = vec2(rect_half_size.x + gap, rect_half_size.y + gap);  // 右上
    vec2 offset_bl = vec2(-rect_half_size.x - gap, -rect_half_size.y - gap); // 左下
    vec2 offset_br = vec2(rect_half_size.x + gap, -rect_half_size.y - gap); // 右下

    float border_thickness = 0.005; // 用于 SDF 渲染的平滑边缘厚度

    // 使用 SDF 计算每个矩形的距离，并根据距离混合颜色
    float d_tl = sdBox(window_uv - offset_tl, rect_half_size);
    float d_tr = sdBox(window_uv - offset_tr, rect_half_size);
    float d_bl = sdBox(window_uv - offset_bl, rect_half_size);
    float d_br = sdBox(window_uv - offset_br, rect_half_size);

    // 使用 smoothstep 进行平滑过渡，将颜色应用到矩形区域
    final_color = mix(final_color, PALETTE_DARK_TEAL,   smoothstep(border_thickness, -border_thickness, d_tl));
    final_color = mix(final_color, PALETTE_RED_ORANGE,  smoothstep(border_thickness, -border_thickness, d_tr));
    final_color = mix(final_color, PALETTE_LIGHT_GREEN, smoothstep(border_thickness, -border_thickness, d_bl));
    final_color = mix(final_color, PALETTE_LIGHT_BLUE,  smoothstep(border_thickness, -border_thickness, d_br));


    // --- 3. 绘制左侧的像素流 ---
    vec3 pixel_stream_color = vec3(0.0);
    float pixel_stream_alpha = 0.0;

    // 像素流只在屏幕左侧区域显示
    if (uv.x < -0.1) { // -0.1 是一个阈值，控制像素流向右延伸的范围
        vec2 stream_uv = uv;
        stream_uv.x += 0.5; // 将像素流的起始位置向左移动，使其在屏幕左侧更明显
        stream_uv *= 20.0; // 放大 UV 坐标，创建更密集的像素网格

        vec2 flow_direction = normalize(vec2(1.0, 1.0)); // 像素流动的方向 (从左上到右下)
        float flow_speed = 0.8; // 像素流动的速度
        float anim_time = u_time * flow_speed; // 动画时间

        // 应用流动效果和波浪形变到像素流
        stream_uv += flow_direction * anim_time;
        stream_uv.x += sin(stream_uv.y * 0.8 + u_time * 1.5) * 0.5; // 水平波浪
        stream_uv.y += cos(stream_uv.x * 0.5 + u_time * 1.2) * 0.3; // 垂直波浪

        vec2 p_id = floor(stream_uv); // 获取当前像素单元的整数 ID
        vec2 p_local = fract(stream_uv) - 0.5; // 获取像素单元内的局部坐标 (-0.5 到 0.5)

        // 使用哈希函数为每个像素单元生成一个伪随机值
        float h = hash(p_id);

        // 根据哈希值循环分配颜色：黑色、红色、蓝色
        if (h < 0.33) {
            pixel_stream_color = PALETTE_BLACK;
        } else if (h < 0.66) {
            pixel_stream_color = PALETTE_RED_ORANGE;
        } else {
            pixel_stream_color = PALETTE_LIGHT_BLUE;
        }

        // 定义像素的形状 (小方块)
        float pixel_half_size = 0.3; // 像素方块的一半尺寸
        float d_pixel = sdBox(p_local, vec2(pixel_half_size)); // 计算当前点到像素方块的距离

        // 像素的淡入淡出效果：当像素流过单元格边界时，使其逐渐消失和重新出现
        // smoothstep(0.0, 0.2, fract(stream_uv.x)) 在 fract(stream_uv.x) 从 0.0 到 0.2 时从 0 渐变到 1
        // smoothstep(1.0, 0.8, fract(stream_uv.x)) 在 fract(stream_uv.x) 从 1.0 到 0.8 时从 0 渐变到 1
        float fade_x = smoothstep(0.0, 0.2, fract(stream_uv.x)) * smoothstep(1.0, 0.8, fract(stream_uv.x));
        float fade_y = smoothstep(0.0, 0.2, fract(stream_uv.y)) * smoothstep(1.0, 0.8, fract(stream_uv.y));
        float pixel_fade = fade_x * fade_y; // 结合 X 和 Y 方向的淡入淡出

        // 渲染像素，使用 smoothstep 赋予平滑边缘，并应用淡入淡出效果
        pixel_stream_alpha = smoothstep(0.02, -0.02, d_pixel) * pixel_fade;
    }

    // --- 4. 最终颜色混合 ---
    // 将像素流混合到主体窗口之上
    final_color = mix(final_color, pixel_stream_color, pixel_stream_alpha);

    // 输出最终颜色，alpha 通道为 1.0 (完全不透明)
    fragColor = vec4(final_color, 1.0);
}