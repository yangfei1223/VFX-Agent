"""FFmpeg 关键帧提取 + 视频元信息获取"""

import json
import subprocess
import tempfile
from pathlib import Path


def extract_keyframes(video_path: str, output_dir: str | None = None, max_frames: int = 8) -> list[str]:
    """从视频中均匀提取关键帧，返回图片路径列表"""
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="vfx_keyframes_")

    # 获取视频时长
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    duration = float(json.loads(result.stdout)["format"]["duration"])

    # 均匀采样时间点
    interval = duration / (max_frames + 1)
    timestamps = [interval * (i + 1) for i in range(max_frames)]

    output_paths: list[str] = []
    for i, ts in enumerate(timestamps):
        out_path = str(Path(output_dir) / f"frame_{i:03d}.png")
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(ts),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            out_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        output_paths.append(out_path)

    return output_paths


def get_video_info(video_path: str) -> dict:
    """获取视频基本信息：时长、帧率、分辨率"""
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)

    video_stream = next(
        (s for s in info["streams"] if s["codec_type"] == "video"), None
    )
    if not video_stream:
        raise ValueError("No video stream found")

    return {
        "duration": float(info["format"]["duration"]),
        "fps": eval(video_stream["r_frame_rate"]),  # e.g. "30/1" -> 30.0
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
    }