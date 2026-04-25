"""Pipeline 状态定义"""

from typing import TypedDict


class PipelineState(TypedDict, total=False):
    # 输入
    input_type: str                     # "video" | "image"
    video_path: str | None              # 视频文件路径
    image_paths: list[str]              # 图片路径列表
    user_notes: str                     # 用户附加参数标注
    video_info: dict | None             # 视频元信息

    # 关键帧（视频输入时由 extractor 生成）
    keyframe_paths: list[str]           # 提取的关键帧路径

    # Decompose Agent 产出
    visual_description: dict            # 视效语义描述

    # 迭代状态
    iteration: int                      # 当前迭代轮次（从 0 开始）
    max_iterations: int                 # 最大迭代次数
    current_shader: str                 # 当前 GLSL 代码
    compile_error: str | None           # 编译错误信息

    # Inspect Agent 产出
    inspect_result: dict | None         # 评估结果
    passed: bool                        # 是否通过检视

    # 截图
    render_screenshots: list[str]       # 渲染截图路径
    design_screenshots: list[str]       # 设计参考截图路径

    # Pipeline 状态
    status: str                         # "running" | "passed" | "failed" | "max_iterations"
    error: str | None                   # 错误信息
    history: list[dict]                 # 迭代历史记录