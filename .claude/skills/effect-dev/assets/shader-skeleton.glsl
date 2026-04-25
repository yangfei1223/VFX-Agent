// assets/shader-skeleton.glsl
// VFX Agent 标准着色器骨架 — 所有生成的 shader 必须遵循此结构

// 效果名称：{effect_name}

// ---- Uniforms（由运行时自动注入，不需要声明）----
// uniform float u_time;        // 全局时间（秒）
// uniform vec2  u_resolution;  // 视窗分辨率（像素）
// uniform vec2  u_mouse;       // 鼠标/触摸位置（像素，左下角原点）
// uniform sampler2D iChannel0; // 系统纹理：backdrop framebuffer
// uniform sampler2D iChannel1; // 用户纹理（可选）

// ---- 辅助函数区 ----
// 在这里放置 SDF、噪声、纹理采样等辅助函数
// 优先从 effect-dev Skill 的 references 中复用已有实现

// float sdCircle(vec2 p, float r) { ... }
// float perlinNoise(vec2 p) { ... }
// vec3 backdropBlur(vec2 uv, float radius) { ... }

// ---- 主着色函数 ----
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // 1. 坐标归一化
    vec2 uv = fragCoord / u_resolution.xy;
    float aspect = u_resolution.x / u_resolution.y;

    // 2. 着色逻辑
    vec3 col = vec3(0.0);

    // ... 在这里实现你的视效逻辑 ...

    // 3. 安全输出
    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}