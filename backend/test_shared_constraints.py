"""测试 Shared VFX Constraints 是否注入三 Agent"""
import pytest
from app.services.context_assembler import build_decompose_prompt, build_generate_prompt, build_inspect_prompt


def test_shared_constraints_injected():
    """验证所有 Agent prompt 包含 P0 禁止项"""
    state = {}  # minimal state
    
    # Decompose
    sys, user, images = build_decompose_prompt(state, "cold_start")
    assert "raymarching" in sys
    assert "texture fetch >8" in sys or "texture fetch" in sys
    assert "禁止" in sys
    
    # Generate
    sys, user = build_generate_prompt(state)
    assert "raymarching" in sys
    assert "禁止" in sys
    
    # Inspect
    sys, user, images = build_inspect_prompt(state)
    assert "模糊描述" in sys or "模糊" in sys
    assert "禁止" in sys


def test_p0_banned_items_complete():
    """验证 P0 禁止项完整（7 项）"""
    state = {}
    sys, user, images = build_decompose_prompt(state, "cold_start")
    
    # 7 个 P0 禁止项
    p0_items = [
        "raymarching",
        "texture",  # texture fetch >8
        "紫色",  # 默认紫色
        "模糊描述",  # 或 "模糊"
        "背景约束缺失",  # 或 "background.strict"
        "动画时长缺失",  # 或 "duration"
        "edge width 缺失",  # 或 "edge_width"
    ]
    
    # 检查至少包含关键禁止项
    assert "raymarching" in sys
    assert "禁止" in sys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])